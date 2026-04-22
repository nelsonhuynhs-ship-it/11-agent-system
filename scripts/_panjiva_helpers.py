# -*- coding: utf-8 -*-
"""
scripts/_panjiva_helpers.py — Shared helpers for migrate-to-unified-v6.py
=========================================================================
Extracted to keep migrate script under 200 lines.
Contains: schema definition, backup rotation, dedup logic, priority lock.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── 5-col LOCK definition ─────────────────────────────────────────────────────
# These columns are NEVER overwritten when updating an existing row.
PRIORITY_LOCK_COLS = {
    "EMAIL_STATUS",
    "SEND_COUNT",
    "LAST_SENT_DATE",
    "REPLY_STATUS",
    # TIER only locked if value is CUSTOMER or VIP
}
TIER_LOCK_VALUES = {"CUSTOMER", "VIP"}

# ── Target 35-col schema (CNEE sheet) ─────────────────────────────────────────
# SHIPPER sheet uses same schema + ACTIVATE_GATE overridden to HOLD.
SCHEMA_V6_COLS = [
    # Identity
    "EMAIL",            # primary key per sheet (lowercase/trim)
    "EMAIL_ALT1",
    "EMAIL_ALT2",
    "COMPANY",
    "PIC",              # person in charge / contact name
    "GREETING",
    "POSITION",
    # Phone
    "PHONE_PRIMARY",
    "PHONE_ALT1",
    "PHONE_ALT2",
    "WHATSAPP",
    # Social
    "LINKEDIN_URL",
    # Geography
    "POL",
    "DESTINATION",
    "STATE",
    "COUNTRY",
    "TIMEZONE",
    "DESTINATION_REGION",
    "ORIGIN_COUNTRY",
    # Freight
    "CARRIER",
    "COMMODITY_CATEGORY",
    "TOTAL_SHIPMENT",
    # Campaign
    "CAMPAIGN_ID",
    "TIER",
    "PRIORITY_SCORE",
    "EMAIL_QUALITY_SCORE",
    "ACTION",
    # Status (5-col LOCK)
    "EMAIL_STATUS",
    "SEND_COUNT",
    "LAST_SENT_DATE",
    "SEQ_STEP",
    "SEQ_STATUS",
    "REPLY_STATUS",
    # Channel
    "WA_STATUS",
    "LI_STATUS",
    "ACTIVATE_GATE",    # CNEE=ACTIVE / SHIPPER=HOLD
    # Meta
    "SOURCE_TAG",
    "IMPORT_DATE",
    "REPLACEMENT_FOR",
    "VN_TEAM_OVERLAP_FLAG",
    # Internal (not persisted in v6 master, used by pipeline only)
    # "SHEET" — excluded from saved schema
]

# Deduplicated list preserving order
_seen: set = set()
SCHEMA_V6_COLS = [c for c in SCHEMA_V6_COLS if not (_seen.add(c) or c in _seen - {c})]


def is_priority_row(row: pd.Series) -> bool:
    """Return True if row has production data that must never be overwritten."""
    send_count = str(row.get("SEND_COUNT", "") or "").strip()
    reply_status = str(row.get("REPLY_STATUS", "") or "").strip()
    tier = str(row.get("TIER", "") or "").strip().upper()
    try:
        if int(send_count) > 0:
            return True
    except (ValueError, TypeError):
        pass
    if reply_status and reply_status.upper() not in ("", "NONE", "NULL", "NAN"):
        return True
    if tier in TIER_LOCK_VALUES:
        return True
    return False


def apply_priority_lock(existing_row: pd.Series, new_row: pd.Series) -> pd.Series:
    """Merge new_row into existing_row, protecting locked cols.

    Returns updated row (copy of existing with non-locked cols from new_row).
    Also locks TIER when existing value is CUSTOMER/VIP.
    """
    updated = existing_row.copy()
    for col in new_row.index:
        if col in PRIORITY_LOCK_COLS:
            continue  # never overwrite lock cols
        if col == "TIER":
            existing_tier = str(existing_row.get("TIER", "") or "").strip().upper()
            if existing_tier in TIER_LOCK_VALUES:
                continue  # keep CUSTOMER/VIP tier
        new_val = new_row.get(col)
        if new_val is not None and str(new_val).strip() not in ("", "nan", "NaN"):
            updated[col] = new_val
    return updated


def align_to_schema(df: pd.DataFrame, sheet: str = "CNEE") -> pd.DataFrame:
    """Ensure DataFrame has all v6 schema cols in order.

    Missing cols filled with "". Extra cols dropped.
    """
    for col in SCHEMA_V6_COLS:
        if col not in df.columns:
            df[col] = ""

    # Set ACTIVATE_GATE default
    if "ACTIVATE_GATE" in df.columns:
        default_gate = "HOLD" if sheet == "SHIPPER" else "ACTIVE"
        df["ACTIVATE_GATE"] = df["ACTIVATE_GATE"].replace("", default_gate)

    return df[SCHEMA_V6_COLS].copy()


# ── Backup rotation ────────────────────────────────────────────────────────────

MAX_BACKUPS = 14


def backup_rotation(target_file: Path, backup_dir: Path) -> Optional[Path]:
    """Copy target_file to backup_dir with timestamp suffix; keep last 14 copies.

    Returns path of new backup, or None if target_file does not exist.
    """
    if not target_file.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup_name = f"contact_unified_v6.backup_{ts}.xlsx"
    backup_path = backup_dir / backup_name
    shutil.copy2(target_file, backup_path)

    # Prune old backups — keep newest MAX_BACKUPS
    all_backups = sorted(
        backup_dir.glob("contact_unified_v6.backup_*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in all_backups[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)

    return backup_path


# ── Email normalization ───────────────────────────────────────────────────────

def norm_email(email: str) -> str:
    return (email or "").lower().strip()


def valid_email(email: str) -> bool:
    em = norm_email(email)
    return bool(em and "@" in em and "." in em.split("@", 1)[1])


# ── Old master schema → v6 schema column rename map ──────────────────────────

# Maps old cnee_master_v2_final.xlsx columns → v6 schema column names.
RENAME_MAP_V5_TO_V6: dict[str, str] = {
    "EMAIL":             "EMAIL",
    "COMPANY":           "COMPANY",
    "PIC":               "PIC",
    "GREETING":          "GREETING",
    "PHONE":             "PHONE_PRIMARY",
    "POSITION":          "POSITION",
    "POL":               "POL",
    "DESTINATION":       "DESTINATION",
    "CARRIER":           "CARRIER",
    "TOTAL_SHIPMENT":    "TOTAL_SHIPMENT",
    "CAMPAIGN_ID":       "CAMPAIGN_ID",
    "EMAIL_QUALITY_SCORE": "EMAIL_QUALITY_SCORE",
    "PRIORITY_SCORE":    "PRIORITY_SCORE",
    "TIER":              "TIER",
    "ACTION":            "ACTION",
    "REPLY_STATUS":      "REPLY_STATUS",
    "SEND_COUNT":        "SEND_COUNT",
    "LAST_SENT_DATE":    "LAST_SENT_DATE",
    "SEQ_STEP":          "SEQ_STEP",
    "SEQ_STATUS":        "SEQ_STATUS",
    "SOURCE_FILE":       "SOURCE_TAG",
    "COMMODITY_CATEGORY": "COMMODITY_CATEGORY",
    "ORIGIN_COUNTRY":    "ORIGIN_COUNTRY",
    "DESTINATION_REGION": "DESTINATION_REGION",
    "HS_CODE_PRIMARY":   "SOURCE_TAG",  # discard, put in SOURCE_TAG as tag
    "EMAIL_STATUS":      "EMAIL_STATUS",
    "STATE":             "STATE",
}


def load_existing_master(path: Path) -> pd.DataFrame:
    """Load old cnee_master_v2_final.xlsx, rename cols to v6 schema."""
    df = pd.read_excel(path, dtype=str).fillna("")

    # Apply rename where columns match known map
    rename = {k: v for k, v in RENAME_MAP_V5_TO_V6.items() if k in df.columns and k != v}
    if rename:
        df = df.rename(columns=rename)

    # Mark sheet type
    df["SHEET"] = "CNEE"

    return df
