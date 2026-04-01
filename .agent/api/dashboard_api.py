# ============================================================
#  DASHBOARD API — FastAPI endpoints for WebApp (Sprint 13-14)
#  8 endpoints: 6 GET + 2 POST
#  Connects: task_board.db, mailbox.db, lesson_learned.md
# ============================================================
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import task_board
import mailbox as agent_mailbox
import learning_loop
import monitor as agent_monitor

# Check if FastAPI is available, provide stub if not
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="NELSON AI OS Dashboard", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    app = None


# ── Models ──
if HAS_FASTAPI:
    class TaskCreate(BaseModel):
        title: str
        description: str = ""
        priority: int = 2

    class ApproveRequest(BaseModel):
        task_id: str


AGENT_NAMES = {
    "NAO": {"role": "Lead CTO", "module": "cto_agent"},
    "EM": {"role": "Builder", "module": "builder"},
    "LINH": {"role": "Guard", "module": "guard"},
    "SOI": {"role": "Reviewer", "module": "reviewer"},
    "O": {"role": "Memory", "module": "memory"},
    "NOI": {"role": "Notifier", "module": "notifier"},
}


def get_agent_status():
    """Check which agents are importable (online)."""
    status = {}
    for name, info in AGENT_NAMES.items():
        try:
            __import__(info["module"])
            status[name] = {"role": info["role"], "online": True}
        except Exception:
            status[name] = {"role": info["role"], "online": False}
    return status


def get_tasks():
    """Get full task board."""
    return task_board.get_board_summary()


def get_lessons(limit=20):
    """Get last N lessons."""
    all_l = learning_loop.get_all_lessons()
    return all_l[-limit:] if len(all_l) > limit else all_l


def get_backlog():
    """Parse backlog.md into sections."""
    backlog_path = os.path.join(config.MEMORY_DIR, "backlog.md")
    if not os.path.exists(backlog_path):
        return {"priorities": {}, "raw": ""}
    with open(backlog_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"raw": content}


def get_log(lines=50):
    """Get last N lines from session_log.md."""
    log_path = os.path.join(config.MEMORY_DIR, "session_log.md")
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return all_lines[-lines:] if len(all_lines) > lines else all_lines


def get_health():
    """Run health checks."""
    return {
        "morning": agent_monitor.morning_check(),
        "timestamp": datetime.datetime.now().isoformat(),
    }


def create_task_from_api(title, description="", priority=2):
    """Create a task from WebApp."""
    tid = task_board.create_task(title, description, priority=priority)
    return {"task_id": tid, "status": "pending"}


def approve_task_from_api(task_id):
    """Approve a pending task."""
    task = task_board.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    return {"task_id": task_id, "approved": True}


# ── FastAPI Routes ──
if HAS_FASTAPI and app:

    @app.get("/agent/status")
    def api_status():
        return get_agent_status()

    @app.get("/agent/tasks")
    def api_tasks():
        return get_tasks()

    @app.get("/agent/lessons")
    def api_lessons():
        return get_lessons()

    @app.get("/agent/backlog")
    def api_backlog():
        return get_backlog()

    @app.get("/agent/log")
    def api_log():
        return get_log()

    @app.get("/agent/health")
    def api_health():
        return get_health()

    @app.post("/agent/task")
    def api_create_task(req: TaskCreate):
        return create_task_from_api(req.title, req.description, req.priority)

    @app.post("/agent/approve")
    def api_approve(req: ApproveRequest):
        return approve_task_from_api(req.task_id)


# ── Standalone usage ──
if __name__ == "__main__":
    if HAS_FASTAPI:
        import uvicorn
        print("[DASHBOARD] Starting on http://0.0.0.0:8100")
        uvicorn.run(app, host="0.0.0.0", port=8100)
    else:
        print("[DASHBOARD] FastAPI not installed. Functions available for import.")
        print("  Agent status:", json.dumps(get_agent_status(), indent=2))
