"""
queue_store.py — SQLite Queue Store cho Email Batch Send (Phase 01)
====================================================================
Atomic SQLite queue với WAL mode, supports:
- enqueue_batch: bulk insert với UNIQUE (cnee_email, batch_id)
- pop_one: atomic pop theo TIER priority + priority_score
- mark_sent / mark_failed: state transitions
- reset_stuck: recovery khi worker chết mid-batch
- kill_switch_active: KILL_SWITCH.flag presence check
- get_batch_status: progress polling cho dashboard

Schema: see SCHEMA_SQL constant.
DB default path: email_engine/data/outlook_queue.db
Kill switch: email_engine/data/KILL_SWITCH.flag (sự tồn tại = stop)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
DEFAULT_DB_PATH = str(_HERE / "data" / "outlook_queue.db")
KILL_SWITCH_PATH = str(_HERE / "data" / "KILL_SWITCH.flag")

# Tier priority — VIP first. Used in pop_one ORDER BY.
TIER_PRIORITY = {
    "VIP": 1,
    "HOT": 2,
    "WARM_A": 3,
    "WARM_B": 4,
    "COOL": 5,
}
DEFAULT_TIER_RANK = 99

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS email_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    cnee_email      TEXT NOT NULL,
    subject         TEXT NOT NULL,
    html_body       TEXT NOT NULL,
    cc              TEXT,
    tier            TEXT,
    priority_score  INTEGER DEFAULT 0,
    campaign_id     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    error_message   TEXT,
    enqueued_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    picked_at       TIMESTAMP,
    sent_at         TIMESTAMP,
    worker_id       TEXT,
    meta_json       TEXT,
    UNIQUE(cnee_email, batch_id)
);
CREATE INDEX IF NOT EXISTS idx_queue_status_priority
    ON email_queue(status, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_queue_batch
    ON email_queue(batch_id);
CREATE INDEX IF NOT EXISTS idx_queue_picked
    ON email_queue(status, picked_at);
"""

# Resolved DB path (set by init_db). Tests pass tmp paths; production uses default.
_DB_PATH: str = DEFAULT_DB_PATH
_DB_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with WAL + sane timeouts. New connection per call
    so it's safe across threads."""
    path = db_path or _DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL + reasonable durability
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(db_path: str | None = None) -> None:
    """Create schema + WAL mode. Idempotent. If db_path passed, sets the
    module-level default (used by worker + tests)."""
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _connect(_DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)


def enqueue_batch(batch_id: str, emails: list[dict[str, Any]]) -> int:
    """Bulk insert emails. Returns count actually queued (skips duplicates).

    Each email dict expects:
      cnee_email (required), subject (required), html_body (required),
      cc (optional, str or list), tier (optional), priority_score (optional int),
      campaign_id (optional), meta_json (optional dict|str), max_attempts (optional int)
    """
    if not emails:
        return 0

    rows = []
    now = _now_iso()
    for em in emails:
        cc_raw = em.get("cc")
        if isinstance(cc_raw, list):
            cc_val = ";".join(cc_raw) if cc_raw else None
        else:
            cc_val = cc_raw

        meta = em.get("meta_json")
        if isinstance(meta, (dict, list)):
            meta = json.dumps(meta, ensure_ascii=False)

        rows.append((
            batch_id,
            em["cnee_email"],
            em["subject"],
            em["html_body"],
            cc_val,
            em.get("tier"),
            int(em.get("priority_score") or 0),
            em.get("campaign_id"),
            "pending",
            0,
            int(em.get("max_attempts") or 3),
            now,
            meta,
        ))

    inserted = 0
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.cursor()
            for row in rows:
                try:
                    cur.execute(
                        """INSERT INTO email_queue
                           (batch_id, cnee_email, subject, html_body, cc,
                            tier, priority_score, campaign_id, status,
                            attempts, max_attempts, enqueued_at, meta_json)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        row,
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # Duplicate (cnee_email, batch_id) — skip silently
                    continue
    return inserted


def pop_one(worker_id: str) -> dict[str, Any] | None:
    """Atomically pop highest-priority pending job.

    Order: TIER rank ASC (VIP=1 first), then priority_score DESC, then id ASC.
    Sets status='sending', picked_at=now, worker_id=worker_id.

    Returns dict (full row) or None if queue empty / kill switch active.
    """
    if kill_switch_active():
        return None

    # Build CASE expression for tier ordering
    tier_case_parts = " ".join(
        f"WHEN '{t}' THEN {rank}" for t, rank in TIER_PRIORITY.items()
    )
    tier_case = f"CASE tier {tier_case_parts} ELSE {DEFAULT_TIER_RANK} END"

    with _DB_LOCK:
        with _connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    f"""SELECT * FROM email_queue
                        WHERE status = 'pending'
                        ORDER BY {tier_case} ASC,
                                 priority_score DESC,
                                 id ASC
                        LIMIT 1"""
                ).fetchone()

                if row is None:
                    conn.execute("COMMIT")
                    return None

                conn.execute(
                    """UPDATE email_queue
                       SET status='sending', picked_at=?, worker_id=?
                       WHERE id=? AND status='pending'""",
                    (_now_iso(), worker_id, row["id"]),
                )
                conn.execute("COMMIT")
                return dict(row) | {"status": "sending",
                                    "worker_id": worker_id}
            except Exception:
                conn.execute("ROLLBACK")
                raise


def mark_sent(job_id: int) -> None:
    """Mark job as successfully sent."""
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """UPDATE email_queue
                   SET status='sent', sent_at=?, error_message=NULL
                   WHERE id=?""",
                (_now_iso(), job_id),
            )


def mark_failed(job_id: int, error: str) -> None:
    """Increment attempts; re-pending if attempts<max, else permanent failed."""
    with _DB_LOCK:
        with _connect() as conn:
            row = conn.execute(
                "SELECT attempts, max_attempts FROM email_queue WHERE id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            new_attempts = (row["attempts"] or 0) + 1
            new_status = "pending" if new_attempts < (row["max_attempts"] or 3) else "failed"
            conn.execute(
                """UPDATE email_queue
                   SET attempts=?, status=?, error_message=?, picked_at=NULL,
                       worker_id=NULL
                   WHERE id=?""",
                (new_attempts, new_status, error[:1000], job_id),
            )


def get_batch_status(batch_id: str) -> dict[str, Any]:
    """Aggregate counts + ETA for a batch_id."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) AS n
                 FROM email_queue
                WHERE batch_id=?
                GROUP BY status""",
            (batch_id,),
        ).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        total = sum(counts.values())

        meta = conn.execute(
            """SELECT MIN(enqueued_at) AS started_at,
                      MIN(picked_at)   AS first_pick,
                      MAX(sent_at)     AS last_sent,
                      COUNT(*) FILTER (WHERE status='sent') AS sent_count
                 FROM email_queue
                WHERE batch_id=?""",
            (batch_id,),
        ).fetchone()

    sent = counts.get("sent", 0)
    pending = counts.get("pending", 0)
    sending = counts.get("sending", 0)
    failed = counts.get("failed", 0)

    rate_per_min = 0.0
    eta_finish = None
    started_at = meta["first_pick"] or meta["started_at"]
    if sent > 0 and meta["first_pick"] and meta["last_sent"]:
        try:
            t0 = datetime.strptime(meta["first_pick"], "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(meta["last_sent"], "%Y-%m-%d %H:%M:%S")
            elapsed_min = max((t1 - t0).total_seconds() / 60.0, 0.001)
            rate_per_min = round(sent / elapsed_min, 2)
            remaining = pending + sending
            if rate_per_min > 0 and remaining > 0:
                eta_min = remaining / rate_per_min
                eta_finish = (datetime.utcnow() + timedelta(minutes=eta_min)) \
                    .strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            pass

    return {
        "batch_id": batch_id,
        "total": total,
        "pending": pending,
        "sending": sending,
        "sent": sent,
        "failed": failed,
        "started_at": started_at,
        "rate_per_min": rate_per_min,
        "eta_finish": eta_finish,
    }


def reset_stuck(older_than_min: int = 10) -> int:
    """Reset jobs stuck in 'sending' state. Returns rows affected."""
    cutoff = (datetime.utcnow() - timedelta(minutes=older_than_min)) \
        .strftime("%Y-%m-%d %H:%M:%S")
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """UPDATE email_queue
                   SET status='pending', picked_at=NULL, worker_id=NULL
                   WHERE status='sending' AND picked_at IS NOT NULL
                     AND picked_at < ?""",
                (cutoff,),
            )
            return cur.rowcount or 0


def kill_switch_active(flag_path: str | None = None) -> bool:
    """True when KILL_SWITCH.flag file exists."""
    return os.path.exists(flag_path or KILL_SWITCH_PATH)


# ---------------------------------------------------------------------------
# CLI helper (for ops debugging)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Queue store CLI")
    parser.add_argument("--init", action="store_true", help="Initialize DB")
    parser.add_argument("--status", metavar="BATCH_ID",
                        help="Show batch status JSON")
    parser.add_argument("--reset-stuck", type=int, default=0,
                        metavar="MIN", help="Reset stuck jobs older than N min")
    parser.add_argument("--db", default=None, help="DB path override")
    args = parser.parse_args()

    init_db(args.db)
    if args.init:
        print(f"Initialized DB at {_DB_PATH}")
    if args.status:
        print(json.dumps(get_batch_status(args.status), indent=2))
    if args.reset_stuck > 0:
        n = reset_stuck(args.reset_stuck)
        print(f"Reset {n} stuck job(s)")
