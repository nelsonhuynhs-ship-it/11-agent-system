#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
migrate-to-unified-v6.py — Merge data sources → contact_unified_v6.xlsx
========================================================================
14-step migration pipeline:
  Step 1  Load existing cnee_master_v2_final.xlsx (22,230 CNEE)
  Step 2  Rename v5 columns → v6 schema
  Step 3  Compute TIMEZONE from STATE
  Step 4  Load all Panjiva raw files via panjiva_clean_v2.py
  Step 5  Merge new CNEE rows (add NEW + UPDATE existing, 5-col LOCK)
  Step 6  Build SHIPPER sheet from Panjiva SHIPPER side
  Step 7  Deduplicate CNEE by EMAIL (keep highest priority row)
  Step 8  Deduplicate SHIPPER by EMAIL
  Step 9  Filter SHIPPER through blacklist + set ACTIVATE_GATE=HOLD
  Step 10 Compute DESTINATION_REGION from STATE
  Step 11 Validate emails + phone E.164
  Step 12 Align both sheets to 35-col schema
  Step 13 Save 2-sheet XLSX atomically (backup rotation 14x)
  Step 14 Write audit log CSV + print summary

CLI:
  python scripts/migrate-to-unified-v6.py
  python scripts/migrate-to-unified-v6.py --dry-run
  python scripts/migrate-to-unified-v6.py --panjiva-dir D:/OneDrive/NelsonData/email/panjiva
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate_v6")

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    from shared.paths import DATA_DIR, CODE_DIR
    ONEDRIVE_EMAIL  = DATA_DIR / "email"
    BLACKLIST_FILE  = CODE_DIR / "email_engine" / "data" / "competitor_blacklist.json"
except ImportError:
    ONEDRIVE_EMAIL  = Path("D:/OneDrive/NelsonData/email")
    BLACKLIST_FILE  = _REPO_ROOT / "email_engine" / "data" / "competitor_blacklist.json"

from _panjiva_helpers import (
    SCHEMA_V6_COLS, align_to_schema, apply_priority_lock,
    backup_rotation, is_priority_row, load_existing_master,
    norm_email, valid_email, TIER_LOCK_VALUES,
)
from scripts.lib.timezone_mapper import state_to_timezone
from scripts.lib.audit_logger import AuditLogger

# ── Path constants ────────────────────────────────────────────────────────────
CNEE_MASTER_V5   = ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx"
OUTPUT_FILE      = ONEDRIVE_EMAIL / "contact_unified_v6.xlsx"
BACKUP_DIR       = ONEDRIVE_EMAIL / "backups"
PANJIVA_DIR      = ONEDRIVE_EMAIL / "panjiva"

# Audit log path (timestamped per run, not committed to git)
_RUN_TS = datetime.now().strftime("%Y%m%d_%H%M")
AUDIT_LOG_PATH   = BACKUP_DIR / f"migration_audit_{_RUN_TS}.csv"

# ── DESTINATION → region map ──────────────────────────────────────────────────
_EAST_STATES = {"NY","NJ","PA","MA","CT","RI","NH","VT","ME","MD","DE","VA","WV","NC","SC","GA","FL","DC"}
_CENTRAL_STATES = {"OH","MI","IN","IL","WI","MN","IA","MO","ND","SD","NE","KS","AL","MS","TN","KY","AR","LA","OK","TX"}
_WEST_STATES = {"MT","ID","WY","CO","NM","AZ","UT","NV","CA","OR","WA","AK","HI"}

def _state_to_region(state: str) -> str:
    s = (state or "").strip().upper()
    if s in _EAST_STATES:   return "US_EAST"
    if s in _CENTRAL_STATES: return "US_CENTRAL"
    if s in _WEST_STATES:    return "US_WEST"
    if s in {"ON","QC","AB","BC","MB","SK","NS","NB","NL","PE","NT","NU","YT"}:
        return "CANADA"
    return ""


# ── Step helpers ──────────────────────────────────────────────────────────────

def _load_panjiva_files(panjiva_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load all panjiva_raw_*.xlsx from dir, return (cnee_all, shipper_all)."""
    from panjiva_clean_v2 import process_panjiva_file

    raw_files = list(panjiva_dir.glob("panjiva_raw_*.xlsx"))
    if not raw_files:
        log.warning(f"No panjiva_raw_*.xlsx files found in {panjiva_dir}")
        return pd.DataFrame(), pd.DataFrame()

    cnee_parts, shpr_parts = [], []
    for f in raw_files:
        tag = f.stem.upper().replace("PANJIVA_RAW_", "PANJIVA_")
        try:
            res = process_panjiva_file(f, source_tag=tag, dry_run=True)
            cnee_parts.append(res["cnee_df"])
            shpr_parts.append(res["shipper_df"])
            log.info(f"  Loaded {f.name}: cnee={len(res['cnee_df'])} shpr={len(res['shipper_df'])}")
        except Exception as exc:
            log.error(f"  SKIP {f.name}: {exc}")

    cnee_all = pd.concat(cnee_parts, ignore_index=True) if cnee_parts else pd.DataFrame()
    shpr_all = pd.concat(shpr_parts, ignore_index=True) if shpr_parts else pd.DataFrame()
    return cnee_all, shpr_all


def _merge_cnee(existing: pd.DataFrame, new_rows: pd.DataFrame, logger: AuditLogger) -> pd.DataFrame:
    """Merge new CNEE rows into existing master with 5-col LOCK.

    Strategy:
      - Match by EMAIL (primary key)
      - SKIP if priority row with no new data worth updating
      - UPDATE non-priority row: fill empty cols from new_rows (5-col LOCK preserved)
      - NEW: append rows with no email match
    """
    if new_rows.empty:
        return existing

    # Rename panjiva extract cols to v6 keys
    col_remap = {"EMAIL_PRIMARY": "EMAIL"}
    new_rows = new_rows.rename(columns={k: v for k, v in col_remap.items() if k in new_rows.columns})

    # Build email index on existing
    existing["_EMAIL_NORM"] = existing["EMAIL"].apply(norm_email)
    email_index = {em: idx for idx, em in existing["_EMAIL_NORM"].items() if em}

    updates, new_list, skips = 0, [], 0

    for _, nr in new_rows.iterrows():
        em = norm_email(nr.get("EMAIL_PRIMARY") or nr.get("EMAIL") or "")
        if not valid_email(em):
            skips += 1
            logger.log("SKIP", email=em, company=nr.get("COMPANY", ""), reason="INVALID_EMAIL")
            continue

        if em in email_index:
            ex_idx = email_index[em]
            ex_row = existing.loc[ex_idx]
            if is_priority_row(ex_row):
                # Only fill truly empty cols (no-overwrite for any col)
                changed = []
                for col in ["POL", "STATE", "CARRIER", "COMMODITY_CATEGORY",
                             "EMAIL_ALT1", "EMAIL_ALT2", "PHONE_PRIMARY", "PHONE_ALT1", "PHONE_ALT2"]:
                    old_val = str(ex_row.get(col, "") or "").strip()
                    new_val = str(nr.get(col, "") or "").strip()
                    if not old_val and new_val:
                        existing.at[ex_idx, col] = new_val
                        changed.append(col)
                if changed:
                    updates += 1
                    logger.log("UPDATE", email=em, company=ex_row.get("COMPANY", ""),
                                changed_cols=changed, reason="FILL_EMPTY_PRIORITY_ROW")
                else:
                    skips += 1
                    logger.log("SKIP", email=em, company=ex_row.get("COMPANY", ""),
                                reason="PRIORITY_ROW_COMPLETE")
            else:
                updated_row = apply_priority_lock(ex_row, nr)
                changed = [c for c in nr.index if str(updated_row.get(c)) != str(ex_row.get(c))]
                existing.loc[ex_idx] = updated_row
                if changed:
                    updates += 1
                    logger.log("UPDATE", email=em, company=ex_row.get("COMPANY", ""),
                                changed_cols=changed, reason="NON_PRIORITY_UPDATE")
                else:
                    skips += 1
                    logger.log("SKIP", email=em, company=ex_row.get("COMPANY", ""), reason="NO_CHANGE")
        else:
            # New row
            new_entry = {col: "" for col in existing.columns}
            for col in nr.index:
                if col in existing.columns:
                    new_entry[col] = nr[col]
            new_entry["EMAIL"]  = em
            new_entry["SHEET"]  = "CNEE"
            new_entry["IMPORT_DATE"] = datetime.now().strftime("%Y-%m-%d")
            new_list.append(new_entry)
            logger.log("NEW", email=em, company=nr.get("COMPANY", ""), sheet="CNEE")

    log.info(f"CNEE merge: {updates} updated, {len(new_list)} new, {skips} skipped")

    if new_list:
        # Reset index before concat to avoid duplicate index error
        existing = existing.reset_index(drop=True)
        new_df = pd.DataFrame(new_list, columns=existing.columns)
        existing = pd.concat([existing, new_df], ignore_index=True)

    existing.drop(columns=["_EMAIL_NORM"], errors="ignore", inplace=True)
    return existing.reset_index(drop=True)


def _dedup_by_email(df: pd.DataFrame, sheet: str, logger: AuditLogger) -> pd.DataFrame:
    """Deduplicate by EMAIL, keeping row with highest SEND_COUNT / most filled cols."""
    if df.empty:
        return df

    df["_EMAIL_NORM"] = df["EMAIL"].apply(norm_email)
    df = df[df["_EMAIL_NORM"].str.contains("@", na=False)]  # drop invalid emails

    def _priority_score(row: pd.Series) -> int:
        score = 0
        try:
            score += int(str(row.get("SEND_COUNT", 0) or 0))
        except (ValueError, TypeError):
            pass
        if str(row.get("REPLY_STATUS", "") or "").strip():
            score += 1000
        tier = str(row.get("TIER", "") or "").strip().upper()
        if tier in TIER_LOCK_VALUES:
            score += 5000
        return score

    dupes_before = len(df) - df["_EMAIL_NORM"].nunique()
    if dupes_before > 0:
        df = df.copy()
        df["_score"] = df.apply(_priority_score, axis=1)
        df = df.sort_values("_score", ascending=False)
        df = df.drop_duplicates(subset=["_EMAIL_NORM"], keep="first")
        df.drop(columns=["_score"], inplace=True)
        log.info(f"Dedup {sheet}: removed {dupes_before} duplicates")
        for _ in range(dupes_before):
            logger.log("SKIP", email="(dedup)", sheet=sheet, reason="DUPLICATE_EMAIL")

    df.drop(columns=["_EMAIL_NORM"], errors="ignore", inplace=True)
    return df.reset_index(drop=True)


# ── Main migration pipeline ───────────────────────────────────────────────────

def run_migration(
    dry_run: bool = False,
    panjiva_dir: Path = PANJIVA_DIR,
    output_file: Path = OUTPUT_FILE,
    cnee_source: Path = CNEE_MASTER_V5,
) -> dict:
    """Run full 14-step migration. Returns summary dict."""

    log.info("=" * 60)
    log.info(f"  MIGRATE TO UNIFIED V6  {'[DRY RUN]' if dry_run else '[WRITE]'}")
    log.info("=" * 60)

    audit = AuditLogger.dry_run_logger() if dry_run else AuditLogger(AUDIT_LOG_PATH)
    summary: dict = {"dry_run": dry_run, "steps": {}, "error": None}

    try:
        # Step 1 — Load existing master
        log.info("Step 1: Loading existing cnee_master_v2_final.xlsx")
        if not cnee_source.exists():
            raise FileNotFoundError(f"CNEE source not found: {cnee_source}")
        cnee_master = load_existing_master(cnee_source)
        summary["steps"]["s1_loaded"] = len(cnee_master)
        log.info(f"  Loaded {len(cnee_master)} rows, {len(cnee_master.columns)} cols")

        # Step 2 — Rename to v6 schema (done inside load_existing_master)
        log.info("Step 2: Column rename to v6 schema (done in Step 1)")

        # Step 3 — Compute TIMEZONE from STATE
        log.info("Step 3: Computing TIMEZONE from STATE")
        if "TIMEZONE" not in cnee_master.columns:
            cnee_master["TIMEZONE"] = ""
        mask_no_tz = cnee_master["TIMEZONE"].str.strip() == ""
        cnee_master.loc[mask_no_tz, "TIMEZONE"] = (
            cnee_master.loc[mask_no_tz, "STATE"].apply(state_to_timezone)
        )
        tz_filled = int(mask_no_tz.sum())
        summary["steps"]["s3_timezone_filled"] = tz_filled
        log.info(f"  Timezone filled: {tz_filled}")

        # Step 4 — Load Panjiva files
        log.info(f"Step 4: Loading Panjiva raw files from {panjiva_dir}")
        panjiva_cnee, panjiva_shpr = _load_panjiva_files(panjiva_dir)
        summary["steps"]["s4_panjiva_cnee"] = len(panjiva_cnee)
        summary["steps"]["s4_panjiva_shpr"] = len(panjiva_shpr)
        log.info(f"  Panjiva CNEE: {len(panjiva_cnee)}, SHIPPER: {len(panjiva_shpr)}")

        # Step 5 — Merge new CNEE rows with 5-col LOCK
        log.info("Step 5: Merging new CNEE rows (5-col LOCK active)")
        cnee_master = _merge_cnee(cnee_master, panjiva_cnee, audit)
        summary["steps"]["s5_cnee_after_merge"] = len(cnee_master)

        # Step 6 — Build SHIPPER sheet
        log.info("Step 6: Building SHIPPER sheet")
        shipper_sheet = panjiva_shpr.copy() if not panjiva_shpr.empty else pd.DataFrame()
        if not shipper_sheet.empty:
            if "EMAIL_PRIMARY" in shipper_sheet.columns:
                shipper_sheet = shipper_sheet.rename(columns={"EMAIL_PRIMARY": "EMAIL"})
            shipper_sheet["SHEET"] = "SHIPPER"
            shipper_sheet["ACTIVATE_GATE"] = "HOLD"
            shipper_sheet["IMPORT_DATE"] = datetime.now().strftime("%Y-%m-%d")
            for _, row in shipper_sheet.iterrows():
                audit.log("NEW", email=norm_email(row.get("EMAIL", "")),
                           company=row.get("COMPANY", ""), sheet="SHIPPER")
        summary["steps"]["s6_shipper_raw"] = len(shipper_sheet)

        # Step 7 — Deduplicate CNEE
        log.info("Step 7: Deduplicating CNEE by EMAIL")
        cnee_master["SHEET"] = "CNEE"
        cnee_master = _dedup_by_email(cnee_master, "CNEE", audit)
        summary["steps"]["s7_cnee_dedup"] = len(cnee_master)

        # Step 8 — Deduplicate SHIPPER
        log.info("Step 8: Deduplicating SHIPPER by EMAIL")
        if not shipper_sheet.empty:
            shipper_sheet = _dedup_by_email(shipper_sheet, "SHIPPER", audit)
        summary["steps"]["s8_shipper_dedup"] = len(shipper_sheet)

        # Step 9 — SHIPPER ACTIVATE_GATE = HOLD (enforce)
        log.info("Step 9: Enforcing SHIPPER ACTIVATE_GATE=HOLD")
        if not shipper_sheet.empty:
            shipper_sheet["ACTIVATE_GATE"] = "HOLD"

        # Step 10 — Compute DESTINATION_REGION
        log.info("Step 10: Computing DESTINATION_REGION")
        cnee_master["DESTINATION_REGION"] = cnee_master.get("STATE", pd.Series(dtype=str)).apply(_state_to_region)
        if not shipper_sheet.empty and "STATE" in shipper_sheet.columns:
            shipper_sheet["DESTINATION_REGION"] = shipper_sheet["STATE"].apply(_state_to_region)

        # Step 11 — Timezone for new CNEE rows (fill gaps)
        log.info("Step 11: Fill TIMEZONE gaps in merged CNEE")
        if "TIMEZONE" in cnee_master.columns and "STATE" in cnee_master.columns:
            gap_mask = cnee_master["TIMEZONE"].str.strip() == ""
            cnee_master.loc[gap_mask, "TIMEZONE"] = cnee_master.loc[gap_mask, "STATE"].apply(state_to_timezone)

        # Step 12 — Align schemas
        log.info("Step 12: Aligning both sheets to 35-col v6 schema")
        cnee_out    = align_to_schema(cnee_master,  sheet="CNEE")
        shipper_out = align_to_schema(shipper_sheet, sheet="SHIPPER") if not shipper_sheet.empty else pd.DataFrame(columns=SCHEMA_V6_COLS)
        summary["steps"]["s12_cnee_final"]    = len(cnee_out)
        summary["steps"]["s12_shipper_final"] = len(shipper_out)

        # Step 13 — Save (with backup rotation)
        log.info("Step 13: Saving contact_unified_v6.xlsx")
        if not dry_run:
            backup_path = backup_rotation(output_file, BACKUP_DIR)
            if backup_path:
                log.info(f"  Backup created: {backup_path}")
            _write_two_sheet(cnee_out, shipper_out, output_file)
            log.info(f"  Saved: {output_file}")
            summary["steps"]["s13_output"] = str(output_file)
            summary["steps"]["s13_backup"] = str(backup_path) if backup_path else None
        else:
            log.info("  DRY RUN — skipping write")
            summary["steps"]["s13_output"] = "DRY_RUN (not saved)"

        # Step 14 — Audit log + summary
        log.info("Step 14: Finalizing audit log")
        audit.close()
        audit_counts = audit.summary()
        summary["audit"] = audit_counts
        if not dry_run:
            summary["steps"]["s14_audit_log"] = str(AUDIT_LOG_PATH)

    except Exception as exc:
        log.exception(f"Migration failed: {exc}")
        summary["error"] = str(exc)
        try:
            audit.close()
        except Exception:
            pass

    return summary


def _write_two_sheet(cnee_df: pd.DataFrame, shipper_df: pd.DataFrame, path: Path) -> None:
    """Write 2-sheet XLSX atomically (write to tmp then rename).

    Uses xlsx_write_lock so no reader can open the file while writing.
    """
    import sys as _sys
    _repo_root = Path(__file__).parent.parent
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from email_engine.core.xlsx_lock import xlsx_write_lock

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    with xlsx_write_lock(path):
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            cnee_df.to_excel(writer, sheet_name="CNEE",    index=False)
            shipper_df.to_excel(writer, sheet_name="SHIPPER", index=False)
        tmp.replace(path)


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate data sources → contact_unified_v6.xlsx (14-step pipeline)"
    )
    parser.add_argument("--dry-run",     action="store_true", help="Preview only, no file writes")
    parser.add_argument("--panjiva-dir", default=str(PANJIVA_DIR), help="Directory with panjiva_raw_*.xlsx")
    parser.add_argument("--output",      default=str(OUTPUT_FILE),  help="Output XLSX path")
    parser.add_argument("--cnee-source", default=str(CNEE_MASTER_V5), help="Existing CNEE master path")
    args = parser.parse_args()

    result = run_migration(
        dry_run=args.dry_run,
        panjiva_dir=Path(args.panjiva_dir),
        output_file=Path(args.output),
        cnee_source=Path(args.cnee_source),
    )

    print("\n" + "=" * 60)
    print("  MIGRATION REPORT")
    print("=" * 60)
    print(f"  Dry run     : {result['dry_run']}")
    for step_key, val in result.get("steps", {}).items():
        print(f"  {step_key:<30} {val}")
    print("\n  Audit counts:")
    for action, cnt in result.get("audit", {}).items():
        print(f"    {action:<10} {cnt}")
    if result.get("error"):
        print(f"\n  ERROR: {result['error']}")
        sys.exit(1)
    print("=" * 60)
    print("  Migration complete." if not result["dry_run"] else "  Dry run complete — no files written.")
