"""
tier_engine.py — TIER promotion / demotion rules (Phase 02)
============================================================
Pure decision layer: given an event + current state, compute the tier change(s)
that should be persisted (TIER_PROMOTED / TIER_DEMOTED events) and the
write-back fields (TIER, ACTION, EMAIL_QUALITY_SCORE, EMAIL_STATUS) for
cnee_master_v2.xlsx.

Rules (per Phase 02 plan):
    REPLY + sentiment=POSITIVE + intent in {booking,price_inquiry}:
        WARM_B/COOL -> WARM_A
        WARM_A      -> HOT
    REPLY (any) on COOL:        -> WARM_B
    BOUNCE (HARD) 1-2x:          EMAIL_QUALITY_SCORE -= 15
    BOUNCE (HARD) >= 3x:         TIER=PARK, ACTION=SKIP, EMAIL_STATUS=HARD_BOUNCE
    UNSUBSCRIBE:                 TIER=PARK, ACTION=SKIP (permanent)
    180d silent on HOT/WARM_A:   TIER=COOL

Action routing post tier change:
    VIP    -> PERSONALIZED
    HOT    -> FOLLOW_UP
    WARM_A -> SEQUENCE_NEXT (caller decides if mid-sequence) else SEND_NOW
    WARM_B -> SEND_NOW
    COOL   -> SEND_NOW (cooldown 5d enforced upstream)
    PARK   -> SKIP

This module deliberately does NOT touch SQLite or xlsx — callers wire the
returned actions to memory.log_event() + writeback.update_master().
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from . import memory
from .events import (
    REPLY, AUTO_REPLY, BOUNCE, UNSUBSCRIBE,
    build_tier_event,
)

# Action map after tier resolves
_ACTION_BY_TIER = {
    "VIP": "PERSONALIZED",
    "HOT": "FOLLOW_UP",
    "WARM_A": "SEND_NOW",   # caller may upgrade to SEQUENCE_NEXT
    "WARM_B": "SEND_NOW",
    "COOL": "SEND_NOW",
    "PARK": "SKIP",
}

POSITIVE_INTENTS = {"booking", "price_inquiry"}
HARD_BOUNCE_PARK_THRESHOLD = 3
SILENT_DAYS_FOR_DEMOTION = 180
EMAIL_QUALITY_BOUNCE_PENALTY = 15


def action_for_tier(tier: str) -> str:
    return _ACTION_BY_TIER.get(tier, "SEND_NOW")


# ---------------------------------------------------------------------------
# Promotion path
# ---------------------------------------------------------------------------

def _promote_path(current_tier: str, sentiment: str | None, intent: str | None) -> str | None:
    """Return new tier if promotion rule matches, else None."""
    sentiment = (sentiment or "").upper()
    intent = (intent or "").lower()
    strong = sentiment == "POSITIVE" and intent in POSITIVE_INTENTS

    if strong:
        if current_tier in ("WARM_B", "COOL"):
            return "WARM_A"
        if current_tier == "WARM_A":
            return "HOT"
        return None

    # Any reply on COOL nudges back to WARM_B (re-engagement signal)
    if current_tier == "COOL":
        return "WARM_B"
    return None


def apply_promotion_rules(
    cnee_email: str,
    event_type: str,
    sentiment: str | None = None,
    intent: str | None = None,
    current_tier: str | None = None,
) -> dict[str, Any] | None:
    """Decide a promotion. Returns action dict or None.

    `current_tier` may be passed by caller (e.g. read from master v2). If None,
    we fall back to the most recent tier event in intel.db.
    """
    if event_type not in (REPLY, AUTO_REPLY):
        return None
    tier = current_tier or _last_known_tier(cnee_email)
    if tier is None:
        return None
    new_tier = _promote_path(tier, sentiment, intent)
    if new_tier is None or new_tier == tier:
        return None
    return {
        "cnee_email": cnee_email,
        "old_tier": tier,
        "new_tier": new_tier,
        "new_action": action_for_tier(new_tier),
        "reason": (
            f"REPLY sentiment={sentiment or '?'} intent={intent or '?'}"
            f" -> promote {tier}->{new_tier}"
        ),
        "writeback_fields": {
            "TIER": new_tier,
            "ACTION": action_for_tier(new_tier),
            "REPLY_STATUS": "REPLIED",
        },
        "promoted": True,
    }


# ---------------------------------------------------------------------------
# Demotion path
# ---------------------------------------------------------------------------

def apply_demotion_rules(
    cnee_email: str,
    event_type: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Decide a demotion. Returns action dict or None.

    `extra` may carry: bounce_type, current_tier, last_reply_at, sent_count.
    HARD bounce threshold uses cnee_state.bounce_count (incremented by
    log_event itself before this is called for fresh BOUNCE events).
    """
    extra = extra or {}
    current_tier = extra.get("current_tier") or _last_known_tier(cnee_email)

    if event_type == UNSUBSCRIBE:
        if current_tier == "PARK":
            return None  # already parked
        return _park(cnee_email, current_tier, "UNSUBSCRIBE")

    if event_type == BOUNCE:
        bounce_type = (extra.get("bounce_type") or "HARD").upper()
        if bounce_type != "HARD":
            return None  # soft/policy don't park
        state = memory.get_cnee_state(cnee_email)
        bcount = int(state.get("bounce_count") or 0)
        if bcount >= HARD_BOUNCE_PARK_THRESHOLD:
            return _park(cnee_email, current_tier,
                         f"HARD bounce x{bcount}",
                         email_status="HARD_BOUNCE")
        # soft penalty: drop quality score but keep tier
        return {
            "cnee_email": cnee_email,
            "old_tier": current_tier,
            "new_tier": current_tier,
            "new_action": None,
            "reason": f"HARD bounce x{bcount} (penalty only)",
            "writeback_fields": {
                "EMAIL_QUALITY_SCORE_DELTA": -EMAIL_QUALITY_BOUNCE_PENALTY,
            },
            "promoted": False,
            "tier_change": False,
        }

    return None


def _park(cnee_email: str, current_tier: str | None,
          reason: str, email_status: str | None = None) -> dict[str, Any]:
    fields = {"TIER": "PARK", "ACTION": "SKIP"}
    if email_status:
        fields["EMAIL_STATUS"] = email_status
    return {
        "cnee_email": cnee_email,
        "old_tier": current_tier,
        "new_tier": "PARK",
        "new_action": "SKIP",
        "reason": reason,
        "writeback_fields": fields,
        "promoted": False,
    }


# ---------------------------------------------------------------------------
# Time-based demotion (180d silent) — called by scanner sweep, not per-event
# ---------------------------------------------------------------------------

def evaluate_silent_demotion(cnee_email: str,
                             current_tier: str,
                             last_reply_at: str | None,
                             last_sent_at: str | None) -> dict[str, Any] | None:
    """If CNEE is HOT/WARM_A and silent > 180d -> demote to COOL.
    `last_reply_at` / `last_sent_at` are ISO strings 'YYYY-MM-DD HH:MM:SS'."""
    if current_tier not in ("HOT", "WARM_A"):
        return None
    last_touch = last_reply_at or last_sent_at
    if not last_touch:
        return None
    try:
        t = datetime.strptime(last_touch, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    if (datetime.utcnow() - t) <= timedelta(days=SILENT_DAYS_FOR_DEMOTION):
        return None
    return {
        "cnee_email": cnee_email,
        "old_tier": current_tier,
        "new_tier": "COOL",
        "new_action": action_for_tier("COOL"),
        "reason": f"silent > {SILENT_DAYS_FOR_DEMOTION}d",
        "writeback_fields": {
            "TIER": "COOL",
            "ACTION": action_for_tier("COOL"),
        },
        "promoted": False,
    }


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------

def evaluate_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Single entry point used by worker / scanner.

    Returns 0..N action dicts. Caller is responsible for:
      1. memory.log_event(build_tier_event(...)) for each action
      2. writeback.update_master(cnee, action['writeback_fields'])
    """
    et = event.get("event_type")
    cnee = (event.get("cnee_email") or "").strip().lower()
    if not et or not cnee:
        return []
    actions: list[dict[str, Any]] = []

    if et in (REPLY, AUTO_REPLY):
        a = apply_promotion_rules(
            cnee, et,
            sentiment=event.get("sentiment"),
            intent=event.get("intent"),
            current_tier=event.get("_current_tier"),
        )
        if a:
            actions.append(a)
    elif et == BOUNCE:
        a = apply_demotion_rules(cnee, et, {
            "bounce_type": event.get("bounce_type"),
            "current_tier": event.get("_current_tier"),
        })
        if a:
            actions.append(a)
    elif et == UNSUBSCRIBE:
        a = apply_demotion_rules(cnee, et, {
            "current_tier": event.get("_current_tier"),
        })
        if a:
            actions.append(a)

    return actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_known_tier(cnee_email: str) -> str | None:
    """Best-effort: last tier change in intel.db. Real source of truth lives in
    cnee_master_v2.xlsx and should be passed via current_tier when available."""
    summary = memory.get_cnee_summary(cnee_email)
    return summary.get("current_tier")


def make_tier_event(action: dict[str, Any]) -> dict[str, Any]:
    """Convenience builder so callers can directly do:
        tier_event = make_tier_event(action); memory.log_event(tier_event)
    """
    return build_tier_event(
        cnee_email=action["cnee_email"],
        old_tier=action.get("old_tier"),
        new_tier=action["new_tier"],
        change_reason=action.get("reason", ""),
        promoted=bool(action.get("promoted")),
    )
