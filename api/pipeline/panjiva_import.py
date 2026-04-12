"""
panjiva_import.py — Auto-import pipeline for Panjiva CSV/Excel files.
Watch incoming dir → clean → blacklist → dedup → score → segment → merge.
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .blacklist import apply_blacklist
from .email_cleaner import clean_panjiva_email

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
INCOMING_DIR = DATA_DIR / "email" / "panjiva" / "incoming"
PROCESSED_DIR = DATA_DIR / "email" / "panjiva" / "processed"
MASTER_FILE = DATA_DIR / "email" / "cnee_master_v2_final.xlsx"

# Panjiva raw column mappings (handle both schema variants)
_COL_MAP = {
    "Consignee": "COMPANY",
    "Consignee Email 1": "EMAIL",
    "Consignee Email 2": "EMAIL_2",
    "Consignee Email 3": "EMAIL_3",
    "Consignee Phone 1": "PHONE",
    "Consignee Phone 2": "PHONE_2",
    "Consignee Phone 3": "PHONE_3",
    "Shipper": "SHIPPER_NAME",
    "Shipper Email 1": "SHIPPER_EMAIL",
    "Carrier": "CARRIER",
    "Shipment Origin": "POL",
    "Place of Receipt": "POL_ALT",
    "Shipment Destination": "DESTINATION",
    "Shipment Destination Region": "DESTINATION_REGION",
    "CNEE_NAME": "COMPANY",
    "CNEE_EMAIL": "EMAIL",
    "CNEE_PIC": "PIC",
    "POL": "POL",
}

# Campaign assignment by commodity keyword
_CAMPAIGN_MAP = {
    "furniture": "FURNITURE",
    "candle": "CANDLE",
    "plywood": "PLYWOOD",
    "frozen": "FROZEN",
    "plastic": "PLASTIC",
    "flooring": "FLOORING",
    "food": "FOODSTUFF",
    "rubber": "RUBBER",
    "lch": "LCH",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map Panjiva raw columns to standard schema."""
    rename = {}
    for raw_col, std_col in _COL_MAP.items():
        if raw_col in df.columns and std_col not in df.columns:
            rename[raw_col] = std_col
    return df.rename(columns=rename)


def _guess_campaign(filename: str, df: pd.DataFrame) -> str:
    """Guess campaign from filename or commodity data."""
    fn = filename.lower()
    for keyword, campaign in _CAMPAIGN_MAP.items():
        if keyword in fn:
            return campaign
    if "CMD_NAME" in df.columns:
        top = df["CMD_NAME"].mode()
        if len(top) > 0:
            return str(top.iloc[0]).upper()
    return "GENERAL"


def import_panjiva_file(filepath: str) -> dict:
    """
    Import a single Panjiva file through the full pipeline.

    Returns dict with stats: total, cleaned, blacklisted, deduped, imported.
    """
    fp = Path(filepath)
    stats = {"file": fp.name, "timestamp": datetime.now().isoformat()}

    # Read file
    if fp.suffix == ".csv":
        df = pd.read_csv(fp)
    elif fp.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(fp)
    else:
        return {**stats, "error": f"Unsupported format: {fp.suffix}"}

    stats["total_rows"] = len(df)

    # Normalize columns
    df = _normalize_columns(df)

    # Clean emails
    if "EMAIL" in df.columns:
        df["EMAIL"] = df["EMAIL"].apply(clean_panjiva_email)
        df = df.dropna(subset=["EMAIL"])
    stats["after_email_clean"] = len(df)

    # Clean secondary emails
    for col in ["EMAIL_2", "EMAIL_3"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_panjiva_email)

    # Apply blacklist
    if "EMAIL" in df.columns:
        df = apply_blacklist(df, email_col="EMAIL", company_col="COMPANY")
        blacklisted = (df.get("ACTION") == "BLACKLISTED").sum()
        df = df[df.get("ACTION") != "BLACKLISTED"]
        stats["blacklisted"] = int(blacklisted)

    # Dedup against existing master
    if MASTER_FILE.exists():
        master = pd.read_excel(MASTER_FILE)
        existing_emails = set(master["EMAIL"].str.lower().dropna())
        before_dedup = len(df)
        df = df[~df["EMAIL"].str.lower().isin(existing_emails)]
        stats["duplicates_removed"] = before_dedup - len(df)
    else:
        stats["duplicates_removed"] = 0

    stats["new_leads"] = len(df)

    if len(df) == 0:
        _move_processed(fp)
        return {**stats, "imported": 0, "message": "No new leads after cleanup"}

    # Score and segment
    campaign = _guess_campaign(fp.name, df)
    df["CAMPAIGN_ID"] = campaign
    df["EMAIL_QUALITY_SCORE"] = 100
    df["PRIORITY_SCORE"] = 50
    df["TIER"] = "WARM_B"
    df["ACTION"] = "SEND_NOW"
    df["REPLY_STATUS"] = "NO_REPLY"
    df["SEND_COUNT"] = 0
    df["SEQ_STEP"] = 0
    df["SEQ_STATUS"] = "ACTIVE"
    df["SOURCE_FILE"] = fp.name
    df["IMPORTED_AT"] = datetime.now().isoformat()

    # Merge into master
    if MASTER_FILE.exists():
        master = pd.read_excel(MASTER_FILE)
        # Align columns
        for col in master.columns:
            if col not in df.columns:
                df[col] = None
        df = df[[c for c in master.columns if c in df.columns]]
        combined = pd.concat([master, df], ignore_index=True)
    else:
        combined = df

    combined.to_excel(MASTER_FILE, index=False)
    stats["imported"] = len(df)

    # Move to processed
    _move_processed(fp)

    return stats


def _move_processed(fp: Path):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    dest = PROCESSED_DIR / f"{ts}_{fp.name}"
    shutil.move(str(fp), str(dest))


def scan_incoming() -> list[dict]:
    """Scan incoming dir and import all new files."""
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in sorted(INCOMING_DIR.iterdir()):
        if f.suffix in (".csv", ".xlsx", ".xls") and not f.name.startswith("."):
            print(f"Importing: {f.name}")
            result = import_panjiva_file(str(f))
            results.append(result)
            print(f"  → {result.get('imported', 0)} new leads, {result.get('blacklisted', 0)} blacklisted")
    return results
