# -*- coding: utf-8 -*-
"""
data-router.py — CNEE Master + Email Log API Endpoints
=======================================================
Endpoints:
  GET  /api/data/cnee                — list CNEE with pagination + filters
  GET  /api/data/cnee/{id}           — single CNEE detail
  GET  /api/data/email-log           — list email log with pagination + filters
  GET  /api/data/email-log/stats     — summary stats (sent/failed/bounce counts)
  POST /api/data/upload              — upload CNEE data (validate + preview)
  GET  /api/data/customer-behavior   — list behaviors with filter
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from database.connection import execute_sync, is_postgres_configured

log = logging.getLogger("nelson.data")

router = APIRouter(prefix="/api/data", tags=["Data"])

REQUIRED_CNEE_COLS = {"email", "company_name"}


# ── Dependency ────────────────────────────────────────────────────────────────

def _require_pg():
    if not is_postgres_configured():
        raise HTTPException(503, "PostgreSQL not configured — set DATABASE_URL")


# ── Response Models ───────────────────────────────────────────────────────────

class CneeItem(BaseModel):
    id: int
    company_name: Optional[str]
    contact_name: Optional[str]
    email: Optional[str]
    campaign: Optional[str]
    country: Optional[str]
    port: Optional[str]
    status: str
    lead_score: float
    last_contacted: Optional[str]

class EmailLogItem(BaseModel):
    id: int
    cnee_id: Optional[int]
    email: str
    subject: Optional[str]
    template_used: Optional[str]
    status: str
    sent_at: Optional[str]
    sent_by: Optional[str]
    error_message: Optional[str]

class UploadPreview(BaseModel):
    total_rows: int
    valid_rows: int
    duplicate_emails: int
    missing_email: int
    sample: List[dict]
    errors: List[str]


# ── CNEE Endpoints ────────────────────────────────────────────────────────────

@router.get("/cnee")
def list_cnee(
    campaign: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List CNEE prospects with optional campaign/status filter and pagination."""
    _require_pg()

    offset = (page - 1) * page_size
    conditions = []
    params: list = []

    if campaign:
        conditions.append("campaign = %s")
        params.append(campaign)
    if status:
        conditions.append("status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = execute_sync(f"SELECT COUNT(*) AS c FROM cnee_master {where}", tuple(params))
    total = count_row[0]["c"] if count_row else 0

    params += [page_size, offset]
    rows = execute_sync(
        f"""
        SELECT id, company_name, contact_name, email, campaign, country, port,
               status, lead_score,
               TO_CHAR(last_contacted, 'YYYY-MM-DD') AS last_contacted
        FROM   cnee_master
        {where}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [dict(r) for r in (rows or [])],
    }


@router.get("/cnee/{cnee_id}")
def get_cnee(cnee_id: int):
    """Get a single CNEE record by ID."""
    _require_pg()

    rows = execute_sync(
        """
        SELECT c.*,
               TO_CHAR(c.last_contacted, 'YYYY-MM-DD') AS last_contacted,
               (SELECT COUNT(*) FROM email_log el WHERE el.cnee_id = c.id) AS emails_sent
        FROM   cnee_master c
        WHERE  c.id = %s
        """,
        (cnee_id,),
    )

    if not rows:
        raise HTTPException(404, f"CNEE {cnee_id} not found")

    return dict(rows[0])


# ── Email Log Endpoints ───────────────────────────────────────────────────────

@router.get("/email-log")
def list_email_log(
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List email log with pagination and optional status/date filters."""
    _require_pg()

    offset = (page - 1) * page_size
    conditions = []
    params: list = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if date_from:
        conditions.append("sent_at >= %s::date")
        params.append(date_from)
    if date_to:
        conditions.append("sent_at <= (%s::date + interval '1 day')")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = execute_sync(f"SELECT COUNT(*) AS c FROM email_log {where}", tuple(params))
    total = count_row[0]["c"] if count_row else 0

    params += [page_size, offset]
    rows = execute_sync(
        f"""
        SELECT id, cnee_id, email, subject, template_used, status,
               TO_CHAR(sent_at, 'YYYY-MM-DD HH24:MI') AS sent_at,
               sent_by, error_message
        FROM   email_log
        {where}
        ORDER BY sent_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [dict(r) for r in (rows or [])],
    }


@router.get("/email-log/stats")
def email_log_stats():
    """Aggregate stats: sent/failed/bounce counts per status."""
    _require_pg()

    rows = execute_sync(
        """
        SELECT status, COUNT(*) AS count
        FROM   email_log
        GROUP BY status
        ORDER BY count DESC
        """
    )

    stats = {r["status"]: r["count"] for r in (rows or [])}
    total = sum(stats.values())

    return {
        "total": total,
        "by_status": stats,
        "sent": stats.get("sent", 0),
        "failed": stats.get("failed", 0),
        "bounced": stats.get("bounced", 0),
        "opened": stats.get("opened", 0),
    }


# ── Upload Endpoint ───────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_cnee(file: UploadFile = File(...)) -> UploadPreview:
    """
    Upload CNEE data file (xlsx/csv). Validates columns and returns preview.
    Does NOT insert data — caller reviews preview before committing.
    """
    _require_pg()

    if not file.filename:
        raise HTTPException(400, "No file provided")

    suffix = file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in ("xlsx", "csv"):
        raise HTTPException(400, "Only .xlsx and .csv files are supported")

    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas not installed on server")

    content = await file.read()

    try:
        if suffix == "xlsx":
            import io
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        else:
            import io
            df = pd.read_csv(io.StringIO(content.decode("utf-8", errors="replace")))
    except Exception as e:
        raise HTTPException(422, f"Cannot parse file: {e}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    errors: list[str] = []

    # Check required columns
    missing_cols = REQUIRED_CNEE_COLS - set(df.columns)
    if missing_cols:
        raise HTTPException(
            422,
            f"Missing required columns: {', '.join(missing_cols)}. "
            f"Found: {', '.join(df.columns)}"
        )

    total = len(df)
    no_email = int(df["email"].isna().sum() + (df["email"].astype(str) == "nan").sum())
    dup_emails = int(df["email"].dropna().duplicated().sum())

    if dup_emails:
        errors.append(f"{dup_emails} duplicate emails in file")
    if no_email:
        errors.append(f"{no_email} rows missing email")

    valid = total - no_email
    sample = df.head(5).fillna("").astype(str).to_dict(orient="records")

    return UploadPreview(
        total_rows=total,
        valid_rows=valid,
        duplicate_emails=dup_emails,
        missing_email=no_email,
        sample=sample,
        errors=errors,
    )


# ── Customer Behavior Endpoint ────────────────────────────────────────────────

@router.get("/customer-behavior")
def list_customer_behavior(
    cnee_id: Optional[int] = Query(None),
    behavior_type: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List customer behavior records with optional filters."""
    _require_pg()

    offset = (page - 1) * page_size
    conditions = []
    params: list = []

    if cnee_id:
        conditions.append("cnee_id = %s")
        params.append(cnee_id)
    if behavior_type:
        conditions.append("behavior_type = %s")
        params.append(behavior_type)
    if classification:
        conditions.append("classification = %s")
        params.append(classification)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = execute_sync(f"SELECT COUNT(*) AS c FROM customer_behavior {where}", tuple(params))
    total = count_row[0]["c"] if count_row else 0

    params += [page_size, offset]
    rows = execute_sync(
        f"""
        SELECT id, cnee_id, behavior_type, email_subject, response_summary,
               classification,
               TO_CHAR(detected_at, 'YYYY-MM-DD HH24:MI') AS detected_at
        FROM   customer_behavior
        {where}
        ORDER BY detected_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in (rows or [])],
    }
