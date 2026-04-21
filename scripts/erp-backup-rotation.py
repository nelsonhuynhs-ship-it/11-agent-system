"""
ERP Backup Rotation — scripts/erp-backup-rotation.py
Keeps newest N backup copies of ERP_Master_v14, deletes the rest.

Usage:
    python scripts/erp-backup-rotation.py [--dry-run] [--keep N]

Flags:
    --dry-run   Show what would be deleted without deleting anything.
    --keep N    Keep the newest N backups (default: 5).

Supported filename patterns:
    ERP_Master_v14.backup_YYYYMMDD_HHMMSS.xlsm   (new convention)
    ERP_Master_v14_BACKUP_YYYYMMDD_HHMM.xlsm     (old convention)

Safety:
    - NEVER deletes ERP_Master_v14.xlsm (live file)
    - NEVER deletes ~$ERP_Master_v14.xlsm (Excel lock file)
    - Skips files that are currently open (PermissionError)
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ERP_DIR = Path("D:/OneDrive/NelsonData/erp")

# Patterns that are protected — never deleted regardless of logic
PROTECTED_NAMES = {
    "ERP_Master_v14.xlsm",
    "~$ERP_Master_v14.xlsm",
}

# Regex for three observed backup naming conventions:
#   new:  ERP_Master_v14.backup_20260420_211144.xlsm   (dot + 6-digit time)
#   old:  ERP_Master_v14_BACKUP_20260414_1915.xlsm     (underscore + 4-digit time)
#   alt:  ERP_Master_v14_backup_20260420_213021.xlsm   (underscore + 6-digit time)
PATTERN_NEW = re.compile(
    r"^ERP_Master_v14\.backup_(\d{8}_\d{6})\.xlsm$", re.IGNORECASE
)
PATTERN_OLD = re.compile(
    r"^ERP_Master_v14_BACKUP_(\d{8}_\d{4})\.xlsm$", re.IGNORECASE
)
PATTERN_ALT = re.compile(
    r"^ERP_Master_v14_backup_(\d{8}_\d{6})\.xlsm$", re.IGNORECASE
)

MIGRATION_TEST_NAME = "ERP_Master_v14.migration_test.xlsm"
MIGRATION_TEST_MAX_AGE_DAYS = 7


def parse_timestamp(filename: str) -> datetime | None:
    """Return UTC-naive datetime parsed from backup filename, or None."""
    m = PATTERN_NEW.match(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            return None

    m = PATTERN_OLD.match(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d_%H%M")
        except ValueError:
            return None

    m = PATTERN_ALT.match(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            return None

    return None


def is_file_open(path: Path) -> bool:
    """Return True if the file is locked (currently open by another process)."""
    try:
        with open(path, "a+b"):
            pass
        return False
    except PermissionError:
        return True


def collect_backups(erp_dir: Path) -> list[tuple[datetime, Path]]:
    """Return list of (timestamp, path) for all recognised backup files, sorted newest→oldest."""
    backups: list[tuple[datetime, Path]] = []
    for entry in erp_dir.iterdir():
        if not entry.is_file():
            continue
        ts = parse_timestamp(entry.name)
        if ts is not None:
            backups.append((ts, entry))
    backups.sort(key=lambda x: x[0], reverse=True)
    return backups


def run(dry_run: bool, keep: int) -> None:
    if not ERP_DIR.exists():
        print(f"ERROR: ERP directory not found: {ERP_DIR}")
        sys.exit(1)

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"{mode_label}ERP Backup Rotation — keep newest {keep}, dir: {ERP_DIR}")
    print()

    backups = collect_backups(ERP_DIR)
    print(f"Found {len(backups)} backup file(s):")
    for ts, p in backups:
        print(f"  {ts.strftime('%Y-%m-%d %H:%M:%S')}  {p.name}")
    print()

    to_keep = backups[:keep]
    to_delete: list[Path] = []

    for ts, p in backups[keep:]:
        if p.name in PROTECTED_NAMES:
            print(f"  PROTECTED (skip): {p.name}")
            continue
        to_delete.append(p)

    # Check migration_test
    migration_path = ERP_DIR / MIGRATION_TEST_NAME
    if migration_path.exists():
        age_days = (
            datetime.now() - datetime.fromtimestamp(migration_path.stat().st_mtime)
        ).days
        if age_days >= MIGRATION_TEST_MAX_AGE_DAYS:
            to_delete.append(migration_path)
            print(
                f"  migration_test is {age_days} days old (>= {MIGRATION_TEST_MAX_AGE_DAYS}) — queued for deletion"
            )
        else:
            print(
                f"  migration_test is {age_days} days old (< {MIGRATION_TEST_MAX_AGE_DAYS}) — keeping"
            )

    if not to_delete:
        print("Nothing to delete.")
        return

    print(f"\nFiles to delete ({len(to_delete)}):")
    total_bytes = 0
    actually_deleted = 0
    skipped_open = 0

    for p in to_delete:
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            continue

        total_bytes += size

        if is_file_open(p):
            print(f"  SKIP (file open): {p.name}  ({size:,} bytes)")
            skipped_open += 1
            continue

        print(f"  {'WOULD DELETE' if dry_run else 'DELETING'}  {p.name}  ({size:,} bytes)")

        if not dry_run:
            try:
                p.unlink()
                actually_deleted += 1
            except PermissionError:
                print(f"    WARNING: PermissionError — skipped {p.name}")
                skipped_open += 1

    print()
    if dry_run:
        print(
            f"[DRY RUN] Would free {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.2f} MB) "
            f"from {len(to_delete) - skipped_open} file(s)."
        )
    else:
        freed = sum(
            0 for p in to_delete
        )  # already deleted; recalculate from actually_deleted count
        print(
            f"Deleted {actually_deleted} file(s). "
            f"Freed approximately {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.2f} MB)."
        )
        if skipped_open:
            print(f"WARNING: {skipped_open} file(s) skipped (open/locked).")

    # Confirm protected file is still present
    live_file = ERP_DIR / "ERP_Master_v14.xlsm"
    if live_file.exists():
        print(f"\nSAFETY CHECK: Live file intact — {live_file.name}")
    else:
        print("\nERROR: Live file ERP_Master_v14.xlsm NOT FOUND — investigate immediately!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rotate ERP backup xlsm files — keep newest N, delete the rest."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=5,
        metavar="N",
        help="Number of newest backups to keep (default: 5).",
    )
    args = parser.parse_args()

    if args.keep < 1:
        print("ERROR: --keep must be >= 1")
        sys.exit(1)

    run(dry_run=args.dry_run, keep=args.keep)


if __name__ == "__main__":
    main()
