#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_cnee_add_status_state.py
=================================
Adds EMAIL_STATUS and STATE columns to cnee_master_v2_final.xlsx.

EMAIL_STATUS : default empty string (clean / not yet classified)
STATE        : 2-letter US state code parsed from DESTINATION column.
               e.g. "Port Of Boston, Boston, Massachusetts" -> "MA"
               Unknown / non-US -> empty string.

Usage:
    python scripts/migrate_cnee_add_status_state.py            # dry-run first
    python scripts/migrate_cnee_add_status_state.py --write    # actually write
    python scripts/migrate_cnee_add_status_state.py --dry-run  # explicit dry-run
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate_cnee")

# ── Target file ──────────────────────────────────────────────────────────────
CNEE_PATH = Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")

# ── US state name → USPS 2-letter code mapping ───────────────────────────────
_STATE_MAP: dict[str, str] = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
    "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
    "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
    "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
    "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND",
    "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY",
    # DC + territories
    "DISTRICT OF COLUMBIA": "DC", "WASHINGTON DC": "DC",
    "PUERTO RICO": "PR", "GUAM": "GU",
    # Already 2-letter codes (pass-through)
    "AL": "AL", "AK": "AK", "AZ": "AZ", "AR": "AR", "CA": "CA",
    "CO": "CO", "CT": "CT", "DE": "DE", "FL": "FL", "GA": "GA",
    "HI": "HI", "ID": "ID", "IL": "IL", "IN": "IN", "IA": "IA",
    "KS": "KS", "KY": "KY", "LA": "LA", "ME": "ME", "MD": "MD",
    "MA": "MA", "MI": "MI", "MN": "MN", "MS": "MS", "MO": "MO",
    "MT": "MT", "NE": "NE", "NV": "NV", "NH": "NH", "NJ": "NJ",
    "NM": "NM", "NY": "NY", "NC": "NC", "ND": "ND", "OH": "OH",
    "OK": "OK", "OR": "OR", "PA": "PA", "RI": "RI", "SC": "SC",
    "SD": "SD", "TN": "TN", "TX": "TX", "UT": "UT", "VT": "VT",
    "VA": "VA", "WA": "WA", "WV": "WV", "WI": "WI", "WY": "WY",
    "DC": "DC", "PR": "PR", "GU": "GU",
    # Canadian provinces (for Canada destinations)
    "BRITISH COLUMBIA": "BC", "ALBERTA": "AB", "ONTARIO": "ON",
    "QUEBEC": "QC", "NOVA SCOTIA": "NS", "NEW BRUNSWICK": "NB",
    "MANITOBA": "MB", "SASKATCHEWAN": "SK",
}

# City → state fallback (common US port cities)
_CITY_TO_STATE: dict[str, str] = {
    "LOS ANGELES": "CA", "LONG BEACH": "CA", "SAN FRANCISCO": "CA",
    "OAKLAND": "CA", "SAN JOSE": "CA", "SAN DIEGO": "CA", "FRESNO": "CA",
    "SEATTLE": "WA", "TACOMA": "WA", "SPOKANE": "WA",
    "PORTLAND": "OR",
    "NEW YORK": "NY", "NEWARK": "NJ", "BROOKLYN": "NY", "BRONX": "NY",
    "BUFFALO": "NY",
    "CHICAGO": "IL", "ROCKFORD": "IL", "AURORA": "IL",
    "HOUSTON": "TX", "DALLAS": "TX", "SAN ANTONIO": "TX", "AUSTIN": "TX",
    "FORT WORTH": "TX", "EL PASO": "TX",
    "MIAMI": "FL", "JACKSONVILLE": "FL", "TAMPA": "FL", "ORLANDO": "FL",
    "SAVANNAH": "GA", "ATLANTA": "GA",
    "CHARLESTON": "SC",
    "NORFOLK": "VA", "VIRGINIA BEACH": "VA", "RICHMOND": "VA",
    "BALTIMORE": "MD",
    "PHILADELPHIA": "PA", "PITTSBURGH": "PA",
    "BOSTON": "MA",
    "MEMPHIS": "TN", "NASHVILLE": "TN",
    "DETROIT": "MI", "GRAND RAPIDS": "MI",
    "COLUMBUS": "OH", "CLEVELAND": "OH", "CINCINNATI": "OH",
    "INDIANAPOLIS": "IN",
    "MINNEAPOLIS": "MN",
    "KANSAS CITY": "MO", "ST LOUIS": "MO",
    "NEW ORLEANS": "LA",
    "MOBILE": "AL", "BIRMINGHAM": "AL",
    "DENVER": "CO",
    "PHOENIX": "AZ", "TUCSON": "AZ",
    "LAS VEGAS": "NV",
    "SALT LAKE CITY": "UT",
    "OMAHA": "NE",
    "LOUISVILLE": "KY",
    "HARTFORD": "CT",
    "VANCOUVER": "BC", "MONTREAL": "QC", "TORONTO": "ON", "HALIFAX": "NS",
}


def parse_state(destination: str) -> str:
    """Extract US/CA 2-letter state code from DESTINATION text.

    Tries tokens right-to-left (last token is usually state name in
    'City, State, Country' format from Panjiva).

    Returns '' if cannot determine.
    """
    if not destination or str(destination).strip().lower() in ("", "nan", "none"):
        return ""

    dest = str(destination).strip().upper()

    # Split on comma or semicolon, try from rightmost token first
    tokens = [t.strip() for t in dest.replace(";", ",").split(",") if t.strip()]

    for tok in reversed(tokens):
        # Direct state code (2-letter)
        code = _STATE_MAP.get(tok)
        if code:
            return code

    # Try whole tokens as city names
    for tok in reversed(tokens):
        code = _CITY_TO_STATE.get(tok)
        if code:
            return code

    # Substring scan: look for state name within any token
    for tok in reversed(tokens):
        for state_name, code in _STATE_MAP.items():
            if len(state_name) > 2 and state_name in tok:
                return code

    return ""


def run_migration(dry_run: bool = True) -> dict:
    """Main migration logic.

    Returns stats dict: {total, email_status_added, state_added, state_filled}.
    """
    import pandas as pd

    if not CNEE_PATH.exists():
        log.error("File not found: %s", CNEE_PATH)
        sys.exit(1)

    log.info("Reading %s ...", CNEE_PATH)
    df = pd.read_excel(CNEE_PATH, engine="openpyxl")
    df.columns = df.columns.str.strip()  # preserve original case for display

    total = len(df)
    log.info("Loaded %d rows, %d columns: %s", total, len(df.columns), list(df.columns))

    # Normalise column lookup (case-insensitive check)
    cols_upper = {c.upper(): c for c in df.columns}

    # ── Add EMAIL_STATUS ──────────────────────────────────────────────────────
    email_status_col = cols_upper.get("EMAIL_STATUS")
    if email_status_col:
        log.info("EMAIL_STATUS column already exists (%s) — skipping add", email_status_col)
        email_status_added = 0
    else:
        df["EMAIL_STATUS"] = ""
        email_status_added = total
        log.info("Added EMAIL_STATUS column (default ''). Rows: %d", total)

    # ── Add STATE ─────────────────────────────────────────────────────────────
    state_col = cols_upper.get("STATE")
    dest_col = cols_upper.get("DESTINATION")

    if state_col:
        log.info("STATE column already exists (%s) — will fill blank cells only", state_col)
        state_added = 0
    else:
        df["STATE"] = ""
        state_added = total
        log.info("Added STATE column. Rows: %d", total)
        state_col = "STATE"
        dest_col = dest_col or cols_upper.get("DESTINATION")

    # Fill STATE values from DESTINATION
    state_filled = 0
    if dest_col:
        dest_series = df[dest_col].astype(str)
        # Only fill rows where STATE is currently empty
        mask_empty = df["STATE"].astype(str).str.strip().isin(["", "nan", "none"])
        for idx in df.index[mask_empty]:
            val = parse_state(dest_series.at[idx])
            if val:
                df.at[idx, "STATE"] = val
                state_filled += 1
    else:
        log.warning("DESTINATION column not found — STATE column will remain empty")

    log.info("STATE filled: %d / %d rows", state_filled, total)

    # State distribution
    state_dist = df["STATE"].value_counts().head(10).to_dict()
    log.info("Top 10 states: %s", state_dist)

    if dry_run:
        log.info("[DRY RUN] No changes written to disk.")
        log.info("  EMAIL_STATUS col added: %d rows", email_status_added)
        log.info("  STATE col added: %d rows", state_added)
        log.info("  STATE values filled: %d rows", state_filled)
        return {
            "dry_run": True,
            "total": total,
            "email_status_added": email_status_added,
            "state_added": state_added,
            "state_filled": state_filled,
            "top_states": state_dist,
        }

    # ── Backup ────────────────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = CNEE_PATH.with_name(
        f"cnee_master_v2_final.backup_{date_str}.xlsx"
    )
    log.info("Creating backup: %s", backup_path.name)
    shutil.copy2(CNEE_PATH, backup_path)
    log.info("Backup saved: %s", backup_path)

    # ── Atomic write ─────────────────────────────────────────────────────────
    tmp = CNEE_PATH.with_suffix(".xlsx.tmp")
    log.info("Writing to temp file: %s", tmp)
    df.to_excel(tmp, index=False, engine="openpyxl")

    import os
    os.replace(tmp, CNEE_PATH)
    log.info("Atomic replace done: %s", CNEE_PATH.name)

    log.info("Migration complete. EMAIL_STATUS added: %d, STATE filled: %d / %d",
             email_status_added, state_filled, total)

    return {
        "dry_run": False,
        "total": total,
        "email_status_added": email_status_added,
        "state_added": state_added,
        "state_filled": state_filled,
        "top_states": state_dist,
        "backup": str(backup_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate cnee_master_v2_final.xlsx")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="Actually write changes (default: dry-run)")
    group.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="Dry-run only (default behavior)")
    args = parser.parse_args()

    is_dry_run = not args.write
    result = run_migration(dry_run=is_dry_run)
    print("\n--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
