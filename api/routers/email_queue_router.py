# -*- coding: utf-8 -*-
"""
email-queue-router.py — Email Queue API Endpoints
==================================================
Worker bridge: WebApp → queue → Outlook COM worker on local machine.

Flow:
  1. WebApp calls POST /api/email/queue   → inserts job (status=pending)
  2. Outlook COM worker polls GET /api/email/queue/pending → marks as 'sending'
  3. Worker sends via Outlook COM, then calls:
     - POST /api/email/queue/{id}/complete  (success)
     - POST /api/email/queue/{id}/fail      (failure, increments retry_count)

Endpoints:
  POST /api/email/queue              — add emails to queue
  GET  /api/email/queue/pending      — worker poll (returns pending, marks 'sending')
  POST /api/email/queue/{id}/complete — worker reports success
  POST /api/email/queue/{id}/fail    — worker reports failure
  GET  /api/email/queue/status       — dashboard stats
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from database.connection import execute_sync, is_postgres_configured

log = logging.getLogger("nelson.email_queue")

router = APIRouter(prefix="/api/email", tags=["Email Queue"])

MAX_RETRY = 3
POLL_BATCH = 10  # max jobs returned per poll


# ── Dependency ────────────────────────────────────────────────────────────────

def _require_pg():
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured — set DATABASE_URL")


# ── Request / Response Models ─────────────────────────────────────────────────

class QueueItem(BaseModel):
    cnee_id: Optional[int] = None
    email: str
    subject: str
    html_body: str


class QueueBatch(BaseModel):
    items: List[QueueItem]


class FailReport(BaseModel):
    error_message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/queue", status_code=201)
def add_to_queue(batch: QueueBatch):
    """
    Add one or more emails to the queue (status=pending).
    Called by WebApp after user approves send.
    """
    _require_pg()

    if not batch.items:
        raise HTTPException(400, "items list is empty")

    ids = []
    for item in batch.items:
        rows = execute_sync(
            """
            INSERT INTO email_queue (cnee_id, email, subject, html_body)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (item.cnee_id, item.email, item.subject, item.html_body),
        )
        if rows:
            ids.append(rows[0]["id"])

    log.info("Queued %d email(s): ids=%s", len(ids), ids)
    return {"queued": len(ids), "ids": ids}


@router.get("/queue/pending")
def get_pending(limit: int = Query(POLL_BATCH, ge=1, le=50)):
    """
    Worker poll endpoint. Returns up to `limit` pending jobs and atomically
    marks them as 'sending' so another worker instance won't pick them up.
    """
    _require_pg()

    # Atomic fetch-and-lock via CTE
    rows = execute_sync(
        """
        WITH selected AS (
            SELECT id FROM email_queue
            WHERE  status = 'pending' AND retry_count < %s
            ORDER BY created_at
            LIMIT  %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE email_queue q
        SET    status = 'sending', picked_at = NOW()
        FROM   selected
        WHERE  q.id = selected.id
        RETURNING q.id, q.cnee_id, q.email, q.subject, q.html_body,
                  q.retry_count, q.created_at
        """,
        (MAX_RETRY, limit),
    )

    jobs = [dict(r) for r in (rows or [])]
    log.info("Worker poll: %d job(s) dispatched", len(jobs))
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/queue/{job_id}/complete")
def complete_job(job_id: int):
    """Worker reports successful send. Marks job as 'sent'."""
    _require_pg()

    rows = execute_sync(
        """
        UPDATE email_queue
        SET    status = 'sent', completed_at = NOW()
        WHERE  id = %s AND status = 'sending'
        RETURNING id
        """,
        (job_id,),
        fetch=True,
    )

    if not rows:
        raise HTTPException(404, f"Job {job_id} not found or not in 'sending' state")

    log.info("Job %d completed", job_id)
    return {"job_id": job_id, "status": "sent"}


@router.post("/queue/{job_id}/fail")
def fail_job(job_id: int, report: FailReport):
    """
    Worker reports failure. Increments retry_count.
    If retry_count >= MAX_RETRY, marks as 'failed' permanently.
    """
    _require_pg()

    rows = execute_sync(
        """
        UPDATE email_queue
        SET    retry_count = retry_count + 1,
               status = CASE
                   WHEN retry_count + 1 >= %s THEN 'failed'
                   ELSE 'pending'
               END
        WHERE  id = %s AND status = 'sending'
        RETURNING id, retry_count, status
        """,
        (MAX_RETRY, job_id),
    )

    if not rows:
        raise HTTPException(404, f"Job {job_id} not found or not in 'sending' state")

    result = dict(rows[0])
    log.warning(
        "Job %d failed (retry %d/%d): %s",
        job_id, result["retry_count"], MAX_RETRY, report.error_message[:120],
    )
    return {
        "job_id": job_id,
        "status": result["status"],
        "retry_count": result["retry_count"],
        "will_retry": result["status"] == "pending",
    }


@router.get("/queue/status")
def queue_status():
    """Dashboard stats: counts by status + oldest pending job age."""
    _require_pg()

    status_rows = execute_sync(
        """
        SELECT status, COUNT(*) AS count
        FROM   email_queue
        GROUP BY status
        ORDER BY count DESC
        """
    )
    by_status = {r["status"]: r["count"] for r in (status_rows or [])}

    oldest_row = execute_sync(
        """
        SELECT EXTRACT(EPOCH FROM (NOW() - MIN(created_at)))::int AS age_seconds
        FROM   email_queue
        WHERE  status = 'pending'
        """
    )
    oldest_pending_sec = (oldest_row[0]["age_seconds"] if oldest_row and oldest_row[0]["age_seconds"] else None)

    stuck_rows = execute_sync(
        """
        SELECT COUNT(*) AS c FROM email_queue
        WHERE status = 'sending'
          AND picked_at < NOW() - interval '10 minutes'
        """
    )
    stuck = stuck_rows[0]["c"] if stuck_rows else 0

    return {
        "by_status": by_status,
        "pending": by_status.get("pending", 0),
        "sending": by_status.get("sending", 0),
        "sent": by_status.get("sent", 0),
        "failed": by_status.get("failed", 0),
        "total": sum(by_status.values()),
        "oldest_pending_seconds": oldest_pending_sec,
        "stuck_jobs": stuck,
    }
