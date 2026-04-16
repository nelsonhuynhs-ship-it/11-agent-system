"""
events.py — Event type constants + builder helpers (Phase 02)
=============================================================
Centralized factory for event dicts so callers (worker / scanner / GoClaw /
manual notes) all produce the same shape, ready for `memory.log_event()`.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Event type catalogue (kept simple — no Enum to avoid serialization friction
# when these dicts cross sqlite / JSON / FastAPI boundaries).
# ---------------------------------------------------------------------------

SENT = "SENT"
REPLY = "REPLY"
AUTO_REPLY = "AUTO_REPLY"
BOUNCE = "BOUNCE"
UNSUBSCRIBE = "UNSUBSCRIBE"
TIER_PROMOTED = "TIER_PROMOTED"
TIER_DEMOTED = "TIER_DEMOTED"
GOCLAW_DRAFTED = "GOCLAW_DRAFTED"
MANUAL_NOTE = "MANUAL_NOTE"

EVENT_TYPES = {
    SENT, REPLY, AUTO_REPLY, BOUNCE, UNSUBSCRIBE,
    TIER_PROMOTED, TIER_DEMOTED, GOCLAW_DRAFTED, MANUAL_NOTE,
}

# Sentiment / intent vocab — kept here for cross-module reference.
SENTIMENTS = {"POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"}
INTENTS = {
    "booking", "price_inquiry", "negotiating",
    "gratitude", "objection", "general",
}
BOUNCE_TYPES = {"HARD", "SOFT", "POLICY"}


def _clean_email(addr: str | None) -> str:
    return (addr or "").strip().lower()


def _trim(text: str | None, n: int = 500) -> str | None:
    if text is None:
        return None
    s = str(text).strip()
    return s[:n] if len(s) > n else s


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_sent_event(
    cnee_email: str,
    subject: str,
    template_id: str | None = None,
    market_state: str | None = None,
    delta_pct: float | None = None,
    batch_id: str | None = None,
    campaign_id: str | None = None,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": SENT,
        "cnee_email": _clean_email(cnee_email),
        "subject": subject,
        "template_id": template_id,
        "market_state": market_state,
        "delta_pct": delta_pct,
        "batch_id": batch_id,
        "campaign_id": campaign_id,
        "raw_meta": raw_meta,
    }


def build_reply_event(
    cnee_email: str,
    reply_subject: str | None = None,
    reply_body_snippet: str | None = None,
    sentiment: str | None = None,
    intent: str | None = None,
    reply_delay_hours: float | None = None,
    auto_reply: bool = False,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": AUTO_REPLY if auto_reply else REPLY,
        "cnee_email": _clean_email(cnee_email),
        "reply_subject": reply_subject,
        "reply_body_snippet": _trim(reply_body_snippet, 500),
        "sentiment": sentiment,
        "intent": intent,
        "reply_delay_hours": reply_delay_hours,
        "raw_meta": raw_meta,
    }


def build_bounce_event(
    cnee_email: str,
    bounce_type: str = "HARD",
    bounce_reason: str | None = None,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": BOUNCE,
        "cnee_email": _clean_email(cnee_email),
        "bounce_type": bounce_type if bounce_type in BOUNCE_TYPES else "HARD",
        "bounce_reason": _trim(bounce_reason, 500),
        "raw_meta": raw_meta,
    }


def build_unsubscribe_event(
    cnee_email: str,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": UNSUBSCRIBE,
        "cnee_email": _clean_email(cnee_email),
        "raw_meta": raw_meta,
    }


def build_tier_event(
    cnee_email: str,
    old_tier: str | None,
    new_tier: str,
    change_reason: str,
    promoted: bool = True,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": TIER_PROMOTED if promoted else TIER_DEMOTED,
        "cnee_email": _clean_email(cnee_email),
        "old_tier": old_tier,
        "new_tier": new_tier,
        "change_reason": change_reason,
        "raw_meta": raw_meta,
    }
