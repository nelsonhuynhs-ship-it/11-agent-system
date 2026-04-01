# -*- coding: utf-8 -*-
"""
job_router.py — Active Job Endpoints (nelson-flow)
=====================================================
Job lifecycle management matching nelson-flow Flow 3:
  Quote → Active Job → Tracking → Monthly Report

Endpoints:
  POST  /api/jobs/activate           — convert quote → active job
  PATCH /api/jobs/{id}/fast-no       — update FAST_JOB_NO
  POST  /api/jobs/{id}/booking-email — generate booking email
  GET   /api/jobs/active             — list active jobs
"""
from __future__ import annotations

import sys
import os
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


# ── Request Models ───────────────────────────────────────────────────────────

class JobActivateRequest(BaseModel):
    """Input for activating a job from a quote."""
    quote_id: Optional[str] = None
    quote_data: Optional[dict] = None  # Direct quote data (from /quotes/build)
    shipper: str = ""
    consignee: str = ""
    etd: str = ""
    volume: str = ""           # e.g. "1x40HQ", "2x20GP"
    fast_job_no: str = ""      # From FAST system → column AL
    hbl_no: str = ""           # House B/L → column AN


class FastNoRequest(BaseModel):
    """Update FAST_JOB_NO for a job."""
    fast_job_no: str


class BookingEmailRequest(BaseModel):
    """Generate booking email for a job."""
    carrier_email: Optional[str] = None
    template: Optional[str] = None


# ── In-memory job store (will migrate to DB later) ───────────────────────────
_jobs: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# 1. ACTIVATE — POST /api/jobs/activate
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/activate")
def activate_job(req: JobActivateRequest):
    """
    Convert a quote into an active job — nelson-flow core endpoint.

    Input: quote_id or quote_data + shipper/consignee/ETD/volume/FAST_JOB_NO/HBL_NO
    Output: active job record + booking email draft + Telegram alert

    Used by: Telegram Bot, WebApp, ERP Excel
    """
    from services.job_service import activate_job as _activate, format_job_telegram

    # Get quote data
    quote_data = req.quote_data
    if not quote_data and req.quote_id:
        # Try to load from quote store
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "TelegramBot"
            ))
            from quote_store import get_quote
            quote_data = get_quote(req.quote_id)
        except (ImportError, Exception):
            pass

    if not quote_data:
        return {"error": "No quote data provided. Pass quote_data or valid quote_id.", "success": False}

    # Activate
    job = _activate(
        quote_data=quote_data,
        shipper=req.shipper,
        consignee=req.consignee,
        etd=req.etd,
        volume=req.volume,
        fast_job_no=req.fast_job_no,
        hbl_no=req.hbl_no,
    )

    # Store in memory
    _jobs[job["job_id"]] = job

    # Telegram notification text
    job["telegram_text"] = format_job_telegram(job)

    # Publish event
    try:
        from event_bus import bus, Event
        bus.publish(Event(
            type="job.activated",
            payload={
                "job_id": job["job_id"],
                "customer": job["customer"],
                "carrier": job["carrier"],
                "selling_rate": job["selling_rate"],
                "profit": job["profit"],
            },
            source="api",
        ))
    except Exception:
        pass

    return {"job": job, "success": True}


# ══════════════════════════════════════════════════════════════════════════════
# 2. UPDATE FAST_JOB_NO — PATCH /api/jobs/{id}/fast-no
# ══════════════════════════════════════════════════════════════════════════════

@router.patch("/{job_id}/fast-no")
def update_fast_no(job_id: str, req: FastNoRequest):
    """
    Update FAST_JOB_NO (column AL in ERP) for an active job.
    Called when Nelson assigns a job number from FAST system.
    """
    from services.job_service import update_fast_no as _update

    job = _jobs.get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found", "success": False}

    updated = _update(job, req.fast_job_no)
    _jobs[job_id] = updated

    return {"job": updated, "success": True}


# ══════════════════════════════════════════════════════════════════════════════
# 3. BOOKING EMAIL — POST /api/jobs/{id}/booking-email
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{job_id}/booking-email")
def generate_booking_email(job_id: str, req: BookingEmailRequest = None):
    """
    Generate or regenerate booking email for a job (column AK in ERP).
    Returns email draft ready for Outlook.
    """
    from services.job_service import build_booking_email

    job = _jobs.get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found", "success": False}

    email = build_booking_email(
        carrier=job["carrier"],
        pol=job["pol"],
        pod=job["pod"],
        place=job.get("place", job["pod"]),
        container=job["container"],
        volume=job.get("volume", job["container"]),
        etd=job.get("etd", "TBA"),
        shipper=job.get("shipper", ""),
        consignee=job.get("consignee", ""),
        fast_job_no=job.get("fast_job_no", ""),
    )

    # Override carrier email if provided
    if req and req.carrier_email:
        email["to"] = req.carrier_email

    return {"email": email, "job_id": job_id, "success": True}


# ══════════════════════════════════════════════════════════════════════════════
# 4. ACTIVE JOBS — GET /api/jobs/active
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/active")
def get_active_jobs(
    customer: Optional[str] = Query(None),
    carrier: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """
    List all active jobs with P&L per job.

    Used by: WebApp Active Jobs tab, ERP Active Jobs sheet, Bot /jobs command
    """
    jobs = list(_jobs.values())

    # Filters
    if customer:
        jobs = [j for j in jobs if customer.upper() in j.get("customer", "").upper()]
    if carrier:
        jobs = [j for j in jobs if carrier.upper() in j.get("carrier", "").upper()]

    # Only active
    jobs = [j for j in jobs if j.get("status") == "ACTIVE"]

    # Sort by created_at descending
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

    # Summary stats
    total_profit = sum(j.get("profit", 0) for j in jobs)
    total_revenue = sum(j.get("selling_rate", 0) for j in jobs)

    return {
        "jobs": jobs[:limit],
        "total": len(jobs),
        "summary": {
            "total_jobs": len(jobs),
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "avg_profit_per_job": round(total_profit / len(jobs), 2) if jobs else 0,
        },
    }
