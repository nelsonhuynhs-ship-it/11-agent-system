import sqlite3
from pathlib import Path

db = Path(r"D:\NELSON\2. Areas\Engine_test\email_engine\data\outlook_queue.db")
print(f"DB exists: {db.exists()} ({db.stat().st_size} bytes)")

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("\n=== ALL ROT_ BATCHES ===")
cur.execute(
    "SELECT batch_id, status, COUNT(*) as c, MIN(enqueued_at) as first, MAX(enqueued_at) as last "
    "FROM email_queue WHERE batch_id LIKE 'ROT_%' "
    "GROUP BY batch_id, status ORDER BY batch_id DESC LIMIT 30"
)
for r in cur.fetchall():
    print(f"  {r['batch_id']:<25} status={r['status']:<10} count={r['c']:<5} first={r['first']} last={r['last']}")

print("\n=== TODAY'S ROT BATCH (2026-04-25) ===")
cur.execute(
    "SELECT batch_id, status, COUNT(*) as c "
    "FROM email_queue "
    "WHERE enqueued_at >= '2026-04-25' "
    "GROUP BY batch_id, status"
)
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  {r['batch_id']} status={r['status']} count={r['c']}")
else:
    print("  NO ROWS ENQUEUED TODAY")

print("\n=== PENDING ROWS (any date) ===")
cur.execute("SELECT COUNT(*) as c FROM email_queue WHERE status='pending'")
print(f"  Total pending: {cur.fetchone()['c']}")

cur.execute("SELECT COUNT(*) as c FROM email_queue WHERE status='picked'")
print(f"  Total picked: {cur.fetchone()['c']}")

cur.execute("SELECT COUNT(*) as c FROM email_queue WHERE status='error'")
print(f"  Total error: {cur.fetchone()['c']}")

print("\n=== LAST 5 ROWS BY enqueued_at ===")
cur.execute(
    "SELECT batch_id, status, enqueued_at, sent_at, error_message "
    "FROM email_queue ORDER BY enqueued_at DESC LIMIT 5"
)
for r in cur.fetchall():
    err = (r['error_message'] or '')[:60]
    print(f"  enq={r['enqueued_at']} batch={r['batch_id']:<22} status={r['status']:<10} sent={r['sent_at']} err={err}")

conn.close()
