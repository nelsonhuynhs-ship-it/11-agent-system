"""
backfill_intel_from_csv.py — Import historical SENT events into intel.db
========================================================================
Reads email_engine/logs/email_log.csv (~17K rows, columns:
timestamp,email,subject,campaign_id,status,reply_timestamp,cycle_id)
and inserts one SENT event per row in batches of 1000 within a single
transaction. Idempotent on re-run only if intel.db is fresh — caller is
expected to start from an empty DB or pass --since-date filter.

Usage:
    python scripts/backfill_intel_from_csv.py
    python scripts/backfill_intel_from_csv.py --csv path/to/log.csv --batch 2000
    python scripts/backfill_intel_from_csv.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

# Make sibling email_engine importable when run as script
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from email_engine.intel import memory, build_sent_event  # noqa: E402

DEFAULT_CSV = _ROOT / "email_engine" / "logs" / "email_log.csv"


def _parse_ts(raw: str) -> str:
    """Source uses 'DD/MM/YYYY HH:MM' — convert to ISO 'YYYY-MM-DD HH:MM:SS'."""
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_event(row: dict) -> dict | None:
    """Convert one CSV row to a SENT event dict. Returns None for rows we skip
    (no email / status not SENT)."""
    email = (row.get("email") or "").strip().lower()
    status = (row.get("status") or "").strip().upper()
    if not email or status != "SENT":
        return None
    event = build_sent_event(
        cnee_email=email,
        subject=(row.get("subject") or "").strip(),
        campaign_id=(row.get("campaign_id") or "").strip() or None,
        batch_id=(row.get("cycle_id") or "").strip() or None,
    )
    event["timestamp"] = _parse_ts(row.get("timestamp", ""))
    return event


def backfill(csv_path: Path, batch_size: int = 1000, dry_run: bool = False) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    memory.init_db()

    inserted = 0
    skipped = 0
    batch: list[dict] = []
    start = time.perf_counter()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ev = _row_to_event(row)
            if ev is None:
                skipped += 1
                continue
            batch.append(ev)
            if len(batch) >= batch_size:
                if not dry_run:
                    memory.log_events_bulk(batch)
                inserted += len(batch)
                batch.clear()
        if batch:
            if not dry_run:
                memory.log_events_bulk(batch)
            inserted += len(batch)

    elapsed = round(time.perf_counter() - start, 2)
    return {"inserted": inserted, "skipped": skipped, "elapsed_s": elapsed,
            "dry_run": dry_run}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--batch", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    summary = backfill(args.csv, args.batch, args.dry_run)
    print(
        f"backfill_intel_from_csv: inserted={summary['inserted']} "
        f"skipped={summary['skipped']} "
        f"elapsed={summary['elapsed_s']}s "
        f"dry_run={summary['dry_run']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
