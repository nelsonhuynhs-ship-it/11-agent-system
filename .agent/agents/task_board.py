# ============================================================
#  TASK BOARD — SQLite-backed shared task board (GoClaw Teams)
#  All agents share this board via atomic SQLite operations.
#  DB: .agent/memory/task_board.db
# ============================================================
import os, sys, uuid, datetime, sqlite3, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DB_PATH = os.path.join(config.MEMORY_DIR, "task_board.db")
_db_lock = threading.Lock()


def _connect():
    """Get a connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    """Create tasks table if not exists."""
    with _db_lock:
        conn = _connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'pending',
                owner       TEXT DEFAULT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                blocked_by  TEXT DEFAULT NULL,
                result      TEXT DEFAULT NULL,
                priority    INTEGER NOT NULL DEFAULT 2,
                FOREIGN KEY (blocked_by) REFERENCES tasks(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_blocked ON tasks(blocked_by)
        """)
        conn.commit()
        conn.close()


# Initialize on import
_init_db()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
#  PUBLIC API
# ============================================================

def create_task(title, description="", blocked_by=None, priority=2):
    """
    Create a new task on the board.
    If blocked_by is set, task starts as 'blocked'.
    Returns task_id (UUID string).
    """
    task_id = str(uuid.uuid4())[:8]
    now = _now()
    status = "blocked" if blocked_by else "pending"

    with _db_lock:
        conn = _connect()
        conn.execute(
            """INSERT INTO tasks (id, title, description, status, owner,
               created_at, updated_at, blocked_by, result, priority)
               VALUES (?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?)""",
            (task_id, title, description, status, now, now, blocked_by, priority)
        )
        conn.commit()
        conn.close()

    print(f"[BOARD] Created: {task_id} '{title}' [{status}] priority={priority}")
    return task_id


def claim_task(task_id, agent_name):
    """
    Atomically claim a task. Only succeeds if status='pending' AND owner IS NULL.
    Returns True if claimed, False if already taken or not claimable.
    CRITICAL: Uses single UPDATE WHERE for atomicity.
    """
    now = _now()
    with _db_lock:
        conn = _connect()
        cursor = conn.execute(
            """UPDATE tasks SET owner=?, status='in_progress', updated_at=?
               WHERE id=? AND status='pending' AND owner IS NULL""",
            (agent_name, now, task_id)
        )
        changed = cursor.rowcount
        conn.commit()
        conn.close()

    if changed > 0:
        print(f"[BOARD] Claimed: {task_id} by {agent_name}")
        return True
    else:
        print(f"[BOARD] Claim FAILED: {task_id} by {agent_name} (already taken or blocked)")
        return False


def complete_task(task_id, result=""):
    """
    Mark task as complete and auto-unblock dependent tasks.
    Returns list of unblocked task_ids.
    """
    now = _now()
    unblocked = []

    with _db_lock:
        conn = _connect()
        # Mark complete
        conn.execute(
            """UPDATE tasks SET status='complete', result=?, updated_at=?
               WHERE id=?""",
            (result, now, task_id)
        )

        # Auto-unblock: find tasks blocked_by this task → set pending
        cursor = conn.execute(
            """SELECT id, title FROM tasks WHERE blocked_by=? AND status='blocked'""",
            (task_id,)
        )
        blocked_tasks = cursor.fetchall()

        for bt in blocked_tasks:
            conn.execute(
                """UPDATE tasks SET status='pending', updated_at=? WHERE id=?""",
                (now, bt["id"])
            )
            unblocked.append(bt["id"])
            print(f"[BOARD] Unblocked: {bt['id']} '{bt['title']}'")

        conn.commit()
        conn.close()

    print(f"[BOARD] Completed: {task_id} → unblocked {len(unblocked)} tasks")
    return unblocked


def fail_task(task_id, reason=""):
    """
    Mark task as failed. Does NOT auto-unblock dependents.
    """
    now = _now()
    with _db_lock:
        conn = _connect()
        conn.execute(
            """UPDATE tasks SET status='failed', result=?, updated_at=?
               WHERE id=?""",
            (f"FAILED: {reason}", now, task_id)
        )
        conn.commit()
        conn.close()

    print(f"[BOARD] Failed: {task_id} — {reason}")


def get_pending_tasks():
    """
    Get all claimable tasks (status='pending', not blocked).
    Returns list of dicts sorted by priority (1=highest first).
    """
    with _db_lock:
        conn = _connect()
        cursor = conn.execute(
            """SELECT * FROM tasks WHERE status='pending' AND owner IS NULL
               ORDER BY priority ASC, created_at ASC"""
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    return rows


def get_task(task_id):
    """Get a single task by ID."""
    with _db_lock:
        conn = _connect()
        cursor = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        row = cursor.fetchone()
        conn.close()
    return dict(row) if row else None


def get_board_summary():
    """
    Get full board summary grouped by status.
    Returns dict: {status: [{id, title, owner, ...}, ...]}
    """
    with _db_lock:
        conn = _connect()
        cursor = conn.execute(
            "SELECT * FROM tasks ORDER BY priority ASC, created_at ASC"
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

    summary = {
        "complete": [],
        "in_progress": [],
        "pending": [],
        "blocked": [],
        "failed": [],
    }
    for row in rows:
        s = row.get("status", "pending")
        if s in summary:
            summary[s].append(row)
    return summary


def format_board_summary(summary=None):
    """Format board summary as Telegram-friendly string."""
    if summary is None:
        summary = get_board_summary()

    lines = ["\U0001F4CB Task Board:"]

    complete = summary.get("complete", [])
    in_prog = summary.get("in_progress", [])
    pending = summary.get("pending", [])
    blocked = summary.get("blocked", [])
    failed = summary.get("failed", [])

    if complete:
        lines.append(f"  \u2705 Complete: {len(complete)} tasks")
    if in_prog:
        detail = ", ".join(f"{t['owner']}: {t['title'][:30]}" for t in in_prog)
        lines.append(f"  \u2699\uFE0F In Progress: {len(in_prog)} ({detail})")
    if pending:
        lines.append(f"  \u23F3 Pending: {len(pending)} tasks")
    if blocked:
        lines.append(f"  \U0001F512 Blocked: {len(blocked)} tasks")
    if failed:
        lines.append(f"  \u274C Failed: {len(failed)} tasks")

    total = len(complete) + len(in_prog) + len(pending) + len(blocked) + len(failed)
    if total == 0:
        lines.append("  (empty)")

    return "\n".join(lines)


def clear_board():
    """Clear all tasks (for testing). Use with care."""
    with _db_lock:
        conn = _connect()
        conn.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
    print("[BOARD] Cleared all tasks")
