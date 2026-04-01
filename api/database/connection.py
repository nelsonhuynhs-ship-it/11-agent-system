# -*- coding: utf-8 -*-
"""
connection.py — PostgreSQL Connection Pool
=============================================
Async connection pool using asyncpg (for FastAPI async endpoints).
Sync fallback using psycopg2 (for workers and scripts).

Config via DATABASE_URL environment variable:
    postgresql://user:password@host:5432/nelson_freight

If DATABASE_URL is not set, PostgreSQL features are disabled
and the system falls back to JSON file backend.
"""
import logging
import os
from typing import Optional

log = logging.getLogger("nelson.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# ── Sync Connection (psycopg2) ───────────────────────────────────────────────

_sync_pool = None


def get_sync_connection():
    """
    Get a synchronous PostgreSQL connection (psycopg2).
    Used by: workers, migration scripts, CLI tools.
    """
    global _sync_pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set — PostgreSQL not configured")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from psycopg2.pool import ThreadedConnectionPool

        if _sync_pool is None:
            _sync_pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=DATABASE_URL,
            )
            log.info("PostgreSQL sync pool created (1-5 connections)")

        conn = _sync_pool.getconn()
        conn.autocommit = False
        return conn

    except ImportError:
        raise RuntimeError("psycopg2 not installed: pip install psycopg2-binary")


def release_sync_connection(conn):
    """Return connection to pool."""
    if _sync_pool and conn:
        _sync_pool.putconn(conn)


def execute_sync(query: str, params: tuple = None, fetch: bool = True) -> Optional[list]:
    """
    Execute a sync query and return results as list of dicts.
    Auto-commits on success, rolls back on failure.
    """
    conn = get_sync_connection()
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch and cur.description:
                result = [dict(row) for row in cur.fetchall()]
            else:
                result = None
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        log.error("Query failed: %s — %s", query[:100], e)
        raise
    finally:
        release_sync_connection(conn)


# ── Async Connection (asyncpg) ───────────────────────────────────────────────

_async_pool = None


async def get_async_pool():
    """
    Get async connection pool (asyncpg).
    Used by: FastAPI async endpoints.
    """
    global _async_pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set — PostgreSQL not configured")

    if _async_pool is None:
        try:
            import asyncpg
            _async_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            log.info("PostgreSQL async pool created (2-10 connections)")
        except ImportError:
            raise RuntimeError("asyncpg not installed: pip install asyncpg")

    return _async_pool


async def execute_async(query: str, *args, fetch: bool = True):
    """Execute async query. Returns list of Record objects."""
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        if fetch:
            return await conn.fetch(query, *args)
        else:
            return await conn.execute(query, *args)


# ── Utilities ─────────────────────────────────────────────────────────────────

def is_postgres_configured() -> bool:
    """Check if DATABASE_URL is set."""
    return bool(DATABASE_URL)


def run_migrations():
    """Run all SQL migration files in order."""
    if not is_postgres_configured():
        log.warning("DATABASE_URL not set — skipping migrations")
        return

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    if not os.path.isdir(migrations_dir):
        log.warning("Migrations directory not found: %s", migrations_dir)
        return

    sql_files = sorted(
        f for f in os.listdir(migrations_dir)
        if f.endswith(".sql")
    )

    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            for sql_file in sql_files:
                path = os.path.join(migrations_dir, sql_file)
                log.info("Running migration: %s", sql_file)
                with open(path, "r", encoding="utf-8") as f:
                    cur.execute(f.read())
            conn.commit()
            log.info("All %d migrations completed", len(sql_files))
    except Exception as e:
        conn.rollback()
        log.error("Migration failed: %s", e)
        raise
    finally:
        release_sync_connection(conn)


async def close_pools():
    """Close all connection pools (call on shutdown)."""
    global _async_pool, _sync_pool
    if _async_pool:
        await _async_pool.close()
        _async_pool = None
    if _sync_pool:
        _sync_pool.closeall()
        _sync_pool = None
    log.info("Database pools closed")
