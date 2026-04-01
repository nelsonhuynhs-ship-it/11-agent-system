# -*- coding: utf-8 -*-
"""
worker_router.py — Worker Monitoring + Control Endpoints
==========================================================
Monitor and control background workers from the API.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/workers", tags=["Workers"])


def _get_workers():
    """Lazy import workers to avoid circular imports."""
    workers = {}
    try:
        from workers.email_worker import email_worker
        workers["email"] = email_worker
    except Exception:
        pass
    try:
        from workers.intelligence_worker import intelligence_worker
        workers["intelligence"] = intelligence_worker
    except Exception:
        pass
    try:
        from workers.evaluator_worker import evaluator_worker
        workers["evaluator"] = evaluator_worker
    except Exception:
        pass
    return workers


@router.get("")
def get_workers_status():
    """Get status of all background workers."""
    workers = _get_workers()
    status = {}
    for name, worker in workers.items():
        try:
            status[name] = worker.status
        except Exception as e:
            status[name] = {"error": str(e)}
    return {"workers": status, "total": len(workers)}


@router.post("/email/scan")
def trigger_email_scan():
    """Manually trigger email scan + sync cycle."""
    try:
        from workers.email_worker import email_worker
        result = email_worker.run_scan_and_sync()
        return {"result": result, "triggered": True}
    except Exception as e:
        return {"error": str(e), "triggered": False}


@router.post("/evaluator/run")
def trigger_evaluation():
    """Manually trigger daily evaluation."""
    try:
        from workers.evaluator_worker import evaluator_worker
        report = evaluator_worker.run_evaluation()
        return {"report": report, "triggered": True}
    except Exception as e:
        return {"error": str(e), "triggered": False}


@router.post("/intelligence/recalculate")
def trigger_intelligence():
    """Manually trigger intelligence batch recalculation."""
    try:
        from workers.intelligence_worker import intelligence_worker
        result = intelligence_worker.recalculate_all()
        return {"result": result, "triggered": True}
    except Exception as e:
        return {"error": str(e), "triggered": False}


@router.get("/alerts")
def get_worker_alerts():
    """Get alert history from notification service."""
    try:
        from services.notification import notification_service
        alerts = notification_service.get_alert_history()
        return {
            "alerts": alerts,
            "total": len(alerts),
            "service_status": notification_service.status,
        }
    except Exception as e:
        return {"error": str(e)}
