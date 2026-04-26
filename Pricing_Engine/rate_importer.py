# -*- coding: utf-8 -*-
"""
rate_importer.py — Semi-Automated Rate Import from Pricing Emails
====================================================================
Scans Outlook for pricing emails from Harry Duong (pricing@pudongprime.vn),
downloads Excel attachments, classifies them, and runs the master_loader
pipeline to update the Parquet rate database.

TRIGGER: User clicks button / calls API endpoint (not automatic).

Usage:
    from rate_importer import run_full_import
    result = run_full_import(days=3)

    # Or from command line:
    python rate_importer.py --days 3
    python rate_importer.py --days 7 --type FAK
    python rate_importer.py --scan-only        # just list emails, no download
"""
import gc
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
from typing import Optional

import pandas as pd

# Setup logging
log = logging.getLogger("nelson.rate_importer")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s",
                        datefmt="%H:%M:%S")

# ── Paths (via shared.paths — OneDrive data) ─────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
_repo_root = str(SCRIPT_DIR.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

DATA_DIR = sp.PRICING_DATA
INCOMING_DIR = DATA_DIR / "incoming"
PROCESSED_DIR = DATA_DIR / "processed"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
PARQUET_FILE = sp.PARQUET_FILE
RATE_TABLES_DIR = DATA_DIR / "rate-tables"

def _find_puc_file() -> Path:
    """Auto-detect latest PUC file (PUC_SOC.xlsx or PUC {MONTH} {YEAR}.xlsx).

    Unified 2026-04-12: drops new PUC file into processed/ alongside FAK/SCFI/FIX
    (one folder for all rate files). Search order:
      1. processed/        (new canonical location)
      2. rate-tables/      (legacy fallback — being phased out)
      3. DATA_DIR root     (for PUC_SOC.xlsx legacy layout)
    Sorted by modification time — newest wins.
    """
    legacy = DATA_DIR / "PUC_SOC.xlsx"
    if legacy.exists():
        return legacy
    candidates = []
    for d in [PROCESSED_DIR, RATE_TABLES_DIR, DATA_DIR]:
        if d.exists():
            candidates.extend(d.glob("PUC*.xlsx"))
    candidates = [f for f in candidates if "PUC_SOC" not in f.name]
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    if candidates:
        log.info("Auto-detected PUC file: %s (from %s)", candidates[0].name, candidates[0].parent.name)
        return candidates[0]
    return legacy  # fallback even if missing

PUC_SOC_FILE = _find_puc_file()

# Related system paths
ERP_REFRESH_SCRIPT = sp.CODE_DIR / "ERP" / "core" / "refresh.py"
TELEGRAM_CONFIG = sp.BOT_CODE / "config.py"

# Ensure dirs exist
for d in [INCOMING_DIR, PROCESSED_DIR, KNOWLEDGE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Drift prevention helpers (added 2026-04-11, plan 260411-2019-rate-pipeline-reorg) ──
_CANONICAL_PREFIX = re.compile(r'^(FAK|SCFI|FIX)_\d{8}_', re.IGNORECASE)
_MONTH_TO_NUM = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}


def _ensure_canonical_prefix(path: Path, ftype: str) -> Path:
    """Rename file in-place to canonical '{TYPE}_YYYYMMDD_{orig}' if prefix missing.

    Date source (priority): (1) 'DD MMM' in filename body, (2) file mtime.
    No-op if prefix already present. Returns new Path (possibly renamed).
    """
    if _CANONICAL_PREFIX.match(path.name):
        return path

    # Extract DD + MMM from filename body (e.g. "14 APR NO. 1" -> 14 APR)
    m = re.search(r'(\d{1,2})\s*([A-Z]{3})', path.stem, re.IGNORECASE)
    if m and (mo_num := _MONTH_TO_NUM.get(m.group(2).upper())):
        year = datetime.now().year
        date_str = f"{year}{mo_num:02d}{int(m.group(1)):02d}"
    else:
        date_str = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d")

    new_name = f"{ftype}_{date_str}_{path.name}"
    new_path = path.parent / new_name
    if new_path.exists():
        log.info("  Canonical name already exists, using it: %s", new_name)
        return new_path
    path.rename(new_path)
    log.info("  Normalized filename: %s -> %s", path.name, new_name)
    return new_path


def safe_move(src: Path, dst: Path, retries: int = 3, delay_s: float = 1.5) -> bool:
    """Move src → dst with bounded retry for PermissionError.

    pandas.ExcelFile can hold a file handle after read; explicit gc before
    each retry lets the interpreter release it. Returns True on success.
    """
    for attempt in range(retries):
        try:
            gc.collect()
            shutil.move(str(src), str(dst))
            return True
        except PermissionError:
            if attempt < retries - 1:
                log.debug("safe_move retry %d/%d: %s", attempt + 1, retries, src.name)
                time.sleep(delay_s)
    return False


def drain_drift() -> int:
    """Delete files in incoming/ that already exist in processed/.

    Safety net for the race where a re-download beat us before an import moved
    the prior copy. Returns count removed. Safe to call anytime.
    """
    removed = 0
    for f in INCOMING_DIR.glob("*.xlsx"):
        if (PROCESSED_DIR / f.name).exists():
            try:
                f.unlink()
                removed += 1
                log.info("[drain_drift] removed %s", f.name)
            except Exception as e:
                log.warning("[drain_drift] failed to remove %s: %s", f.name, e)
    return removed

# ── Email Config ──────────────────────────────────────────────────────────────
PRICING_SENDER = "pricing@pudongprime.vn"
PRICING_SENDER_ALT = "socvn@pudongprime.vn"  # Sometimes uses this address

# Subject pattern → rate type classification
RATE_PATTERNS = {
    "FAK": [
        r"UPDATED\s+US\s+CAD\s+RATE\s+SHEET",
        r"Update\s+rate\s+to\s+US\s+CANADA",
        r"US\s+CAD.*RATE.*SHEET",
    ],
    "SCFI": [
        r"HPL\s+SCFI\s+contract",
        r"SCFI\s+contract",
        r"SCFI\s+NO",
    ],
    "FIX": [
        r"FIXED\s+RATE\s+SUMMARY",
        r"Fixed\s+Rate\s+Summary",
    ],
}

# Knowledge email patterns (surcharges, advisories)
KNOWLEDGE_PATTERNS = [
    r"Bunker.*Fuel.*Surcharge",
    r"Surcharge\s+Update",
    r"ADVISORY",
    r"Rate\s+Notice",
]


# ==============================================================================
# 1. SCAN OUTLOOK FOR PRICING EMAILS
# ==============================================================================

def scan_pricing_emails(days: int = 7, rate_type: Optional[str] = None) -> list[dict]:
    """
    Scan Outlook inbox for pricing emails from Harry Duong.

    Args:
        days: Look back N days
        rate_type: Filter by type (FAK, SCFI, FIX, KNOWLEDGE, or None for all)

    Returns:
        List of email metadata dicts with: subject, date, sender, type, attachments
    """
    try:
        import win32com.client
    except ImportError:
        log.error("pywin32 not installed — cannot access Outlook")
        return []

    log.info("=" * 60)
    log.info("RATE IMPORT — Scanning Outlook emails")
    log.info("  Sender: %s", PRICING_SENDER)
    log.info("  Looking back: %d days", days)
    log.info("=" * 60)

    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

    emails_found = []
    cutoff = datetime.now() - timedelta(days=days)
    # Outlook Restrict requires locale-specific date format.
    # Try both MM/DD/YYYY and DD/MM/YYYY — one will match the system locale.
    cutoff_str_us = cutoff.strftime("%m/%d/%Y %H:%M %p")
    cutoff_str_vn = cutoff.strftime("%d/%m/%Y %H:%M")

    # Search in all stores
    for store in outlook.Stores:
        try:
            inbox = store.GetDefaultFolder(6)  # 6 = Inbox
            _scan_folder_filtered(inbox, cutoff_str_us, cutoff_str_vn, cutoff, emails_found, rate_type)
        except Exception:
            continue

    # Sort by date descending (newest first)
    emails_found.sort(key=lambda e: e.get("date", ""), reverse=True)

    # Stats
    type_counts = {}
    for e in emails_found:
        t = e.get("type", "UNKNOWN")
        type_counts[t] = type_counts.get(t, 0) + 1

    log.info("\nFound %d pricing emails:", len(emails_found))
    for t, c in sorted(type_counts.items()):
        log.info("  %s: %d emails", t, c)

    return emails_found


def _get_sender_smtp(item) -> str:
    """
    Get SMTP email address from Outlook item.
    Handles both SMTP and Exchange (X500) sender types.
    """
    try:
        addr_type = getattr(item, 'SenderEmailType', '')
        if addr_type == 'SMTP':
            return str(item.SenderEmailAddress).lower()
        # For Exchange addresses, resolve via PropertyAccessor
        try:
            PR_SMTP = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
            sender = item.Sender
            if sender:
                return str(sender.PropertyAccessor.GetProperty(PR_SMTP)).lower()
        except Exception:
            pass
        # Fallback: check SenderEmailAddress for domain
        addr = str(getattr(item, 'SenderEmailAddress', '')).lower()
        return addr
    except Exception:
        return ""


def _is_pricing_sender(item) -> bool:
    """Check if email is from our pricing contact."""
    # Method 1: SMTP address
    smtp = _get_sender_smtp(item)
    if 'pudongprime.vn' in smtp:
        return True

    # Method 2: Sender display name
    try:
        sender_name = str(item.SenderName or '').lower()
        if 'pudong' in sender_name or 'harry' in sender_name:
            return True
    except Exception:
        pass

    # Method 3: Raw SenderEmailAddress
    try:
        raw = str(item.SenderEmailAddress or '').lower()
        if 'pudongprime' in raw or 'pricing' in raw:
            return True
    except Exception:
        pass

    return False


def _scan_folder_filtered(folder, cutoff_str_us: str, cutoff_str_vn: str,
                           cutoff_dt: datetime,
                           results: list, rate_type: Optional[str]):
    """
    Scan an Outlook folder using Restrict filter for speed.
    Falls back to iteration for folders where Restrict fails.
    """
    try:
        items = folder.Items
        items.Sort("[ReceivedTime]", True)

        # Use Restrict for date filter — try US locale, then VN locale, then no filter
        filtered = None
        for date_str in [cutoff_str_us, cutoff_str_vn]:
            try:
                date_filter = f"[ReceivedTime] >= '{date_str}'"
                filtered = items.Restrict(date_filter)
                # Quick check: if filter returned something, use it
                if filtered.Count > 0:
                    break
            except Exception:
                continue

        if filtered is None or filtered.Count == 0:
            filtered = items  # Fallback: scan all items manually

        count = 0
        for item in filtered:
            try:
                # Date check (safety)
                received = item.ReceivedTime
                if hasattr(received, 'replace'):
                    dt = received.replace(tzinfo=None)
                else:
                    dt = datetime(received.year, received.month, received.day,
                                  received.hour, received.minute, received.second)

                if dt < cutoff_dt:
                    continue

                # Sender check
                if not _is_pricing_sender(item):
                    continue

                subject = str(item.Subject or "")
                email_type = _classify_email(subject)

                # Filter by type if requested
                if rate_type and email_type != rate_type:
                    continue

                # Extract attachment info
                attachments = []
                try:
                    for att in item.Attachments:
                        fname = str(att.FileName or "")
                        if fname.lower().endswith(('.xlsx', '.xls', '.csv')):
                            attachments.append({
                                "filename": fname,
                                "size": att.Size if hasattr(att, 'Size') else 0,
                            })
                except Exception:
                    pass

                results.append({
                    "subject": subject,
                    "date": dt.isoformat() if hasattr(dt, 'isoformat') else str(dt),
                    "sender": _get_sender_smtp(item) or str(getattr(item, 'SenderName', '')),
                    "type": email_type,
                    "attachments": attachments,
                    "attachment_count": len(attachments),
                    "has_rate_file": len(attachments) > 0,
                    "_outlook_item": item,  # Keep reference for download
                })
                count += 1

            except Exception:
                continue

        if count > 0:
            log.info("  Found %d pricing emails in '%s'", count, folder.Name)

    except Exception as e:
        log.debug("Error scanning folder '%s': %s", getattr(folder, 'Name', '?'), e)

    # Recursively scan subfolders
    try:
        for subfolder in folder.Folders:
            _scan_folder_filtered(subfolder, cutoff_str_us, cutoff_str_vn, cutoff_dt, results, rate_type)
    except Exception:
        pass


def _classify_email(subject: str) -> str:
    """Classify email by subject pattern."""
    for rtype, patterns in RATE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return rtype

    for pattern in KNOWLEDGE_PATTERNS:
        if re.search(pattern, subject, re.IGNORECASE):
            return "KNOWLEDGE"

    return "OTHER"


# ==============================================================================
# 2. DOWNLOAD ATTACHMENTS
# ==============================================================================

def download_attachments(email_list: list[dict], force: bool = False) -> list[dict]:
    """
    Download .xlsx attachments from pricing emails to incoming/ folder.

    Args:
        email_list: Output from scan_pricing_emails()
        force: Re-download even if file exists

    Returns:
        List of downloaded file info dicts
    """
    downloaded = []

    for email in email_list:
        if not email.get("has_rate_file"):
            continue

        item = email.get("_outlook_item")
        if not item:
            continue

        email_type = email["type"]
        email_date = email["date"][:10]  # YYYY-MM-DD

        try:
            for att in item.Attachments:
                fname = str(att.FileName or "")
                if not fname.lower().endswith(('.xlsx', '.xls')):
                    continue

                # Create descriptive filename: TYPE_YYYY-MM-DD_originalname.xlsx
                safe_date = email_date.replace("-", "")
                target_name = f"{email_type}_{safe_date}_{fname}"
                target_path = INCOMING_DIR / target_name
                processed_path = PROCESSED_DIR / target_name

                # Skip if already imported (lives in processed/) — prevents drift
                if processed_path.exists() and not force:
                    log.info("  Skip (already processed): %s", target_name)
                    downloaded.append({
                        "file": str(processed_path),
                        "type": email_type,
                        "status": "already_processed",
                        "original_name": fname,
                    })
                    continue

                # Skip if already staged in incoming/
                if target_path.exists() and not force:
                    log.info("  Skip (exists): %s", target_name)
                    downloaded.append({
                        "file": str(target_path),
                        "type": email_type,
                        "status": "skipped",
                        "original_name": fname,
                    })
                    continue

                # Save attachment
                att.SaveAsFile(str(target_path))
                size_kb = target_path.stat().st_size / 1024

                log.info("  Downloaded: %s (%.0f KB)", target_name, size_kb)
                downloaded.append({
                    "file": str(target_path),
                    "type": email_type,
                    "status": "downloaded",
                    "original_name": fname,
                    "size_kb": round(size_kb, 1),
                    "email_subject": email["subject"],
                    "email_date": email_date,
                })

        except Exception as e:
            log.error("  Download error for '%s': %s", email["subject"][:50], e)

    log.info("\nDownloaded %d files to %s",
             sum(1 for d in downloaded if d["status"] == "downloaded"),
             INCOMING_DIR)

    return downloaded


# ==============================================================================
# 3. EXTRACT KNOWLEDGE FROM NON-RATE EMAILS
# ==============================================================================

def extract_knowledge(email_list: list[dict]) -> list[dict]:
    """
    Extract surcharge updates and advisories as knowledge items.
    Saves email body + metadata to knowledge/ folder.
    """
    knowledge_items = []

    for email in email_list:
        if email["type"] not in ("KNOWLEDGE", "OTHER"):
            continue

        subject = email["subject"]
        date = email["date"][:10]

        try:
            item = email.get("_outlook_item")
            if not item:
                continue

            body = str(item.Body or "")[:5000]  # Limit body size

            # Save as JSON knowledge file
            safe_subject = re.sub(r'[^\w\s-]', '', subject)[:60].strip()
            knowledge_file = KNOWLEDGE_DIR / f"{date}_{safe_subject}.json"

            knowledge_entry = {
                "subject": subject,
                "date": date,
                "sender": email["sender"],
                "type": email["type"],
                "body_preview": body[:2000],
                "extracted_at": datetime.now().isoformat(),
            }

            with knowledge_file.open("w", encoding="utf-8") as f:
                json.dump(knowledge_entry, f, ensure_ascii=False, indent=2)

            log.info("  Knowledge: %s", knowledge_file.name)
            knowledge_items.append({
                "file": str(knowledge_file),
                "subject": subject,
                "date": date,
            })

        except Exception as e:
            log.warning("  Knowledge extraction error: %s", e)

    return knowledge_items


# ==============================================================================
# 4. CLASSIFY AND IMPORT — Parse files + merge to Parquet
# ==============================================================================

def classify_and_import(files: list[dict] = None) -> dict:
    """
    Process downloaded files in incoming/ folder.
    Classifies each file, runs master_loader_v2 pipeline, merges into Parquet.

    Args:
        files: Optional list from download_attachments(). If None, scans incoming/.

    Returns:
        Import result summary dict
    """
    # If no files provided, scan incoming/ folder
    if files is None:
        files = []
        for f in INCOMING_DIR.glob("*.xlsx"):
            fname = f.name.upper()
            if "FAK" in fname or "RATE SHEET" in fname or "US CANADA" in fname or "US CAD" in fname:
                ftype = "FAK"
            elif "SCFI" in fname:
                ftype = "SCFI"
            elif "FIX" in fname or "FIXED" in fname:
                ftype = "FIX"
            else:
                ftype = "FAK"  # Default

            # Auto-add canonical prefix {TYPE}_YYYYMMDD_ for files dropped manually.
            # refresh-v14.py sorts by this prefix to pick the latest rate version;
            # a naked name like "Update rate to US CANADA_ 14 APR NO. 1.xlsx" would
            # fall to the bottom and the ribbon would show a stale version.
            f = _ensure_canonical_prefix(f, ftype)
            files.append({"file": str(f), "type": ftype, "status": "pending"})

    if not files:
        log.info("No files to import")
        return {"files_processed": 0, "rates_imported": 0}

    log.info("\n" + "=" * 60)
    log.info("IMPORTING %d files into Parquet", len([f for f in files if f.get("status") != "error"]))
    log.info("=" * 60)

    # Import master_loader_v2 functions
    # NOTE: per 2026-04-13 cleanup, master_loader_v2 moved to repo-root scripts/
    # (previously Pricing_Engine/scripts/). Try both locations for backward compat.
    _repo_root = SCRIPT_DIR.parent  # Engine_test/
    _candidate_dirs = [
        _repo_root / "scripts",           # current canonical location
        SCRIPT_DIR / "scripts",           # legacy location (pre-2026-04-13)
    ]
    for _d in _candidate_dirs:
        if (_d / "master_loader_v2.py").exists():
            sys.path.insert(0, str(_d))
            break
    try:
        from master_loader_v2 import (
            parse_file_with_mapping,
            apply_puc_soc_correct,
            RATE_PRIORITY,
        )
    except ImportError as e:
        log.error("Cannot import master_loader_v2: %s", e)
        log.error("Searched: %s", [str(d) for d in _candidate_dirs])
        return {"error": str(e)}

    all_data = []
    files_ok = 0

    for file_info in files:
        fpath = Path(file_info["file"])
        ftype = file_info["type"]

        if not fpath.exists():
            continue
        if file_info.get("status") == "error":
            continue

        log.info("\n[>] %s (type: %s)", fpath.name, ftype)

        try:
            if ftype == "SCFI":
                # SCFI has different layout — use dedicated parser
                df = _parse_scfi_rate_table(fpath)
            else:
                # FAK and FIX use master_loader mapping
                mode = ftype
                df = parse_file_with_mapping(str(fpath), fpath.name, mode)

            if df is not None and not df.empty:
                # For FIX with SOC HPL sheet: parse separately and apply PUC
                if ftype == "FIX":
                    df_soc = _parse_fix_soc_hpl(fpath)
                    if df_soc is not None and not df_soc.empty:
                        log.info("  [SOC HPL] Parsed %d SOC HPL rows", len(df_soc))
                        df = pd.concat([df, df_soc], ignore_index=True)

                all_data.append(df)
                files_ok += 1
                log.info("  [OK] %d records extracted", len(df))
            else:
                log.warning("  [!] No data extracted from %s", fpath.name)

        except Exception as e:
            log.error("  [!] Error processing %s: %s", fpath.name, e)
            import traceback
            traceback.print_exc()

    if not all_data:
        return {"files_processed": files_ok, "rates_imported": 0, "error": "No data extracted"}

    # Merge all new data
    new_df = pd.concat(all_data, ignore_index=True)
    log.info("\n[+] Total new records: %d", len(new_df))

    # Apply PUC_SOC correction for SOC rows (CMA/ONE/YML + HPL SOC)
    log.info("[+] Applying PUC_SOC correction...")
    new_df = apply_puc_soc_correct(new_df, str(PUC_SOC_FILE))

    # ── REEFER container remap (same as master_loader_v2 L513-517) ──
    # ONE/COSCO REEFER: 20GP→20RF, 40GP/40HQ/40NOR→40RF
    is_reefer = new_df['Commodity'].str.contains("REEFER", case=False, na=False)
    is_target = new_df['Carrier'].str.upper().isin(["ONE", "COSCO"])
    _reefer_fixed = 0
    if (is_reefer & is_target).any():
        mask_20 = is_reefer & is_target & new_df['Container_Type'].str.contains("20", na=False)
        mask_40 = is_reefer & is_target & new_df['Container_Type'].str.contains("40", na=False)
        _reefer_fixed = mask_20.sum() + mask_40.sum()
        new_df.loc[mask_20, 'Container_Type'] = "20RF"
        new_df.loc[mask_40, 'Container_Type'] = "40RF"
    if _reefer_fixed:
        log.info("[+] REEFER remap: %d container types fixed (ONE/COSCO)", _reefer_fixed)

    # Date conversion
    for col in ['Eff', 'Exp']:
        if col in new_df.columns:
            new_df[col] = pd.to_datetime(new_df[col], errors='coerce')

    # Force string type on all text columns to prevent ArrowTypeError
    text_cols = ['POL', 'POD', 'Place', 'Carrier', 'Note', 'Group Rate',
                 'Commodity', 'Charge_Name', 'Container_Type', 'Source_File',
                 'Rate_Type', 'Contract', 'Group_Code']
    for col in text_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].fillna('').astype(str)

    # Ensure standard columns exist
    for col in ['Contract', 'Group_Code']:
        if col not in new_df.columns:
            new_df[col] = ''

    # Load existing Parquet and merge
    rates_before = 0
    if PARQUET_FILE.exists():
        existing_df = pd.read_parquet(PARQUET_FILE)
        rates_before = len(existing_df)

        # Ensure new columns exist in existing data too
        for col in ['Contract', 'Group_Code']:
            if col not in existing_df.columns:
                existing_df[col] = ''

        # Force string types on existing data too (prevent concat type conflicts)
        for col in text_cols:
            if col in existing_df.columns:
                existing_df[col] = existing_df[col].fillna('').astype(str)

        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df

    # Smart dedup (same as master_loader_v2)
    combined['Rate_Priority'] = combined['Rate_Type'].map(RATE_PRIORITY).fillna(99)
    combined = combined.sort_values(
        by=['POL', 'POD', 'Carrier', 'Container_Type', 'Rate_Priority', 'Source_File'],
        ascending=[True, True, True, True, True, False]
    )
    combined = combined.drop_duplicates(
        subset=['POL', 'POD', 'Carrier', 'Place', 'Commodity', 'Note',
                'Container_Type', 'Charge_Name', 'Eff', 'Exp'],
        keep='first'
    )
    combined = combined.drop(columns=['Rate_Priority'], errors='ignore')

    rates_after = len(combined)

    # Backup + Save ? keep only 1 backup in _backup/ folder
    if PARQUET_FILE.exists():
        backup_dir = DATA_DIR / "_backup"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"Cleaned_Master_History_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.parquet"
        shutil.copy2(PARQUET_FILE, backup)
        log.info("[+] Backup: _backup/%s", backup.name)
        # Cleanup: keep only the latest backup, delete older ones
        old_backups = sorted(backup_dir.glob("Cleaned_Master_History_BACKUP_*.parquet"))[:-1]
        for old_bk in old_backups:
            old_bk.unlink()
            log.info("[+] Removed old backup: %s", old_bk.name)

    combined.to_parquet(PARQUET_FILE, index=False, engine='pyarrow')
    log.info("[+] Saved: %s (%d rows)", PARQUET_FILE.name, rates_after)

    # Bump forecast-retrain counter — nightly check_retrain decides the rest.
    # Fire-and-forget: retrain trigger should never block a successful import.
    try:
        from Pricing_Engine.forecast_retrain import bump_import_counter
        # Determine dominant rate type from files list (fallback "MIXED")
        _types = {f.get("type", "") for f in files if f.get("type")}
        _source = next(iter(_types)) if len(_types) == 1 else "MIXED"
        bump_import_counter(
            rows_added=max(0, rates_after - rates_before),
            source=_source,
            parquet_rows_after=rates_after,
        )
    except Exception as _e:
        log.warning("forecast_retrain bump failed (non-blocking): %s", _e)

    # Move processed files to processed/ using safe_move (retries on lock)
    for file_info in files:
        fpath = Path(file_info["file"])
        if fpath.exists() and fpath.parent == INCOMING_DIR:
            dest = PROCESSED_DIR / fpath.name
            if safe_move(fpath, dest):
                log.info("  Moved → processed/%s", fpath.name)
            else:
                log.warning("  ⚠️ safe_move failed after retries: %s — will be drained next run", fpath.name)

    result = {
        "files_processed": files_ok,
        "rates_before": rates_before,
        "rates_imported": len(new_df),
        "rates_after_dedup": rates_after,
        "net_new": rates_after - rates_before,
        "parquet_updated": True,
    }

    log.info("\n" + "=" * 60)
    log.info("IMPORT COMPLETE")
    log.info("  Files: %d processed", files_ok)
    log.info("  Before: %d | Imported: %d | After dedup: %d",
             rates_before, len(new_df), rates_after)
    log.info("  Net new rates: %d", rates_after - rates_before)
    log.info("=" * 60)

    return result


# ==============================================================================
# SPECIAL PARSERS
# ==============================================================================

def _parse_scfi_rate_table(file_path: Path) -> Optional[pd.DataFrame]:
    """
    Parse SCFI RATE TABLE sheet directly (not via master_loader).

    SCFI layout:
        Col 0: Destination (e.g. 'Los Angeles, CA / Long Beach, CA')
        Col 1: via PORT
        Col 2: via (WC/EC)
        Col 3: Contract (SC number)
        Col 4: mr code (Group_Code)
        Col 5: VALID EFF
        Col 6: VALID END
        Col 7+: Charge groups (BASE O/F, HLCU Offer, ISPS, EMF, DLF, COMMISSION)
                each with sub-columns: 20', 40', 40'HC
    """
    try:
        xls = pd.ExcelFile(file_path)
        if 'RATE TABLE' not in xls.sheet_names:
            log.warning("  [SCFI] No 'RATE TABLE' sheet in %s", file_path.name)
            return None

        raw = xls.parse('RATE TABLE', header=None)
        if len(raw) < 3:
            return None

        # Row 0 = parent headers (charge group names)
        # Row 1 = container type sub-headers (20', 40', 40'HC)
        header_parent = raw.iloc[0].fillna(method='ffill')
        header_container = raw.iloc[1]
        data = raw.iloc[2:].reset_index(drop=True)

        # Container normalization
        cmap = {"20'": "20GP", "40'": "40GP", "40'HC": "40HQ"}

        records = []
        for _, row in data.iterrows():
            dest = str(row.iloc[0] if pd.notna(row.iloc[0]) else '').strip()
            if not dest or dest == 'nan':
                continue

            via_port = str(row.iloc[1] if pd.notna(row.iloc[1]) else '').strip()
            via = str(row.iloc[2] if pd.notna(row.iloc[2]) else '').strip()
            contract = str(row.iloc[3] if pd.notna(row.iloc[3]) else '').strip()
            mrcode = str(row.iloc[4] if pd.notna(row.iloc[4]) else '').strip()
            eff = row.iloc[5] if pd.notna(row.iloc[5]) else None
            exp = row.iloc[6] if pd.notna(row.iloc[6]) else None

            # Parse all charge columns (col 7+)
            for col_idx in range(7, len(row)):
                amount = row.iloc[col_idx]
                if pd.isna(amount):
                    continue
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    continue
                if amount == 0:
                    continue

                charge = str(header_parent.iloc[col_idx]).strip()
                container = str(header_container.iloc[col_idx]).strip()
                container = cmap.get(container, container)

                # Normalize via JSON source of truth (CARRIER_RATE_MAPPING.json).
                # See docs/CHARGE_NAME_SOURCE_OF_TRUTH.md for the 2026-04-17 incident.
                try:
                    from .charge_normalizer import normalize_charge_name as _norm
                except ImportError:
                    from charge_normalizer import normalize_charge_name as _norm  # type: ignore
                charge_norm = _norm(charge, rate_type="SCFI")
                if charge_norm is None:
                    charge_norm = charge  # pass-through for surcharges; helper already warned

                records.append({
                    'POL': 'HCM',  # SCFI always from HCM
                    'POD': via_port,  # via PORT = POD (cảng đến)
                    'Place': dest,  # Destination = Place of delivery
                    'Carrier': 'HPL',
                    'Commodity': '',
                    'Contract': contract,
                    'Group_Code': mrcode,
                    'Eff': eff,
                    'Exp': exp,
                    'Note': f'SCFI via {via}' if via else 'SCFI',
                    'Group Rate': '',
                    'Charge_Name': charge_norm,
                    'Container_Type': container,
                    'Amount': amount,
                    'Source_File': file_path.name,
                    'Rate_Type': 'SCFI',
                })

        if records:
            df = pd.DataFrame(records)
            log.info("  [SCFI] Parsed %d rows, %d destinations, Contract: %s",
                     len(df), df['Place'].nunique(),
                     'YES' if df['Contract'].notna().any() and (df['Contract'] != '').any() else 'NO')
            return df

    except Exception as e:
        log.error("  [SCFI] Parse error: %s", e)
        import traceback
        traceback.print_exc()

    return None


def _enrich_scfi_columns(file_path: Path, df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich SCFI data with Contract (SC) and Group_Code (mr code) columns.
    Reads these from the RATE TABLE sheet directly.
    """
    try:
        xls = pd.ExcelFile(file_path)
        if 'RATE TABLE' in xls.sheet_names:
            raw = xls.parse('RATE TABLE', header=None)

            # Row 0 = header parent, Row 1 = sub-header
            # Contract is typically column D (index 3), mr code is column E (index 4)
            data = raw.iloc[2:].reset_index(drop=True)

            # Find Contract and mr code columns
            header0 = raw.iloc[0]
            contract_col = None
            mrcode_col = None

            for i, val in enumerate(header0):
                s = str(val).strip().lower()
                if 'contract' in s:
                    contract_col = i
                elif 'mr code' in s or 'mr_code' in s:
                    mrcode_col = i

            if contract_col is not None and len(data) > 0:
                contracts = data.iloc[:, contract_col].fillna('').astype(str).values
                # Map by Destination (row index)
                if len(contracts) == len(df.groupby(['POL', 'POD', 'Place']).ngroup().unique()) or True:
                    # Best effort: assign contracts by matching destination order
                    dest_data = data.iloc[:, 0].fillna('').astype(str).values  # Destination column

                    contract_map = {}
                    mrcode_map = {}
                    for i, dest in enumerate(dest_data):
                        if dest.strip():
                            contract_map[dest.strip().upper()] = str(contracts[i]).strip()
                            if mrcode_col is not None and i < len(data.iloc[:, mrcode_col]):
                                mrcode_map[dest.strip().upper()] = str(data.iloc[i, mrcode_col]).strip()

                    # Match to df by Place or POD
                    df['Contract'] = df.apply(
                        lambda r: contract_map.get(str(r.get('Place', '')).strip().upper(),
                                  contract_map.get(str(r.get('POD', '')).strip().upper(), '')),
                        axis=1
                    )
                    df['Group_Code'] = df.apply(
                        lambda r: mrcode_map.get(str(r.get('Place', '')).strip().upper(),
                                  mrcode_map.get(str(r.get('POD', '')).strip().upper(), '')),
                        axis=1
                    )
                    log.info("  [SCFI] Enriched with Contract + Group_Code")

    except Exception as e:
        log.warning("  [SCFI] Could not extract SC/mr code: %s", e)

    # Ensure columns exist
    if 'Contract' not in df.columns:
        df['Contract'] = ''
    if 'Group_Code' not in df.columns:
        df['Group_Code'] = ''

    return df


def _parse_fix_soc_hpl(file_path: Path) -> Optional[pd.DataFrame]:
    """
    Parse the 'SOC HPL' sheet from Fixed Rate file.
    This sheet has HPL SOC rates with detailed charge breakdown.
    Needs PUC_SOC correction applied afterward.

    Layout: Destination | POD | SC | VALID(start) | VALID(end) |
            TOTAL O/F (20/40/40HC) | BASIC O/F (20/40/40HC) | MFR | PUC | ALF | ISPS | DLF | PSS | CARBON | COMMISSION
    """
    try:
        xls = pd.ExcelFile(file_path)
        if 'SOC HPL' not in xls.sheet_names:
            return None

        raw = xls.parse('SOC HPL', header=None)
        if len(raw) < 3:
            return None

        # Row 0 = charge group names (parent headers)
        # Row 1 = container types (20'/40GP/40HC)
        # Row 2+ = data
        header_parent = raw.iloc[0].fillna(method='ffill')
        header_container = raw.iloc[1]
        data = raw.iloc[2:].reset_index(drop=True)

        records = []

        # Identify base columns
        # Col 0 = Destination, Col 1 = POD, Col 2 = SC, Col 3 = VALID start, Col 4 = VALID end
        for row_idx, row in data.iterrows():
            dest = str(row.iloc[0] if pd.notna(row.iloc[0]) else '').strip()
            if not dest or dest == 'nan':
                continue

            pod = str(row.iloc[1] if pd.notna(row.iloc[1]) else '').strip()
            sc = str(row.iloc[2] if pd.notna(row.iloc[2]) else '').strip()
            eff = row.iloc[3] if pd.notna(row.iloc[3]) else ''
            exp = row.iloc[4] if pd.notna(row.iloc[4]) else ''

            # Parse charge columns (starting from col 5)
            for col_idx in range(5, len(row)):
                amount = row.iloc[col_idx]
                if pd.isna(amount):
                    continue
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    continue
                if amount == 0:
                    continue

                charge_name = str(header_parent.iloc[col_idx]).strip()
                container = str(header_container.iloc[col_idx]).strip()

                # Normalize container
                container_map = {
                    "20'": "20GP", "40GP": "40GP", "40HC": "40HQ", "40'HC": "40HQ",
                    "20GP": "20GP", "40HQ": "40HQ", "45'HQ": "45'HQ",
                }
                container = container_map.get(container, container)

                # Normalize charge name
                charge_map = {
                    "TOTAL O/F": "Total Ocean Freight",
                    "TOTAL O/F ": "Total Ocean Freight",
                    "BASIC O/F": "BASIC O/F",
                    "BASIC O/F ": "BASIC O/F",
                }
                charge_name = charge_map.get(charge_name, charge_name)

                records.append({
                    'POL': 'HPH',  # Default for HPL SOC
                    'POD': pod or dest,
                    'Place': dest,
                    'Carrier': 'HPL',
                    'Eff': eff,
                    'Exp': exp,
                    'Note': 'SOC',  # Critical: mark as SOC for PUC correction
                    'Group Rate': '',
                    'Commodity': '',
                    'Contract': sc,
                    'Group_Code': '',
                    'Charge_Name': charge_name,
                    'Container_Type': container,
                    'Amount': amount,
                    'Source_File': file_path.name,
                    'Rate_Type': 'FIX',
                })

        if records:
            return pd.DataFrame(records)

    except Exception as e:
        log.warning("  [SOC HPL] Parse error: %s", e)

    return None


# ==============================================================================
# 5a. POST-IMPORT HOOKS — ERP Refresh + Telegram Notification
# ==============================================================================

def _trigger_erp_refresh() -> bool:
    """
    Trigger ERP data refresh after Parquet update.
    Non-blocking — returns False on failure, pipeline continues.
    """
    if not ERP_REFRESH_SCRIPT.exists():
        log.warning("[⚠️] ERP refresh script not found: %s", ERP_REFRESH_SCRIPT)
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(ERP_REFRESH_SCRIPT)],
            capture_output=True, text=True, timeout=300,
            cwd=str(ERP_REFRESH_SCRIPT.parent),
        )
        if result.returncode == 0:
            log.info("[✅] ERP refresh triggered successfully")
            return True
        else:
            log.warning("[⚠️] ERP refresh warning: %s", result.stderr[-200:] if result.stderr else "unknown")
            return False
    except subprocess.TimeoutExpired:
        log.warning("[⚠️] ERP refresh timed out (300s)")
        return False
    except Exception as e:
        log.warning("[⚠️] ERP refresh skipped: %s", e)
        return False


def _notify_telegram(import_result: dict, erp_refreshed: bool = False) -> bool:
    """Send import summary to Nelson via Telegram. DISABLED 2026-04-26 — no-op."""
    log.debug("rate_importer._notify_telegram disabled — alert dropped")
    return True
    try:  # noqa: unreachable
        # Read Telegram config (same source as bot_v5.py)
        import importlib.util
        spec = importlib.util.spec_from_file_location("tg_config", str(TELEGRAM_CONFIG))
        tg_cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tg_cfg)
        token = getattr(tg_cfg, 'BOT_TOKEN', None)
        chat_id = getattr(tg_cfg, 'ADMIN_CHAT_ID', None)

        if not token or not chat_id:
            log.warning("[⚠️] Telegram config missing BOT_TOKEN or ADMIN_CHAT_ID")
            return False

        # Build message
        files = import_result.get('files_processed', 0)
        imported = import_result.get('rates_imported', 0)
        total = import_result.get('rates_after_dedup', 0)
        net_new = import_result.get('net_new', 0)
        erp_status = "✅ ERP refreshed + reopened" if erp_refreshed else "⚠️ Manual refresh needed"
        ts = datetime.now().strftime("%H:%M %d/%m")

        message = (
            f"📦 Rates Updated\n"
            f"Files: {files} processed\n"
            f"Records: +{imported} imported\n"
            f"Net new: {net_new}\n"
            f"Parquet: {total:,} total rows\n"
            f"Time: {ts}\n"
            f"{erp_status}"
        )

        import urllib.request
        import urllib.parse
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("[✅] Telegram notification sent")
                return True
            else:
                log.warning("[⚠️] Telegram response: %d", resp.status)
                return False

    except FileNotFoundError:
        log.warning("[⚠️] TelegramBot/config.py not found — Telegram skipped")
        return False
    except Exception as e:
        log.warning("[⚠️] Telegram notification failed: %s", e)
        return False


# ==============================================================================
# 5. FULL IMPORT PIPELINE — One-click
# ==============================================================================

def run_full_import(days: int = 3, rate_type: Optional[str] = None,
                    scan_only: bool = False) -> dict:
    """
    Full import pipeline: scan → download → classify → import → report.

    Args:
        days: Look back N days in email
        rate_type: Filter by type (FAK, SCFI, FIX, or None for all)
        scan_only: Just scan and report, don't download or import

    Returns:
        Complete result summary
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "days_scanned": days,
        "rate_type_filter": rate_type,
    }

    # Step 1: Scan emails
    emails = scan_pricing_emails(days=days, rate_type=rate_type)
    rate_emails = [e for e in emails if e["type"] in ("FAK", "SCFI", "FIX")]
    knowledge_emails = [e for e in emails if e["type"] in ("KNOWLEDGE", "OTHER")]

    result["emails_found"] = len(emails)
    result["rate_emails"] = len(rate_emails)
    result["knowledge_emails"] = len(knowledge_emails)
    result["email_summary"] = [
        {"subject": e["subject"][:80], "date": e["date"][:10], "type": e["type"],
         "attachments": e["attachment_count"]}
        for e in emails
    ]

    if scan_only:
        result["mode"] = "scan_only"
        return result

    # Step 2: Download attachments
    downloaded = download_attachments(rate_emails)
    new_downloads = [d for d in downloaded if d["status"] == "downloaded"]
    result["files_downloaded"] = len(new_downloads)

    # Step 3: Extract knowledge
    if knowledge_emails:
        knowledge = extract_knowledge(knowledge_emails)
        result["knowledge_items"] = len(knowledge)

    # Step 4: Import to Parquet
    if new_downloads:
        import_result = classify_and_import(new_downloads)
        result.update(import_result)
    else:
        # Try importing any files already in incoming/
        pending = list(INCOMING_DIR.glob("*.xlsx"))
        if pending:
            log.info("\nNo new downloads, but %d files in incoming/", len(pending))
            import_result = classify_and_import()
            result.update(import_result)
        else:
            result["rates_imported"] = 0
            result["message"] = "No new rate files to import"

    # Publish event if event_bus available
    try:
        sys.path.insert(0, str(SCRIPT_DIR.parent / "api"))
        from event_bus import bus, Event
        bus.publish(Event(
            type="rate.imported",
            payload={
                "files": result.get("files_processed", 0),
                "rates_imported": result.get("rates_imported", 0),
                "net_new": result.get("net_new", 0),
            },
            source="rate_importer",
        ))
    except Exception:
        pass  # Event bus not available (standalone mode)

    # ── Post-import hooks (non-blocking) ──
    erp_ok = False
    if result.get("parquet_updated"):
        # Normalize data before ERP refresh
        try:
            sys.path.insert(0, str(Path(__file__).parent / "scripts"))
            from normalize_parquet import normalize_parquet_data
            norm_result = normalize_parquet_data(backup=False)
            if norm_result:
                log.info("[✅] Parquet normalized post-import")
                result["normalized"] = True
        except Exception as e:
            log.warning("[⚠️] Normalization skipped: %s", e)

        erp_ok = _trigger_erp_refresh()
        result["erp_refreshed"] = erp_ok

        tg_ok = _notify_telegram(result, erp_refreshed=erp_ok)
        result["telegram_sent"] = tg_ok

        # ── Anomaly check — scan rates for pricing deviations ──
        try:
            from intelligence.alert_dispatcher import run_alert_cycle
            alert_result = run_alert_cycle()
            result["anomaly_check"] = alert_result
            if alert_result.get("anomalies", 0) > 0:
                log.info("[🚨] Anomalies detected: %d (critical: %d, warning: %d)",
                         alert_result["anomalies"], alert_result["critical"], alert_result["warnings"])
        except Exception as e:
            log.warning("[⚠️] Anomaly check skipped: %s", e)

        # ── Rate delta alert — compare new vs 7-day-prior prices ──
        # NOTE: path only valid on Laptop VP (C:\Users\Nelson\...) — PC Home will
        #       log a warning and continue normally (non-blocking, safe to skip).
        try:
            import subprocess as _sp
            _alert_bat = r"C:\Users\Nelson\5398948978\rate-alert.bat"
            _sp.Popen(_alert_bat, shell=True)  # shell=True required to run .bat
            log.info("[📊] Rate alert check triggered (non-blocking)")
        except Exception as e:
            log.warning("[⚠️] Rate alert skipped: %s", e)

    return result


# ==============================================================================
# CLI
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nelson Freight Rate Importer")
    parser.add_argument("--days", type=int, default=3, help="Days to look back (default: 3)")
    parser.add_argument("--type", choices=["FAK", "SCFI", "FIX"], default=None,
                        help="Filter by rate type")
    parser.add_argument("--scan-only", action="store_true", help="Just scan, don't import")
    parser.add_argument("--import-pending", action="store_true",
                        help="Import files already in incoming/ folder")
    parser.add_argument("--drain", action="store_true",
                        help="Delete incoming/ files that already exist in processed/ then exit")

    args = parser.parse_args()

    if args.drain:
        n = drain_drift()
        result = {"drained": n, "action": "drain-only"}
    elif args.import_pending:
        # Always drain before re-importing to avoid duplicate work
        drain_drift()
        result = classify_and_import()
    else:
        # Always drain before full import
        drain_drift()
        result = run_full_import(days=args.days, rate_type=args.type,
                                 scan_only=args.scan_only)

    import sys
    # Report result to Fox Spirit (GoClaw VPS) — fire-and-forget
    try:
        import importlib.util, pathlib
        _rep = pathlib.Path(__file__).parent.parent / "tools" / "goclaw" / "goclaw_reporter.py"
        _spec = importlib.util.spec_from_file_location("goclaw_reporter", _rep)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.report_to_fox("rate-import", result)
    except Exception:
        pass
    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout.buffer.write(("\n" + output + "\n").encode("utf-8", errors="replace"))
    elif sys.stdout:
        sys.stdout.write("\n" + output + "\n")


if __name__ == "__main__":
    main()
