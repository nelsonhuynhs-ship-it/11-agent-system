# -*- coding: utf-8 -*-
"""
email_router.py — Email Event Engine Endpoints
================================================
Email scan, sync, alerts, and timeline.
"""
from __future__ import annotations

import os
import sys

from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/email-events", tags=["Email Events"])

# Lazy import email engine
_email_engine = None


def _get_email_engine():
    global _email_engine
    if _email_engine is None:
        try:
            from email_event_engine import (
                sync_email_dataset, get_sync_status, get_active_alerts,
                get_shipment_email_timeline, generate_summary,
            )
            _email_engine = {
                "sync": sync_email_dataset,
                "status": get_sync_status,
                "alerts": get_active_alerts,
                "timeline": get_shipment_email_timeline,
                "summary": generate_summary,
            }
        except ImportError:
            return None
    return _email_engine


@router.post("/sync")
def email_events_sync():
    """Trigger sync: outlook_dataset.json -> shipment_state.json."""
    ee = _get_email_engine()
    if not ee:
        return {"error": "email_event_engine not available", "ok": False}
    try:
        stats = ee["sync"]()
        return {"ok": True, **stats}
    except Exception as e:
        return {"error": str(e), "ok": False}


@router.get("/status")
def email_events_status():
    """Return sync status."""
    ee = _get_email_engine()
    if not ee:
        return {"error": "email_event_engine not available"}
    return ee["status"]()


@router.get("/alerts")
def email_events_alerts():
    """Return active trouble alerts detected from emails."""
    ee = _get_email_engine()
    if not ee:
        return {"alerts": [], "error": "email_event_engine not available"}
    alerts = ee["alerts"]()
    return {"alerts": alerts, "total": len(alerts)}


@router.post("/scan")
def email_events_scan(quick: bool = Query(True)):
    """Trigger Outlook email scan + dataset rebuild."""
    try:
        from email_scanner import run_scan
        result = run_scan(quick=quick)
        ee = _get_email_engine()
        if result.get("ok") and ee:
            sync_stats = ee["sync"]()
            result["sync_stats"] = sync_stats
        return result
    except ImportError:
        return {"error": "email_scanner module not available", "ok": False}
    except Exception as e:
        return {"error": str(e), "ok": False}


@router.get("/timeline/{shipment_id}")
def email_timeline(shipment_id: str):
    """Get email-sourced event timeline for a specific shipment."""
    ee = _get_email_engine()
    if not ee:
        return {"events": [], "error": "email_event_engine not available"}
    events = ee["timeline"](shipment_id)
    return {"shipment_id": shipment_id, "events": events, "total": len(events)}


# ─── Email AI Features ────────────────────────────────────────────

@router.post("/api/emails/summarize")
def summarize_email_route(sender: str = "", body: str = ""):
    """Summarize email content and return structured sentiment/action."""
    from email_engine.core.ai_email import summarize_email
    return summarize_email(body=body, sender=sender)


@router.post("/api/emails/draft-reply")
def draft_reply_route(incoming: dict = None, cnee_context: dict = None):
    """Draft a reply to an incoming email using CNEE context."""
    from email_engine.core.ai_email import draft_reply
    if incoming is None:
        incoming = {}
    if cnee_context is None:
        cnee_context = {}
    return {"reply": draft_reply(incoming, cnee_context)}


@router.post("/api/compose/suggest")
def suggest_route(thread_history: list = None, draft_so_far: str = ""):
    """Suggest the next sentence given thread history and current draft."""
    from email_engine.core.ai_email import suggest_next_sentence
    if thread_history is None:
        thread_history = []
    return {"suggestion": suggest_next_sentence(thread_history, draft_so_far)}
