"""
charge_normalizer.py — Single source of truth loader for charge-name mapping.

Reads CARRIER_RATE_MAPPING.json (OneDrive) and exposes:
  - normalize_charge_name(source_name, rate_type=None)  -> normalized name or None (if unknown)
  - validate_parquet(df) -> list[str] of issues found

Any rate loader (master_loader_v2.py, rate_importer.py) MUST use this helper
instead of hardcoded dicts. This prevents a repeat of the 2026-04-17 incident
where HPL SCFI BASE O/F was mislabeled and under-quoted customers up to
$1,561/40HQ on inland routes.

See: CARRIER_RATE_MAPPING.json + docs/CHARGE_NAME_SOURCE_OF_TRUTH.md
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("charge_normalizer")

# Primary location (OneDrive); fallback resolves via shared.paths if available.
_DEFAULT_JSON = Path("D:/OneDrive/NelsonData/pricing/mapping/CARRIER_RATE_MAPPING.json")


def _resolve_json_path() -> Path:
    """Resolve mapping JSON path. Prefer shared.paths.MAPPING_DIR if available."""
    try:
        from shared.paths import MAPPING_DIR  # type: ignore
        p = Path(str(MAPPING_DIR)) / "CARRIER_RATE_MAPPING.json"
        if p.exists():
            return p
    except Exception:
        pass
    return _DEFAULT_JSON


@lru_cache(maxsize=1)
def load_mapping() -> dict:
    """Load the canonical mapping JSON (cached)."""
    p = _resolve_json_path()
    if not p.exists():
        log.error("CARRIER_RATE_MAPPING.json not found at %s", p)
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def invalidate_cache() -> None:
    """Clear cache — call after editing JSON."""
    load_mapping.cache_clear()


def normalize_charge_name(source_name: str, rate_type: str | None = None) -> str | None:
    """
    Normalize an Excel-source charge name to the Parquet canonical name.

    Args:
        source_name: The raw column header from Excel (e.g. "BASE O/F", "ALL IN COST").
        rate_type:   One of "FAK", "SCFI", "FIX_COC", "FIX_SOC_HPL" — optional.
                     If provided, uses type-specific mapping (preferred).
                     If None, falls back to charge_normalize_flat.

    Returns:
        The normalized name (e.g. "Total Ocean Freight"), or None if unknown.
        Callers should WARN + SKIP rows when this returns None — do not silently
        pass unknown charge names through, it caused the 2026-04-17 incident.
    """
    if not source_name:
        return None
    raw = str(source_name).strip()

    mapping = load_mapping()
    if not mapping:
        return raw  # Degrade gracefully if JSON missing (should not happen in prod)

    # Type-specific table (preferred)
    if rate_type:
        per_type = mapping.get("charge_normalize_table", {}).get(rate_type)
        if per_type and raw in per_type:
            return per_type[raw]

    # Flat fallback
    flat = mapping.get("charge_normalize_flat", {})
    if raw in flat:
        return flat[raw]

    # Pass-through for surcharges / known raw names that do not need remapping
    known_surcharges = set(mapping.get("canonical_charge_names", {}).get("surcharges", []))
    known_surcharges |= {"ISPS", "EMF", "DLF", "COMMISSION", "ARB/OLF"}
    if raw in known_surcharges or raw in {"BASIC O/F", "HLCU Basic Cost", "Total Ocean Freight"}:
        return raw

    log.warning("Unknown charge name '%s' (rate_type=%s) — caller should drop this row", raw, rate_type)
    return None


def canonical_total_ocean_freight() -> str:
    """Return the canonical charge name for all-in price. Always 'Total Ocean Freight'."""
    mapping = load_mapping()
    return mapping.get("canonical_charge_names", {}).get("all_in_price", "Total Ocean Freight")


def validate_parquet_charges(df) -> list[str]:
    """
    Scan a Parquet DataFrame for known bad patterns.
    Returns list of human-readable issues. Empty list = clean.

    Use from a post-import hook or `check_parquet_integrity.py`.
    """
    issues: list[str] = []
    mapping = load_mapping()
    forbidden = set(mapping.get("validators", {}).get("forbidden_stale_charge_names", []))
    if "Charge_Name" not in df.columns:
        return ["Parquet missing 'Charge_Name' column"]

    actual_names = set(df["Charge_Name"].dropna().astype(str).unique())
    stale = actual_names & forbidden
    if stale:
        issues.append(
            f"Forbidden stale charge names present in Parquet: {sorted(stale)}. "
            f"Loader must normalize these — see CARRIER_RATE_MAPPING.json."
        )

    canonical = canonical_total_ocean_freight()
    if canonical not in actual_names:
        issues.append(f"Canonical charge '{canonical}' missing from Parquet — no all-in rates?")

    return issues


if __name__ == "__main__":
    # CLI smoke test + validator
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("Mapping JSON:", _resolve_json_path())
    m = load_mapping()
    print("Version:", m.get("_meta", {}).get("version"))
    print()
    # Test known mappings
    tests = [
        ("BASE O/F", "SCFI", "Total Ocean Freight"),
        ("HLCU Offer", "SCFI", "HLCU Basic Cost"),
        ("ALL IN COST", "FAK", "Total Ocean Freight"),
        ("BASIC O/F", "FAK", "BASIC O/F"),
        ("Base Ocean Freight", "FIX_COC", "Total Ocean Freight"),
        ("TOTAL O/F", "FIX_SOC_HPL", "Total Ocean Freight"),
        ("UNKNOWN", None, None),
    ]
    ok = True
    for src, rt, expected in tests:
        got = normalize_charge_name(src, rt)
        mark = "OK" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"  [{mark}] {src!r:30s} + {rt!r:15s} -> {got!r}  (expected {expected!r})")

    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        import pandas as pd
        from shared.paths import PARQUET_FILE
        print("\nValidating Parquet...")
        df = pd.read_parquet(PARQUET_FILE)
        issues = validate_parquet_charges(df)
        if issues:
            print("ISSUES:")
            for i in issues:
                print(f"  - {i}")
            sys.exit(1)
        print("  Parquet is clean [OK]")

    sys.exit(0 if ok else 1)
