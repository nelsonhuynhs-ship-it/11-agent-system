# -*- coding: utf-8 -*-
"""
hpl_router.py — FastAPI Router for HPL Integration
====================================================
Provides REST endpoints for HPL Schedule, Tracking, and Spot data.
Consumed by the Next.js Webapp dashboard.

Endpoints:
    GET  /api/hpl/spot?pol=VNHPH&pod=USLAX&cont=40HQ
    GET  /api/hpl/spot/all?pol=VNHPH&pod=USLAX
    POST /api/hpl/spot/refresh
    GET  /api/hpl/track/{identifier}     — container_no or job_id
    POST /api/hpl/track/add
    POST /api/hpl/webhook/events         — DCSA T&T webhook receiver
    GET  /api/hpl/status                 — HPL integration health

Usage in api/app.py:
    from routers.hpl_router import router as hpl_router
    app.include_router(hpl_router)
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("nelson.api.hpl")

# ── Ensure ERP modules are importable ─────────────────────────
_API_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.dirname(os.path.dirname(_API_DIR))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

router = APIRouter(prefix="/api/hpl", tags=["Hapag-Lloyd"])


# ── Pydantic Models ──────────────────────────────────────────

class AddContainersRequest(BaseModel):
    job_id: str
    containers: list[dict]  # [{"container_no": "HLXU...", "cont_type": "40HQ"}]
    pol: str = ""
    pod: str = ""


class SpotRefreshResponse(BaseModel):
    total_inserted: int
    routes_checked: int
    errors: list[str]
    expired_cleaned: int
    mode: str
    timestamp: str


# ── SPOT Endpoints ────────────────────────────────────────────

@router.get("/spot")
async def get_spot_rate(pol: str, pod: str, cont: str = "40HQ"):
    """Get latest HPL spot rate for a route."""
    from ERP.intelligence.spot_cache import get_spot, get_spot_comparison

    spot = get_spot(pol.upper(), pod.upper(), cont.upper())
    comparison = get_spot_comparison(pol.upper(), pod.upper(), cont.upper())

    return {
        "spot": spot,
        "comparison": comparison,
        "query": {"pol": pol, "pod": pod, "cont": cont},
    }


@router.get("/spot/all")
async def get_all_spot_rates(pol: str, pod: str):
    """Get spot rates for all container types on a route."""
    from ERP.intelligence.spot_cache import get_all_spots

    spots = get_all_spots(pol.upper(), pod.upper())
    return {
        "spots": spots,
        "count": len(spots),
        "query": {"pol": pol, "pod": pod},
    }


@router.post("/spot/refresh", response_model=SpotRefreshResponse)
async def refresh_spot_cache():
    """Force refresh the spot rate cache."""
    from ERP.intelligence.spot_cache import refresh_spot_cache as do_refresh

    result = do_refresh()
    return SpotRefreshResponse(**result)


# ── TRACKING Endpoints ────────────────────────────────────────

@router.get("/track/{identifier}")
async def track(identifier: str):
    """
    Track a container or job.
    Auto-detects if identifier is a container number or job ID.
    """
    identifier = identifier.strip().upper()

    # Container number: 4 letters + 7 digits
    if len(identifier) == 11 and identifier[:4].isalpha() and identifier[4:].isdigit():
        return await _track_container(identifier)
    else:
        return await _track_job(identifier)


async def _track_container(container_no: str):
    """Track a single container."""
    from ERP.intelligence.tracking_manager import (
        get_container_detail,
        track_container_hpl,
    )

    # Try HPL API first
    track_container_hpl(container_no)

    detail = get_container_detail(container_no)
    if not detail:
        raise HTTPException(404, f"Container {container_no} not found")

    return {
        "type": "container",
        "data": detail,
    }


async def _track_job(job_id: str):
    """Track all containers in a job."""
    from ERP.intelligence.tracking_manager import get_job_tracking_summary

    containers = get_job_tracking_summary(job_id)

    total = len(containers)
    loaded = sum(1 for c in containers if c.get("status") in ("LOAD", "VD", "VA", "DISC", "GTOT", "AVPU", "DLVD"))

    return {
        "type": "job",
        "job_id": job_id,
        "containers": containers,
        "summary": {
            "total": total,
            "loaded": loaded,
            "pending": total - loaded,
        },
    }


@router.post("/track/add")
async def add_containers(req: AddContainersRequest):
    """Add containers to a job."""
    from ERP.intelligence.tracking_manager import add_containers_to_job

    result = add_containers_to_job(
        job_id=req.job_id,
        containers=req.containers,
        pol=req.pol,
        pod=req.pod,
    )

    return {"status": "ok", "message": result}


# ── WEBHOOK Endpoint ─────────────────────────────────────────

@router.post("/webhook/events")
async def receive_webhook(request: Request):
    """
    DCSA T&T v2.2 webhook receiver.
    HPL pushes tracking events here.

    Expected payload:
        {
            "eventType": "EQUIPMENT",
            "eventClassifierCode": "LOAD",
            "equipmentReference": "HLXU1234567",
            ...
        }
    """
    try:
        event_data = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    from ERP.intelligence.tracking_manager import handle_webhook_event

    success = handle_webhook_event(event_data)

    if success:
        return {"status": "accepted"}
    else:
        raise HTTPException(422, "Could not process event")


# ── HEALTH Endpoint ───────────────────────────────────────────

@router.get("/status")
async def hpl_status():
    """HPL integration health check."""
    import sqlite3

    status = {
        "hpl_integration": "active",
        "api_configured": bool(os.getenv("HPL_CLIENT_ID")),
        "timestamp": datetime.now().isoformat(),
        "databases": {},
    }

    # Check spot_cache.sqlite
    _data_dir = os.path.join(os.path.dirname(os.path.dirname(_API_DIR)),
                             "ERP", "data")
    for db_name in ["spot_cache.sqlite", "tracking.sqlite"]:
        db_path = os.path.join(_data_dir, db_name)
        if os.path.exists(db_path):
            try:
                from shared.db_connect import get_db
                conn = get_db(db_path, readonly=True)
                if "spot" in db_name:
                    count = conn.execute("SELECT COUNT(*) FROM spot_rates").fetchone()[0]
                    latest = conn.execute(
                        "SELECT MAX(fetched_at) FROM spot_rates"
                    ).fetchone()[0]
                else:
                    count = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
                    latest = conn.execute(
                        "SELECT MAX(updated_at) FROM containers"
                    ).fetchone()[0]
                conn.close()
                status["databases"][db_name] = {
                    "exists": True,
                    "records": count,
                    "last_updated": latest,
                }
            except Exception as e:
                status["databases"][db_name] = {"exists": True, "error": str(e)}
        else:
            status["databases"][db_name] = {"exists": False}

    return status
