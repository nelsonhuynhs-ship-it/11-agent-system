"""
memory.py — SQLite event store + query helpers (Phase 02)
==========================================================
Append-only event log per CNEE. WAL mode, short transactions,
indexes tuned for (cnee_email, time DESC) timeline + (event_type, time DESC)
recency scans.

Public API:
    init_db(db_path=None)           -- create schema, set module default
    log_event(event)                -- insert one event, returns row id
    log_events_bulk(events)         -- batched transaction insert (backfill)
    get_timeline(cnee, limit=20)    -- DESC chain of events
    get_cnee_summary(cnee)          -- aggregate dict for dashboards / GoClaw
    get_stale(days=7, tier=None)    -- CNEEs sent > N days ago, no reply since
    count_events(event_type, ...)   -- counter for alerts
    recent_events(event_type, ...)  -- recent feed for scanner UI
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .events import (
    EVENT_TYPES, SENT, REPLY, AUTO_REPLY, BOUNCE,
)

# ---------------------------------------------------------------------------
# Paths + module state
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent           # email_engine/intel
_PKG = _HERE.parent                               # email_engine
DEFAULT_DB_PATH = str(_PKG / "data" / "intel.db")
SCHEMA_PATH = str(_HERE / "schema.sql")

_DB_PATH: str = DEFAULT_DB_PATH
_DB_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path,
        timeout=30.0,
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce one event dict into the column shape."""
    if "event_type" not in event:
        raise ValueError("event missing event_type")
    if event["event_type"] not in EVENT_TYPES:
        raise ValueError(f"unknown event_type: {event['event_type']}")
    if "cnee_email" not in event or not event["cnee_email"]:
        raise ValueError("event missing cnee_email")

    cnee = (event.get("cnee_email") or "").strip().lower()

    raw_meta = event.get("raw_meta")
    if isinstance(raw_meta, (dict, list)):
        raw_meta = json.dumps(raw_meta, ensure_ascii=False)

    snippet = event.get("reply_body_snippet")
    if snippet is not None:
        snippet = str(snippet)[:500]

    return {
        "cnee_email": cnee,
        "event_type": event["event_type"],
        "timestamp": event.get("timestamp") or _now_iso(),
        "subject": event.get("subject"),
        "template_id": event.get("template_id"),
        "market_state": event.get("market_state"),
        "delta_pct": event.get("delta_pct"),
        "batch_id": event.get("batch_id"),
        "campaign_id": event.get("campaign_id"),
        "reply_subject": event.get("reply_subject"),
        "reply_body_snippet": snippet,
        "sentiment": event.get("sentiment"),
        "intent": event.get("intent"),
        "reply_delay_hours": event.get("reply_delay_hours"),
        "bounce_type": event.get("bounce_type"),
        "bounce_reason": event.get("bounce_reason"),
        "old_tier": event.get("old_tier"),
        "new_tier": event.get("new_tier"),
        "change_reason": event.get("change_reason"),
        "raw_meta": raw_meta,
    }


_INSERT_COLS = (
    "cnee_email,event_type,timestamp,subject,template_id,market_state,"
    "delta_pct,batch_id,campaign_id,reply_subject,reply_body_snippet,"
    "sentiment,intent,reply_delay_hours,bounce_type,bounce_reason,"
    "old_tier,new_tier,change_reason,raw_meta"
)
_INSERT_PLACEHOLDERS = ",".join(["?"] * 20)
_INSERT_SQL = f"INSERT INTO email_events ({_INSERT_COLS}) VALUES ({_INSERT_PLACEHOLDERS})"


def _row_tuple(e: dict[str, Any]) -> tuple:
    return (
        e["cnee_email"], e["event_type"], e["timestamp"],
        e.get("subject"), e.get("template_id"), e.get("market_state"),
        e.get("delta_pct"), e.get("batch_id"), e.get("campaign_id"),
        e.get("reply_subject"), e.get("reply_body_snippet"),
        e.get("sentiment"), e.get("intent"), e.get("reply_delay_hours"),
        e.get("bounce_type"), e.get("bounce_reason"),
        e.get("old_tier"), e.get("new_tier"), e.get("change_reason"),
        e.get("raw_meta"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(db_path: str | None = None) -> None:
    """Create schema + WAL. Idempotent. Sets module default if path given."""
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    schema = Path(SCHEMA_PATH).read_text(encoding="utf-8")
    with _DB_LOCK:
        with _connect(_DB_PATH) as conn:
            conn.executescript(schema)


def log_event(event: dict[str, Any]) -> int:
    """Insert one event. Returns auto-incremented id."""
    norm = _normalize_event(event)
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(_INSERT_SQL, _row_tuple(norm))
            event_id = cur.lastrowid
            _bump_state(conn, norm)
    return int(event_id or 0)


def log_events_bulk(events: Iterable[dict[str, Any]]) -> int:
    """Bulk insert in a single transaction. Returns rows inserted.
    Used by backfill (~17K rows)."""
    payload = [_row_tuple(_normalize_event(e)) for e in events]
    if not payload:
        return 0
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute("BEGIN")
            try:
                conn.executemany(_INSERT_SQL, payload)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    return len(payload)


def _bump_state(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    """Update cnee_state cache (bounce_count, unsubscribed). Safe to skip if
    table missing (e.g. legacy db). Authoritative count remains email_events."""
    et = event["event_type"]
    cnee = event["cnee_email"]
    if et == BOUNCE and (event.get("bounce_type") or "HARD").upper() == "HARD":
        conn.execute(
            """INSERT INTO cnee_state(cnee_email, bounce_count, updated_at)
               VALUES(?, 1, ?)
               ON CONFLICT(cnee_email) DO UPDATE SET
                   bounce_count = bounce_count + 1,
                   updated_at = excluded.updated_at""",
            (cnee, _now_iso()),
        )
    elif et == "UNSUBSCRIBE":
        conn.execute(
            """INSERT INTO cnee_state(cnee_email, unsubscribed, updated_at)
               VALUES(?, 1, ?)
               ON CONFLICT(cnee_email) DO UPDATE SET
                   unsubscribed = 1,
                   updated_at = excluded.updated_at""",
            (cnee, _now_iso()),
        )
    elif et in ("TIER_PROMOTED", "TIER_DEMOTED"):
        conn.execute(
            """INSERT INTO cnee_state(cnee_email, last_tier_change_at, updated_at)
               VALUES(?, ?, ?)
               ON CONFLICT(cnee_email) DO UPDATE SET
                   last_tier_change_at = excluded.last_tier_change_at,
                   updated_at = excluded.updated_at""",
            (cnee, _now_iso(), _now_iso()),
        )


def get_timeline(cnee_email: str, limit: int = 20) -> list[dict[str, Any]]:
    """DESC timeline of events for one CNEE. Returns list of dicts."""
    cnee = (cnee_email or "").strip().lower()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM email_events
                WHERE cnee_email = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?""",
            (cnee, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def get_cnee_summary(cnee_email: str) -> dict[str, Any]:
    """Aggregate snapshot for dashboards / templates / GoClaw context."""
    cnee = (cnee_email or "").strip().lower()
    with _connect() as conn:
        agg = conn.execute(
            """SELECT
                 SUM(CASE WHEN event_type = 'SENT' THEN 1 ELSE 0 END)        AS total_sent,
                 SUM(CASE WHEN event_type IN ('REPLY','AUTO_REPLY') THEN 1 ELSE 0 END)
                                                                              AS total_replied,
                 SUM(CASE WHEN event_type = 'BOUNCE' THEN 1 ELSE 0 END)      AS total_bounced,
                 MAX(CASE WHEN event_type = 'SENT' THEN timestamp END)       AS last_sent_at,
                 MAX(CASE WHEN event_type IN ('REPLY','AUTO_REPLY') THEN timestamp END)
                                                                              AS last_reply_at,
                 AVG(reply_delay_hours)                                       AS avg_reply_delay_hours
                 FROM email_events WHERE cnee_email = ?""",
            (cnee,),
        ).fetchone()

        last_sent = conn.execute(
            """SELECT subject FROM email_events
                WHERE cnee_email = ? AND event_type = 'SENT'
                ORDER BY timestamp DESC LIMIT 1""",
            (cnee,),
        ).fetchone()
        last_reply = conn.execute(
            """SELECT reply_body_snippet FROM email_events
                WHERE cnee_email = ? AND event_type IN ('REPLY','AUTO_REPLY')
                ORDER BY timestamp DESC LIMIT 1""",
            (cnee,),
        ).fetchone()
        last_tier = conn.execute(
            """SELECT new_tier, change_reason FROM email_events
                WHERE cnee_email = ?
                  AND event_type IN ('TIER_PROMOTED','TIER_DEMOTED')
                ORDER BY timestamp DESC LIMIT 1""",
            (cnee,),
        ).fetchone()
        intents = conn.execute(
            """SELECT intent, COUNT(*) AS n FROM email_events
                WHERE cnee_email = ?
                  AND event_type IN ('REPLY','AUTO_REPLY')
                  AND intent IS NOT NULL AND intent <> ''
                GROUP BY intent""",
            (cnee,),
        ).fetchall()

    sent = int(agg["total_sent"] or 0)
    replied = int(agg["total_replied"] or 0)
    bounced = int(agg["total_bounced"] or 0)

    days_since = None
    last_reply_at = agg["last_reply_at"]
    if last_reply_at:
        try:
            t = datetime.strptime(last_reply_at, "%Y-%m-%d %H:%M:%S")
            days_since = max((datetime.utcnow() - t).days, 0)
        except (TypeError, ValueError):
            days_since = None

    reply_rate = round(replied / sent, 4) if sent else 0.0

    return {
        "cnee_email": cnee,
        "total_sent": sent,
        "total_replied": replied,
        "total_bounced": bounced,
        "last_sent_at": agg["last_sent_at"],
        "last_reply_at": last_reply_at,
        "days_since_last_reply": days_since,
        "avg_reply_delay_hours": (
            round(float(agg["avg_reply_delay_hours"]), 2)
            if agg["avg_reply_delay_hours"] is not None else None
        ),
        "last_subject": last_sent["subject"] if last_sent else None,
        "last_reply_snippet": last_reply["reply_body_snippet"] if last_reply else None,
        "reply_rate": reply_rate,
        "current_tier": last_tier["new_tier"] if last_tier else None,
        "current_action": None,  # action lives in master v2; resolve in writeback layer
        "intent_distribution": {r["intent"]: r["n"] for r in intents},
    }


def get_stale(days: int = 7, tier: str | None = None) -> list[dict[str, Any]]:
    """Return CNEEs that received SENT > `days` days ago AND no REPLY since.

    Returns rows {cnee_email, last_sent_at, last_reply_at, days_since_sent}.
    Optional `tier` filters by latest TIER_PROMOTED/DEMOTED's new_tier — kept
    optional because the source of truth tier really lives in master v2; we use
    the event log's last tier change as a best-effort proxy.
    """
    cutoff = (datetime.utcnow() - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        # last_sent / last_reply per cnee
        rows = conn.execute(
            """SELECT cnee_email,
                      MAX(CASE WHEN event_type='SENT' THEN timestamp END) AS last_sent_at,
                      MAX(CASE WHEN event_type IN ('REPLY','AUTO_REPLY') THEN timestamp END)
                                                                          AS last_reply_at
                 FROM email_events
                GROUP BY cnee_email"""
        ).fetchall()

        tier_map: dict[str, str] = {}
        if tier is not None:
            tier_rows = conn.execute(
                """SELECT cnee_email, new_tier
                     FROM (SELECT cnee_email, new_tier, timestamp,
                                  ROW_NUMBER() OVER (PARTITION BY cnee_email
                                                     ORDER BY timestamp DESC, id DESC) AS rn
                             FROM email_events
                            WHERE event_type IN ('TIER_PROMOTED','TIER_DEMOTED'))
                    WHERE rn = 1"""
            ).fetchall()
            tier_map = {r["cnee_email"]: r["new_tier"] for r in tier_rows}

    out: list[dict[str, Any]] = []
    for r in rows:
        last_sent = r["last_sent_at"]
        last_reply = r["last_reply_at"]
        if not last_sent:
            continue
        if last_sent >= cutoff:
            continue   # sent within window — not stale
        if last_reply and last_reply > last_sent:
            continue   # already replied since last send
        if tier is not None and tier_map.get(r["cnee_email"]) != tier:
            continue
        try:
            t = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S")
            days_since_sent = (datetime.utcnow() - t).days
        except (TypeError, ValueError):
            days_since_sent = None
        out.append({
            "cnee_email": r["cnee_email"],
            "last_sent_at": last_sent,
            "last_reply_at": last_reply,
            "days_since_sent": days_since_sent,
        })
    return out


def count_events(
    event_type: str,
    cnee_email: str | None = None,
    since_days: int | None = None,
) -> int:
    """Count events matching filters. Cheap counter for alerts."""
    where = ["event_type = ?"]
    params: list[Any] = [event_type]
    if cnee_email:
        where.append("cnee_email = ?")
        params.append(cnee_email.strip().lower())
    if since_days is not None:
        cutoff = (datetime.utcnow() - timedelta(days=int(since_days))).strftime("%Y-%m-%d %H:%M:%S")
        where.append("timestamp >= ?")
        params.append(cutoff)
    sql = f"SELECT COUNT(*) AS n FROM email_events WHERE {' AND '.join(where)}"
    with _connect() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    return int(row["n"] or 0)


def query_events(
    days: int = 7,
    limit: int = 100,
    types: list | None = None,
) -> list[dict[str, Any]]:
    """Query email_events for dashboard alerts feed.

    Args:
        days: Look-back window in calendar days.
        limit: Max rows to return (sorted newest first).
        types: Filter event_type list. Default: BOUNCE, REPLY, AUTO_REPLY, UNSUBSCRIBE.
    """
    if types is None:
        types = ["BOUNCE", "REPLY", "AUTO_REPLY", "UNSUBSCRIBE"]
    cutoff = (datetime.utcnow() - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
    placeholders = ",".join("?" * len(types))
    sql = f"""
        SELECT id, cnee_email, event_type, timestamp,
               subject, reply_subject, reply_body_snippet,
               sentiment, intent, bounce_type, bounce_reason
        FROM email_events
        WHERE timestamp >= ?
          AND event_type IN ({placeholders})
        ORDER BY timestamp DESC
        LIMIT ?
    """
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(sql, [cutoff, *types, int(limit)]).fetchall()
    return [dict(r) for r in rows]


def recent_events(event_type: str, limit: int = 50) -> list[dict[str, Any]]:
    """Recent feed of one event type — useful for scanner UI / GoClaw queue."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM email_events
                WHERE event_type = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?""",
            (event_type, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def get_cnee_state(cnee_email: str) -> dict[str, Any]:
    """Return cached state row for a CNEE (bounce_count, unsubscribed,
    last_tier_change_at). Empty defaults if not seen yet."""
    cnee = (cnee_email or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cnee_state WHERE cnee_email = ?", (cnee,)
        ).fetchone()
    if row is None:
        return {
            "cnee_email": cnee,
            "bounce_count": 0,
            "unsubscribed": 0,
            "last_tier_change_at": None,
            "updated_at": None,
        }
    return dict(row)


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="intel.memory CLI")
    p.add_argument("--init", action="store_true")
    p.add_argument("--summary", metavar="EMAIL")
    p.add_argument("--stale", type=int, default=0, metavar="DAYS")
    p.add_argument("--db", default=None)
    args = p.parse_args()

    init_db(args.db)
    if args.init:
        print(f"intel.db initialized at {_DB_PATH}")
    if args.summary:
        print(json.dumps(get_cnee_summary(args.summary), indent=2))
    if args.stale > 0:
        rows = get_stale(args.stale)
        print(f"{len(rows)} stale CNEEs")
        for r in rows[:20]:
            print(r)
