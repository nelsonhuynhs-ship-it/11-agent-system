"""xlsx_lock.py — Global file lock wrapper for xlsx operations.

Prevents concurrent write corruption between:
- migrate-to-unified-v6.py
- scan-sent-outlook.py --update-master
- rotation_engine.py (read via load_master_df)
- web_server.py _get_cnee_df (read)
- contacts_router.py (read/write)
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

LOCK_TIMEOUT_SEC = 60


@contextmanager
def xlsx_write_lock(xlsx_path: str | Path):
    """Exclusive lock for WRITE operations. Blocks readers."""
    lock_path = str(xlsx_path) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT_SEC)
    try:
        with lock:
            yield
    except Timeout:
        raise RuntimeError(f"xlsx_write_lock timeout ({LOCK_TIMEOUT_SEC}s) on {xlsx_path}")


@contextmanager
def xlsx_read_lock(xlsx_path: str | Path):
    """Shared lock for READ. Blocks if writer is holding lock."""
    lock_path = str(xlsx_path) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT_SEC)
    try:
        with lock:
            yield
    except Timeout:
        raise RuntimeError(f"xlsx_read_lock timeout ({LOCK_TIMEOUT_SEC}s) on {xlsx_path}")
