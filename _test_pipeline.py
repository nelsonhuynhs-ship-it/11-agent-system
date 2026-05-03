"""Test full rotation pipeline directly — NO background task, NO try/except hiding errors."""
import sys
import os
import traceback
from datetime import date

os.chdir(r"D:\NELSON\2. Areas\Engine_test")
sys.path.insert(0, r"D:\NELSON\2. Areas\Engine_test")
sys.path.insert(0, r"D:\NELSON\2. Areas\Engine_test\email_engine")

print("=== STEP 1: Import modules ===")
try:
    from email_engine.core.rotation_engine import build_daily_plan, queue_to_outlook_worker
    print("  [OK] Imports successful")
except Exception as e:
    print(f"  [FAIL] Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== STEP 2: build_daily_plan(force_build=True) ===")
try:
    plan = build_daily_plan(target_date=date.today(), force_build=True)
    print(f"  [OK] plan keys: {list(plan.keys())}")
    print(f"  date: {plan.get('date')}")
    print(f"  skipped_reason: {plan.get('skipped_reason')}")
    by_commodity = plan.get("by_commodity", {})
    print(f"  by_commodity count: {len(by_commodity)}")
    for cm, lst in list(by_commodity.items())[:3]:
        print(f"    {cm}: {len(lst)} rows")
    total = sum(len(v) for v in by_commodity.values())
    print(f"  TOTAL plan rows: {total}")
except Exception as e:
    print(f"  [FAIL] build_daily_plan error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== STEP 3: queue_to_outlook_worker(plan, user_markup=20) ===")
try:
    queued = queue_to_outlook_worker(plan, user_markup=20)
    print(f"  [RESULT] queued = {queued}")
except Exception as e:
    print(f"  [FAIL] queue_to_outlook_worker error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== STEP 4: Verify DB rows ===")
import sqlite3
conn = sqlite3.connect(r"D:\NELSON\2. Areas\Engine_test\email_engine\data\outlook_queue.db")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM email_queue WHERE enqueued_at >= '2026-04-25'")
print(f"  Today rows: {cur.fetchone()[0]}")
conn.close()
