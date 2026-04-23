# -*- coding: utf-8 -*-
"""
scripts/_panjiva_v3_helpers.py — Helpers for panjiva_clean_v3.py
================================================================
Column mapping, tier scoring, POL aggregation, shipper extraction,
filename hint parsing, date parsing utilities.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger("panjiva_v3")

# ── Commodity hint keywords → canonical bucket ────────────────────────────────
_COMMODITY_HINT_MAP: dict[str, str] = {
    "flooring":         "FLOORING",
    "floor":            "FLOORING",
    "hardwood":         "FLOORING",
    "vinyl":            "FLOORING",
    "laminate":         "FLOORING",
    "furniture":        "FURNITURE_INDOOR",
    "indoor":          "FURNITURE_INDOOR",
    "outdoor":         "FURNITURE_OUTDOOR",
    "patio":           "FURNITURE_OUTDOOR",
    "rubber":          "RUBBER",
    "plastic":         "PLASTIC",
    "candle":          "CANDLE",
    "textile":         "TEXTILE",
    "apparel":         "APPAREL",
    "clothing":        "APPAREL",
    "footwear":        "FOOTWEAR",
    "shoe":            "FOOTWEAR",
    "electronics":     "ELECTRONICS",
    "electronic":      "ELECTRONICS",
    "metal":           "METAL",
    "steel":           "METAL",
    "wood":            "WOOD",
    "ceramic":         "CERAMIC",
    "food":            "FOOD",
    "chemical":        "CHEMICAL",
    "paper":           "PAPER",
    "cosmetics":       "COSMETICS",
    "cosmetic":        "COSMETICS",
}

# Country name/alias → ISO 2-letter
_COUNTRY_ALIAS: dict[str, str] = {
    "vietnam":     "VN",
    "viet nam":    "VN",
    "vn":          "VN",
    "thailand":    "TH",
    "thai":        "TH",
    "th":          "TH",
    "cambodia":    "KH",
    "kh":          "KH",
    "malaysia":    "MY",
    "my":          "MY",
    "indonesia":   "ID",
    "id":          "ID",
    "china":       "CN",
    "cn":          "CN",
    "india":       "IN",
    "in":          "IN",
}

# US State name → 2-letter code
_US_STATE_ABBR: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


# ── Filename hint extractor ────────────────────────────────────────────────────

def auto_hint_from_filename(filename: str) -> tuple[str, str]:
    """Extract commodity + origin country hints from Panjiva filename pattern.

    Patterns recognized:
      'Panjiva-buyer-Flooring-...'             → ('FLOORING', '')
      'Panjiva-US_Imports-Furniture_Thailand-' → ('FURNITURE_INDOOR', 'TH')
      'Panjiva-buyer-Candle_Vietnam-...'       → ('CANDLE', 'VN')

    Returns (commodity_hint, country_code). Empty string if not detected.
    """
    name = Path(filename).stem.lower()

    # Remove common prefix patterns
    name = re.sub(r"panjiva[-_](buyer|us_imports|shipment)[-_]?", "", name, flags=re.I)

    # Split on dash/underscore/space
    parts = re.split(r"[-_\s]+", name)

    commodity = ""
    country = ""

    for part in parts:
        part_clean = part.strip()
        if not part_clean:
            continue
        # Check commodity
        if not commodity:
            for kw, cat in _COMMODITY_HINT_MAP.items():
                if kw in part_clean:
                    commodity = cat
                    break
        # Check country
        if not country:
            c = _COUNTRY_ALIAS.get(part_clean, "")
            if c:
                country = c

    return commodity, country


# ── Revenue / employee parsers ────────────────────────────────────────────────

def parse_revenue(raw: str) -> Optional[float]:
    """Parse revenue string like '$45M', '$1.2B', '10000000' → float USD."""
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return None
    s = str(raw).strip().replace(",", "").replace("$", "").replace(" ", "")
    multiplier = 1.0
    if s.upper().endswith("B"):
        multiplier = 1_000_000_000
        s = s[:-1]
    elif s.upper().endswith("M"):
        multiplier = 1_000_000
        s = s[:-1]
    elif s.upper().endswith("K"):
        multiplier = 1_000
        s = s[:-1]
    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


def parse_int_safe(raw: str) -> Optional[int]:
    """Parse integer, return None on failure."""
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return None
    s = re.sub(r"[^\d]", "", str(raw))
    try:
        return int(s) if s else None
    except (ValueError, TypeError):
        return None


def parse_date_safe(raw: str) -> Optional[str]:
    """Parse date string → ISO YYYY-MM-DD. Returns None on failure."""
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return None
    try:
        parsed = pd.to_datetime(str(raw), errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


# ── State normalizer ──────────────────────────────────────────────────────────

def normalize_state(raw: str) -> str:
    """Convert state name or mixed string to 2-letter uppercase code."""
    if not raw:
        return ""
    s = str(raw).strip()
    # Already 2-letter code
    if len(s) == 2 and s.isalpha():
        return s.upper()
    # Full name lookup
    lower = s.lower()
    if lower in _US_STATE_ABBR:
        return _US_STATE_ABBR[lower]
    # Try extracting 2-letter from string (last occurrence)
    m = re.search(r"\b([A-Z]{2})\b", s.upper())
    return m.group(1) if m else s.upper()[:2] if len(s) >= 2 else ""


# ── JSON list helpers ─────────────────────────────────────────────────────────

def parse_json_list(raw: str) -> str:
    """Convert pipe/semicolon/newline separated values to JSON array string."""
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return "[]"
    text = str(raw).strip()
    # Already JSON
    if text.startswith("["):
        try:
            json.loads(text)
            return text
        except Exception:
            pass
    # Split on common delimiters
    parts = re.split(r"[|\n;]+", text)
    cleaned = [p.strip() for p in parts if p.strip()]
    return json.dumps(cleaned, ensure_ascii=False)


# ── Tier auto-scoring ─────────────────────────────────────────────────────────

def auto_tier(row: dict) -> str:
    """Compute HOT/WARM/COLD tier from firmographic data.

    Rules:
      - No email → COLD (cannot contact)
      - revenue > $50M OR shipments > 100 → HOT
      - revenue > $10M OR shipments > 30  → WARM
      - shipments >= 10                   → WARM
      - else                              → COLD
    """
    has_email = bool(str(row.get("EMAIL") or "").strip())
    if not has_email:
        return "COLD"

    revenue = row.get("REVENUE_USD") or 0
    try:
        revenue = float(revenue)
    except (ValueError, TypeError):
        revenue = 0.0

    shipments = row.get("TOTAL_SHIPMENTS_ALL") or 0
    try:
        shipments = int(shipments)
    except (ValueError, TypeError):
        shipments = 0

    if revenue > 50_000_000 or shipments > 100:
        return "HOT"
    if revenue > 10_000_000 or shipments > 30:
        return "WARM"
    if shipments >= 10:
        return "WARM"
    return "COLD"


# ── Buyer-level column mapping ────────────────────────────────────────────────

# Maps Panjiva buyer-level column header → (v7_canonical, transform_hint)
BUYER_COL_MAP: dict[str, tuple[str, str]] = {
    "Buyer Name":                              ("COMPANY",              "title_strip"),
    "Full Address (main address)":             ("ADDRESS",              "raw"),
    "Full Address":                            ("ADDRESS",              "raw"),
    "State/Region":                            ("STATE",                "state"),
    "City":                                    ("CITY",                 "title"),
    "Country":                                 ("COUNTRY_DEST",         "upper"),
    "Postal Code":                             ("ZIP",                  "raw"),
    "Global HQ":                               ("PARENT_COMPANY",       "strip"),
    "Global HQ Address":                       ("GLOBAL_HQ_ADDRESS",    "raw"),
    "Global HQ DUNS":                          ("DUNS",                 "raw"),
    "Domestic HQ":                             ("DOMESTIC_HQ",          "strip"),
    "Domestic HQ Address":                     ("DOMESTIC_HQ_ADDRESS",  "raw"),
    "Domestic HQ DUNS":                        ("DOMESTIC_HQ_DUNS",     "raw"),
    "Revenue":                                 ("REVENUE_USD",          "revenue"),
    "Employees Count":                         ("EMPLOYEES",            "int"),
    "Total Number of Shipments":               ("TOTAL_SHIPMENTS_ALL",  "int"),
    "Number of Matched Shipments":             ("MATCHED_SHIPMENTS",    "int"),
    "Email":                                   ("EMAIL",                "lower"),
    "Contact Email":                           ("EMAIL_ALT1",           "lower"),
    "Phone":                                   ("PHONE_PRIMARY",        "strip"),
    "Contact Phone":                           ("PHONE_ALT1",           "strip"),
    "Contact Person":                          ("PIC_NAME",             "title_strip"),
    "Top 3 Suppliers":                         ("TOP_SUPPLIERS",        "json_list"),
    "Top 5 Products":                          ("TOP_PRODUCTS",         "json_list"),
    "Route":                                   ("ROUTE_DESC",           "raw"),
    "Last Shipment Date of Matched Shipments": ("LAST_SHIPMENT_DATE",   "date"),
    "Panjiva URL":                             ("PANJIVA_URL",          "raw"),
    "Website":                                 ("WEBSITE",              "raw"),
    "Weight of Matching Shipments (kg)":       ("WEIGHT_KG",            "raw"),
    "Value of Matching China Trade Data (USD)":("CHINA_TRADE_VALUE_USD","raw"),
}

# Fallback fuzzy matching for slightly renamed Panjiva headers
_BUYER_FUZZY: list[tuple[str, str, str]] = [
    # (substring_to_match, v7_col, transform)
    ("buyer name",          "COMPANY",            "title_strip"),
    ("full address",        "ADDRESS",            "raw"),
    ("state",               "STATE",              "state"),
    ("city",                "CITY",               "title"),
    ("country",             "COUNTRY_DEST",       "upper"),
    ("postal",              "ZIP",                "raw"),
    ("global hq duns",      "DUNS",               "raw"),
    ("global hq",           "PARENT_COMPANY",     "strip"),
    ("revenue",             "REVENUE_USD",        "revenue"),
    ("employee",            "EMPLOYEES",          "int"),
    ("total number of ship","TOTAL_SHIPMENTS_ALL","int"),
    ("number of matched",   "MATCHED_SHIPMENTS",  "int"),
    ("contact email",       "EMAIL_ALT1",         "lower"),
    ("email",               "EMAIL",              "lower"),
    ("contact phone",       "PHONE_ALT1",         "strip"),
    ("phone",               "PHONE_PRIMARY",      "strip"),
    ("contact person",      "PIC_NAME",           "title_strip"),
    ("top 3 supplier",      "TOP_SUPPLIERS",      "json_list"),
    ("top 5 product",       "TOP_PRODUCTS",       "json_list"),
    ("top supplier",        "TOP_SUPPLIERS",      "json_list"),
    ("top product",         "TOP_PRODUCTS",       "json_list"),
    ("route",               "ROUTE_DESC",         "raw"),
    ("last shipment date",  "LAST_SHIPMENT_DATE", "date"),
    ("panjiva url",         "PANJIVA_URL",        "raw"),
    ("website",             "WEBSITE",            "raw"),
    ("weight",              "WEIGHT_KG",          "raw"),
    ("china trade",         "CHINA_TRADE_VALUE_USD","raw"),
]


def resolve_buyer_columns(df_cols: list[str]) -> dict[str, tuple[str, str]]:
    """Match actual DataFrame columns to BUYER_COL_MAP (exact then fuzzy).

    Returns {actual_col_name: (v7_canonical, transform)}.
    """
    resolved: dict[str, tuple[str, str]] = {}
    used_canonical: set[str] = set()

    # Exact match first
    for col in df_cols:
        col_stripped = col.strip()
        if col_stripped in BUYER_COL_MAP:
            canon, transform = BUYER_COL_MAP[col_stripped]
            if canon not in used_canonical:
                resolved[col] = (canon, transform)
                used_canonical.add(canon)

    # Fuzzy fallback for unmatched columns
    for col in df_cols:
        if col in resolved:
            continue
        col_lower = col.strip().lower()
        for substr, canon, transform in _BUYER_FUZZY:
            if substr in col_lower and canon not in used_canonical:
                resolved[col] = (canon, transform)
                used_canonical.add(canon)
                break

    return resolved


def apply_transform(series: pd.Series, transform: str) -> pd.Series:
    """Apply named transform to a pandas Series."""
    s = series.fillna("").astype(str)
    if transform == "raw":
        return s.str.strip()
    if transform == "lower":
        return s.str.strip().str.lower()
    if transform == "upper":
        return s.str.strip().str.upper()
    if transform == "strip":
        return s.str.strip()
    if transform == "title":
        return s.str.strip().str.title()
    if transform == "title_strip":
        return s.str.strip().str.title()
    if transform == "state":
        return s.apply(normalize_state)
    if transform == "revenue":
        return s.apply(parse_revenue)
    if transform == "int":
        return s.apply(parse_int_safe)
    if transform == "date":
        return s.apply(parse_date_safe)
    if transform == "json_list":
        return s.apply(parse_json_list)
    return s.str.strip()


# ── v7 schema column order ────────────────────────────────────────────────────

V7_COLS = [
    # v6 preserved
    "EMAIL", "COMPANY", "PIC", "POL", "DESTINATION", "COMMODITY_CATEGORY", "TIER",
    "ORIGIN_COUNTRY", "STATE", "TIMEZONE",
    "EMAIL_STATUS", "SEND_COUNT", "LAST_SENT_DATE", "REPLY_STATUS",
    "EMAIL_ALT1", "EMAIL_ALT2", "PHONE_PRIMARY", "PHONE_ALT1", "PHONE_ALT2",
    "WHATSAPP", "LINKEDIN_URL", "WA_STATUS", "LI_STATUS",
    "REPLACEMENT_FOR", "VN_TEAM_OVERLAP_FLAG", "ACTIVATE_GATE",
    "COMPANY_BRANCH", "SOURCE_TAG", "IMPORT_DATE",
    # v7 NEW firmographic
    "REVENUE_USD", "EMPLOYEES", "TOTAL_SHIPMENTS_ALL", "MATCHED_SHIPMENTS",
    "PARENT_COMPANY", "DUNS", "PIC_NAME", "PIC_POSITION",
    "TOP_SUPPLIERS", "TOP_PRODUCTS",
    "LAST_SHIPMENT_DATE", "ROUTE_DESC", "PANJIVA_URL", "WEBSITE",
    "CITY", "ZIP", "COUNTRY_DEST",
    "ADDRESS",
    # v7 NEW multi-origin
    "POL_LIST", "ORIGIN_COUNTRIES", "MULTI_ORIGIN", "PRIMARY_POL",
    # v7 NEW tier scoring
    "TIER_AUTO_SCORE",
]
