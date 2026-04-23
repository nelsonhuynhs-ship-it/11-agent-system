#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
panjiva_clean_v3.py — Panjiva Export Cleaner v3
================================================
Supports 2 export formats:
  1. Buyer-level (group by buyer): 29 cols, 1 sheet "Panjiva Search Results"
  2. Shipment-level (per shipment): 32 cols, 3 sheets (Info / US Imports Shipments / Contact Info)

Public API:
  clean_panjiva_buyer_file(xlsx_path, commodity_hint, origin_country_hint) → DataFrame
  clean_panjiva_shipment_file(xlsx_path, commodity_hint, origin_country_hint) → dict
  detect_file_type(xlsx_path) → 'buyer-level' | 'shipment-level'
  auto_hint_from_filename(filename) → (commodity, country_code)

CLI:
  python scripts/panjiva_clean_v3.py --file path.xlsx --commodity FLOORING --country VN
  python scripts/panjiva_clean_v3.py --file path.xlsx --auto-hint --dry-run
  python scripts/panjiva_clean_v3.py --file path.xlsx --shipment-mode --output out.parquet
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts._panjiva_v3_helpers import (  # noqa: E402
    auto_hint_from_filename,
    apply_transform,
    auto_tier,
    normalize_state,
    parse_date_safe,
    parse_int_safe,
    parse_revenue,
    resolve_buyer_columns,
    V7_COLS,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("panjiva_v3")

# ── Blacklist path ────────────────────────────────────────────────────────────
_BLACKLIST_FILE = _REPO_ROOT / "email_engine" / "data" / "competitor_blacklist.json"


# ── File type detection ───────────────────────────────────────────────────────

def detect_file_type(xlsx_path: Path) -> str:
    """Detect 'buyer-level' or 'shipment-level' from sheet names."""
    try:
        xl = pd.ExcelFile(str(xlsx_path), engine="openpyxl")
        sheets = [s.strip() for s in xl.sheet_names]
    except Exception as exc:
        log.warning(f"detect_file_type: cannot open {xlsx_path}: {exc}")
        return "buyer-level"

    lower_sheets = [s.lower() for s in sheets]
    if any("us imports shipments" in s or "shipment" in s for s in lower_sheets):
        return "shipment-level"
    if any("search results" in s or "buyer" in s for s in lower_sheets):
        return "buyer-level"
    # Fallback: >1 sheet → shipment-level
    return "shipment-level" if len(sheets) > 1 else "buyer-level"


# ── Blacklist loader ──────────────────────────────────────────────────────────

def _load_blacklist() -> dict:
    try:
        data = json.loads(_BLACKLIST_FILE.read_text(encoding="utf-8"))
        whitelist = set(d.lower().strip() for d in data.get("whitelist_domains", []) if d)
        whitelist.add("pudongprime.vn")
        return {
            "domains":  set(d.lower().strip() for d in data.get("domains", []) if d),
            "emails":   set(e.lower().strip() for e in data.get("emails", []) if e),
            "keywords": [k.upper().strip() for k in data.get("keywords_in_company", []) if k],
            "whitelist_domains": whitelist,
        }
    except Exception as exc:
        log.warning(f"Blacklist load failed: {exc} — filter disabled")
        return {"domains": set(), "emails": set(), "keywords": [], "whitelist_domains": {"pudongprime.vn"}}


def _is_blacklisted(email: str, company: str, bl: dict) -> bool:
    em = (email or "").lower().strip()
    if not em or "@" not in em:
        return False
    domain = em.split("@", 1)[1]
    if domain in bl.get("whitelist_domains", set()):
        return False
    if em in bl["emails"] or domain in bl["domains"]:
        return True
    co = (company or "").upper()
    for kw in bl["keywords"]:
        if kw in co:
            return True
    return False


# ── Email validator ───────────────────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    em = (email or "").lower().strip()
    return bool(em and "@" in em and "." in em.split("@", 1)[1])


# ── Buyer-level cleaner ───────────────────────────────────────────────────────

def clean_panjiva_buyer_file(
    xlsx_path: Path,
    commodity_hint: str = "",
    origin_country_hint: str = "",
) -> pd.DataFrame:
    """Parse buyer-level Panjiva xlsx → normalized v7 DataFrame.

    Args:
        xlsx_path: Path to buyer-level Panjiva export (.xlsx)
        commodity_hint: Override COMMODITY_CATEGORY (FLOORING/FURNITURE_INDOOR/etc.)
        origin_country_hint: Override ORIGIN_COUNTRY (VN/TH/KH/MY)

    Returns:
        DataFrame with v7 schema columns. Empty DataFrame on fatal error.
    """
    xlsx_path = Path(xlsx_path)
    log.info(f"[buyer] Loading: {xlsx_path.name}")

    # ── Read sheet ────────────────────────────────────────────────────────────
    try:
        xl = pd.ExcelFile(str(xlsx_path), engine="openpyxl")
        # Find the right sheet
        target_sheet = xl.sheet_names[0]
        for s in xl.sheet_names:
            if "search results" in s.lower() or "buyer" in s.lower() or "panjiva" in s.lower():
                target_sheet = s
                break
        df_raw = pd.read_excel(xl, sheet_name=target_sheet, dtype=str)
    except Exception as exc:
        log.error(f"[buyer] Cannot read file: {exc}")
        return pd.DataFrame(columns=V7_COLS)

    df_raw = df_raw.fillna("")
    log.info(f"[buyer] Raw rows: {len(df_raw)}, cols: {len(df_raw.columns)}")

    # ── Map columns → v7 canonical ────────────────────────────────────────────
    col_resolve = resolve_buyer_columns(list(df_raw.columns))
    log.info(f"[buyer] Matched {len(col_resolve)}/{len(df_raw.columns)} columns")

    out = pd.DataFrame(index=df_raw.index)
    for raw_col, (canonical, transform) in col_resolve.items():
        out[canonical] = apply_transform(df_raw[raw_col], transform)

    # ── Drop empty COMPANY rows ───────────────────────────────────────────────
    if "COMPANY" in out.columns:
        out = out[out["COMPANY"].str.strip().str.len() > 0].copy()

    # ── Apply commodity + origin hints to all rows ────────────────────────────
    out["COMMODITY_CATEGORY"] = commodity_hint.upper() if commodity_hint else ""
    out["ORIGIN_COUNTRY"]     = origin_country_hint.upper() if origin_country_hint else ""

    # ── Validate / clean emails ───────────────────────────────────────────────
    for email_col in ("EMAIL", "EMAIL_ALT1", "EMAIL_ALT2"):
        if email_col in out.columns:
            out[email_col] = out[email_col].apply(
                lambda e: e.lower().strip() if _valid_email(e) else ""
            )

    # ── Ensure STATE is 2-letter ──────────────────────────────────────────────
    if "STATE" in out.columns:
        out["STATE"] = out["STATE"].apply(normalize_state)

    # ── Tier auto-score ───────────────────────────────────────────────────────
    out["TIER_AUTO_SCORE"] = out.apply(lambda row: auto_tier(row.to_dict()), axis=1)

    # ── Multi-origin placeholders (buyer-level has no shipment breakdown) ─────
    out["POL_LIST"]          = ""
    out["ORIGIN_COUNTRIES"]  = origin_country_hint.upper() if origin_country_hint else ""
    out["MULTI_ORIGIN"]      = False
    out["PRIMARY_POL"]       = ""

    # ── Blacklist filter ──────────────────────────────────────────────────────
    bl = _load_blacklist()
    pre_bl = len(out)
    bl_mask = out.apply(
        lambda r: _is_blacklisted(r.get("EMAIL", ""), r.get("COMPANY", ""), bl), axis=1
    )
    out = out[~bl_mask].reset_index(drop=True)
    log.info(f"[buyer] Blacklist: excluded {pre_bl - len(out)}, kept {len(out)}")

    # ── Add metadata ──────────────────────────────────────────────────────────
    out["SOURCE_TAG"]  = "PANJIVA_BUYER"
    out["IMPORT_DATE"] = datetime.now().strftime("%Y-%m-%d")
    out["ACTIVATE_GATE"] = "ACTIVE"

    # ── Ensure all v7 cols present ────────────────────────────────────────────
    for col in V7_COLS:
        if col not in out.columns:
            out[col] = ""

    # Return only v7 cols in canonical order
    return out[[c for c in V7_COLS if c in out.columns]].reset_index(drop=True)


# ── Shipment-level aggregation ────────────────────────────────────────────────

def aggregate_shipment_to_buyer(shipments_df: pd.DataFrame) -> pd.DataFrame:
    """Group raw shipments by Consignee → 1 row per buyer with POL aggregation.

    Aggregates:
      - POL_LIST: unique ports of lading (comma-separated)
      - ORIGIN_COUNTRIES: unique Port of Lading Country (comma-separated)
      - PRIMARY_POL: most frequent POL
      - MULTI_ORIGIN: bool (unique countries > 1)
      - TOP_CARRIER: most frequent Carrier
      - LATEST_SHIPMENT_DATE: latest date found
    Also collects Consignee Email 1/2/3 into EMAIL/EMAIL_ALT1/EMAIL_ALT2.
    """
    if shipments_df.empty:
        return pd.DataFrame()

    df = shipments_df.copy()

    # Normalize consignee name for grouping
    def _norm_name(name: str) -> str:
        import re as _re
        return _re.sub(r"[^A-Z0-9 ]", "", str(name or "").upper().strip())

    df["_CNEE_NORM"] = df.get("Consignee", pd.Series(dtype=str)).apply(_norm_name)
    df = df[df["_CNEE_NORM"].str.len() > 0]

    rows = []
    for cnee_norm, grp in df.groupby("_CNEE_NORM"):
        # POL aggregation
        pol_col = next((c for c in grp.columns if "port of lading" in c.lower() and "region" not in c.lower() and "country" not in c.lower()), None)
        country_col = next((c for c in grp.columns if "port of lading country" in c.lower()), None)
        carrier_col = next((c for c in grp.columns if "carrier" in c.lower()), None)
        date_col = next((c for c in grp.columns if "arrival" in c.lower() or "date" in c.lower()), None)

        pol_vals = sorted(grp[pol_col].dropna().astype(str).str.strip().unique().tolist()) if pol_col else []
        pol_vals = [p for p in pol_vals if p and p.lower() not in ("", "nan")]

        country_vals = sorted(grp[country_col].dropna().astype(str).str.strip().unique().tolist()) if country_col else []
        country_vals = [c for c in country_vals if c and c.lower() not in ("", "nan")]

        primary_pol = ""
        if pol_col and not grp[pol_col].dropna().empty:
            primary_pol = grp[pol_col].dropna().astype(str).str.strip().mode().iloc[0] if not grp[pol_col].dropna().empty else ""

        top_carrier = ""
        if carrier_col and not grp[carrier_col].dropna().empty:
            top_carrier = grp[carrier_col].dropna().astype(str).str.strip().mode().iloc[0]

        latest_date = ""
        if date_col:
            dates = grp[date_col].dropna().astype(str).apply(parse_date_safe)
            valid_dates = [d for d in dates if d]
            latest_date = max(valid_dates) if valid_dates else ""

        # Company name (first non-empty)
        company = grp["Consignee"].dropna().astype(str).str.strip().iloc[0] if "Consignee" in grp.columns else cnee_norm

        # Email aggregation from Consignee Email 1/2/3
        def _first_email(col_name: str) -> str:
            if col_name in grp.columns:
                vals = grp[col_name].dropna().astype(str).str.strip().str.lower()
                valid = [e for e in vals if _valid_email(e)]
                return valid[0] if valid else ""
            return ""

        email1 = _first_email("Consignee Email 1")
        email2 = _first_email("Consignee Email 2")
        email3 = _first_email("Consignee Email 3")

        # Phone
        def _first_val(col_name: str) -> str:
            if col_name in grp.columns:
                vals = grp[col_name].dropna().astype(str).str.strip()
                valid = [v for v in vals if v and v.lower() != "nan"]
                return valid[0] if valid else ""
            return ""

        # Address
        addr_col = next((c for c in grp.columns if "consignee full address" in c.lower()), None)
        address = _first_val(addr_col) if addr_col else ""

        rows.append({
            "COMPANY":           company,
            "EMAIL":             email1,
            "EMAIL_ALT1":        email2,
            "EMAIL_ALT2":        email3,
            "PHONE_PRIMARY":     _first_val("Consignee Phone 1"),
            "PHONE_ALT1":        _first_val("Consignee Phone 2"),
            "ADDRESS":           address,
            "POL_LIST":          ", ".join(pol_vals),
            "ORIGIN_COUNTRIES":  ", ".join(country_vals),
            "PRIMARY_POL":       primary_pol,
            "MULTI_ORIGIN":      len(country_vals) > 1,
            "TOP_CARRIER":       top_carrier,
            "LAST_SHIPMENT_DATE": latest_date,
            "TOTAL_SHIPMENTS_ALL": len(grp),
        })

    result = pd.DataFrame(rows)
    result["TIER_AUTO_SCORE"] = result.apply(lambda r: auto_tier(r.to_dict()), axis=1)
    return result.reset_index(drop=True)


# ── Shipper extraction ────────────────────────────────────────────────────────

def extract_shippers(shipments_df: pd.DataFrame, origin_country_hint: str = "") -> pd.DataFrame:
    """Extract unique Shipper rows for a separate SHIPPER output.

    Nelson rule: VN shippers → set SHIPPER_RISK_VN = True (require blacklist check).
                 Other SEA shippers → safe to add directly.

    Returns shipper DataFrame with SHIPPER_RISK_VN flag.
    """
    if shipments_df.empty:
        return pd.DataFrame()

    df = shipments_df.copy()
    shipper_col = next((c for c in df.columns if c.strip().lower() == "shipper"), None)
    if not shipper_col:
        log.warning("[shipper] No 'Shipper' column found in shipments sheet")
        return pd.DataFrame()

    addr_col = next((c for c in df.columns if "shipper full address" in c.lower()), None)
    email_cols = [c for c in df.columns if "shipper email" in c.lower()]
    phone_cols = [c for c in df.columns if "shipper phone" in c.lower()]
    origin_col = next((c for c in df.columns if "port of lading country" in c.lower()), None)

    rows = []
    seen_shippers: set[str] = set()

    for _, row in df.iterrows():
        shipper = str(row.get(shipper_col, "") or "").strip()
        if not shipper or shipper.lower() == "nan":
            continue
        shipper_norm = shipper.upper()
        if shipper_norm in seen_shippers:
            continue
        seen_shippers.add(shipper_norm)

        origin = str(row.get(origin_col, "") or "").strip() if origin_col else ""
        if not origin and origin_country_hint:
            origin = origin_country_hint.upper()

        emails = [str(row.get(c, "") or "").strip().lower() for c in email_cols]
        phones = [str(row.get(c, "") or "").strip() for c in phone_cols]

        valid_emails = [e for e in emails if _valid_email(e)]
        valid_phones = [p for p in phones if p and p.lower() != "nan"]

        is_vn = origin.upper() in ("VN", "VIET NAM", "VIETNAM")

        rows.append({
            "COMPANY":          shipper,
            "EMAIL":            valid_emails[0] if len(valid_emails) > 0 else "",
            "EMAIL_ALT1":       valid_emails[1] if len(valid_emails) > 1 else "",
            "ADDRESS":          str(row.get(addr_col, "") or "").strip() if addr_col else "",
            "PHONE_PRIMARY":    valid_phones[0] if len(valid_phones) > 0 else "",
            "PHONE_ALT1":       valid_phones[1] if len(valid_phones) > 1 else "",
            "ORIGIN_COUNTRY":   origin,
            "ACTIVATE_GATE":    "HOLD",
            "SHIPPER_RISK_VN":  is_vn,
            "SOURCE_TAG":       "PANJIVA_SHIPPER",
            "IMPORT_DATE":      datetime.now().strftime("%Y-%m-%d"),
        })

    result = pd.DataFrame(rows)
    log.info(f"[shipper] Extracted {len(result)} unique shippers, VN risk: {result['SHIPPER_RISK_VN'].sum() if not result.empty else 0}")
    return result.reset_index(drop=True)


# ── Shipment-level cleaner ────────────────────────────────────────────────────

def clean_panjiva_shipment_file(
    xlsx_path: Path,
    commodity_hint: str = "",
    origin_country_hint: str = "",
) -> dict:
    """Parse shipment-level xlsx (3 sheets). Returns dict with keys:
       - 'shipments_df': full raw shipments (32 cols)
       - 'contacts_df':  decision makers from Contact Info sheet
       - 'aggregated_df': 1 row per CNEE (POL_LIST aggregated)
       - 'shippers_df': unique shippers with SHIPPER_RISK_VN flag
    """
    xlsx_path = Path(xlsx_path)
    log.info(f"[shipment] Loading: {xlsx_path.name}")

    try:
        xl = pd.ExcelFile(str(xlsx_path), engine="openpyxl")
        all_sheets = xl.sheet_names
    except Exception as exc:
        log.error(f"[shipment] Cannot open file: {exc}")
        return {"shipments_df": pd.DataFrame(), "contacts_df": pd.DataFrame(),
                "aggregated_df": pd.DataFrame(), "shippers_df": pd.DataFrame()}

    # ── Identify sheets ───────────────────────────────────────────────────────
    shipment_sheet = None
    contact_sheet  = None
    for s in all_sheets:
        sl = s.lower()
        if "us imports shipments" in sl or "shipment" in sl:
            shipment_sheet = s
        elif "contact info" in sl or "contact" in sl:
            contact_sheet = s

    # ── Read shipments ────────────────────────────────────────────────────────
    shipments_df = pd.DataFrame()
    if shipment_sheet:
        try:
            shipments_df = pd.read_excel(xl, sheet_name=shipment_sheet, dtype=str).fillna("")
            log.info(f"[shipment] Shipments sheet: {len(shipments_df)} rows, {len(shipments_df.columns)} cols")
        except Exception as exc:
            log.warning(f"[shipment] Cannot read shipments sheet: {exc}")
    else:
        log.warning("[shipment] No shipments sheet found — trying first sheet")
        try:
            shipments_df = pd.read_excel(xl, sheet_name=0, dtype=str).fillna("")
        except Exception:
            pass

    # ── Read contacts ─────────────────────────────────────────────────────────
    contacts_df = pd.DataFrame()
    if contact_sheet:
        try:
            contacts_df = pd.read_excel(xl, sheet_name=contact_sheet, dtype=str).fillna("")
            # Normalize contact email
            email_col = next((c for c in contacts_df.columns if "email" in c.lower()), None)
            if email_col:
                contacts_df[email_col] = contacts_df[email_col].str.strip().str.lower()
            log.info(f"[shipment] Contacts sheet: {len(contacts_df)} rows")
        except Exception as exc:
            log.warning(f"[shipment] Cannot read contacts sheet: {exc}")

    # ── Aggregate shipments → 1 row per CNEE ─────────────────────────────────
    aggregated_df = pd.DataFrame()
    shippers_df   = pd.DataFrame()
    if not shipments_df.empty:
        aggregated_df = aggregate_shipment_to_buyer(shipments_df)
        aggregated_df["COMMODITY_CATEGORY"] = commodity_hint.upper() if commodity_hint else ""
        aggregated_df["ORIGIN_COUNTRY"]     = origin_country_hint.upper() if origin_country_hint else ""
        aggregated_df["SOURCE_TAG"]  = "PANJIVA_SHIPMENT"
        aggregated_df["IMPORT_DATE"] = datetime.now().strftime("%Y-%m-%d")
        aggregated_df["ACTIVATE_GATE"] = "ACTIVE"

        # Blacklist filter on aggregated
        bl = _load_blacklist()
        pre = len(aggregated_df)
        bl_mask = aggregated_df.apply(
            lambda r: _is_blacklisted(r.get("EMAIL", ""), r.get("COMPANY", ""), bl), axis=1
        )
        aggregated_df = aggregated_df[~bl_mask].reset_index(drop=True)
        log.info(f"[shipment] Aggregated: {pre} → {len(aggregated_df)} (after blacklist)")

        shippers_df = extract_shippers(shipments_df, origin_country_hint)

    return {
        "shipments_df":  shipments_df,
        "contacts_df":   contacts_df,
        "aggregated_df": aggregated_df,
        "shippers_df":   shippers_df,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_preview(df: pd.DataFrame, label: str, n: int = 3) -> None:
    print(f"\n{'='*60}")
    print(f"  {label} — {len(df)} rows, {len(df.columns)} cols")
    print(f"{'='*60}")
    if df.empty:
        print("  (empty)")
        return
    preview_cols = [c for c in df.columns if c in (
        "COMPANY", "EMAIL", "STATE", "COMMODITY_CATEGORY",
        "TIER_AUTO_SCORE", "REVENUE_USD", "TOTAL_SHIPMENTS_ALL",
        "MATCHED_SHIPMENTS", "POL_LIST", "ORIGIN_COUNTRY",
    )]
    print(df[preview_cols].head(n).to_string(index=False))


def _tier_distribution(df: pd.DataFrame) -> dict:
    if "TIER_AUTO_SCORE" not in df.columns or df.empty:
        return {}
    return df["TIER_AUTO_SCORE"].value_counts().to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Panjiva Clean v3 — parse buyer-level and shipment-level exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", required=True, help="Path to Panjiva .xlsx file")
    parser.add_argument("--commodity", default="", help="Commodity hint (FLOORING, FURNITURE_INDOOR, etc.)")
    parser.add_argument("--country", default="", help="Origin country ISO code (VN/TH/KH/MY)")
    parser.add_argument("--output", default="", help="Output path (.parquet or .xlsx). Skip if dry-run.")
    parser.add_argument("--auto-hint", action="store_true", help="Infer commodity + country from filename")
    parser.add_argument("--dry-run", action="store_true", help="Show preview without writing output")
    parser.add_argument("--shipment-mode", action="store_true", help="Force shipment-level parsing")
    args = parser.parse_args()

    t0 = time.time()
    xlsx_path = Path(args.file)
    if not xlsx_path.exists():
        print(f"ERROR: File not found: {xlsx_path}", file=sys.stderr)
        sys.exit(1)

    # ── Auto-hint from filename ───────────────────────────────────────────────
    commodity_hint = args.commodity
    country_hint   = args.country
    if args.auto_hint:
        auto_commodity, auto_country = auto_hint_from_filename(xlsx_path.name)
        if auto_commodity and not commodity_hint:
            commodity_hint = auto_commodity
            log.info(f"Auto-hint commodity: {commodity_hint}")
        if auto_country and not country_hint:
            country_hint = auto_country
            log.info(f"Auto-hint country: {country_hint}")

    # ── Detect file type ──────────────────────────────────────────────────────
    if args.shipment_mode:
        file_type = "shipment-level"
    else:
        file_type = detect_file_type(xlsx_path)
    log.info(f"File type detected: {file_type}")

    # ── Parse ─────────────────────────────────────────────────────────────────
    if file_type == "buyer-level":
        df = clean_panjiva_buyer_file(xlsx_path, commodity_hint, country_hint)

        _cli_preview(df, "Buyer-level cleaned")
        tier_dist = _tier_distribution(df)
        print(f"\n  Tier distribution: {tier_dist}")
        print(f"  Cols: {len(df.columns)} | Rows: {len(df)} | Duration: {time.time()-t0:.1f}s")

        assert len(df) > 0, "No rows returned"
        assert len(df.columns) >= 35, f"Expected ≥35 cols, got {len(df.columns)}"

        if not args.dry_run and args.output:
            out_path = Path(args.output)
            if out_path.suffix == ".parquet":
                df.to_parquet(str(out_path), index=False)
            else:
                df.to_excel(str(out_path), index=False)
            log.info(f"Written: {out_path} ({len(df)} rows)")

    else:
        result = clean_panjiva_shipment_file(xlsx_path, commodity_hint, country_hint)
        agg = result["aggregated_df"]
        contacts = result["contacts_df"]
        shippers = result["shippers_df"]

        _cli_preview(agg, "Aggregated CNEE (shipment-level)")
        _cli_preview(contacts, "Contact Info sheet")
        _cli_preview(shippers, "Shippers extracted")
        tier_dist = _tier_distribution(agg)
        print(f"\n  CNEE Tier distribution: {tier_dist}")
        print(f"  Aggregated rows: {len(agg)} | Contacts: {len(contacts)} | Shippers: {len(shippers)}")
        print(f"  Duration: {time.time()-t0:.1f}s")

        if not args.dry_run and args.output:
            out_path = Path(args.output)
            if out_path.suffix == ".parquet":
                agg.to_parquet(str(out_path), index=False)
            else:
                with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
                    agg.to_excel(writer, sheet_name="CNEE", index=False)
                    if not contacts.empty:
                        contacts.to_excel(writer, sheet_name="Contacts", index=False)
                    if not shippers.empty:
                        shippers.to_excel(writer, sheet_name="Shippers", index=False)
            log.info(f"Written: {out_path}")


if __name__ == "__main__":
    main()
