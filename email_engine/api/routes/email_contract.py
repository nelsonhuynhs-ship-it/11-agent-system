# email_contract.py — Phase 6: Backend API Contract
# Canonical response shape for email dashboard v9.
# All email-state endpoints return the same base shape: ok, version, source, counts.
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from email_engine.queue_store import (
    event_summary as _event_summary,
    get_batch_status as _get_batch_status,
    kill_switch_active,
)
from email_engine.core.email_address_guard import EmailAddressGuard
from email_engine.core.outlook_reconcile import reconcile
from email_engine.core.reply_sync import generate_writeback_payload
from email_engine.core.followup_suggestion import get_followup_suggestions

log = logging.getLogger("email_contract")

router = APIRouter(prefix="/api/email", tags=["email-v9-contract"])

# ---------------------------------------------------------------------------
# Canonical response base
# ---------------------------------------------------------------------------

def canonical_ok(version: str = "v9", source: str = "outlook_com",
                  campaign_id: str = "", counts: dict | None = None,
                  items: list | None = None, warnings: list | None = None,
                  needs_verification: list | None = None) -> dict:
    return {
        "ok": True,
        "version": version,
        "source": source,
        "campaign_id": campaign_id,
        "counts": counts or {},
        "items": items or [],
        "warnings": warnings or [],
        "needs_verification": needs_verification or [],
    }


def canonical_error(msg: str, version: str = "v9") -> dict:
    return {"ok": False, "version": version, "error": msg}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ValidateRequest(BaseModel):
    emails: list[str]
    campaign_id: str = ""


class QueuePreviewRequest(BaseModel):
    emails: list[dict]
    campaign_id: str = ""


class SendOutlookRequest(BaseModel):
    to: str
    subject: str
    html_body: str
    campaign_id: str = ""
    cc: str = ""


class PostSendReconcileRequest(BaseModel):
    message_key: str
    to: str
    subject: str
    sent_after: str = ""


class QuarantineResolveRequest(BaseModel):
    cnee_email: str
    resolution: str  # "approve" | "reject" | "fix"
    fixed_email: str | None = None


class SuppressionAddRequest(BaseModel):
    cnee_email: str
    reason: str
    status: str = "HARD_BOUNCE"


# ---------------------------------------------------------------------------
# GET /api/dashboard/v9/status
# ---------------------------------------------------------------------------

@router.get("/dashboard/v9/status")
def dashboard_v9_status(campaign_id: str = ""):
    """Top-level dashboard state: event counts + queue batch status."""
    try:
        # Aggregate from event store
        es = _event_summary(campaign_id=campaign_id or "")
        batch_status = {}
        if campaign_id:
            bs = _get_batch_status(campaign_id)
            batch_status = {
                "total": bs.get("total", 0),
                "pending": bs.get("pending", 0),
                "sending": bs.get("sending", 0),
                "sent": bs.get("sent", 0),
                "failed": bs.get("failed", 0),
                "rate_per_min": bs.get("rate_per_min", 0.0),
                "eta_finish": bs.get("eta_finish"),
            }

        counts = {
            **es.get("by_status", {}),
            "total_events": es.get("total", 0),
            **batch_status,
        }
        # Add kill switch state
        if kill_switch_active():
            counts["kill_switch_active"] = True

        return canonical_ok(
            campaign_id=campaign_id,
            counts=counts,
        )
    except Exception as exc:
        log.error("dashboard_v9_status error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# POST /api/email/validate
# ---------------------------------------------------------------------------

@router.post("/validate")
def validate_emails(req: ValidateRequest):
    """Pre-send validation: run EmailAddressGuard on each email, return summary."""
    guard = EmailAddressGuard()
    results = []
    for email in req.emails:
        r = guard.guard(email)
        results.append(r)

    sendable = [r for r in results if r.get("is_sendable", False)]
    blocked = [r for r in results if not r.get("is_sendable", True)]
    by_reason: dict[str, int] = {}
    for r in blocked:
        rc = r.get("reason_code", "UNKNOWN")
        by_reason[rc] = by_reason.get(rc, 0) + 1

    return {
        "ok": True,
        "version": "v9",
        "campaign_id": req.campaign_id,
        "counts": {
            "total": len(results),
            "sendable_count": len(sendable),
            "quarantine_count": len(blocked),
        },
        "blocked_by_reason": by_reason,
        "items": results,
    }


# ---------------------------------------------------------------------------
# POST /api/email/queue-preview
# ---------------------------------------------------------------------------

@router.post("/queue-preview")
def queue_preview(req: QueuePreviewRequest):
    """Preview what would be queued: validation + stats without enqueueing."""
    guard = EmailAddressGuard()
    sendable = []
    blocked = []
    warnings = []

    for em in req.emails:
        email_addr = em.get("cnee_email", "")
        if not email_addr:
            warnings.append({"email": "", "warning": "missing cnee_email"})
            continue
        r = guard.guard(email_addr)
        if r.get("is_sendable", False):
            sendable.append(em)
        else:
            blocked.append({**em, "block_reason": r.get("reason_code", "UNKNOWN")})

    return {
        "ok": True,
        "version": "v9",
        "campaign_id": req.campaign_id,
        "counts": {
            "total": len(req.emails),
            "sendable_count": len(sendable),
            "blocked_count": len(blocked),
        },
        "items": sendable,
        "blocked_items": blocked,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# POST /api/email/send-outlook
# ---------------------------------------------------------------------------

@router.post("/send-outlook")
def send_outlook(req: SendOutlookRequest):
    """Send one email via Outlook COM. Returns SENT_PENDING_VERIFICATION."""
    try:
        from email_engine.core.outlook_com_adapter import send_mail
        result = send_mail(
            to=req.to,
            subject=req.subject,
            html_body=req.html_body,
            campaign_id=req.campaign_id,
            cc=req.cc,
        )
        return {
            "ok": result["ok"],
            "version": "v9",
            "source": "outlook_com",
            "message_key": result.get("message_key", ""),
            "verification_status": result.get("verification_status", "SENT_PENDING_VERIFICATION"),
            "outlook_entry_id": result.get("outlook_entry_id"),
            "conversation_id": result.get("conversation_id"),
            "sent_at": result.get("sent_at"),
            "to": req.to,
            "subject": req.subject,
            "error": result.get("error"),
        }
    except Exception as exc:
        log.error("send_outlook error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# GET /api/email/send-status/{campaign_id}
# ---------------------------------------------------------------------------

@router.get("/send-status/{campaign_id}")
def email_send_status(campaign_id: str):
    """Get batch send status for a campaign."""
    try:
        bs = _get_batch_status(campaign_id)
        return {
            "ok": True,
            "version": "v9",
            "campaign_id": campaign_id,
            "counts": {
                "total": bs.get("total", 0),
                "pending": bs.get("pending", 0),
                "sending": bs.get("sending", 0),
                "sent": bs.get("sent", 0),
                "failed": bs.get("failed", 0),
            },
            "rate_per_min": bs.get("rate_per_min", 0.0),
            "eta_finish": bs.get("eta_finish"),
            "started_at": bs.get("started_at"),
            "last_sent": bs.get("last_sent"),
        }
    except Exception as exc:
        log.error("email_send_status error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# POST /api/email/post-send-reconcile
# ---------------------------------------------------------------------------

@router.post("/post-send-reconcile")
def post_send_reconcile(req: PostSendReconcileRequest):
    """Run post-send reconciliation: find_sent_mail + scan_inbox_for_ndr."""
    try:
        from datetime import datetime as dt
        sent_after = dt.now(timezone.utc)
        if req.sent_after:
            try:
                sent_after = dt.fromisoformat(req.sent_after)
            except Exception:
                pass

        result = reconcile(
            to=req.to,
            subject=req.subject,
            message_key=req.message_key,
            sent_after=sent_after,
        )
        return {
            "ok": True,
            "version": "v9",
            "message_key": req.message_key,
            "sent_confirmed": result.get("sent_confirmed", {}),
            "ndr_results": result.get("ndr_results", []),
        }
    except Exception as exc:
        log.error("post_send_reconcile error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# GET /api/email/replies
# ---------------------------------------------------------------------------

@router.get("/replies")
def get_replies(campaign_id: str = "", hours_back: int = 72):
    """Return reply events from the event store."""
    try:
        from email_engine.queue_store import get_events_for_email
        # Just return all reply events across campaign
        # (events are stored per-email, so we query via email)
        # For now, return event summary grouped by reply_class
        es = _event_summary(campaign_id=campaign_id)
        counts = es.get("by_status", {})
        return {
            "ok": True,
            "version": "v9",
            "campaign_id": campaign_id,
            "counts": {
                "total_replies": counts.get("REPLY_DETECTED", 0) + counts.get("REPLY_CLASSIFIED", 0),
                "hot_reply": counts.get("HOT_REPLY", 0),
                "quote_request": counts.get("QUOTE_REQUEST", 0),
                "rate_question": counts.get("RATE_QUESTION", 0),
                "needs_human_reply": counts.get("NEEDS_HUMAN_REPLY", 0),
                "auto_reply": counts.get("AUTO_REPLY", 0),
            },
        }
    except Exception as exc:
        log.error("get_replies error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# POST /api/email/replies/scan
# ---------------------------------------------------------------------------

@router.post("/replies/scan")
def scan_replies_endpoint(sender_emails: list[str] = [], hours_back: int = 72):
    """Scan inbox for replies from given sender emails."""
    try:
        from email_engine.core.reply_sync import scan_inbox_for_replies
        from email_engine.queue_store import log_event
        import uuid

        results = scan_inbox_for_replies(
            sender_emails=sender_emails,
            hours_back=hours_back,
        )

        # Log detected replies as events
        for detection in results:
            event_id = str(uuid.uuid4())
            log_event(
                event_id=event_id,
                cnee_email=detection.get("sender", ""),
                event_type="REPLY_DETECTED",
                status=detection.get("reply_class", "UNKNOWN_REPLY"),
                message_key=detection.get("conversation_id", ""),
                subject=detection.get("subject", ""),
                raw_json=str(detection),
            )

        return {
            "ok": True,
            "version": "v9",
            "counts": {"replies_found": len(results)},
            "items": results,
        }
    except Exception as exc:
        log.error("scan_replies error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# GET /api/email/followups/suggest
# ---------------------------------------------------------------------------

@router.get("/followups/suggest")
def followups_suggest(campaign_id: str = "", days_back: int = 3):
    """Return follow-up candidates: sent but no reply after N days."""
    try:
        suggestions = get_followup_suggestions(
            campaign_id=campaign_id,
            days_back=days_back,
        )
        return {
            "ok": True,
            "version": "v9",
            "campaign_id": campaign_id,
            "counts": {
                "total": len(suggestions),
                "urgent": sum(1 for s in suggestions if s["days_since_sent"] >= 7),
                "pending": sum(1 for s in suggestions if s["days_since_sent"] < 7),
            },
            "items": suggestions,
        }
    except Exception as exc:
        log.error("followups_suggest error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# GET /api/email/quarantine
# ---------------------------------------------------------------------------

@router.get("/quarantine")
def get_quarantine(campaign_id: str = ""):
    """Return emails currently quarantined (blocked by guard)."""
    try:
        es = _event_summary(campaign_id=campaign_id)
        by_status = es.get("by_status", {})
        quarantined = {
            k: v for k, v in by_status.items()
            if k not in (
                "SENT_CONFIRMED", "SENT_PENDING_VERIFICATION",
                "PRE_SEND_VALIDATED", "QUEUED", "OUTLOOK_SEND_ATTEMPT"
            )
        }
        return {
            "ok": True,
            "version": "v9",
            "campaign_id": campaign_id,
            "counts": quarantined,
            "total": sum(quarantined.values()),
        }
    except Exception as exc:
        log.error("get_quarantine error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# POST /api/email/quarantine/resolve
# ---------------------------------------------------------------------------

@router.post("/quarantine/resolve")
def resolve_quarantine(req: QuarantineResolveRequest):
    """Resolve a quarantined email: approve (move to sendable) or reject."""
    try:
        from email_engine.queue_store import log_event
        import uuid

        event_id = str(uuid.uuid4())
        if req.resolution == "approve":
            status = "APPROVED"
        elif req.resolution == "fix" and req.fixed_email:
            status = f"FIXED:{req.fixed_email}"
        else:
            status = "REJECTED"

        log_event(
            event_id=event_id,
            cnee_email=req.cnee_email,
            event_type="QUARANTINE_RESOLVED",
            status=status,
            campaign_id="",
        )
        return {
            "ok": True,
            "version": "v9",
            "cnee_email": req.cnee_email,
            "resolution": status,
        }
    except Exception as exc:
        log.error("resolve_quarantine error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# GET /api/email/suppression
# ---------------------------------------------------------------------------

@router.get("/suppression")
def get_suppression():
    """Return suppression summary from event store."""
    try:
        es = _event_summary()
        by_status = es.get("by_status", {})
        suppressed = {
            k: v for k, v in by_status.items()
            if k in (
                "HARD_BOUNCE", "SOFT_BOUNCE", "DEAD",
                "UNSUBSCRIBED", "SPAM", "INVALID", "NO_MX"
            )
        }
        return {
            "ok": True,
            "version": "v9",
            "counts": suppressed,
            "total": sum(suppressed.values()),
        }
    except Exception as exc:
        log.error("get_suppression error: %s", exc)
        return canonical_error(str(exc))


# ---------------------------------------------------------------------------
# POST /api/email/suppression/add
# ---------------------------------------------------------------------------

@router.post("/suppression/add")
def add_suppression(req: SuppressionAddRequest):
    """Add a customer to the suppression list."""
    try:
        from email_engine.queue_store import log_event
        import uuid

        event_id = str(uuid.uuid4())
        log_event(
            event_id=event_id,
            cnee_email=req.cnee_email,
            event_type="SUPPRESSION_ADDED",
            status=req.status,
            reason_code=req.reason,
        )
        return {
            "ok": True,
            "version": "v9",
            "cnee_email": req.cnee_email,
            "status": req.status,
            "reason": req.reason,
        }
    except Exception as exc:
        log.error("add_suppression error: %s", exc)
        return canonical_error(str(exc))