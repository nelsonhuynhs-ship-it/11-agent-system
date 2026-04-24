"""sent_scan_router.py — FastAPI router for Outlook Sent Items scan.

Endpoints:
    POST /api/sent-scan/run          — trigger scan in background
    GET  /api/sent-scan/status/{id}  — poll progress
    GET  /api/sent-scan/latest       — return latest JSON summary
    POST /api/sent-scan/auto-block   — manually trigger auto-block with custom threshold
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

log = logging.getLogger("sent_scan")

# ── Paths ──────────────────────────────────────────────────────────
_ENGINE_TEST  = Path(__file__).parent.parent.parent.parent
_SCRIPT       = _ENGINE_TEST / "scripts" / "scan-sent-outlook.py"
_BACKUP_DIR   = Path("D:/OneDrive/NelsonData/email/backups")
_LATEST_JSON  = _BACKUP_DIR / "sent_audit_latest.json"

# ── In-memory job registry ─────────────────────────────────────────
# job_id → {status, started_at, finished_at, result, error}
_JOBS: dict[str, dict] = {}

router = APIRouter(prefix="/api/sent-scan", tags=["sent-scan"])


# ── Background worker ──────────────────────────────────────────────

def _run_scan(
    job_id: str,
    days: int,
    update_master: bool,
    block_threshold: int,
    threshold: int,
):
    job = _JOBS[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.now().isoformat()

    cmd = [
        sys.executable, str(_SCRIPT),
        "--days", str(days),
        "--threshold", str(threshold),
    ]
    if update_master:
        cmd.append("--update-master")
    if block_threshold > 0:
        cmd += ["--block-threshold", str(block_threshold)]

    log.info(f"[job {job_id}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
        )
        job["return_code"]  = result.returncode
        job["stdout"]       = result.stdout[-3000:] if result.stdout else ""
        job["stderr"]       = result.stderr[-1000:] if result.stderr else ""
        job["finished_at"]  = datetime.now().isoformat()

        if result.returncode == 0:
            job["status"] = "done"
            # Load summary if available
            if _LATEST_JSON.exists():
                try:
                    job["summary"] = json.loads(_LATEST_JSON.read_text(encoding="utf-8"))
                except Exception:
                    pass
            log.info(f"[job {job_id}] Scan complete")
        else:
            job["status"] = "failed"
            log.error(f"[job {job_id}] Script exited {result.returncode}: {result.stderr[:200]}")

    except subprocess.TimeoutExpired:
        job["status"]       = "timeout"
        job["error"]        = "Scan exceeded 5-minute timeout"
        job["finished_at"]  = datetime.now().isoformat()
        log.error(f"[job {job_id}] Timeout")
    except Exception as exc:
        job["status"]       = "failed"
        job["error"]        = str(exc)
        job["finished_at"]  = datetime.now().isoformat()
        log.error(f"[job {job_id}] Exception: {exc}")


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/run", status_code=202)
def run_scan(
    background_tasks: BackgroundTasks,
    days: int = 14,
    threshold: int = 3,
    update_master: bool = False,
    block_threshold: int = 0,
):
    """Trigger Outlook Sent Items scan in background.

    - days: how many days back to scan (default 14)
    - threshold: flag emails sent >= N times (default 3)
    - update_master: patch SEND_COUNT/LAST_SENT_DATE in cnee_master_v2_final.xlsx
    - block_threshold: auto-add to excluded_emails.json if sent >= N (0 = disabled)

    Returns job_id for polling via GET /api/sent-scan/status/{job_id}
    """
    if not _SCRIPT.exists():
        raise HTTPException(503, f"scan-sent-outlook.py not found at {_SCRIPT}")

    job_id = f"scan_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    # 2026-04-24 HIGH-3: bound _JOBS to 100 — drop oldest FIFO to avoid OOM
    # if something spams POST /run. Nelson only needs recent history.
    while len(_JOBS) >= 100:
        _JOBS.pop(next(iter(_JOBS)))
    _JOBS[job_id] = {
        "job_id":      job_id,
        "status":      "queued",
        "days":        days,
        "threshold":   threshold,
        "queued_at":   datetime.now().isoformat(),
        "started_at":  None,
        "finished_at": None,
        "summary":     None,
        "error":       None,
    }

    background_tasks.add_task(
        _run_scan, job_id, days, update_master, block_threshold, threshold
    )
    log.info(f"Scan queued: {job_id} (days={days} threshold={threshold} update_master={update_master} block>={block_threshold})")
    return {"job_id": job_id, "status": "queued", "days": days}


@router.get("/status/{job_id}")
def get_status(job_id: str):
    """Poll scan progress by job_id."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, f"job_id '{job_id}' not found")
    return job


@router.get("/status/latest")
def get_latest_status():
    """Return status of the most recently triggered scan job."""
    if not _JOBS:
        return {"status": "no_jobs", "message": "No scan has been run yet"}
    latest = max(_JOBS.values(), key=lambda j: j.get("queued_at", ""))
    return latest


@router.get("/latest")
def get_latest_summary():
    """Return latest sent_audit_latest.json summary (from most recent scan)."""
    if not _LATEST_JSON.exists():
        return {
            "message":  "No scan results yet — run POST /api/sent-scan/run first",
            "top30":    [],
            "total_recipients": 0,
        }
    try:
        return json.loads(_LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Failed to read summary: {exc}")


@router.post("/auto-block")
def manual_auto_block(threshold: int = 5):
    """Manually trigger auto-block using latest scan results.

    Reads sent_audit_latest.json and adds emails sent >= threshold to excluded_emails.json.
    """
    if not _LATEST_JSON.exists():
        raise HTTPException(404, "No scan results found — run scan first")

    try:
        summary   = json.loads(_LATEST_JSON.read_text(encoding="utf-8"))
        top_rows  = summary.get("top30", [])
        # import helper from scan script
        sys.path.insert(0, str(_ENGINE_TEST / "scripts"))
        from scan_sent_outlook import auto_block  # type: ignore
        blocked = auto_block(top_rows, threshold=threshold)
        return {
            "blocked":   blocked,
            "count":     len(blocked),
            "threshold": threshold,
        }
    except ImportError:
        # Fallback: inline auto-block without importing script
        _EXCLUDED_FILE = _ENGINE_TEST / "email_engine" / "data" / "excluded_emails.json"
        try:
            data = json.loads(_EXCLUDED_FILE.read_text(encoding="utf-8")) if _EXCLUDED_FILE.exists() else {"excluded": {}}
        except Exception:
            data = {"excluded": {}}
        data.setdefault("excluded", {})
        summary = json.loads(_LATEST_JSON.read_text(encoding="utf-8"))
        blocked = []
        for rec in summary.get("top30", []):
            if rec.get("count", 0) >= threshold and rec["email"] not in data["excluded"]:
                data["excluded"][rec["email"]] = {
                    "reason":    f"auto-blocked: sent {rec['count']}x",
                    "count":     rec["count"],
                    "last_sent": rec.get("last_sent", ""),
                    "added_at":  datetime.now().strftime("%Y-%m-%d"),
                    "added_by":  "sent-scan-api",
                }
                blocked.append(rec["email"])
        _EXCLUDED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _EXCLUDED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"blocked": blocked, "count": len(blocked), "threshold": threshold}
    except Exception as exc:
        raise HTTPException(500, str(exc))
