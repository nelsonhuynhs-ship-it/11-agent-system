#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
panjiva_clean_v2.py — Panjiva Raw Extractor v2 (15-col full extract)
=====================================================================
Upgrade từ panjiva_clean.py (chỉ extract 3 cols).
V2 extract đầy đủ 15 cols Panjiva raw và split thành 2 DataFrame:
  - CNEE side  (Consignee data) → dùng cho sheet CNEE
  - SHIPPER side (Shipper data) → dùng cho sheet SHIPPER

CLI:
  python scripts/panjiva_clean_v2.py --input panjiva_raw.xlsx
  python scripts/panjiva_clean_v2.py --input panjiva_raw.xlsx --dry-run
  python scripts/panjiva_clean_v2.py --input panjiva_raw.xlsx --source-tag PANJIVA_2026W17

Output dict:
  {
    "cnee_df":    pd.DataFrame,   # CNEE rows (mapped to 35-col schema)
    "shipper_df": pd.DataFrame,   # SHIPPER rows
    "stats":      dict,           # counts + breakdown
  }
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("panjiva_v2")

# ── Imports from shared + helpers ─────────────────────────────────────────────
try:
    from shared.paths import CODE_DIR
    BLACKLIST_FILE = CODE_DIR / "email_engine" / "data" / "competitor_blacklist.json"
except ImportError:
    BLACKLIST_FILE = _REPO_ROOT / "email_engine" / "data" / "competitor_blacklist.json"

# ── 18 Commodity categories (CNEE schema v3.1) ───────────────────────────────
COMMODITY_CATEGORIES = [
    "FLOORING", "FURNITURE_INDOOR", "FURNITURE_OUTDOOR",
    "RUBBER", "PLASTIC", "CANDLE", "TEXTILE", "APPAREL",
    "FOOTWEAR", "ELECTRONICS", "METAL", "WOOD", "CERAMIC",
    "FOOD", "CHEMICAL", "PAPER", "COSMETICS", "OTHERS",
]

_KEYWORD_MAP: dict[str, str] = {
    "flooring": "FLOORING", "vinyl floor": "FLOORING", "laminate": "FLOORING",
    "hardwood floor": "FLOORING", "hardwood": "FLOORING", "plank": "FLOORING",
    "parquet": "FLOORING", "lvt": "FLOORING", "spc floor": "FLOORING",
    "tile floor": "FLOORING", "floor": "FLOORING",
    "outdoor furniture": "FURNITURE_OUTDOOR", "patio": "FURNITURE_OUTDOOR",
    "garden furniture": "FURNITURE_OUTDOOR", "adirondack": "FURNITURE_OUTDOOR",
    "furniture": "FURNITURE_INDOOR", "sofa": "FURNITURE_INDOOR",
    "chair": "FURNITURE_INDOOR", "table": "FURNITURE_INDOOR",
    "cabinet": "FURNITURE_INDOOR", "drawer": "FURNITURE_INDOOR",
    "desk": "FURNITURE_INDOOR", "bed frame": "FURNITURE_INDOOR",
    "rubber": "RUBBER", "latex": "RUBBER", "gasket": "RUBBER",
    "plastic": "PLASTIC", "pvc": "PLASTIC", "hdpe": "PLASTIC",
    "polypropylene": "PLASTIC", "polyethylene": "PLASTIC", "nylon": "PLASTIC",
    "candle": "CANDLE", "wax": "CANDLE", "taper": "CANDLE",
    "textile": "TEXTILE", "fabric": "TEXTILE", "yarn": "TEXTILE",
    "curtain": "TEXTILE", "blanket": "TEXTILE",
    "apparel": "APPAREL", "garment": "APPAREL", "clothing": "APPAREL",
    "shirt": "APPAREL", "jacket": "APPAREL", "dress": "APPAREL",
    "footwear": "FOOTWEAR", "shoe": "FOOTWEAR", "boot": "FOOTWEAR",
    "sandal": "FOOTWEAR", "sneaker": "FOOTWEAR",
    "electronic": "ELECTRONICS", "circuit": "ELECTRONICS",
    "cable": "ELECTRONICS", "battery": "ELECTRONICS", "led": "ELECTRONICS",
    "steel": "METAL", "iron": "METAL", "aluminum": "METAL",
    "copper": "METAL", "metal": "METAL", "alloy": "METAL",
    "wood": "WOOD", "plywood": "WOOD", "lumber": "WOOD", "mdf": "WOOD",
    "ceramic": "CERAMIC", "porcelain": "CERAMIC",
    "food": "FOOD", "frozen": "FOOD", "seafood": "FOOD",
    "beverage": "FOOD", "snack": "FOOD",
    "chemical": "CHEMICAL", "solvent": "CHEMICAL", "resin": "CHEMICAL",
    "paper": "PAPER", "carton": "PAPER", "tissue": "PAPER",
    "cosmetic": "COSMETICS", "skincare": "COSMETICS", "beauty": "COSMETICS",
}

_HS_MAP: dict[str, str] = {
    "39": "PLASTIC", "40": "RUBBER", "44": "WOOD", "48": "PAPER",
    "54": "TEXTILE", "55": "TEXTILE", "57": "FLOORING",
    "61": "APPAREL", "62": "APPAREL", "64": "FOOTWEAR",
    "69": "CERAMIC", "72": "METAL", "73": "METAL", "76": "METAL",
    "85": "ELECTRONICS", "94": "FURNITURE_INDOOR",
}

# ── US state abbreviations for address parsing ────────────────────────────────
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC","PR","GU","VI",
    # Canadian provinces
    "AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT",
}

# ── POL normalization (Place of Receipt → port code) ─────────────────────────
_POL_MAP: dict[str, str] = {
    "hai phong": "HPH", "haiphong": "HPH", "hải phòng": "HPH",
    "ho chi minh": "HCM", "hochiminh": "HCM", "hồ chí minh": "HCM",
    "saigon": "HCM", "ho chi minh city": "HCM",
    "da nang": "DAN", "danang": "DAN", "đà nẵng": "DAN",
    "quy nhon": "QNH", "quynhon": "QNH",
    "vung tau": "VUT", "vungtau": "VUT",
    "cat lai": "HCM",
    "cai mep": "CMT", "caimep": "CMT",
    "china": "CHINA", "shanghai": "SHA", "shenzhen": "SZX",
    "ningbo": "NGB", "guangzhou": "CAN", "tianjin": "TSN",
    "qingdao": "TAO", "xiamen": "XMN",
    "hong kong": "HKG", "hongkong": "HKG",
    "singapore": "SIN", "busan": "PUS",
    "bangkok": "BKK", "thailand": "BKK",
    "indonesia": "JKT", "jakarta": "JKT",
    "malaysia": "PEN",
    "india": "INDIA", "nhava sheva": "INNSA", "mundra": "INMUN",
}


def _normalize_pol(place_of_receipt: str) -> str:
    """Map Place of Receipt free-text → port code."""
    if not place_of_receipt:
        return ""
    text = place_of_receipt.lower().strip()
    for key, code in _POL_MAP.items():
        if key in text:
            return code
    # Return cleaned original if no match
    return place_of_receipt.strip().upper()[:10]


def _classify_commodity(product_desc: str, hs_code: str = "") -> str:
    """Keyword + HS-code commodity classifier."""
    text = (product_desc or "").lower()
    for kw, cat in _KEYWORD_MAP.items():
        if kw in text:
            return cat
    hs = re.sub(r"[^0-9]", "", hs_code or "")[:2]
    return _HS_MAP.get(hs, "OTHERS")


def _parse_state(destination: str) -> str:
    """Extract US state code from a destination address string."""
    if not destination:
        return ""
    # Prefer a 2-letter all-caps word that matches known states
    tokens = re.findall(r"\b([A-Z]{2})\b", destination.upper())
    for tok in reversed(tokens):  # last occurrence usually the state
        if tok in _US_STATES:
            return tok
    return ""


def _normalize_phone(phone: str) -> str:
    """Strip non-digits; basic E.164 prefix if looks like US number."""
    if not phone:
        return ""
    digits = re.sub(r"[^0-9+]", "", phone.strip())
    if not digits:
        return ""
    # If purely 10 digits (US/CA), prefix +1
    if re.fullmatch(r"[0-9]{10}", digits):
        return "+1" + digits
    # If 11 digits starting with 1
    if re.fullmatch(r"1[0-9]{10}", digits):
        return "+" + digits
    return digits


def _load_blacklist() -> dict:
    try:
        data = json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        whitelist = {d.lower().strip() for d in data.get("whitelist_domains", [])}
        whitelist.add("pudongprime.vn")
        return {
            "domains":  {d.lower().strip() for d in data.get("domains", [])},
            "emails":   {e.lower().strip() for e in data.get("emails", [])},
            "keywords": [k.upper().strip() for k in data.get("keywords_in_company", [])],
            "whitelist": whitelist,
        }
    except Exception as exc:
        log.warning(f"Blacklist load failed: {exc} — filter disabled")
        return {"domains": set(), "emails": set(), "keywords": [], "whitelist": {"pudongprime.vn"}}


def _is_blacklisted(email: str, company: str, bl: dict) -> bool:
    em = (email or "").lower().strip()
    if not em or "@" not in em:
        return False
    domain = em.split("@", 1)[1]
    if domain in bl["whitelist"]:
        return False
    if em in bl["emails"] or domain in bl["domains"]:
        return True
    co = (company or "").upper()
    return any(kw in co for kw in bl["keywords"])


# ── Column detection helper ────────────────────────────────────────────────────

def _detect_col(df: pd.DataFrame, *patterns: str) -> Optional[str]:
    """Return first column whose upper-stripped name matches any pattern."""
    for col in df.columns:
        cu = col.strip().upper()
        for pat in patterns:
            if pat.upper() in cu:
                return col
    return None


def _get_series(df: pd.DataFrame, col_name: Optional[str], lower: bool = False) -> pd.Series:
    if col_name and col_name in df.columns:
        s = df[col_name].fillna("").astype(str).str.strip()
        return s.str.lower() if lower else s
    return pd.Series([""] * len(df), dtype=str, index=df.index)


# ── Core extract function ─────────────────────────────────────────────────────

def extract_panjiva_file(
    input_path: str | Path,
    source_tag: str = "PANJIVA",
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Extract one raw Panjiva XLSX → two DataFrames (CNEE, SHIPPER).

    Panjiva columns recognized (case-insensitive):
      Matching Fields, Consignee, Consignee Email 1/2/3,
      Consignee Phone 1/2/3, Shipper, Shipper Email 1/2/3,
      Carrier, Shipment Destination, Place of Receipt

    Returns:
        (cnee_df, shipper_df, stats_dict)
        Both DataFrames use internal schema keys, ready for migrate pipeline.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Panjiva file not found: {input_path}")

    raw = pd.read_excel(input_path, dtype=str).fillna("")
    log.info(f"Loaded {len(raw)} rows × {len(raw.columns)} cols from {input_path.name}")

    # ── Map columns (detect both standard + variant names) ───────────────────
    col = {
        "desc":          _detect_col(raw, "MATCHING FIELD", "PRODUCT"),
        "consignee":     _detect_col(raw, "CONSIGNEE NAME", "CONSIGNEE"),
        "cnee_email1":   _detect_col(raw, "CONSIGNEE EMAIL 1"),
        "cnee_email2":   _detect_col(raw, "CONSIGNEE EMAIL 2"),
        "cnee_email3":   _detect_col(raw, "CONSIGNEE EMAIL 3"),
        "cnee_phone1":   _detect_col(raw, "CONSIGNEE PHONE 1"),
        "cnee_phone2":   _detect_col(raw, "CONSIGNEE PHONE 2"),
        "cnee_phone3":   _detect_col(raw, "CONSIGNEE PHONE 3"),
        "shipper":       _detect_col(raw, "SHIPPER NAME", "SHIPPER"),
        "shpr_email1":   _detect_col(raw, "SHIPPER EMAIL 1"),
        "shpr_email2":   _detect_col(raw, "SHIPPER EMAIL 2"),
        "shpr_email3":   _detect_col(raw, "SHIPPER EMAIL 3"),
        "carrier":       _detect_col(raw, "CARRIER"),
        "destination":   _detect_col(raw, "SHIPMENT DESTINATION", "DESTINATION"),
        "pol":           _detect_col(raw, "PLACE OF RECEIPT"),
    }

    # Exclude "CONSIGNEE EMAIL" variants when looking for plain "CONSIGNEE"
    if col["consignee"] and "EMAIL" in col["consignee"].upper():
        col["consignee"] = None
        col["consignee"] = _detect_col_exact_consignee(raw)

    log.info(f"Column map: { {k: v for k, v in col.items() if v} }")

    # ── Build per-row data ────────────────────────────────────────────────────
    desc        = _get_series(raw, col["desc"])
    destination = _get_series(raw, col["destination"])
    pol_raw     = _get_series(raw, col["pol"])
    carrier     = _get_series(raw, col["carrier"])

    states      = destination.apply(_parse_state)
    pols        = pol_raw.apply(_normalize_pol)
    commodity   = pd.Series(
        [_classify_commodity(d) for d in desc], index=raw.index, dtype=str
    )

    # ── CNEE side ─────────────────────────────────────────────────────────────
    cnee_company  = _get_series(raw, col["consignee"])
    cnee_email1   = _get_series(raw, col["cnee_email1"], lower=True)
    cnee_email2   = _get_series(raw, col["cnee_email2"], lower=True)
    cnee_email3   = _get_series(raw, col["cnee_email3"], lower=True)
    cnee_phone1   = _get_series(raw, col["cnee_phone1"]).apply(_normalize_phone)
    cnee_phone2   = _get_series(raw, col["cnee_phone2"]).apply(_normalize_phone)
    cnee_phone3   = _get_series(raw, col["cnee_phone3"]).apply(_normalize_phone)

    cnee_df = pd.DataFrame({
        "COMPANY":           cnee_company,
        "EMAIL_PRIMARY":     cnee_email1,
        "EMAIL_ALT1":        cnee_email2,
        "EMAIL_ALT2":        cnee_email3,
        "PHONE_PRIMARY":     cnee_phone1,
        "PHONE_ALT1":        cnee_phone2,
        "PHONE_ALT2":        cnee_phone3,
        "POL":               pols,
        "STATE":             states,
        "CARRIER":           carrier,
        "COMMODITY_CATEGORY": commodity,
        "PRODUCT_DESCRIPTION": desc,
        "DESTINATION":       destination,
        "SHEET":             "CNEE",
        "SOURCE_TAG":        source_tag,
        "ACTIVATE_GATE":     "ACTIVE",
    })
    # Filter: drop rows with no COMPANY and no EMAIL
    cnee_df = cnee_df[
        (cnee_df["COMPANY"].str.len() > 0) | (cnee_df["EMAIL_PRIMARY"].str.contains("@", na=False))
    ].reset_index(drop=True)

    # ── SHIPPER side ──────────────────────────────────────────────────────────
    shpr_company = _get_series(raw, col["shipper"])
    shpr_email1  = _get_series(raw, col["shpr_email1"], lower=True)
    shpr_email2  = _get_series(raw, col["shpr_email2"], lower=True)
    shpr_email3  = _get_series(raw, col["shpr_email3"], lower=True)

    shipper_df = pd.DataFrame({
        "COMPANY":           shpr_company,
        "EMAIL_PRIMARY":     shpr_email1,
        "EMAIL_ALT1":        shpr_email2,
        "EMAIL_ALT2":        shpr_email3,
        "PHONE_PRIMARY":     pd.Series([""] * len(raw), dtype=str),
        "PHONE_ALT1":        pd.Series([""] * len(raw), dtype=str),
        "PHONE_ALT2":        pd.Series([""] * len(raw), dtype=str),
        "POL":               pols,
        "STATE":             pd.Series([""] * len(raw), dtype=str),
        "CARRIER":           carrier,
        "COMMODITY_CATEGORY": commodity,
        "PRODUCT_DESCRIPTION": desc,
        "DESTINATION":       destination,
        "SHEET":             "SHIPPER",
        "SOURCE_TAG":        source_tag,
        "ACTIVATE_GATE":     "HOLD",  # default HOLD pending VN blacklist Phase 3
    })
    # Filter: drop rows with no COMPANY and no EMAIL
    shipper_df = shipper_df[
        (shipper_df["COMPANY"].str.len() > 0) | (shipper_df["EMAIL_PRIMARY"].str.contains("@", na=False))
    ].reset_index(drop=True)

    stats = {
        "raw_rows":     len(raw),
        "cnee_rows":    len(cnee_df),
        "shipper_rows": len(shipper_df),
        "commodity":    commodity.value_counts().to_dict(),
        "state_top":    dict(states[states != ""].value_counts().head(10)),
        "pol_top":      dict(pols[pols != ""].value_counts().head(10)),
    }
    log.info(
        f"Extract done: {stats['raw_rows']} raw -> "
        f"{stats['cnee_rows']} CNEE + {stats['shipper_rows']} SHIPPER rows"
    )
    return cnee_df, shipper_df, stats


def _detect_col_exact_consignee(df: pd.DataFrame) -> Optional[str]:
    """Find the plain 'Consignee' column (not email/phone/address variants)."""
    for col in df.columns:
        cu = col.strip().upper()
        if cu == "CONSIGNEE":
            return col
        if "CONSIGNEE" in cu and not any(
            x in cu for x in ("EMAIL", "PHONE", "ADDRESS", "CITY", "STATE", "ZIP")
        ):
            return col
    return None


def apply_blacklist_filter(
    cnee_df: pd.DataFrame,
    shipper_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Filter competitor/blacklisted rows from both DataFrames.

    Returns (filtered_cnee, filtered_shipper, total_excluded).
    """
    bl = _load_blacklist()
    total_excl = 0

    def _filter(df: pd.DataFrame) -> pd.DataFrame:
        nonlocal total_excl
        mask = df.apply(
            lambda r: _is_blacklisted(r["EMAIL_PRIMARY"], r["COMPANY"], bl), axis=1
        )
        excl = int(mask.sum())
        total_excl += excl
        if excl:
            log.info(f"Blacklist: excluded {excl} rows from {df['SHEET'].iloc[0] if len(df) else 'unknown'}")
        return df[~mask].reset_index(drop=True)

    cnee_df    = _filter(cnee_df)    if not cnee_df.empty    else cnee_df
    shipper_df = _filter(shipper_df) if not shipper_df.empty else shipper_df
    return cnee_df, shipper_df, total_excl


def process_panjiva_file(
    input_path: str | Path,
    source_tag: str = "PANJIVA",
    dry_run: bool = False,
) -> dict:
    """
    High-level entry point: extract + blacklist filter + return results.

    Returns dict with keys: cnee_df, shipper_df, stats, dry_run.
    """
    cnee_df, shipper_df, stats = extract_panjiva_file(input_path, source_tag)

    pre_cnee    = len(cnee_df)
    pre_shipper = len(shipper_df)
    cnee_df, shipper_df, excl = apply_blacklist_filter(cnee_df, shipper_df)
    stats["blacklist_excluded"] = excl
    stats["cnee_after_filter"]    = len(cnee_df)
    stats["shipper_after_filter"] = len(shipper_df)

    log.info(
        f"After blacklist: CNEE {pre_cnee}->{len(cnee_df)}, "
        f"SHIPPER {pre_shipper}->{len(shipper_df)}"
    )

    if dry_run:
        log.info("DRY RUN — DataFrames returned but not written to any master file")

    return {
        "cnee_df":    cnee_df,
        "shipper_df": shipper_df,
        "stats":      stats,
        "dry_run":    dry_run,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Panjiva Raw Extractor v2 — extract 15 cols, split CNEE/SHIPPER"
    )
    parser.add_argument("--input",      required=True, help="Path to raw Panjiva .xlsx file")
    parser.add_argument("--source-tag", default="PANJIVA", help="Import tag e.g. PANJIVA_2026W17")
    parser.add_argument("--dry-run",    action="store_true", help="Extract only, do not write")
    parser.add_argument("--show-cols",  action="store_true", help="Print detected columns and exit")
    args = parser.parse_args()

    if args.show_cols:
        raw = pd.read_excel(args.input, dtype=str, nrows=0)
        print("Columns in file:")
        for c in raw.columns:
            print(f"  {c!r}")
        sys.exit(0)

    result = process_panjiva_file(
        input_path=args.input,
        source_tag=args.source_tag,
        dry_run=args.dry_run,
    )

    s = result["stats"]
    print("\n" + "=" * 55)
    print("  PANJIVA EXTRACT v2 REPORT")
    print("=" * 55)
    print(f"  Source tag      : {args.source_tag}")
    print(f"  Input rows      : {s['raw_rows']}")
    print(f"  CNEE rows       : {s['cnee_rows']} -> after filter: {s.get('cnee_after_filter', s['cnee_rows'])}")
    print(f"  SHIPPER rows    : {s['shipper_rows']} -> after filter: {s.get('shipper_after_filter', s['shipper_rows'])}")
    print(f"  Blacklist excl  : {s.get('blacklist_excluded', 0)}")
    print(f"  Dry run         : {result['dry_run']}")
    print("\n  Commodity breakdown:")
    for cat, cnt in sorted(s["commodity"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {cnt}")
    print("\n  Top POL:")
    for pol, cnt in sorted(s["pol_top"].items(), key=lambda x: -x[1])[:5]:
        print(f"    {pol:<10} {cnt}")
    print("\n  Top states:")
    for st, cnt in sorted(s["state_top"].items(), key=lambda x: -x[1])[:8]:
        print(f"    {st:<8} {cnt}")
    print("=" * 55)
