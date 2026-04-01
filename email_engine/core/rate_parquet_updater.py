# -*- coding: utf-8 -*-
"""
rate_parquet_updater.py — FAK Rate File Auto-Importer
=====================================================
Watches the "incoming" folder for new FAK rate files (Excel/CSV),
normalises them into the Cleaned_Master_History.parquet schema,
appends new rows, and removes duplicates.

Expected FAK file columns (flexible mapping):
  POL, POD, Place, Carrier, Container_Type, Amount, Charge_Name, Eff, Exp

Run manually:
    python core/rate_parquet_updater.py

Scheduled:  called by Claude task "rate-parquet-updater" daily at 07:30

Output:
  Logs to logs/rate_updater.log
  Updates: ../Pricing_Engine/data/Cleaned_Master_History.parquet
"""
from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent           # email_engine/core/
PROJECT_ROOT  = BASE_DIR.parent                 # email_engine/
ENGINE_TEST   = PROJECT_ROOT.parent             # Engine_test/
PARQUET_FILE  = ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
INCOMING_DIR  = ENGINE_TEST / "Pricing_Engine" / "data" / "incoming"
PROCESSED_DIR = ENGINE_TEST / "Pricing_Engine" / "data" / "processed"
LOG_FILE      = PROJECT_ROOT / "logs" / "rate_updater.log"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("rate_updater")


# ── Column normaliser ─────────────────────────────────────────────────────────
# Maps common FAK column name variants → canonical Parquet schema names
COLUMN_MAP = {
    # POL
    "pol":              "POL",
    "port_of_loading":  "POL",
    "loading_port":     "POL",
    "origin":           "POL",
    # POD
    "pod":              "POD",
    "port_of_discharge":"POD",
    "discharge_port":   "POD",
    "destination_port": "POD",
    # Place
    "place":            "Place",
    "place_of_delivery":"Place",
    "delivery_place":   "Place",
    "city":             "Place",
    # Carrier
    "carrier":          "Carrier",
    "scac":             "Carrier",
    "shipping_line":    "Carrier",
    "line":             "Carrier",
    # Container type
    "container_type":   "Container_Type",
    "type":             "Container_Type",
    "equipment":        "Container_Type",
    "cont_type":        "Container_Type",
    # Amount / Rate
    "amount":           "Amount",
    "rate":             "Amount",
    "freight":          "Amount",
    "ocean_freight":    "Amount",
    "price":            "Amount",
    # Charge name
    "charge_name":      "Charge_Name",
    "charge":           "Charge_Name",
    "fee_name":         "Charge_Name",
    # Dates
    "eff":              "Eff",
    "effective":        "Eff",
    "eff_date":         "Eff",
    "valid_from":       "Eff",
    "validfrom":        "Eff",
    "effective_date":   "Eff",
    "exp":              "Exp",
    "expiry":           "Exp",
    "exp_date":         "Exp",
    "valid_to":         "Exp",
    "validto":          "Exp",
    "expiry_date":      "Exp",
    "expiration":       "Exp",
    # Note / Remark
    "note":             "Note",
    "remark":           "Note",
    "remarks":          "Note",
}

REQUIRED_COLS = ["POL", "POD", "Carrier", "Container_Type", "Amount", "Charge_Name"]


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical schema using COLUMN_MAP."""
    rename = {}
    for col in df.columns:
        canonical = COLUMN_MAP.get(col.strip().lower().replace(" ", "_"))
        if canonical:
            rename[col] = canonical
    df = df.rename(columns=rename)
    return df


def _read_fak_file(path: Path) -> pd.DataFrame | None:
    """Read a FAK rate file (Excel or CSV) and return normalised DataFrame."""
    try:
        if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, dtype=str)
        elif path.suffix.lower() in (".csv",):
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        else:
            log.warning("Unsupported file type: %s", path.name)
            return None

        df = _normalise_columns(df)
        df.columns = df.columns.str.strip()

        # Check required columns exist
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            log.warning("File %s missing columns: %s", path.name, missing)
            log.warning("Available columns: %s", list(df.columns))
            return None

        # Coerce Amount to numeric
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df = df.dropna(subset=["Amount"])

        # Standardise container types → canonical names
        ct_map = {
            "40HC": "40HQ", "40HG": "40HQ", "40HH": "40HQ",
            "40DC": "40HQ",
            "20DC": "20GP", "20": "20GP",
        }
        if "Container_Type" in df.columns:
            df["Container_Type"] = (
                df["Container_Type"].str.strip().str.upper()
                .replace(ct_map)
            )

        # Coerce date columns
        for date_col in ("Eff", "Exp"):
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        # Add source metadata
        df["_source_file"] = path.name
        df["_imported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log.info("  Read %d rows from %s", len(df), path.name)
        return df

    except Exception as e:
        log.error("Error reading %s: %s", path.name, e)
        return None


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate rate rows.
    Key: POL + POD + Carrier + Container_Type + Charge_Name + Exp
    Keep the row with the lowest Amount (best rate).
    """
    dedup_key = ["POL", "POD", "Carrier", "Container_Type", "Charge_Name", "Exp"]
    present_keys = [k for k in dedup_key if k in df.columns]
    if not present_keys:
        return df
    df = df.sort_values("Amount", ascending=True)
    df = df.drop_duplicates(subset=present_keys, keep="first")
    return df


def run_update() -> dict:
    """
    Main update pipeline:
    1. Scan INCOMING_DIR for new FAK files
    2. Read + normalise each file
    3. Load existing Parquet
    4. Append new rows, dedup, save

    Returns summary dict.
    """
    summary = {
        "files_found":   0,
        "files_ok":      0,
        "rows_added":    0,
        "rows_total":    0,
        "parquet_exists": PARQUET_FILE.exists(),
        "errors":        [],
    }

    # ── 1. Scan incoming folder ────────────────────────────────────────────────
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    fak_files = sorted(
        INCOMING_DIR.glob("*.xlsx"),
        key=lambda f: f.stat().st_mtime,
    ) + sorted(
        INCOMING_DIR.glob("*.xls"),
        key=lambda f: f.stat().st_mtime,
    ) + sorted(
        INCOMING_DIR.glob("*.csv"),
        key=lambda f: f.stat().st_mtime,
    )

    summary["files_found"] = len(fak_files)

    if not fak_files:
        log.info("[Updater] No new files in %s — nothing to do.", INCOMING_DIR)
        return summary

    log.info("[Updater] Found %d file(s) in incoming/", len(fak_files))

    # ── 2. Read each file ──────────────────────────────────────────────────────
    new_frames = []
    for f in fak_files:
        log.info("  Processing: %s", f.name)
        df_new = _read_fak_file(f)
        if df_new is not None:
            new_frames.append(df_new)
            summary["files_ok"] += 1
        else:
            summary["errors"].append(f.name)

    if not new_frames:
        log.warning("[Updater] No valid data extracted from any file.")
        return summary

    df_incoming = pd.concat(new_frames, ignore_index=True)
    log.info("[Updater] Total new rows from incoming: %d", len(df_incoming))

    # ── 3. Load existing Parquet ───────────────────────────────────────────────
    if PARQUET_FILE.exists():
        df_existing = pd.read_parquet(PARQUET_FILE)
        log.info("[Updater] Existing Parquet: %d rows", len(df_existing))
    else:
        log.warning("[Updater] Parquet not found — will create new: %s", PARQUET_FILE)
        PARQUET_FILE.parent.mkdir(parents=True, exist_ok=True)
        df_existing = pd.DataFrame()

    # ── 4. Append + deduplicate ────────────────────────────────────────────────
    df_combined = pd.concat([df_existing, df_incoming], ignore_index=True)
    rows_before = len(df_combined)
    df_combined = _dedup(df_combined)
    rows_after  = len(df_combined)
    summary["rows_added"] = len(df_incoming)
    summary["rows_total"] = rows_after

    log.info("[Updater] After dedup: %d → %d rows (-%d duplicates)",
             rows_before, rows_after, rows_before - rows_after)

    # ── 5. Save back to Parquet ────────────────────────────────────────────────
    # Backup first
    if PARQUET_FILE.exists():
        backup = PARQUET_FILE.with_suffix(
            f".bak_{datetime.now():%Y%m%d_%H%M}.parquet")
        shutil.copy2(PARQUET_FILE, backup)
        log.info("[Updater] Backup saved: %s", backup.name)

    df_combined.to_parquet(PARQUET_FILE, index=False, compression="snappy")
    log.info("[Updater] Parquet updated: %s (%d rows)", PARQUET_FILE, rows_after)

    # ── 6. Move processed files ────────────────────────────────────────────────
    for f in fak_files:
        if f.name not in summary["errors"]:
            dest = PROCESSED_DIR / f"{datetime.now():%Y%m%d_%H%M}_{f.name}"
            shutil.move(str(f), str(dest))
            log.info("[Updater] Moved to processed: %s", dest.name)

    return summary


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 60)
    log.info("  Nelson Rate Parquet Updater — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("  Parquet: %s", PARQUET_FILE)
    log.info("  Incoming: %s", INCOMING_DIR)
    log.info("=" * 60)

    # ── Diagnostic: print current Parquet columns ────────────────────────────
    if PARQUET_FILE.exists():
        df_check = pd.read_parquet(PARQUET_FILE)
        log.info("Current Parquet columns: %s", list(df_check.columns))
        log.info("Current Parquet rows: %d", len(df_check))
        date_cols = [c for c in df_check.columns
                     if any(k in c.lower() for k in ("eff", "exp", "valid", "date"))]
        log.info("Date-related columns: %s", date_cols if date_cols else "NONE FOUND")
        # Sample a few rows to show data quality
        if not df_check.empty:
            log.info("Sample row:\n%s", df_check.iloc[0].to_dict())
    else:
        log.warning("Parquet file does not exist yet: %s", PARQUET_FILE)

    result = run_update()

    log.info("-" * 40)
    log.info("Summary:")
    log.info("  Files found:  %d", result["files_found"])
    log.info("  Files OK:     %d", result["files_ok"])
    log.info("  Rows added:   %d", result["rows_added"])
    log.info("  Total rows:   %d", result["rows_total"])
    if result["errors"]:
        log.warning("  Errors:       %s", result["errors"])
    log.info("=" * 60)
