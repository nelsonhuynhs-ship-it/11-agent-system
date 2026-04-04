# -*- coding: utf-8 -*-
"""
shared/db_connect.py — Centralized SQLite connection with WAL + busy_timeout.
=============================================================================
All modules should use get_db() instead of sqlite3.connect() directly.
WAL mode enables concurrent reads + serialized writes (no more "database is locked").

Usage:
    from shared.db_connect import get_db
    conn = get_db("/path/to/db.sqlite")
    # or read-only:
    conn = get_db("/path/to/db.sqlite", readonly=True)
"""
import sqlite3
from pathlib import Path


def get_db(
    db_path: str | Path,
    readonly: bool = False,
    timeout: float = 10.0,
    row_factory: bool = True,
) -> sqlite3.Connection:
    """Open SQLite connection with WAL journal mode and busy timeout.

    Args:
        db_path: Path to the SQLite database file.
        readonly: If True, open in read-only mode (URI mode).
        timeout: Connection timeout in seconds (default 10s).
        row_factory: If True, set row_factory to sqlite3.Row for dict-like access.

    Returns:
        sqlite3.Connection configured with WAL + busy_timeout.
    """
    db_path = str(db_path)

    if readonly:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
    else:
        conn = sqlite3.connect(db_path, timeout=timeout)

    # WAL mode: concurrent reads, serialized writes — persists per db file
    conn.execute("PRAGMA journal_mode=WAL")
    # Wait up to 5s if another writer holds the lock
    conn.execute("PRAGMA busy_timeout=5000")

    if row_factory:
        conn.row_factory = sqlite3.Row

    return conn
