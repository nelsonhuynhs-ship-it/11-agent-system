# ============================================================
#  DASHBOARD API — N.E.L.S.O.N AI OS (Standalone FastAPI)
#  8 endpoints: 6 GET + 2 POST
#  Run: uvicorn dashboard_api:app --host 0.0.0.0 --port 8000 --reload
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, json, os
from pathlib import Path

BASE = Path(r"D:\NELSON\2. Areas\PricingSystem\Engine_test\.agent")

app = FastAPI(title="N.E.L.S.O.N Dashboard API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/agent/status")
def get_status():
    return {
        "NÃO": "online", "ÉM": "online", "LÍNH": "online",
        "SOI": "online", "Ổ": "online", "NÓI": "online",
        "erp_version": "V13", "listener": "running",
    }


@app.get("/agent/tasks")
def get_tasks():
    db = BASE / "memory" / "task_board.db"
    if not db.exists():
        return {"tasks": []}
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    tasks = [dict(r) for r in
             conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50")]
    conn.close()
    return {"tasks": tasks}


@app.get("/agent/lessons")
def get_lessons():
    f = BASE / "memory" / "lesson_learned.md"
    return {"content": f.read_text(encoding="utf-8") if f.exists() else ""}


@app.get("/agent/backlog")
def get_backlog():
    f = BASE / "memory" / "backlog.md"
    return {"content": f.read_text(encoding="utf-8") if f.exists() else ""}


@app.get("/agent/log")
def get_log():
    f = BASE / "memory" / "session_log.md"
    if not f.exists():
        return {"lines": []}
    lines = f.read_text(encoding="utf-8").splitlines()
    return {"lines": lines[-50:]}


@app.get("/agent/health")
def get_health():
    erp = Path(r"D:\NELSON\2. Areas\PricingSystem\Engine_test\ERP\data\ERP_Master.xlsm")
    return {
        "erp_exists": erp.exists(),
        "erp_size_mb": round(erp.stat().st_size / 1024 / 1024, 2) if erp.exists() else 0,
        "task_db": (BASE / "memory" / "task_board.db").exists(),
        "mailbox_db": (BASE / "memory" / "mailbox.db").exists(),
        "lesson_md": (BASE / "memory" / "lesson_learned.md").exists(),
        "backlog_md": (BASE / "memory" / "backlog.md").exists(),
        "agents_count": len(list((BASE / "agents").glob("*.py"))),
    }


@app.post("/agent/task")
def create_task(body: dict):
    f = BASE / "memory" / "pending_tasks.json"
    tasks = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    tasks.append(body)
    f.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "queued", "task": body}


@app.post("/agent/approve")
def approve_task(body: dict):
    return {"status": "approved", "task_id": body.get("task_id")}


if __name__ == "__main__":
    import uvicorn
    print("[DASHBOARD] Starting on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
