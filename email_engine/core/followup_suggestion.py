#!/usr/bin/env python3
"""
Phase 5: Follow-up Suggestion — surface customers ready for follow-up.
Rules:
- Customer was sent 3+ days ago with no reply detected.
- Not already in HOT_REPLY, QUOTE_REQUEST, or RATE_QUESTION state.
- Not already in cooldown period.
- Dashboard may suggest a follow-up draft; must NOT auto-send.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

log = logging.getLogger(__name__)

FOLLOWUP_DAYS_DEFAULT = 3


class FollowupSuggestion(TypedDict):
    cnee_email: str
    campaign_id: str
    subject: str
    followup_reason: str  # "no_reply_3d" | "ndr_cleared" | etc.
    days_since_sent: int
    draft_preview: str  # truncated html body preview
    priority_score: int  # lower = higher priority


def get_followup_suggestions(
    campaign_id: str = "",
    days_back: int = 3,
    db_path: str | None = None,
) -> list[FollowupSuggestion]:
    """Scan email_events for sent customers with no reply, return follow-up candidates.

    Logic:
    - Find SENT_CONFIRMED events with no subsequent REPLY_DETECTED.
    - Skip customers who already have HOT_REPLY, QUOTE_REQUEST, RATE_QUESTION.
    - Skip customers in cooldown (last activity < cooldown threshold).
    - Sort by days_since_sent descending (oldest first = highest priority).
    """
    from email_engine.queue_store import _connect, _now_iso

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with _connect(db_path) as conn:
        # Find customers who were sent but haven't replied
        if campaign_id:
            rows = conn.execute(
                """SELECT e.cnee_email, e.campaign_id, e.subject,
                          MIN(e.detected_at) as sent_at,
                          COUNT(*) as event_count
                     FROM email_events e
                     WHERE e.event_type = 'SENT_CONFIRMED'
                       AND e.campaign_id = ?
                       AND e.detected_at <= ?
                       AND e.cnee_email NOT IN (
                           SELECT cnee_email FROM email_events
                           WHERE event_type IN ('REPLY_DETECTED','REPLY_CLASSIFIED')
                             AND reply_class IN ('HOT_REPLY','QUOTE_REQUEST','RATE_QUESTION')
                       )
                     GROUP BY e.cnee_email, e.campaign_id, e.subject
                     ORDER BY sent_at ASC""",
                (campaign_id, cutoff_str),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT e.cnee_email, e.campaign_id, e.subject,
                          MIN(e.detected_at) as sent_at,
                          COUNT(*) as event_count
                     FROM email_events e
                     WHERE e.event_type = 'SENT_CONFIRMED'
                       AND e.detected_at <= ?
                       AND e.cnee_email NOT IN (
                           SELECT cnee_email FROM email_events
                           WHERE event_type IN ('REPLY_DETECTED','REPLY_CLASSIFIED')
                             AND reply_class IN ('HOT_REPLY','QUOTE_REQUEST','RATE_QUESTION')
                       )
                     GROUP BY e.cnee_email, e.campaign_id, e.subject
                     ORDER BY sent_at ASC""",
                (cutoff_str,),
            ).fetchall()

    suggestions: list[FollowupSuggestion] = []
    now_str = _now_iso()

    for row in rows:
        cnee_email = row["cnee_email"]
        sent_at_str = row["sent_at"]

        # Calculate days since sent
        try:
            sent_dt = datetime.strptime(sent_at_str, "%Y-%m-%d %H:%M:%S")
            sent_dt = sent_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            days_since = (now_dt - sent_dt).days
        except Exception:
            days_since = 999  # unknown, treat as high priority

        # Skip if in cooldown (last activity < 7 days ago)
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_activity = conn.execute(
            """SELECT detected_at FROM email_events
               WHERE cnee_email=? AND detected_at > ?
               ORDER BY detected_at DESC LIMIT 1""",
            (cnee_email, cooldown_cutoff.strftime("%Y-%m-%d %H:%M:%S")),
        ).fetchone()
        if recent_activity:
            continue  # still in cooldown window

        # Priority: older = higher priority (lower score)
        priority_score = max(0, days_since - days_back)

        # Determine follow-up reason
        if days_since >= 7:
            followup_reason = "no_reply_7d"
        elif days_since >= 3:
            followup_reason = "no_reply_3d"
        else:
            followup_reason = "no_reply_pending"

        # Generate draft preview (truncated, first 200 chars of subject context)
        draft_subject = f"FOLLOWUP: {row['subject'] or 'Your freight rates'}"
        draft_preview = f"Follow-up on {row['subject'] or 'our previous email'} — sent {days_since} days ago. Tap to review and send manually."

        suggestions.append(FollowupSuggestion(
            cnee_email=cnee_email,
            campaign_id=row["campaign_id"] or "",
            subject=draft_subject,
            followup_reason=followup_reason,
            days_since_sent=days_since,
            draft_preview=draft_preview,
            priority_score=priority_score,
        ))

    # Sort by priority_score desc (higher score = more urgent)
    suggestions.sort(key=lambda x: x["priority_score"], reverse=True)
    return suggestions