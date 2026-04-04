# Phase 3: Enable SQLite WAL Mode

## Context
- CONCERNS.md ghi: multiple scripts write to `shipments.db` simultaneously
- Outlook scanner + data_collector.py + main.py đều write cùng DB
- Không WAL → lock contention → silent data loss hoặc crash

## Overview
- **Priority:** P1
- **Status:** ⬜ TODO
- **Description:** Enable WAL (Write-Ahead Logging) cho tất cả SQLite connections, thêm busy_timeout

## Key Insights
- WAL mode cho phép concurrent reads + 1 writer (thay vì exclusive lock)
- `PRAGMA journal_mode=WAL` chỉ cần set 1 lần per database file — persists
- `PRAGMA busy_timeout=5000` → writer đợi 5s thay vì fail ngay
- Không cần thay đổi logic code, chỉ thêm 2 dòng PRAGMA sau connection

## Requirements

### Functional
- Tất cả SQLite connections phải set WAL + busy_timeout
- Centralize connection factory để không lặp code
- Backward compatible — WAL tương thích mọi SQLite >= 3.7

### Non-functional
- Performance improvement: concurrent reads không bị block
- Data integrity: giảm `database is locked` errors

## Related Code Files
- **Search:** Tất cả file `.py` có `sqlite3.connect` hoặc `import sqlite3`
- **Create:** `shared/db_connect.py` — centralized SQLite connection factory
- **Modify:** Mọi file dùng sqlite3 trực tiếp

## Architecture
```
Before:                          After:
script_a.py → sqlite3.connect   script_a.py → shared.db_connect.get_db()
script_b.py → sqlite3.connect   script_b.py → shared.db_connect.get_db()
  ↓ EXCLUSIVE LOCK                ↓ WAL MODE
  ❌ database locked              ✅ concurrent reads, serialized writes
```

## Implementation Steps

### Step 1: Create shared/db_connect.py
```python
"""Centralized SQLite connection with WAL + busy_timeout."""
import sqlite3
from pathlib import Path

def get_db(db_path: Path | str, readonly: bool = False) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro" if readonly else str(db_path)
    conn = sqlite3.connect(uri, uri=readonly, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn
```

### Step 2: Find & replace all sqlite3.connect calls
- Grep `sqlite3.connect` across codebase
- Replace with `from shared.db_connect import get_db`

### Step 3: Verify
- Run affected scripts
- Check `.db-wal` and `.db-shm` files appear next to .db files

## Todo
- [ ] Grep all sqlite3.connect usages
- [ ] Create shared/db_connect.py
- [ ] Replace all direct sqlite3.connect calls
- [ ] Test concurrent writes (2 scripts simultaneously)
- [ ] Verify WAL files created

## Success Criteria
- Zero `database is locked` errors in concurrent scenarios
- `.db-wal` files exist alongside `.db` files
- All scripts use shared.db_connect.get_db()

## Risk Assessment
- **LOW risk:** WAL is backward compatible, no data migration needed
- **Edge case:** NFS/network drives don't support WAL — but all our DBs are local/VPS → OK
- **VPS Docker:** SQLite inside Docker container → WAL works fine on overlay2 filesystem

## Next Steps
- Monitor for any remaining lock errors in logs after deployment
