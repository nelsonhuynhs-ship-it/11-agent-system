# -*- coding: utf-8 -*-
"""
ORACLE — Persistent memory layer for N.E.L.S.O.N v2.0
======================================================
Storage: SQLite (conversations + profiles + task queue)
Consumers: bot_v5.py, Sentinel, all agents

Usage:
    from memory.oracle import Oracle
    oracle = Oracle()
    oracle.remember(user_id, "user", "HCM to LAX 40HQ?")
    context = oracle.build_context(user_id)
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent
DB_PATH = MEMORY_DIR / "oracle.db"


class Oracle:
    """Persistent memory for conversations, customer profiles, and task queue."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    agent      TEXT,
                    ts         TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS customer_profiles (
                    user_id     TEXT PRIMARY KEY,
                    username    TEXT,
                    segment     TEXT DEFAULT 'unknown',
                    risk_level  TEXT DEFAULT 'normal',
                    deal_count  INTEGER DEFAULT 0,
                    top_route   TEXT,
                    last_seen   TEXT,
                    notes       TEXT
                );

                CREATE TABLE IF NOT EXISTS task_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type   TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    status      TEXT DEFAULT 'pending',
                    blocked_by  INTEGER,
                    created_at  TEXT DEFAULT (datetime('now')),
                    completed_at TEXT,
                    result      TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_conv_user
                    ON conversations(user_id, ts);
                CREATE INDEX IF NOT EXISTS idx_task_status
                    ON task_queue(status);
            """)
        log.info("[ORACLE] Database initialized: %s", self.db_path)

    # ── Conversation Memory ──────────────────────────────────────────────

    def remember(self, user_id: str, role: str,
                 content: str, agent: str = None):
        """Save one message turn."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO conversations(user_id, role, content, agent) "
                "VALUES (?, ?, ?, ?)",
                (str(user_id), role, content[:4000], agent)
            )

    def recall(self, user_id: str, limit: int = 10) -> list[dict]:
        """Last N turns for a user — for context injection."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT role, content, agent, ts FROM conversations "
                "WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
                (str(user_id), limit)
            ).fetchall()
        return [{"role": r, "content": c, "agent": a, "ts": t}
                for r, c, a, t in reversed(rows)]

    def forget(self, user_id: str) -> int:
        """Clear conversation history for a user. Returns count deleted."""
        with self._conn() as c:
            cursor = c.execute(
                "DELETE FROM conversations WHERE user_id = ?",
                (str(user_id),)
            )
            return cursor.rowcount

    # ── Customer Profiles ────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> dict:
        """Get customer profile."""
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM customer_profiles WHERE user_id = ?",
                (str(user_id),)
            ).fetchone()
        if not row:
            return {}
        cols = ["user_id", "username", "segment", "risk_level",
                "deal_count", "top_route", "last_seen", "notes"]
        return dict(zip(cols, row))

    def upsert_profile(self, user_id: str, **kwargs):
        """Update or create customer profile fields."""
        kwargs["last_seen"] = datetime.now().isoformat()
        existing = self.get_profile(user_id)
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            with self._conn() as c:
                c.execute(
                    f"UPDATE customer_profiles SET {sets} WHERE user_id = ?",
                    list(kwargs.values()) + [str(user_id)]
                )
        else:
            kwargs["user_id"] = str(user_id)
            cols = ", ".join(kwargs.keys())
            vals = ", ".join("?" * len(kwargs))
            with self._conn() as c:
                c.execute(
                    f"INSERT INTO customer_profiles({cols}) VALUES({vals})",
                    list(kwargs.values())
                )

    # ── Context Builder ──────────────────────────────────────────────────

    def build_context(self, user_id: str) -> str:
        """Returns a context string to prepend to agent prompts.
        
        Includes recent conversation turns so follow-up questions
        like 'Còn ONE?' have context from previous freetime/price answers.
        """
        history = self.recall(user_id, limit=12)
        profile = self.get_profile(user_id)
        lines = []

        if profile:
            lines.append(
                f"[Customer: {profile.get('username', '?')} | "
                f"Segment: {profile.get('segment', '?')} | "
                f"Risk: {profile.get('risk_level', 'normal')} | "
                f"Deals: {profile.get('deal_count', 0)} | "
                f"Top route: {profile.get('top_route', '?')}]"
            )

        if history:
            lines.append("Recent conversation:")
            for h in history[-8:]:
                # Give more chars to assistant (has tables/data)
                max_len = 300 if h['role'] == 'assistant' else 200
                content = h['content'][:max_len]
                if len(h['content']) > max_len:
                    content += "..."
                lines.append(f"  {h['role']}: {content}")

        return "\n".join(lines) if lines else ""

    # ── Task Queue (DAG-inspired) ────────────────────────────────────────

    def queue_task(self, task_type: str, payload: dict,
                   blocked_by: int = None) -> int:
        """
        Add task to queue. Returns task_id.

        Args:
            task_type: 'quote' | 'check_anomaly' | 'notify' | 'briefing'
            payload: task-specific data dict
            blocked_by: task_id that must complete first (simple DAG)
        """
        status = "blocked" if blocked_by else "pending"
        with self._conn() as c:
            cursor = c.execute(
                "INSERT INTO task_queue(task_type, payload, status, blocked_by) "
                "VALUES (?, ?, ?, ?)",
                (task_type, json.dumps(payload, ensure_ascii=False),
                 status, blocked_by)
            )
            task_id = cursor.lastrowid
        log.debug("[ORACLE] Task queued: #%d %s (status=%s)", task_id, task_type, status)
        return task_id

    def get_pending_tasks(self) -> list[dict]:
        """Get all pending (unblocked) tasks."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, task_type, payload, status, blocked_by, created_at "
                "FROM task_queue WHERE status = 'pending' "
                "ORDER BY created_at ASC"
            ).fetchall()

        tasks = []
        for r in rows:
            tasks.append({
                "id": r[0], "task_type": r[1],
                "payload": json.loads(r[2]),
                "status": r[3], "blocked_by": r[4],
                "created_at": r[5],
            })
        return tasks

    def complete_task(self, task_id: int, result: str = None):
        """Mark task as done, unblock dependents."""
        with self._conn() as c:
            c.execute(
                "UPDATE task_queue SET status = 'done', "
                "completed_at = datetime('now'), result = ? "
                "WHERE id = ?",
                (result, task_id)
            )
            # Unblock tasks that were waiting on this one
            c.execute(
                "UPDATE task_queue SET status = 'pending' "
                "WHERE blocked_by = ? AND status = 'blocked'",
                (task_id,)
            )

    def fail_task(self, task_id: int, error: str):
        """Mark task as failed."""
        with self._conn() as c:
            c.execute(
                "UPDATE task_queue SET status = 'failed', "
                "completed_at = datetime('now'), result = ? "
                "WHERE id = ?",
                (f"ERROR: {error}", task_id)
            )

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Overall memory statistics."""
        with self._conn() as c:
            total_msgs = c.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            total_users = c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM conversations"
            ).fetchone()[0]
            total_profiles = c.execute(
                "SELECT COUNT(*) FROM customer_profiles"
            ).fetchone()[0]
            pending_tasks = c.execute(
                "SELECT COUNT(*) FROM task_queue WHERE status = 'pending'"
            ).fetchone()[0]
            total_tasks = c.execute(
                "SELECT COUNT(*) FROM task_queue"
            ).fetchone()[0]

        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "total_messages": total_msgs,
            "unique_users": total_users,
            "profiles": total_profiles,
            "pending_tasks": pending_tasks,
            "total_tasks": total_tasks,
            "db_size_kb": round(db_size / 1024, 1),
        }
