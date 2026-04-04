# -*- coding: utf-8 -*-
"""
collect_all_sources.py — Multi-Source Email Prospect Collector
==============================================================
Collects email prospect records from ALL 3 source locations:

  Source 1: PANJIVA_DIR (email/panjiva/) — 14 files
    - panjiva_raw_*.xlsx  : shipment sheets + Contact Info sheets
    - data_*.xlsx         : pre-processed CNEE/SHIPPER rows

  Source 2: DATA_LOC_DIR (Data Loc/) — 26 files
    - Panjiva LOC files   : FLOORING LOC, RUBBER LOC, etc. (same panjiva structure)
    - DATA USA report.xlsx: 10,201 verified + 28 PROTENTIAL VIP contacts
    - Manual Nelson files : CNEE.xlsx, DATA CNEE.xlsx, DATA LOC.xlsx
    - LOC PLASTIC.xlsx    : bare 2-column company/email list

  Source 3: Existing pipeline outputs
    - cnee_master.xlsx    : 5,316 rows
    - email_log.csv       : 16,775 send history rows

Output schema (unified dict per record):
  EMAIL, COMPANY, CONTACT_NAME, POSITION, PHONE, CAMPAIGN_ID,
  SOURCE_FILE, RECORD_TYPE (cnee|contact|shipper|protential),
  EXTRA (dict of additional fields)

Usage:
    from email_engine.ingest.collect_all_sources import collect_all
    records = collect_all()
    print(f"Collected {len(records)} raw records")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from shared import paths as sp
from email_engine.ingest.email_cleaner import clean_panjiva_email, validate_email

# ── Paths ─────────────────────────────────────────────────────────────────────
PANJIVA_DIR  = sp.PANJIVA_DIR
DATA_LOC_DIR = sp.DATA_LOC_DIR
CNEE_MASTER  = sp.CNEE_MASTER
EMAIL_LOG    = sp.EMAIL_LOG

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── Sheet name variants ───────────────────────────────────────────────────────
_SHIPMENT_SHEETS = [
    "US Imports Shipments",
    "US Imports Consignee Shipments",
    "Shipment Destination",
    "Consignee",
]
_CONTACT_SHEETS = ["Contact Info"]

# ── Stats accumulator ─────────────────────────────────────────────────────────
_stats: dict[str, int] = {
    "panjiva_raw": 0,
    "panjiva_data": 0,
    "data_loc_panjiva": 0,
    "data_loc_manual": 0,
    "data_loc_usa_report": 0,
    "data_loc_protential": 0,
    "existing_cnee_master": 0,
    "email_log_history": 0,
    "total_raw": 0,
    "emails_cleaned": 0,
    "emails_invalid": 0,
}


# ── Column finder ─────────────────────────────────────────────────────────────

def _find_col(cols: list[str], *keys: str) -> str | None:
    """Find first column whose lowered name contains all keys."""
    for c in cols:
        cl = c.lower()
        if all(k.lower() in cl for k in keys):
            return c
    return None


def _safe_str(val: Any) -> str:
    """Convert to string, return '' for nan/None."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "nat", "") else s


# ── Record builder ────────────────────────────────────────────────────────────

def _make_record(
    email: str,
    company: str = "",
    contact_name: str = "",
    position: str = "",
    phone: str = "",
    campaign_id: str = "",
    source_file: str = "",
    record_type: str = "cnee",
    **extra: Any,
) -> dict:
    return {
        "EMAIL": email.strip().lower(),
        "COMPANY": company.strip().upper() if company else "",
        "CONTACT_NAME": contact_name.strip(),
        "POSITION": position.strip(),
        "PHONE": phone.strip(),
        "CAMPAIGN_ID": campaign_id.strip().upper(),
        "SOURCE_FILE": source_file,
        "RECORD_TYPE": record_type,
        **{k: v for k, v in extra.items() if v},
    }


def _extract_emails_from_cells(*cells: Any) -> list[str]:
    """
    Extract and validate emails from multiple raw cell values.
    Returns only emails with quality_score > 0.
    """
    seen: set[str] = set()
    result = []
    for cell in cells:
        candidates = clean_panjiva_email(str(cell) if cell is not None else "")
        for cand in candidates:
            email, score = validate_email(cand)
            if score > 0 and email not in seen:
                seen.add(email)
                result.append(email)
                _stats["emails_cleaned"] += 1
    return result


# ── Source 1: panjiva_raw_*.xlsx ─────────────────────────────────────────────

def _load_panjiva_raw(fpath: Path) -> list[dict]:
    """Load shipment + Contact Info sheets from a panjiva_raw_*.xlsx file."""
    records: list[dict] = []
    campaign = fpath.stem.replace("panjiva_raw_", "").upper()

    try:
        xls = pd.ExcelFile(fpath)
    except Exception as exc:
        log.warning("Cannot open %s: %s", fpath.name, exc)
        return records

    # Shipment sheet → cnee + shipper records
    ship_sheet = next((s for s in _SHIPMENT_SHEETS if s in xls.sheet_names), None)
    if ship_sheet:
        try:
            df = pd.read_excel(fpath, sheet_name=ship_sheet, dtype=str)
            df.columns = df.columns.astype(str).str.strip()
            cols = list(df.columns)

            col_cnee    = _find_col(cols, "consignee")
            col_shipper = _find_col(cols, "shipper")
            col_carrier = _find_col(cols, "carrier")
            col_dest    = _find_col(cols, "destination")
            cnee_email_cols    = [c for c in cols if "consignee" in c.lower() and "email" in c.lower()]
            shipper_email_cols = [c for c in cols if "shipper" in c.lower() and "email" in c.lower()]

            for _, row in df.iterrows():
                cnee_name    = _safe_str(row.get(col_cnee, "")) if col_cnee else ""
                shipper_name = _safe_str(row.get(col_shipper, "")) if col_shipper else ""
                carrier      = _safe_str(row.get(col_carrier, "")) if col_carrier else ""
                dest         = _safe_str(row.get(col_dest, "")) if col_dest else ""

                for email in _extract_emails_from_cells(*(row.get(c, "") for c in cnee_email_cols)):
                    records.append(_make_record(
                        email, company=cnee_name, campaign_id=campaign,
                        source_file=fpath.name, record_type="cnee",
                        CARRIER=carrier, DESTINATION=dest,
                    ))

                for email in _extract_emails_from_cells(*(row.get(c, "") for c in shipper_email_cols)):
                    records.append(_make_record(
                        email, company=shipper_name, campaign_id=campaign,
                        source_file=fpath.name, record_type="shipper",
                        CARRIER=carrier, DESTINATION=dest,
                    ))
        except Exception as exc:
            log.warning("Error reading shipment sheet in %s: %s", fpath.name, exc)

    # Contact Info sheet → named contact records
    if "Contact Info" in xls.sheet_names:
        try:
            df_ci = pd.read_excel(fpath, sheet_name="Contact Info", dtype=str)
            df_ci.columns = df_ci.columns.astype(str).str.strip()
            ci_cols = list(df_ci.columns)

            col_email    = _find_col(ci_cols, "email") or _find_col(ci_cols, "ail")
            col_company  = _find_col(ci_cols, "company")
            col_name     = _find_col(ci_cols, "contact name") or _find_col(ci_cols, "name")
            col_position = _find_col(ci_cols, "position")
            col_phone    = _find_col(ci_cols, "phone")

            for _, row in df_ci.iterrows():
                raw_email = _safe_str(row.get(col_email, "")) if col_email else ""
                if not raw_email:
                    continue
                for email in _extract_emails_from_cells(raw_email):
                    records.append(_make_record(
                        email,
                        company=_safe_str(row.get(col_company, "")) if col_company else "",
                        contact_name=_safe_str(row.get(col_name, "")) if col_name else "",
                        position=_safe_str(row.get(col_position, "")) if col_position else "",
                        phone=_safe_str(row.get(col_phone, "")) if col_phone else "",
                        campaign_id=campaign,
                        source_file=fpath.name,
                        record_type="contact",
                    ))
        except Exception as exc:
            log.warning("Error reading Contact Info in %s: %s", fpath.name, exc)

    return records


# ── Source 1: data_*.xlsx (pre-processed) ────────────────────────────────────

def _load_panjiva_data(fpath: Path) -> list[dict]:
    """Load pre-processed data_*.xlsx files (CNEE_NAME, CNEE_EMAIL schema)."""
    records: list[dict] = []
    try:
        df = pd.read_excel(fpath, sheet_name=0, dtype=str)
        df.columns = df.columns.astype(str).str.strip().str.upper()
        cols = list(df.columns)

        col_cnee_email    = _find_col(cols, "CNEE", "EMAIL")
        col_cnee_name     = _find_col(cols, "CNEE", "NAME")
        col_shipper_email = _find_col(cols, "SHIPPER", "EMAIL")
        col_shipper_name  = _find_col(cols, "SHIPPER", "NAME")
        col_campaign      = _find_col(cols, "CMD") or _find_col(cols, "CAMPAIGN")

        for _, row in df.iterrows():
            campaign = _safe_str(row.get(col_campaign, "")) if col_campaign else fpath.stem.upper()

            if col_cnee_email:
                cnee_email = _safe_str(row.get(col_cnee_email, ""))
                if cnee_email and "@" in cnee_email:
                    email, score = validate_email(cnee_email.lower().strip())
                    if score > 0:
                        records.append(_make_record(
                            email,
                            company=_safe_str(row.get(col_cnee_name, "")) if col_cnee_name else "",
                            campaign_id=campaign,
                            source_file=fpath.name,
                            record_type="cnee",
                        ))
                        _stats["emails_cleaned"] += 1

            if col_shipper_email:
                shipper_email = _safe_str(row.get(col_shipper_email, ""))
                if shipper_email and "@" in shipper_email:
                    email, score = validate_email(shipper_email.lower().strip())
                    if score > 0:
                        records.append(_make_record(
                            email,
                            company=_safe_str(row.get(col_shipper_name, "")) if col_shipper_name else "",
                            campaign_id=campaign,
                            source_file=fpath.name,
                            record_type="shipper",
                        ))
                        _stats["emails_cleaned"] += 1

    except Exception as exc:
        log.warning("Error reading %s: %s", fpath.name, exc)

    return records


# ── Source 2: Panjiva LOC files (same structure as panjiva_raw) ───────────────

def _load_data_loc_panjiva(fpath: Path) -> list[dict]:
    """Load LOC files that have Panjiva sheet structure (US Imports Shipments + Contact Info)."""
    # Reuse panjiva_raw loader — same sheet structure
    campaign = fpath.stem.upper().replace(" LOC", "").replace("DATA ", "").replace(" ", "_")
    records = _load_panjiva_raw(fpath)
    # Override campaign_id since _load_panjiva_raw parses from panjiva_raw_ prefix
    for r in records:
        if not r.get("CAMPAIGN_ID"):
            r["CAMPAIGN_ID"] = campaign
    return records


# ── Source 2: DATA USA report.xlsx ───────────────────────────────────────────

def _load_data_usa_report(fpath: Path) -> list[dict]:
    """Load DATA USA report.xlsx — main sheet (10,201 verified) + PROTENTIAL (28 VIP)."""
    records: list[dict] = []
    try:
        xls = pd.ExcelFile(fpath)

        # Main sheet: DATE, COMPANY, EMAIL, STATUS & MODE
        if "DATA CNEE US" in xls.sheet_names:
            df = pd.read_excel(fpath, sheet_name="DATA CNEE US", dtype=str)
            df.columns = df.columns.astype(str).str.strip().str.upper()
            for _, row in df.iterrows():
                raw_email = _safe_str(row.get("EMAIL", ""))
                if not raw_email or "@" not in raw_email:
                    continue
                for email in _extract_emails_from_cells(raw_email):
                    records.append(_make_record(
                        email,
                        company=_safe_str(row.get("COMPANY", "")),
                        campaign_id="USA_VERIFIED",
                        source_file=fpath.name,
                        record_type="cnee",
                        STATUS=_safe_str(row.get("STATUS & MODE", "")),
                    ))
            _stats["data_loc_usa_report"] += len([r for r in records if r["SOURCE_FILE"] == fpath.name])

        # PROTENTIAL sheet: VIP replied contacts (header on row 1)
        if "PROTENTIAL" in xls.sheet_names:
            df_p = pd.read_excel(fpath, sheet_name="PROTENTIAL", header=1, dtype=str)
            df_p.columns = df_p.columns.astype(str).str.strip().str.upper()
            cols = list(df_p.columns)

            col_email   = _find_col(cols, "CONTACT") or _find_col(cols, "EMAIL")
            col_company = _find_col(cols, "COMPANY")
            col_name    = _find_col(cols, "COLUMN1") or _find_col(cols, "NAME")
            col_cmd     = _find_col(cols, "COMMODITY")

            for _, row in df_p.iterrows():
                raw_email = _safe_str(row.get(col_email, "")) if col_email else ""
                if not raw_email or "@" not in raw_email:
                    continue
                for email in _extract_emails_from_cells(raw_email):
                    records.append(_make_record(
                        email,
                        company=_safe_str(row.get(col_company, "")) if col_company else "",
                        contact_name=_safe_str(row.get(col_name, "")) if col_name else "",
                        campaign_id=_safe_str(row.get(col_cmd, "PROTENTIAL")) if col_cmd else "PROTENTIAL",
                        source_file=fpath.name,
                        record_type="protential",
                    ))
            _stats["data_loc_protential"] += len([r for r in records if r.get("RECORD_TYPE") == "protential"])

    except Exception as exc:
        log.warning("Error reading DATA USA report: %s", exc)

    return records


# ── Source 2: Manual Nelson files (CNEE.xlsx / DATA CNEE.xlsx / DATA LỌC.xlsx) ──

def _load_manual_nelson_file(fpath: Path) -> list[dict]:
    """
    Load manual Nelson files with schema:
      STT, DATE, CNEE NAME, EMAIL, PIC, COMMODITY, ROUTING, STATUS
    or:
      STT, COMPANY, EMAIL, PIC
    Reads all sheets, skips sheets with <2 rows or no EMAIL column.
    """
    records: list[dict] = []
    try:
        xls = pd.ExcelFile(fpath)
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(fpath, sheet_name=sheet, dtype=str)
                df.columns = df.columns.astype(str).str.strip().str.upper()
                cols = list(df.columns)

                col_email   = _find_col(cols, "EMAIL")
                col_company = _find_col(cols, "CNEE NAME") or _find_col(cols, "COMPANY")
                col_pic     = _find_col(cols, "PIC")
                col_cmd     = _find_col(cols, "COMMODITY")

                if not col_email:
                    continue

                for _, row in df.iterrows():
                    raw_email = _safe_str(row.get(col_email, ""))
                    if not raw_email or "@" not in raw_email:
                        continue
                    for email in _extract_emails_from_cells(raw_email):
                        records.append(_make_record(
                            email,
                            company=_safe_str(row.get(col_company, "")) if col_company else "",
                            contact_name=_safe_str(row.get(col_pic, "")) if col_pic else "",
                            campaign_id=_safe_str(row.get(col_cmd, "")) if col_cmd else fpath.stem.upper(),
                            source_file=fpath.name,
                            record_type="cnee",
                        ))
            except Exception:
                continue  # skip bad sheets silently

    except Exception as exc:
        log.warning("Error reading %s: %s", fpath.name, exc)

    return records


# ── Source 2: LOC PLASTIC bare 2-column list ──────────────────────────────────

def _load_bare_email_list(fpath: Path, campaign_id: str = "") -> list[dict]:
    """
    Load bare 2-column files: [company_name, email] with no header.
    Detects by checking if first row contains '@'.
    """
    records: list[dict] = []
    try:
        df = pd.read_excel(fpath, sheet_name=0, header=None, dtype=str)
        if df.shape[1] < 2:
            return records

        # Detect email column (whichever column has @)
        email_col = None
        company_col = None
        for c in df.columns:
            sample = df[c].dropna().astype(str)
            if sample.str.contains("@").mean() > 0.3:
                email_col = c
            else:
                company_col = c

        if email_col is None:
            return records

        cid = campaign_id or fpath.stem.upper()
        for _, row in df.iterrows():
            raw_email = _safe_str(row.get(email_col, ""))
            if not raw_email or "@" not in raw_email:
                continue
            for email in _extract_emails_from_cells(raw_email):
                records.append(_make_record(
                    email,
                    company=_safe_str(row.get(company_col, "")) if company_col is not None else "",
                    campaign_id=cid,
                    source_file=fpath.name,
                    record_type="cnee",
                ))

    except Exception as exc:
        log.warning("Error reading bare list %s: %s", fpath.name, exc)

    return records


# ── Source 3: Existing cnee_master.xlsx ──────────────────────────────────────

def _load_existing_cnee_master() -> list[dict]:
    """Load existing cnee_master.xlsx to preserve enriched data."""
    records: list[dict] = []
    if not CNEE_MASTER.exists():
        log.warning("cnee_master.xlsx not found at %s", CNEE_MASTER)
        return records
    try:
        df = pd.read_excel(CNEE_MASTER, dtype=str)
        df.columns = df.columns.astype(str).str.strip().str.upper()
        for _, row in df.iterrows():
            email = _safe_str(row.get("EMAIL", ""))
            if not email or "@" not in email:
                continue
            records.append(_make_record(
                email.lower().strip(),
                company=_safe_str(row.get("COMPANY", "")),
                campaign_id=_safe_str(row.get("CAMPAIGN_ID", "")),
                source_file="cnee_master.xlsx",
                record_type="cnee",
                SEQ_STATUS=_safe_str(row.get("SEQ_STATUS", "")),
                ALREADY_SENT=_safe_str(row.get("ALREADY_SENT", "")),
                LAST_SENT_DATE=_safe_str(row.get("LAST_SENT_DATE", "")),
            ))
        _stats["existing_cnee_master"] = len(records)
    except Exception as exc:
        log.warning("Error reading cnee_master: %s", exc)
    return records


# ── Source 3: email_log.csv send history ─────────────────────────────────────

def load_sent_history() -> set[str]:
    """
    Return set of all emails in the send log (already contacted).
    Used externally by combine_all.py to mark ALREADY_SENT.
    """
    if not EMAIL_LOG.exists():
        return set()
    try:
        df = pd.read_csv(EMAIL_LOG, dtype=str)
        df.columns = df.columns.str.lower().str.strip()
        if "email" not in df.columns:
            return set()
        return set(df["email"].dropna().str.lower().str.strip().unique())
    except Exception as exc:
        log.warning("Error reading email_log: %s", exc)
        return set()


# ── File classifier ───────────────────────────────────────────────────────────

# Files to explicitly skip (internal / system / non-prospect files)
_SKIP_FILES = frozenset([
    "data_from_panjiva_final.xlsx",
    "DATA SHIPPER - NELSON NOV 2024.xlsx",
    "DSKH DATAMYNE NELSON.xlsx",
    "DSKH DATAMYNE NELSON 1.xlsx",
    "DSKH KCN - JUNE 2022 - NELSON.xlsx",
    "DSKH KCN - JUNE 2022.xlsx",
    "DSKH - SALES TEAM - NELSON 100.xlsx",
    "DANH SACH KH – NELSON.xlsx",
])

# Files treated as panjiva LOC (have US Imports + Contact Info sheets)
_PANJIVA_LOC_KEYWORDS = [
    "US Imports Shipments", "US Imports Consignee Shipments",
    "Shipment Destination", "Consignee",
]


def _classify_data_loc_file(fpath: Path) -> str:
    """
    Classify a Data Loc file into processing category.

    Returns: 'panjiva_loc' | 'usa_report' | 'manual_cnee' | 'bare_list' | 'skip'
    """
    name = fpath.name

    if name in _SKIP_FILES:
        return "skip"

    # Check known special files
    if "DATA USA report" in name:
        return "usa_report"
    if name in ("LOC PLASTIC.xlsx",):
        return "bare_list"

    # Probe sheet names
    try:
        xls = pd.ExcelFile(fpath)
        sheets = xls.sheet_names
        if any(s in _PANJIVA_LOC_KEYWORDS for s in sheets):
            return "panjiva_loc"
        # Manual Nelson structure: CNEE sheet or EMAIL column in main sheet
        if any("cnee" in s.lower() or "data" in s.lower() for s in sheets[:3]):
            return "manual_cnee"
    except Exception:
        pass

    return "manual_cnee"  # default attempt


# ── Main collector ────────────────────────────────────────────────────────────

def collect_all(
    include_existing_master: bool = True,
) -> list[dict]:
    """
    Collect all prospect records from all 3 sources.

    Args:
        include_existing_master: Whether to include existing cnee_master.xlsx rows.

    Returns:
        list[dict]: Raw prospect records with unified schema.
                    Not deduplicated — caller should handle dedup.
    """
    all_records: list[dict] = []

    # ── Source 1a: PANJIVA_DIR panjiva_raw_*.xlsx ─────────────────────────────
    log.info("Source 1a: Loading panjiva_raw files from %s", PANJIVA_DIR)
    if PANJIVA_DIR.exists():
        for fpath in sorted(PANJIVA_DIR.glob("panjiva_raw_*.xlsx")):
            recs = _load_panjiva_raw(fpath)
            _stats["panjiva_raw"] += len(recs)
            all_records.extend(recs)
            log.info("  %s → %d records", fpath.name, len(recs))
    else:
        log.warning("PANJIVA_DIR not found: %s", PANJIVA_DIR)

    # ── Source 1b: PANJIVA_DIR data_*.xlsx (pre-processed) ───────────────────
    log.info("Source 1b: Loading panjiva data_ files")
    if PANJIVA_DIR.exists():
        for fpath in sorted(PANJIVA_DIR.glob("data_*.xlsx")):
            if fpath.name == "data_from_panjiva_final.xlsx":
                continue  # Skip aggregated output file
            recs = _load_panjiva_data(fpath)
            _stats["panjiva_data"] += len(recs)
            all_records.extend(recs)
            log.info("  %s → %d records", fpath.name, len(recs))

    # ── Source 2: DATA_LOC_DIR ────────────────────────────────────────────────
    log.info("Source 2: Loading Data Loc files from %s", DATA_LOC_DIR)
    if DATA_LOC_DIR.exists():
        for fpath in sorted(DATA_LOC_DIR.glob("*.xlsx")):
            category = _classify_data_loc_file(fpath)
            if category == "skip":
                log.debug("  SKIP: %s", fpath.name)
                continue

            if category == "panjiva_loc":
                recs = _load_data_loc_panjiva(fpath)
                _stats["data_loc_panjiva"] += len(recs)
            elif category == "usa_report":
                recs = _load_data_usa_report(fpath)
                # stats already updated inside loader
            elif category == "bare_list":
                recs = _load_bare_email_list(fpath)
                _stats["data_loc_manual"] += len(recs)
            else:  # manual_cnee
                recs = _load_manual_nelson_file(fpath)
                _stats["data_loc_manual"] += len(recs)

            all_records.extend(recs)
            log.info("  [%s] %s → %d records", category, fpath.name, len(recs))
    else:
        log.warning("DATA_LOC_DIR not found: %s", DATA_LOC_DIR)

    # ── Source 3: Existing cnee_master.xlsx ───────────────────────────────────
    if include_existing_master:
        log.info("Source 3: Loading existing cnee_master.xlsx")
        recs = _load_existing_cnee_master()
        all_records.extend(recs)
        log.info("  cnee_master.xlsx → %d records", len(recs))

    _stats["total_raw"] = len(all_records)
    _log_summary()

    return all_records


def _log_summary() -> None:
    log.info("")
    log.info("=" * 55)
    log.info("  collect_all_sources — COLLECTION SUMMARY")
    log.info("=" * 55)
    log.info("  Source 1a panjiva_raw         : %d", _stats["panjiva_raw"])
    log.info("  Source 1b panjiva data_        : %d", _stats["panjiva_data"])
    log.info("  Source 2  Data Loc panjiva     : %d", _stats["data_loc_panjiva"])
    log.info("  Source 2  Data Loc manual      : %d", _stats["data_loc_manual"])
    log.info("  Source 2  USA report verified  : %d", _stats["data_loc_usa_report"])
    log.info("  Source 2  PROTENTIAL VIP       : %d", _stats["data_loc_protential"])
    log.info("  Source 3  cnee_master existing : %d", _stats["existing_cnee_master"])
    log.info("  ─────────────────────────────────────────")
    log.info("  TOTAL RAW RECORDS              : %d", _stats["total_raw"])
    log.info("  Emails extracted + cleaned     : %d", _stats["emails_cleaned"])
    log.info("=" * 55)


def get_stats() -> dict[str, int]:
    """Return collection stats dict (read-only copy)."""
    return dict(_stats)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    records = collect_all()
    unique_emails = len({r["EMAIL"] for r in records if r.get("EMAIL")})
    print(f"\nDone. {len(records)} total records, {unique_emails} unique emails.")
