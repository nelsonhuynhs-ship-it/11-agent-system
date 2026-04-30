"""sent_scan_router.py — FastAPI router for Graph API Sent Item verification.

Endpoints:
    GET  /api/sent-scan/pending     — list sent emails with graph_msg_id but not verified
    POST /api/sent-scan/verify-batch — verify messageIds via Graph /me/messages/{id}
    GET  /api/sent-scan/status     — health / throttle status
"""
from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger("sent_scan")

# ── Paths ──────────────────────────────────────────────────────────
_ENGINE_TEST = Path(__file__).parent.parent.parent.parent
_LOG_FILE    = _ENGINE_TEST / "email_engine" / "logs" / "email_log.csv"
_BACKUP_DIR  = Path("D:/OneDrive/NelsonData/email/backups")

GRAPH_SENT_FOLDER_ID = "sentitems"

# ── Throttle: sliding window 30 req/min ───────────────────────────
_throttle_lock  = threading.Lock()
_throttle_window: list[float] = []   # timestamps of recent requests
THROTTLE_MAX    = 30
THROTTLE_WINDOW = 60.0   # seconds


def _throttle_check() -> tuple[bool, int]:
    """Return (allowed, current_count) after purging old entries."""
    now = time.time()
    with _throttle_lock:
        # drop entries older than window
        while _throttle_window and _throttle_window[0] < now - THROTTLE_WINDOW:
            _throttle_window.pop(0)
        allowed = len(_throttle_window) < THROTTLE_MAX
        if allowed:
            _throttle_window.append(now)
        return allowed, len(_throttle_window)


# ── CSV helpers ────────────────────────────────────────────────────

def _read_log() -> list[dict]:
    if not _LOG_FILE.exists():
        return []
    try:
        with open(_LOG_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception:
        return []


def _write_log(rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(_LOG_FILE, newline="", encoding="utf-8", write=True) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _update_rows(predicate, update_fn) -> int:
    """Apply update_fn to rows matching predicate. Returns count of modified."""
    rows = _read_log()
    modified = 0
    for row in rows:
        if predicate(row):
            updated = update_fn(row)
            if updated:
                modified += 1
    if modified:
        _write_log(rows)
    return modified


# ── Graph helpers ──────────────────────────────────────────────────

def _get_graph_token():
    from email_engine.senders.graph_sender import get_token
    return get_token()


def _verify_message_id(message_id: str, token: str) -> dict | None:
    """GET /me/messages/{id} — returns message dict or None."""
    import requests
    try:
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"$select": "id,parentFolderId,sentDateTime"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


# ── Endpoints ──────────────────────────────────────────────────────

router = APIRouter(prefix="/api/sent-scan", tags=["sent-scan"])


@router.get("/pending")
def sent_scan_pending(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """List sent emails that have a graph_msg_id but are not verified.

    These are candidates for the verify-batch endpoint.
    """
    rows = _read_log()
    pending = []
    for row in rows:
        msg_id = (row.get("graph_msg_id") or "").strip()
        verified = (row.get("verified") or "").strip()
        if msg_id and not verified:
            pending.append({
                "timestamp":    row.get("timestamp", ""),
                "email":        row.get("email", ""),
                "subject":       row.get("subject", ""),
                "campaign_id":   row.get("campaign_id", ""),
                "graph_msg_id":  msg_id,
                "verified":     verified,
            })
    pending.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    return {"count": len(pending), "items": pending[:limit]}


@router.post("/verify-batch")
def verify_batch(message_ids: list[str], limit: int = 30):
    """Verify up to limit messageIds via Graph /me/messages/{id}.

    Checks parentFolderId == 'sentitems' to confirm message is in Sent folder.
    Updates 'verified' column with sentDateTime on success.
    Returns: {verified, failed, throttle_count}
    """
    if limit < 1:
        limit = 30
    ids_to_verify = message_ids[:limit]

    verified_count = 0
    failed: list[dict] = []
    throttle_count = 0

    token = _get_graph_token()

    for msg_id in ids_to_verify:
        allowed, _ = _throttle_check()
        if not allowed:
            throttle_count += 1
            log.warning(f"verify-batch throttle hit at {throttle_count}")
            continue

        result = _verify_message_id(msg_id, token)
        if result is None:
            failed.append({"id": msg_id, "reason": "message not found or HTTP error"})
            continue

        parent_id = result.get("parentFolderId", "")
        # parentFolderId ends with 'sentitems' for the Sent folder
        if parent_id and parent_id.endswith(GRAPH_SENT_FOLDER_ID):
            sent_dt = result.get("sentDateTime", "")
            _update_rows(
                lambda r: (r.get("graph_msg_id") or "").strip() == msg_id,
                lambda r: {**r, "verified": sent_dt}
            )
            verified_count += 1
        else:
            failed.append({"id": msg_id, "reason": f"in folder {parent_id}"})

        # Small pause to stay under throttle
        time.sleep(0.5)

    return {
        "verified":    verified_count,
        "failed":      failed,
        "throttle_count": throttle_count,
    }


@router.get("/status")
def sent_scan_status():
    """Return current throttle window count."""
    _, count = _throttle_check()
    return {
        "throttle_count":  count,
        "throttle_max":    THROTTLE_MAX,
        "window_sec":      int(THROTTLE_WINDOW),
    }
