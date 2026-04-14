# arb_pricing.py — ARB Cross-Origin Surcharge Module
# ====================================================
# Reads arb_rates.yaml and computes cross-origin surcharges.
# Adds ARB on top of HCM/HPH base rates for China/Thailand/Cambodia/Malaysia.
#
# Usage:
#   from arb_pricing import get_arb_surcharge, build_cross_origin_label
import logging
from pathlib import Path
from functools import lru_cache

log = logging.getLogger("arb_pricing")

# Path to YAML (relative to this file: core/ → data/)
_YAML_PATH = Path(__file__).parent.parent / "data" / "arb_rates.yaml"

# Human-readable labels for origins
ORIGIN_LABELS = {
    "shanghai":    "Shanghai, China",
    "ningbo":      "Ningbo, China",
    "lat_krabang": "Lat Krabang, Thailand",
    "phnom_penh":  "Phnom Penh, Cambodia",
    "port_klang":  "Port Klang, Malaysia",
    "da_nang":     "Da Nang, Vietnam",
    "qui_nhon":    "Qui Nhon, Vietnam",
}

# Flag emoji for origins
ORIGIN_FLAGS = {
    "shanghai":    "CN",
    "ningbo":      "CN",
    "lat_krabang": "TH",
    "phnom_penh":  "KH",
    "port_klang":  "MY",
    "da_nang":     "VN",
    "qui_nhon":    "VN",
}


@lru_cache(maxsize=1)
def load_arb_rates() -> dict:
    """
    Load arb_rates.yaml. Returns empty dict if file not found.
    Cached — call invalidate_cache() to reload.
    """
    if not _YAML_PATH.exists():
        log.warning("[ARB] arb_rates.yaml not found at %s", _YAML_PATH)
        return {}
    try:
        import yaml
        with open(_YAML_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        log.info("[ARB] Loaded %d origins from arb_rates.yaml", len(data))
        return data
    except Exception as e:
        log.error("[ARB] Failed to load arb_rates.yaml: %s", e)
        return {}


def invalidate_cache():
    """Clear the YAML cache so next call reloads from disk."""
    load_arb_rates.cache_clear()


def get_arb_surcharge(
    origin: str,
    carrier: str,
    contract_type: str = "FAK",
    container: str = "40HQ",
    pod_region: str = None,
) -> int | None:
    """
    Look up ARB surcharge (USD) for a given origin/carrier/contract/container.

    Supports flat format: {20GP: 80, 40HQ: 100}
    And region-nested:   {PSW: {20GP: 180, 40HQ: 200}, PNW: ...}

    Args:
        origin:        Origin key (e.g. "shanghai", "lat_krabang")
        carrier:       Carrier code (e.g. "HPL", "CMA", "ONE", "YML")
        contract_type: "FAK" | "FAK_SOC" | "FAK_COC" | "FIX"
        container:     "20GP" | "40GP" | "40HQ" | "45HQ"
        pod_region:    Optional region for CMA-style rates ("PSW", "EC", etc.)

    Returns:
        int USD surcharge, or None if not found.
    """
    rates = load_arb_rates()
    origin_key = origin.lower().strip()
    carrier_key = carrier.upper().strip()
    contract_key = contract_type.upper().strip()
    container_key = container.upper().strip()

    # Normalize legacy keys: FAK_SOC/FAK_COC → try FAK as fallback
    contract_candidates = [contract_key]
    if contract_key in ("FAK_SOC", "FAK_COC"):
        contract_candidates.append("FAK")
    elif contract_key == "FAK":
        contract_candidates.extend(["FAK_SOC", "FAK_COC"])

    for ck in contract_candidates:
        try:
            rate_node = rates[origin_key][carrier_key][ck]
        except (KeyError, TypeError):
            continue

        # Check if rate_node is region-nested (e.g. CMA FAK: {PSW: {...}, PNW: {...}})
        if isinstance(rate_node, dict):
            first_val = next(iter(rate_node.values()), None)
            if isinstance(first_val, dict) and container_key not in rate_node:
                # Region-nested — pick region or first available
                if pod_region:
                    region_node = rate_node.get(pod_region.upper())
                    if region_node:
                        return region_node.get(container_key)
                # Fallback: first region
                return first_val.get(container_key)
            else:
                # Flat: {20GP: 80, 40HQ: 100}
                val = rate_node.get(container_key)
                if val is not None:
                    return val

    return None


def get_available_origins() -> list[dict]:
    """
    Return list of available origins with metadata.
    """
    rates = load_arb_rates()
    result = []
    for origin_key, carriers in rates.items():
        result.append({
            "key":      origin_key,
            "label":    ORIGIN_LABELS.get(origin_key, origin_key.replace("_", " ").title()),
            "flag":     ORIGIN_FLAGS.get(origin_key, ""),
            "carriers": list(carriers.keys()),
        })
    return result


def build_cross_origin_rates(
    base_rows: list[dict],
    origin: str,
    carrier_filter: list[str] | None = None,
    contract_type: str = "FAK_SOC",
) -> list[dict]:
    """
    Take base HCM/HPH rate rows and add ARB surcharge for cross-origin.

    Args:
        base_rows:      List of rate dicts from auto_rate_builder (must have 'carrier', 'rate_20', 'rate_40')
        origin:         ARB origin key (e.g. "shanghai")
        carrier_filter: Optional list of carriers to include (None = all)
        contract_type:  Contract type for surcharge lookup

    Returns:
        New list of rate dicts with ARB applied.
        Each row gets: arb_20, arb_40, total_20, total_40, arb_origin, arb_label.
        Original 'pol' is replaced with arb_origin label.
    """
    if not origin:
        return base_rows

    origin_label = ORIGIN_LABELS.get(origin.lower(), origin.replace("_", " ").title())
    result = []

    for row in base_rows:
        carrier = str(row.get("carrier", "")).upper()
        if carrier_filter and carrier not in [c.upper() for c in carrier_filter]:
            continue

        arb_20 = get_arb_surcharge(origin, carrier, contract_type, "20GP")
        arb_40 = get_arb_surcharge(origin, carrier, contract_type, "40HQ")

        # Skip if no ARB rate found for this carrier
        if arb_20 is None and arb_40 is None:
            log.debug("[ARB] No surcharge for %s/%s — skipping row", origin, carrier)
            continue

        new_row = dict(row)
        new_row["pol"] = origin_label           # Replace POL with origin label
        new_row["arb_origin"] = origin
        new_row["arb_label"] = origin_label
        new_row["arb_20"] = arb_20 or 0
        new_row["arb_40"] = arb_40 or 0

        if row.get("rate_20") is not None and arb_20 is not None:
            new_row["rate_20"] = int(row["rate_20"]) + arb_20
        if row.get("rate_40") is not None and arb_40 is not None:
            new_row["rate_40"] = int(row["rate_40"]) + arb_40

        result.append(new_row)

    return result


def arb_badge_html(origin: str, surcharge_20: int | None, surcharge_40: int | None) -> str:
    """Small HTML badge showing ARB breakdown for email display."""
    if not origin:
        return ""
    label = ORIGIN_LABELS.get(origin.lower(), origin)
    parts = []
    if surcharge_20:
        parts.append(f"20GP +${surcharge_20:,}")
    if surcharge_40:
        parts.append(f"40HQ +${surcharge_40:,}")
    surcharge_text = " | ".join(parts) if parts else "surcharge TBD"
    return (
        f'<div style="display:inline-block;padding:3px 10px;margin-bottom:6px;'
        f'border-radius:4px;font-size:11px;font-family:Arial,sans-serif;'
        f'color:#92400e;background:#fffbeb;border:1px solid #fbbf2440;">'
        f'ARB: {label} — {surcharge_text}</div>'
    )
