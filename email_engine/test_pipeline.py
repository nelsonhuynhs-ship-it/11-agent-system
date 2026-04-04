"""
test_pipeline.py — End-to-End Pipeline Test
=============================================
Uses existing .msg files in outlook/ to test the full pipeline.
"""

import io
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Fix Windows encoding for Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure core/ is importable
sys.path.insert(0, str(Path(__file__).parent / 'core'))

PROJECT_ROOT = Path(__file__).parent
DB_PATH      = PROJECT_ROOT / 'logs' / 'shipments.db'
OUTLOOK_DIR  = PROJECT_ROOT / 'outlook'


def find_test_msg_files() -> list[Path]:
    """Find .msg files anywhere in outlook/ for testing."""
    files = []
    for f in OUTLOOK_DIR.rglob('*.msg'):
        # Skip _processed and _unmatched
        if '_processed' in str(f) or '_unmatched' in str(f):
            continue
        files.append(f)
    return files


def setup_test_files(msg_files: list[Path]) -> int:
    """
    Copy test .msg files into appropriate folders for processing.
    Returns count of files prepared.
    """
    count = 0
    nelson_dir = OUTLOOK_DIR / 'NELSON'
    nelson_dir.mkdir(parents=True, exist_ok=True)

    for f in msg_files:
        # If already in a scan-eligible folder, skip copy
        parent_name = f.parent.name.upper()
        if parent_name in ('NELSON', 'BLUE', 'JENNIE', 'OTIS', 'JUN',
                           'MARK', 'LINA', 'JOHNNY',
                           'CNEE', 'SHIPPER', 'AGENT', 'INTERNAL'):
            count += 1
            continue

        # Copy to NELSON/ for processing
        dest = nelson_dir / f.name
        if not dest.exists():
            shutil.copy2(str(f), str(dest))
            count += 1
            print(f"  Copied → NELSON/{f.name}")
        else:
            count += 1

    return count


def run_test():
    """Run the full pipeline test."""
    print("=" * 60)
    print("  EMAIL INTELLIGENCE PIPELINE — TEST")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Find .msg files
    print("─" * 40)
    print("  STEP 1: Find test .msg files")
    print("─" * 40)
    msg_files = find_test_msg_files()
    print(f"  Found {len(msg_files)} .msg files in outlook/")
    if not msg_files:
        print("  ❌ No .msg files found! Place some .msg files in outlook/ and try again.")
        return

    # Step 2: Prepare test files
    print()
    print("─" * 40)
    print("  STEP 2: Prepare test files")
    print("─" * 40)
    prepared = setup_test_files(msg_files)
    print(f"  Prepared {prepared} files for processing")

    # Step 3: Init DB + Run data collector
    print()
    print("─" * 40)
    print("  STEP 3: Run DataCollector")
    print("─" * 40)
    from data_collector import DataCollector

    collector = DataCollector()
    collector.init_db()
    print("  ✅ Database initialized")

    stats = collector.scan_msg_files()
    print(f"  Scan results: {stats}")

    # Step 4: Query DB stats
    print()
    print("─" * 40)
    print("  STEP 4: Database Statistics")
    print("─" * 40)
    if not DB_PATH.exists():
        print("  ❌ Database not found!")
        return

    from shared.db_connect import get_db
    conn = get_db(DB_PATH, readonly=True)

    # email_events
    total_events = conn.execute("SELECT COUNT(*) FROM email_events").fetchone()[0]
    print(f"  email_events:   {total_events} rows")

    # By type
    type_counts = conn.execute(
        "SELECT email_type, COUNT(*) FROM email_events GROUP BY email_type"
    ).fetchall()
    for etype, cnt in type_counts:
        print(f"    - {etype}: {cnt}")

    # shipments
    total_shipments = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
    active_shipments = conn.execute(
        "SELECT COUNT(*) FROM shipments WHERE is_complete=0"
    ).fetchone()[0]
    complete_shipments = conn.execute(
        "SELECT COUNT(*) FROM shipments WHERE is_complete=1"
    ).fetchone()[0]
    print(f"  shipments:      {total_shipments} total ({active_shipments} active, {complete_shipments} complete)")

    # Unique shipment keys
    unique_keys = conn.execute(
        "SELECT COUNT(DISTINCT shipment_key) FROM email_events WHERE shipment_key IS NOT NULL"
    ).fetchone()[0]
    print(f"  unique keys:    {unique_keys}")

    # sales_replies
    total_replies = conn.execute("SELECT COUNT(*) FROM sales_replies").fetchone()[0]
    intent_counts = conn.execute(
        "SELECT intent, COUNT(*) FROM sales_replies GROUP BY intent"
    ).fetchall()
    print(f"  sales_replies:  {total_replies} total")
    for intent, cnt in intent_counts:
        print(f"    - {intent}: {cnt}")

    # alerts
    total_alerts = conn.execute("SELECT COUNT(*) FROM nelson_alerts").fetchone()[0]
    alert_by_level = conn.execute(
        "SELECT risk_level, COUNT(*) FROM nelson_alerts GROUP BY risk_level"
    ).fetchall()
    print(f"  nelson_alerts:  {total_alerts} total")
    for level, cnt in alert_by_level:
        print(f"    - {level}: {cnt}")

    # customers
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    print(f"  customers:      {total_customers}")

    conn.close()

    # Step 5: Generate briefing
    print()
    print("─" * 40)
    print("  STEP 5: Generate Nelson Briefing")
    print("─" * 40)
    from nelson_briefing import generate
    briefing_path = generate()
    if briefing_path:
        print(f"  ✅ Briefing: {briefing_path}")
    else:
        print("  ⚠️  Briefing generation returned None (check logs)")

    # Final report
    print()
    print("=" * 60)
    print("  PIPELINE TEST COMPLETE")
    print("=" * 60)
    print(f"  email_events:  {total_events} rows")
    print(f"  shipments:     {active_shipments} active, {complete_shipments} complete")
    print(f"  sales_replies: {total_replies} ({', '.join(f'{i}: {c}' for i, c in intent_counts)})")
    print(f"  alerts:        {total_alerts} ({', '.join(f'{l}: {c}' for l, c in alert_by_level)})")
    print(f"  customers:     {total_customers}")
    if briefing_path:
        print(f"  Briefing:      {briefing_path}")
    print("=" * 60)


if __name__ == '__main__':
    run_test()
