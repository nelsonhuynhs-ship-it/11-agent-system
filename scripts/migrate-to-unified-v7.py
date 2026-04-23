#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
migrate-to-unified-v7.py — Merge v6 master + Panjiva v3 → contact_unified_v7.xlsx
====================================================================================
10-step migration pipeline:
  Step 1  Backup v6 (rotation 14x)
  Step 2  Load v6 (CNEE + SHIPPER sheets)
  Step 3  Parse Panjiva files via panjiva_clean_v3
  Step 4  Dedup within Panjiva batch (multi-file, aggregate commodities)
  Step 5  Add v7 new columns to v6 rows (schema migration)
  Step 6  Match + Enrich existing v6 rows with Panjiva firmographic data
  Step 7  Insert new buyers (not in v6) with TIER=TIER_AUTO_SCORE
  Step 8  Final dedup master by EMAIL
  Step 9  Compute TIER_AUTO_SCORE for all rows
  Step 10 Write 2-sheet XLSX + audit CSV + validate

Public API:
  migrate_v6_to_v7(v6_path, panjiva_files, output_path, dry_run, backup, match_threshold)

CLI:
  python scripts/migrate-to-unified-v7.py --dry-run --panjiva-dir "D:/OneDrive/NelsonData/email/panjiva/"
  python scripts/migrate-to-unified-v7.py --panjiva-dir "D:/OneDrive/NelsonData/email/panjiva/"
  python scripts/migrate-to-unified-v7.py --files file1.xlsx file2.xlsx --match-threshold 85
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
log = logging.getLogger("migrate_v7")

# ── Resolve OneDrive path ─────────────────────────────────────────────────────
try:
    from shared.paths import DATA_DIR, CODE_DIR
    ONEDRIVE_EMAIL = DATA_DIR / "email"
except ImportError:
    ONEDRIVE_EMAIL = Path("D:/OneDrive/NelsonData/email")

# ── Path constants ────────────────────────────────────────────────────────────
V6_DEFAULT       = ONEDRIVE_EMAIL / "contact_unified_v6.xlsx"
V7_DEFAULT       = ONEDRIVE_EMAIL / "contact_unified_v7.xlsx"
BACKUP_DIR       = ONEDRIVE_EMAIL / "backups"
PANJIVA_DIR_DEF  = ONEDRIVE_EMAIL / "panjiva"
PANJIVA_GLOB     = "Panjiva-buyer-*.xlsx"

_RUN_TS = datetime.now().strftime("%Y%m%d_%H%M")
AUDIT_LOG_PATH   = BACKUP_DIR / f"migration_v7_audit_{_RUN_TS}.csv"

# ── Import helpers ────────────────────────────────────────────────────────────
from _migrate_v7_helpers import (
    SCHEMA_V7_COLS,
    LOCKED_COLUMNS,
    LOCKED_IF_TIER,
    V7_NEW_COLS,
    backup_rotation_v7,
    add_v7_columns,
    align_to_v7_schema,
    enrich_row,
    match_panjiva_to_v6,
    build_email_index,
    dedup_panjiva_batch,
    apply_tier_auto_score,
    norm_email,
    valid_email,
)
from scripts.lib.audit_logger import AuditLogger


# ── Step 3: Parse Panjiva files ───────────────────────────────────────────────

def _parse_panjiva_files(panjiva_files: list[Path]) -> pd.DataFrame:
    """Call panjiva_clean_v3 for each file, concat results.

    Graceful: 1 bad file logs error but does NOT crash the migration.
    Returns combined DataFrame (may be empty if all files fail).
    """
    # Lazy import — panjiva_clean_v3 is built by a parallel agent
    try:
        from panjiva_clean_v3 import clean_panjiva_buyer_file, auto_hint_from_filename  # type: ignore[import]
        _has_v3 = True
    except ImportError:
        log.warning("panjiva_clean_v3 not found — Panjiva enrichment step will be skipped.")
        log.warning("Run this migration again once panjiva_clean_v3.py is available.")
        _has_v3 = False

    if not _has_v3 or not panjiva_files:
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    for f in panjiva_files:
        try:
            commodity, country = auto_hint_from_filename(f.name)
            df = clean_panjiva_buyer_file(f, commodity, country)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df["_source_file"] = f.name
                parts.append(df)
                log.info(f"  Parsed {f.name}: {len(df)} buyers")
            else:
                log.warning(f"  {f.name} returned empty DataFrame — skipped")
        except Exception as exc:
            log.error(f"  SKIP {f.name}: {exc}")

    if not parts:
        return pd.DataFrame()

    combined = pd.concat(parts, ignore_index=True)
    log.info(f"Panjiva total: {len(combined)} rows from {len(parts)} file(s)")
    return combined


# ── Step 6+7: Merge Panjiva into v6 master ───────────────────────────────────

def _merge_panjiva_into_master(
    cnee_df: pd.DataFrame,
    panjiva_df: pd.DataFrame,
    audit: AuditLogger,
    match_threshold: int = 85,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Match each Panjiva row to v6, enrich or insert.

    Returns (updated_cnee_df, counts_dict).
    """
    if panjiva_df.empty:
        log.info("No Panjiva data to merge.")
        return cnee_df, {"enriched": 0, "new": 0, "lock_skip": 0, "invalid": 0}

    threshold_f = match_threshold / 100.0
    email_index, domain_index = build_email_index(cnee_df)
    new_rows: list[dict] = []
    counts = {"enriched": 0, "new": 0, "lock_skip": 0, "invalid": 0}

    for _, prow in panjiva_df.iterrows():
        prow_dict = prow.to_dict()
        em = norm_email(prow_dict.get("EMAIL", "") or "")

        if not valid_email(em):
            counts["invalid"] += 1
            audit.log("SKIP", email=em, company=prow_dict.get("COMPANY", ""),
                      reason="INVALID_EMAIL")
            continue

        v6_idx, match_type = match_panjiva_to_v6(
            prow_dict, cnee_df, email_index, domain_index, threshold_f
        )

        if v6_idx is not None:
            # Enrich existing row
            existing_row = cnee_df.loc[v6_idx]
            updated_row, changed_cols = enrich_row(existing_row, prow)

            if changed_cols:
                cnee_df.loc[v6_idx] = updated_row
                counts["enriched"] += 1
                audit.log(
                    "UPDATE",
                    email=em,
                    company=str(existing_row.get("COMPANY", "")),
                    changed_cols=changed_cols,
                    reason=f"ENRICH_{match_type}",
                )
            else:
                counts["lock_skip"] += 1
                audit.log(
                    "SKIP",
                    email=em,
                    company=str(existing_row.get("COMPANY", "")),
                    reason=f"NO_CHANGE_{match_type}",
                )
        else:
            # Insert new buyer
            new_entry: dict = {col: "" for col in SCHEMA_V7_COLS}
            for col, val in prow_dict.items():
                if col in new_entry:
                    new_entry[col] = val

            new_entry["EMAIL"]         = em
            new_entry["EMAIL_STATUS"]  = "NEW"
            new_entry["SEND_COUNT"]    = "0"
            new_entry["SEND_COUNT_EMAIL"] = "0"
            new_entry["SEND_COUNT_WA"] = "0"
            new_entry["SEND_COUNT_LI"] = "0"
            new_entry["ACTIVATE_GATE"] = "ACTIVE"
            new_entry["SHEET"]         = "CNEE"
            new_entry["IMPORT_DATE"]   = datetime.now().strftime("%Y-%m-%d")
            # TIER will be set in Step 9 (TIER_AUTO_SCORE)
            new_entry["TIER"]          = ""

            new_rows.append(new_entry)
            counts["new"] += 1
            audit.log("NEW", email=em, company=prow_dict.get("COMPANY", ""),
                      reason="NO_MATCH")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        # Align to v7 schema before concat
        for col in SCHEMA_V7_COLS:
            if col not in new_df.columns:
                new_df[col] = ""
        new_df = new_df[[c for c in SCHEMA_V7_COLS if c in new_df.columns]]
        cnee_df = pd.concat([cnee_df, new_df], ignore_index=True)

    log.info(
        f"Merge result: {counts['enriched']} enriched, {counts['new']} new, "
        f"{counts['lock_skip']} lock-skip, {counts['invalid']} invalid email"
    )
    return cnee_df, counts


# ── Step 8: Final dedup ───────────────────────────────────────────────────────

def _dedup_by_email(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    """Dedup by EMAIL, keeping row with highest SEND_COUNT + TIER priority."""
    if df.empty:
        return df

    df = df.copy()
    df["_em_norm"] = df["EMAIL"].apply(norm_email)
    valid_mask = df["_em_norm"].str.contains("@", na=False)
    df = df[valid_mask]

    def _score(row: pd.Series) -> int:
        s = 0
        try:
            s += int(str(row.get("SEND_COUNT", 0) or 0))
        except (ValueError, TypeError):
            pass
        if str(row.get("REPLY_STATUS", "") or "").strip():
            s += 1000
        tier = str(row.get("TIER", "") or "").upper()
        if tier in ("CUSTOMER", "VIP"):
            s += 5000
        return s

    dupe_before = len(df) - df["_em_norm"].nunique()
    if dupe_before > 0:
        df["_score"] = df.apply(_score, axis=1)
        df = df.sort_values("_score", ascending=False)
        df = df.drop_duplicates(subset=["_em_norm"], keep="first")
        df.drop(columns=["_score"], inplace=True)
        log.info(f"Final dedup {sheet}: removed {dupe_before} duplicates")

    df.drop(columns=["_em_norm"], errors="ignore", inplace=True)
    return df.reset_index(drop=True)


# ── Write 2-sheet XLSX ────────────────────────────────────────────────────────

def _write_two_sheet(cnee_df: pd.DataFrame, shipper_df: pd.DataFrame, path: Path) -> None:
    """Write atomically: write to .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    try:
        from email_engine.core.xlsx_lock import xlsx_write_lock
        with xlsx_write_lock(path):
            with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
                cnee_df.to_excel(writer, sheet_name="CNEE", index=False)
                shipper_df.to_excel(writer, sheet_name="SHIPPER", index=False)
            tmp.replace(path)
    except ImportError:
        # xlsx_lock not available — write directly (safe in dry-run context)
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            cnee_df.to_excel(writer, sheet_name="CNEE", index=False)
            shipper_df.to_excel(writer, sheet_name="SHIPPER", index=False)
        tmp.replace(path)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def migrate_v6_to_v7(
    v6_path: Path = V6_DEFAULT,
    panjiva_files: Optional[list[Path]] = None,
    output_path: Path = V7_DEFAULT,
    dry_run: bool = False,
    backup: bool = True,
    match_threshold: int = 85,
) -> dict:
    """Main migration entry point.

    Returns report dict:
    {
        "v6_rows_loaded": int,
        "panjiva_files_parsed": int,
        "panjiva_buyers_total": int,
        "matched_to_v6_enriched": int,
        "new_buyers_inserted": int,
        "locked_rows_skipped_update": int,
        "output_path": str,
        "backup_path": str,
        "audit_csv_path": str,
    }
    """
    log.info("=" * 64)
    log.info(f"  MIGRATE TO UNIFIED V7  {'[DRY RUN]' if dry_run else '[WRITE]'}")
    log.info("=" * 64)

    audit = AuditLogger.dry_run_logger() if dry_run else AuditLogger(AUDIT_LOG_PATH)
    report: dict = {
        "dry_run": dry_run,
        "v6_rows_loaded": 0,
        "panjiva_files_parsed": 0,
        "panjiva_buyers_total": 0,
        "matched_to_v6_enriched": 0,
        "new_buyers_inserted": 0,
        "locked_rows_skipped_update": 0,
        "output_path": str(output_path),
        "backup_path": "",
        "audit_csv_path": str(AUDIT_LOG_PATH) if not dry_run else "DRY_RUN",
        "error": None,
    }

    try:
        # ── Step 1: Backup ────────────────────────────────────────────────────
        log.info("Step 1: Backup v6")
        backup_path = None
        if backup and not dry_run and v6_path.exists():
            backup_path = backup_rotation_v7(v6_path, BACKUP_DIR)
            log.info(f"  Backup: {backup_path}")
        report["backup_path"] = str(backup_path) if backup_path else ""

        # ── Step 2: Load v6 ───────────────────────────────────────────────────
        log.info(f"Step 2: Load v6 from {v6_path}")
        if not v6_path.exists():
            raise FileNotFoundError(f"v6 master not found: {v6_path}")

        cnee_df = pd.read_excel(v6_path, sheet_name="CNEE", dtype=str).fillna("")
        try:
            shipper_df = pd.read_excel(v6_path, sheet_name="SHIPPER", dtype=str).fillna("")
        except Exception:
            log.warning("  SHIPPER sheet not found in v6 — creating empty")
            shipper_df = pd.DataFrame()

        report["v6_rows_loaded"] = len(cnee_df)
        log.info(f"  CNEE: {len(cnee_df)} rows, SHIPPER: {len(shipper_df)} rows")

        # ── Step 3: Parse Panjiva files ───────────────────────────────────────
        log.info("Step 3: Parse Panjiva v3 files")
        panjiva_files = panjiva_files or []
        report["panjiva_files_parsed"] = len(panjiva_files)

        panjiva_raw = _parse_panjiva_files(panjiva_files)
        report["panjiva_buyers_total"] = len(panjiva_raw)
        log.info(f"  Panjiva buyers (raw): {len(panjiva_raw)}")

        # ── Step 4: Dedup Panjiva batch ───────────────────────────────────────
        log.info("Step 4: Dedup within Panjiva batch")
        if not panjiva_raw.empty:
            before = len(panjiva_raw)
            panjiva_deduped = dedup_panjiva_batch(panjiva_raw)
            log.info(f"  Panjiva dedup: {before} → {len(panjiva_deduped)} rows")
        else:
            panjiva_deduped = panjiva_raw

        # ── Step 5: Schema migration v6 → v7 ─────────────────────────────────
        log.info("Step 5: Migrate v6 schema → v7 (add 15 new cols)")
        cnee_df = add_v7_columns(cnee_df)
        if not shipper_df.empty:
            shipper_df = add_v7_columns(shipper_df)
        log.info(f"  v7 schema: {len(SCHEMA_V7_COLS)} cols total ({len(V7_NEW_COLS)} new)")

        # ── Step 6+7: Match, enrich, insert ──────────────────────────────────
        log.info("Step 6-7: Match Panjiva → v6, enrich existing, insert new")
        cnee_df, merge_counts = _merge_panjiva_into_master(
            cnee_df, panjiva_deduped, audit, match_threshold
        )
        report["matched_to_v6_enriched"]    = merge_counts["enriched"]
        report["new_buyers_inserted"]        = merge_counts["new"]
        report["locked_rows_skipped_update"] = merge_counts["lock_skip"]

        # ── Step 8: Final dedup ───────────────────────────────────────────────
        log.info("Step 8: Final dedup master by EMAIL")
        cnee_df = _dedup_by_email(cnee_df, "CNEE")
        log.info(f"  CNEE after dedup: {len(cnee_df)} rows")

        # ── Step 9: Compute TIER_AUTO_SCORE ──────────────────────────────────
        log.info("Step 9: Compute TIER_AUTO_SCORE")
        cnee_df = apply_tier_auto_score(cnee_df)
        if not shipper_df.empty:
            shipper_df = apply_tier_auto_score(shipper_df)

        # ── Align both sheets to v7 schema ────────────────────────────────────
        cnee_out    = align_to_v7_schema(cnee_df,    sheet="CNEE")
        shipper_out = align_to_v7_schema(shipper_df, sheet="SHIPPER") if not shipper_df.empty \
                      else pd.DataFrame(columns=SCHEMA_V7_COLS)

        log.info(f"  Final CNEE: {len(cnee_out)} rows | SHIPPER: {len(shipper_out)} rows")

        # ── Step 10: Write output ─────────────────────────────────────────────
        log.info("Step 10: Write output + audit log")
        if not dry_run:
            _write_two_sheet(cnee_out, shipper_out, output_path)
            log.info(f"  Saved: {output_path}")

            # Validate data contracts
            try:
                import subprocess
                result_proc = subprocess.run(
                    [sys.executable, str(_REPO_ROOT / "scripts" / "validate-data-contracts.py")],
                    capture_output=True, text=True, timeout=60,
                )
                if result_proc.returncode != 0:
                    log.warning(f"Validation warnings:\n{result_proc.stdout}")
                else:
                    log.info("  Data contract validation: PASS")
            except Exception as vex:
                log.warning(f"  Validation skipped: {vex}")
        else:
            log.info("  DRY RUN — no files written")

        audit.close()
        audit_counts = audit.summary()
        report["audit"] = audit_counts

    except Exception as exc:
        log.exception(f"Migration failed: {exc}")
        report["error"] = str(exc)
        try:
            audit.close()
        except Exception:
            pass

    return report


# ── CLI ────────────────────────────────────────────────────────────────────────

def _find_panjiva_files(panjiva_dir: Path) -> list[Path]:
    """Auto-scan directory for Panjiva-buyer-*.xlsx files."""
    files = sorted(panjiva_dir.glob(PANJIVA_GLOB))
    if not files:
        log.warning(f"No '{PANJIVA_GLOB}' files found in {panjiva_dir}")
    else:
        log.info(f"Found {len(files)} Panjiva file(s) in {panjiva_dir}:")
        for f in files:
            log.info(f"  {f.name}")
    return files


def _print_report(report: dict) -> None:
    print("\n" + "=" * 64)
    print("  MIGRATION V7 REPORT")
    print("=" * 64)
    print(f"  Dry run                 : {report['dry_run']}")
    print(f"  v6 rows loaded          : {report['v6_rows_loaded']}")
    print(f"  Panjiva files parsed    : {report['panjiva_files_parsed']}")
    print(f"  Panjiva buyers (raw)    : {report['panjiva_buyers_total']}")
    print(f"  Enriched existing rows  : {report['matched_to_v6_enriched']}")
    print(f"  New buyers inserted     : {report['new_buyers_inserted']}")
    print(f"  Lock-skip (no change)   : {report['locked_rows_skipped_update']}")
    print(f"  Output path             : {report['output_path']}")
    print(f"  Backup path             : {report['backup_path'] or '(none)'}")
    print(f"  Audit CSV               : {report['audit_csv_path']}")
    if report.get("audit"):
        print("\n  Audit action counts:")
        for action, cnt in report["audit"].items():
            print(f"    {action:<10} {cnt}")
    if report.get("error"):
        print(f"\n  ERROR: {report['error']}")
    print("=" * 64)
    status = "Migration complete." if not report["dry_run"] else "Dry run complete — no files written."
    print(f"  {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate contact_unified_v6.xlsx + Panjiva v3 → contact_unified_v7.xlsx"
    )
    parser.add_argument(
        "--v6-path", default=str(V6_DEFAULT),
        help="Path to contact_unified_v6.xlsx"
    )
    parser.add_argument(
        "--output", default=str(V7_DEFAULT),
        help="Output path for contact_unified_v7.xlsx"
    )
    parser.add_argument(
        "--panjiva-dir", default=None,
        help="Directory to auto-scan for Panjiva-buyer-*.xlsx files"
    )
    parser.add_argument(
        "--files", nargs="+", default=None,
        help="Explicit list of Panjiva .xlsx files to process"
    )
    parser.add_argument(
        "--match-threshold", type=int, default=85,
        help="Fuzzy company match threshold 0-100 (default: 85)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview only — no files written"
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip backup rotation"
    )
    args = parser.parse_args()

    # Resolve Panjiva files
    panjiva_files: list[Path] = []
    if args.files:
        panjiva_files = [Path(f) for f in args.files]
        missing = [f for f in panjiva_files if not f.exists()]
        if missing:
            for m in missing:
                log.error(f"File not found: {m}")
            sys.exit(1)
    elif args.panjiva_dir:
        panjiva_files = _find_panjiva_files(Path(args.panjiva_dir))

    result = migrate_v6_to_v7(
        v6_path=Path(args.v6_path),
        panjiva_files=panjiva_files if panjiva_files else None,
        output_path=Path(args.output),
        dry_run=args.dry_run,
        backup=not args.no_backup,
        match_threshold=args.match_threshold,
    )

    _print_report(result)
    sys.exit(1 if result.get("error") else 0)
