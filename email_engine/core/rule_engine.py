"""
rule_engine.py — Resolve per-email config for rotation batches.

Nelson workflow v6: click Start batch with user markup input.
Engine resolves POL, destination, ARB origin, subject per contact
based on ORIGIN_COUNTRY + commodity + week context.

Maps per Nelson's market knowledge (2026-04-22):
  VN    -> HCM or HPH  -> None          (direct VN->US)
  MY    -> PKG          -> port_klang   (direct MY->US)
  TH    -> BKK          -> lat_krabang  (direct TH->US)
  CN    -> SHA or NGB   -> shanghai/ningbo (DIRECT, NOT via VN)
  KH    -> HCM          -> phnom_penh   (transit via HCM + ARB surcharge)
"""
from __future__ import annotations

import random
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

# ── Country → route config ───────────────────────────────────────────────────
# Nelson confirmed 2026-04-22. China NEVER transits via VN.
ARB_MAPPING: dict[str, dict[str, str | None]] = {
    "VN": {"pol_default": "HCM", "arb_key": None},
    "MY": {"pol_default": "PKG", "arb_key": "port_klang"},
    "TH": {"pol_default": "BKK", "arb_key": "lat_krabang"},
    "CN": {"pol_default": "SHA", "arb_key": "shanghai"},   # NGB variant → ningbo
    "KH": {"pol_default": "HCM", "arb_key": "phnom_penh"}, # Cambodia → HCM base + ARB
    "BD": {"pol_default": "CGP", "arb_key": None},          # Bangladesh (arb TBD)
    "IN": {"pol_default": "NSA", "arb_key": None},           # India Nhava Sheva (arb TBD)
    "PH": {"pol_default": "MNL", "arb_key": None},
    "ID": {"pol_default": "JKT", "arb_key": None},
}

# VN domestic ports — never apply ARB surcharge
VN_PORTS: frozenset[str] = frozenset({
    "HPH", "HCM", "SGN", "HAN", "DAD", "VUT", "CMT",
    "DONG NAI", "BINH DUONG", "VNSGN", "VNHPH", "VNDAD",
})

# China NGB variants that map to "ningbo" ARB key instead of "shanghai"
CN_NINGBO_VARIANTS: frozenset[str] = frozenset({"NGB", "NINGBO"})

# ── YAML Config Loading ──────────────────────────────────────────────────────

_YAML_PATH = Path(__file__).parent.parent / "config" / "commodity_groups.yaml"


@lru_cache(maxsize=1)
def _load_yaml() -> dict:
    """Load commodity_groups.yaml. Cached — call cache_clear() to reload."""
    if not _YAML_PATH.exists():
        return {}
    try:
        import yaml
        with open(_YAML_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def invalidate_yaml_cache():
    """Clear YAML cache so next call reloads from disk."""
    _load_yaml.cache_clear()


@lru_cache(maxsize=1)
def load_commodity_groups() -> list[dict]:
    """Return list of commodity group dicts from YAML. Priority order = YAML order."""
    data = _load_yaml()
    return data.get("commodity_groups", [])


@lru_cache(maxsize=1)
def load_pol_patterns() -> list[dict]:
    """Return list of pol_pattern dicts from YAML. Priority order = YAML order."""
    data = _load_yaml()
    return data.get("pol_patterns", [])


@lru_cache(maxsize=1)
def load_arb_origins() -> dict[str, dict]:
    """Return arb_origins dict from YAML. Key = arb_origin key (e.g. 'port_klang')."""
    data = _load_yaml()
    return data.get("arb_origins", {})


@lru_cache(maxsize=1)
def load_vn_domestic_ports() -> frozenset[str]:
    """Return frozenset of VN domestic ports that never get ARB surcharge."""
    data = _load_yaml()
    ports = data.get("vn_domestic_ports", [])
    return frozenset(p.upper() for p in ports if p)


def normalize_commodity(raw: str | None) -> str:
    """Map raw COMMODITY_CATEGORY string to canonical group name.

    Priority: YAML commodity_groups order (first match wins).
    Falls back to 'OTHERS' if no pattern matches.
    """
    if not raw:
        return "OTHERS"
    raw_upper = str(raw).upper().strip()
    if raw_upper in ("", "NAN", "NONE"):
        return "OTHERS"
    for group in load_commodity_groups():
        for pattern in group.get("patterns", []):
            if pattern == ".*":
                # OTHERS fallback — only use if nothing else matched
                continue
            if re.search(rf"\b{re.escape(pattern.upper())}\b", raw_upper):
                return group["name"]
    return "OTHERS"


def pol_from_campaign(campaign_id: str | None) -> dict | None:
    """Extract POL + country + ARB key from CAMPAIGN_ID string.

    Returns dict {pol, country, arb_key, label} or None if no pattern matched.
    Uses pol_patterns from YAML, priority order.
    """
    if not campaign_id:
        return None
    camp_upper = str(campaign_id).upper().strip()
    if not camp_upper or camp_upper in ("", "NAN", "NONE"):
        return None
    for pattern_group in load_pol_patterns():
        for pattern in pattern_group.get("patterns", []):
            if re.search(rf"\b{re.escape(pattern.upper())}\b", camp_upper):
                return {
                    "pol":      pattern_group["pol"],
                    "country":  pattern_group["country"],
                    "arb_key":  pattern_group.get("arb_key"),
                    "label":    pattern_group.get("label", pattern_group["pol"]),
                }
    return None


def get_pod_default(commodity_group: str) -> list[str]:
    """Return default POD list for a canonical commodity group."""
    for group in load_commodity_groups():
        if group["name"] == commodity_group:
            return group.get("pod_default", ["USLAX", "USLGB"])
    return ["USLAX", "USLGB"]


def get_arb_origin_config(arb_key: str | None) -> dict | None:
    """Return arb_origin config dict from YAML, or None if not found."""
    if not arb_key:
        return None
    return load_arb_origins().get(arb_key)


# ── Subject templates ─────────────────────────────────────────────────────────
# 5 variants for anti-spam rotation — prevents Gmail/Outlook pattern filter
SUBJECT_TEMPLATES: list[str] = [
    "Ocean Freight Update — {pol} to {region} | Week {week} | NELSON",
    "Weekly Rate Update — {commodity} | {pol} → US",
    "{pol} to US Freight Rates — Week {week}",
    "Latest Container Rates from {pol} — {region}",
    "Shipping Quote — {pol} to US | Valid end of month",
]

# POD → region label
_POD_REGION_MAP: dict[str, str] = {
    "USLAX": "West Coast", "USLGB": "West Coast", "USOAK": "West Coast",
    "USSEA": "West Coast", "USTIW": "West Coast", "USTAC": "West Coast",
    "USNYC": "East Coast", "USJAX": "East Coast", "USCHS": "East Coast",
    "USSAV": "East Coast", "USORF": "East Coast", "USEWR": "East Coast",
    "USHOU": "Gulf Coast", "USMSY": "Gulf Coast",
    "USCHI": "Midwest",   "USDAL": "Midwest",
    "CAVAN": "Canada West", "CATOR": "Canada East",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalize_country(country: str | None) -> str:
    """Normalize country code to uppercase. Defaults to VN for empty/unknown."""
    if not country:
        return "VN"
    c = str(country).upper().strip()
    if c in {"", "NAN", "NONE"}:
        return "VN"
    return c


_DEST_TEXT_TO_CODE = {
    "LOS ANGELES": "USLAX", "LONG BEACH": "USLGB", "OAKLAND": "USOAK",
    "TACOMA": "USTIW", "SEATTLE": "USSEA", "PORTLAND": "USPDX",
    "NEW YORK": "USNYC", "NEWARK": "USEWR", "BALTIMORE": "USBAL",
    "PHILADELPHIA": "USPHL", "BOSTON": "USBOS", "WILMINGTON": "USILG",
    "SAVANNAH": "USSAV", "CHARLESTON": "USCHS", "JACKSONVILLE": "USJAX",
    "MIAMI": "USMIA", "HOUSTON": "USHOU", "NEW ORLEANS": "USMSY",
    "NORFOLK": "USORF", "CHICAGO": "USCHI", "DALLAS": "USDAL",
    "MEMPHIS": "USMEM", "ATLANTA": "USATL", "NASHVILLE": "USNSH",
    "CHARLOTTE": "USCLT", "ST LOUIS": "USSTL", "KANSAS CITY": "USKC",
    "DENVER": "USDEN", "MINNEAPOLIS": "USMSP", "DETROIT": "USDTW",
    "CLEVELAND": "USCLE", "COLUMBUS": "USCOL", "CINCINNATI": "USCVG",
    "VANCOUVER": "CAVAN", "PRINCE RUPERT": "CAPRR",
    "MONTREAL": "CAMTR", "HALIFAX": "CAHAL", "TORONTO": "CATOR",
}


def _normalize_dest_token(token: str) -> str | None:
    """Map a single destination token to a US/CA port code.

    Accepts: "USLAX", "Los Angeles", "The Port of Long Beach", "CA",
             "Long Beach, California", etc. Returns port code or None if
             unmappable (caller should drop None tokens).
    """
    t = (token or "").strip().upper()
    if not t or t in ("NAN", "NONE"):
        return None
    # Already a port code
    if len(t) == 5 and (t.startswith("US") or t.startswith("CA")):
        return t
    # Strip noise: "THE PORT OF LOS ANGELES" → "LOS ANGELES"
    for prefix in ("THE PORT OF ", "PORT OF ", "PORT "):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    # Drop trailing US state codes: "LOS ANGELES CA" → "LOS ANGELES"
    parts = t.split()
    if parts and len(parts[-1]) == 2 and parts[-1].isalpha():
        t = " ".join(parts[:-1]).strip()
    # Direct lookup
    if t in _DEST_TEXT_TO_CODE:
        return _DEST_TEXT_TO_CODE[t]
    return None


def _resolve_destination(dest_raw: str | None) -> str:
    """Return comma-joined port codes; default to USLAX,USLGB if blank/unmappable.

    Handles raw master text like "The Port of Los Angeles, Los Angeles, California"
    by mapping each comma-part to a port code and deduping.
    """
    if not dest_raw:
        return "USLAX,USLGB"
    raw = str(dest_raw).strip()
    if raw.lower() in ("nan", "none", ""):
        return "USLAX,USLGB"
    # If already all port codes, keep as-is
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    codes: list[str] = []
    for p in parts:
        code = _normalize_dest_token(p)
        if code and code not in codes:
            codes.append(code)
    if codes:
        return ",".join(codes)
    # Fallback: nothing mapped — return original (may still hit if parquet loose-matches)
    return raw


def _resolve_pol(row_pol: str | None, country: str) -> str:
    """Return POL: row value if present, else country default from ARB_MAPPING."""
    pol_up = str(row_pol or "").upper().strip()
    if pol_up and pol_up not in {"", "NAN", "NONE"}:
        return pol_up
    rule = ARB_MAPPING.get(country, ARB_MAPPING["VN"])
    return str(rule["pol_default"])


def _resolve_arb_key(pol: str, country: str) -> str | None:
    """Derive ARB key for surcharge lookup.

    Special cases:
    - CN + NGB port → use 'ningbo' key
    - VN domestic port + VN country → no ARB (direct lane)
    - Unknown country → fall back to VN rule (None)
    """
    try:
        rule = ARB_MAPPING.get(country, ARB_MAPPING["VN"])
        arb = rule["arb_key"]

        # China: NGB/NINGBO port → ningbo key
        if country == "CN" and pol in CN_NINGBO_VARIANTS:
            return "ningbo"

        # VN domestic: no surcharge regardless of arb_key
        if pol in VN_PORTS and country == "VN":
            return None

        return arb
    except Exception:
        return None


def _pod_region(destination: str) -> str:
    """Derive short region label from first destination port code."""
    first = destination.split(",")[0].strip().upper()
    return _POD_REGION_MAP.get(first, "US")


def _resolve_subject(
    pol: str,
    commodity: str,
    destination: str,
    seed: int | None = None,
) -> str:
    """Pick anti-spam subject from 5 templates. Seed for reproducible tests."""
    rng = random.Random(seed) if seed is not None else random
    tpl = rng.choice(SUBJECT_TEMPLATES)
    week_num = datetime.now().isocalendar()[1]
    return tpl.format(
        pol=pol,
        region=_pod_region(destination),
        week=week_num,
        commodity=commodity or "General",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_config(
    row: dict[str, Any],
    user_markup: int = 20,
    campaign_override: str | None = None,
    subject_seed: int | None = None,
) -> dict[str, Any]:
    """Return per-email config dict for rotation_engine.queue_to_outlook_worker.

    Input `row` accepts v6 keys (EMAIL, ORIGIN_COUNTRY, POL, DESTINATION,
    COMMODITY_CATEGORY, TIER, COMPANY, PIC) or legacy v5 keys
    (CNEE_EMAIL, CNEE_NAME, CNEE_PIC) — schema-adaptive.

    Args:
        row:              Contact row as dict (from master DataFrame).
        user_markup:      USD markup entered by Nelson for this batch.
        campaign_override: Force commodity label (overrides row column).
        subject_seed:     Random seed for deterministic subject in tests.

    Returns dict with keys: email, pol, destination, arb_origin, markup,
        subject, commodity, company, pic, tier, country.
    """
    def g(primary: str, *fallbacks: str, default: str = "") -> str:
        """Get first non-empty string value from row by key priority."""
        for k in (primary, *fallbacks):
            v = row.get(k)
            if v is not None and str(v).strip().lower() not in ("", "nan", "none"):
                return str(v).strip()
        return default

    try:
        # 1. Try POL from CAMPAIGN_ID (Malaysia LOC patterns — Priority)
        pol_config = pol_from_campaign(g("CAMPAIGN_ID"))
        if pol_config:
            pol        = pol_config["pol"]
            arb_origin = pol_config["arb_key"]
            country    = pol_config["country"]  # override ORIGIN_COUNTRY
        else:
            # 2. Fallback: normalize country, then POL from row
            country    = _normalize_country(g("ORIGIN_COUNTRY"))
            pol        = _resolve_pol(g("POL"), country)
            arb_origin = _resolve_arb_key(pol, country)

        destination = _resolve_destination(g("DESTINATION"))
        commodity   = normalize_commodity(
            campaign_override or g("COMMODITY_CATEGORY", "CAMPAIGN_ID", "CMD_NAME")
        )
        subject     = _resolve_subject(pol, commodity, destination, subject_seed)

        return {
            "email":       g("EMAIL", "CNEE_EMAIL"),
            "pol":         pol,
            "destination": destination,
            "arb_origin":  arb_origin,
            "markup":      user_markup,
            "subject":     subject,
            "commodity":   commodity,   # normalized canonical group
            "company":     g("COMPANY", "CNEE_NAME"),
            "pic":         g("PIC", "CNEE_PIC", default="there"),
            "tier":        g("TIER", default=""),
            "country":     country,
        }
    except Exception as exc:
        # Graceful fallback: return safe defaults so batch never crashes
        import logging
        logging.getLogger("rule_engine").error(
            "resolve_config error for row=%s: %s", row.get("EMAIL", "?"), exc
        )
        return {
            "email":       row.get("EMAIL", row.get("CNEE_EMAIL", "")),
            "pol":         "HCM",
            "destination": "USLAX,USLGB",
            "arb_origin":  None,
            "markup":      user_markup,
            "subject":     f"Ocean Freight Rates | Week {datetime.now().isocalendar()[1]}",
            "commodity":   campaign_override or "General",
            "company":     "",
            "pic":         "there",
            "tier":        "",
            "country":     "VN",
        }
