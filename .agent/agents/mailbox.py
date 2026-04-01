# ============================================================
#  MAILBOX — Peer-to-peer messaging between agents (GoClaw Phase 2)
#  Each agent can send/receive/broadcast messages.
#  DB: .agent/memory/mailbox.db
# ============================================================
import os, sys, uuid, datetime, sqlite3, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DB_PATH = os.path.join(config.MEMORY_DIR, "mailbox.db")
_db_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    with _db_lock:
        conn = _connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                from_agent  TEXT NOT NULL,
                to_agent    TEXT NOT NULL,
                subject     TEXT NOT NULL,
                body        TEXT DEFAULT '',
                sent_at     TEXT NOT NULL,
                read_at     TEXT DEFAULT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_to ON messages(to_agent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_read ON messages(read_at)")
        conn.commit()
        conn.close()


_init_db()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
#  PUBLIC API
# ============================================================

def send_message(from_agent, to_agent, subject, body=""):
    """Send a message from one agent to another."""
    msg_id = str(uuid.uuid4())[:8]
    now = _now()

    with _db_lock:
        conn = _connect()
        conn.execute(
            """INSERT INTO messages (id, from_agent, to_agent, subject, body, sent_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (msg_id, from_agent, to_agent, subject, body, now)
        )
        conn.commit()
        conn.close()

    print(f"[MAIL] {from_agent} -> {to_agent}: [{subject}] {body[:60]}")
    return msg_id


def broadcast(from_agent, subject, body=""):
    """Broadcast a message to all agents (to_agent='ALL')."""
    return send_message(from_agent, "ALL", subject, body)


def read_messages(agent_name):
    """
    Get unread messages for an agent.
    Returns messages addressed to this agent OR to 'ALL'.
    """
    with _db_lock:
        conn = _connect()
        cursor = conn.execute(
            """SELECT * FROM messages
               WHERE (to_agent=? OR to_agent='ALL')
               AND read_at IS NULL
               ORDER BY sent_at ASC""",
            (agent_name,)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    return rows


def mark_read(message_id):
    """Mark a message as read."""
    now = _now()
    with _db_lock:
        conn = _connect()
        conn.execute(
            "UPDATE messages SET read_at=? WHERE id=?",
            (now, message_id)
        )
        conn.commit()
        conn.close()


def get_unread_count(agent_name=None):
    """Get count of unread messages, optionally filtered by recipient."""
    with _db_lock:
        conn = _connect()
        if agent_name:
            cursor = conn.execute(
                """SELECT COUNT(*) as cnt FROM messages
                   WHERE (to_agent=? OR to_agent='ALL') AND read_at IS NULL""",
                (agent_name,)
            )
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE read_at IS NULL"
            )
        count = cursor.fetchone()["cnt"]
        conn.close()
    return count


def get_unread_summary():
    """Get summary of unread messages grouped by sender."""
    with _db_lock:
        conn = _connect()
        cursor = conn.execute(
            """SELECT from_agent, subject, COUNT(*) as cnt
               FROM messages WHERE read_at IS NULL
               GROUP BY from_agent, subject
               ORDER BY cnt DESC"""
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

    if not rows:
        return ""

    parts = []
    for row in rows:
        parts.append(f"{row['from_agent']} sent {row['cnt']} {row['subject']}")
    return "\U0001F4EC Unread: " + ", ".join(parts)


def clear_mailbox():
    """Clear all messages (for testing)."""
    with _db_lock:
        conn = _connect()
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()
    print("[MAIL] Cleared all messages")
