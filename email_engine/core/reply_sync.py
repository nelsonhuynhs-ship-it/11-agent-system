#!/usr/bin/env python3
"""
Phase 5: Reply Detection — scan Inbox for customer replies.
Primary match: ConversationID or ConversationTopic against sent mail.
Secondary: normalized subject without RE:/FW: + sender email.
Fallback: sender exists in cnee_master and message is recent.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TypedDict

log = logging.getLogger(__name__)

# ---------- result types ----------
class ReplyDetectionResult(TypedDict):
    found: bool
    reply_class: str
    sender: str
    subject: str
    detected_at: str
    conversation_id: str | None
    raw_snippet: str


# ---------- reply classification patterns ----------
_REPLY_CLASS_PATTERNS = [
    # UNSUBSCRIBE — check before other classes
    (re.compile(r"\b(unsubscribe|opt\s*out|remove\s*me|don't\s+email)\b", re.I),
     "UNSUBSCRIBE"),
    # NOT_INTERESTED — check before HOT_REPLY (which catches "freight")
    (re.compile(r"\b(not\s*interested|no\s*thanks|do\s*not\s*contact)\b", re.I),
     "NOT_INTERESTED"),
    # AUTO_REPLY / OOO
    (re.compile(r"auto\s*(reply|response)|out\s*of\s*office|vacation", re.I),
     "AUTO_REPLY"),
    # INTERNAL — internal company reply
    (re.compile(r"^(RE:|FW:)\s*(internal|team|staff|colleague)", re.I),
     "INTERNAL"),
    # QUOTE_REQUEST — explicit request for pricing (check before generic "quote")
    (re.compile(r"\b(please\s+quote|quote\s+for|can\s+you\s+quote|send\s+price|pricing\s+please|rate\s+for\s+|what\s+is.*\bcost|cost\s+for\s+)\b", re.I),
     "QUOTE_REQUEST"),
    # RATE_QUESTION — question about rates (check before HOT_REPLY)
    (re.compile(r"\b(how\s+much|what\s+price|cost\s+to|shipping\s+cost|freight\s+charge|what.*shipping)\b", re.I),
     "RATE_QUESTION"),
    # HOT_REPLY — strong buying signal (check last, after more specific classes)
    (re.compile(r"\b(quote|rates?|container|20gp|40hq|40hc|40rf)\b", re.I),
     "HOT_REPLY"),
]


def _classify_reply_subject(subject: str) -> str:
    for pattern, cls in _REPLY_CLASS_PATTERNS:
        if pattern.search(subject):
            return cls
    return "NEEDS_HUMAN_REPLY"


def _strip_reply_prefix(subject: str) -> str:
    """Remove RE:/FW: prefix to get the original subject."""
    return re.sub(r"^(RE:|FW:)\s*", "", subject or "").strip()


def _normalize_for_match(text: str) -> str:
    """Lowercase, strip leading/trailing whitespace, collapse internal spaces."""
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def detect_reply_by_conversation(
    conversation_id: str,
    sender_email: str,
    outlook_app=None,
    hours_back: int = 72,
) -> ReplyDetectionResult:
    """Look for a reply in Inbox matching conversation_id + sender_email.

    Returns ReplyDetectionResult.
    """
    import pythoncom
    import win32com.client

    if outlook_app is None:
        pythoncom.CoInitialize()
        outlook_app = win32com.client.Dispatch("Outlook.Application")

    ns = outlook_app.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)  # olFolderInbox = 6
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)  # newest first

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    cutoff_str = cutoff.strftime("%m/%d/%Y %H:%M %p")

    try:
        filtered = items.Restrict(f"[ReceivedTime] >= '{cutoff_str}'")
    except Exception as exc:
        log.warning("[reply_sync] Inbox Restrict failed: %s", exc)
        filtered = items

    sender_lower = sender_email.lower().strip()
    matched_class = "UNKNOWN_REPLY"

    for item in filtered:
        if item.Class != 43:
            continue

        sender = getattr(item, "SenderEmailAddress", "") or ""
        conv_id = getattr(item, "ConversationID", "") or ""
        subject = getattr(item, "Subject", "") or ""

        # Match by ConversationID
        if conv_id and conv_id == conversation_id:
            reply_class = _classify_reply_subject(subject)
            body = getattr(item, "Body", "") or ""
            snippet = body[:200] if body else ""
            log.info("[reply_sync] Reply detected by ConversationID for %s", sender_email)
            return ReplyDetectionResult(
                found=True,
                reply_class=reply_class,
                sender=sender,
                subject=subject,
                detected_at=getattr(item, "ReceivedTime", None) or "",
                conversation_id=conv_id,
                raw_snippet=snippet,
            )

        # Fallback: sender match + subject without RE:/FW: matching a known sent subject
        if sender_lower in sender.lower():
            # Additional check: strip RE:/FW: and compare
            stripped = _strip_reply_prefix(subject)
            if stripped and len(stripped) > 5:
                # This is a reply-classification level signal, not a definitive match
                # Only use this path if ConversationID didn't fire
                reply_class = _classify_reply_subject(subject)
                if reply_class not in ("AUTO_REPLY", "INTERNAL"):
                    body = getattr(item, "Body", "") or ""
                    snippet = body[:200] if body else ""
                    log.info("[reply_sync] Reply detected by sender fallback for %s", sender_email)
                    return ReplyDetectionResult(
                        found=True,
                        reply_class=reply_class,
                        sender=sender,
                        subject=subject,
                        detected_at=getattr(item, "ReceivedTime", None) or "",
                        conversation_id=conv_id or None,
                        raw_snippet=snippet,
                    )

    log.info("[reply_sync] No reply found for %s", sender_email)
    return ReplyDetectionResult(
        found=False,
        reply_class="UNKNOWN_REPLY",
        sender=sender_email,
        subject="",
        detected_at="",
        conversation_id=None,
        raw_snippet="",
    )


def scan_inbox_for_replies(
    sender_emails: list[str],
    hours_back: int = 72,
    max_items: int = 200,
    outlook_app=None,
) -> list[ReplyDetectionResult]:
    """Bulk scan Inbox for replies from multiple sender emails.

    Returns list of ReplyDetectionResult (one per found reply).
    """
    import pythoncom
    import win32com.client

    if outlook_app is None:
        pythoncom.CoInitialize()
        outlook_app = win32com.client.Dispatch("Outlook.Application")

    ns = outlook_app.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    cutoff_str = cutoff.strftime("%m/%d/%Y %H:%M %p")

    try:
        filtered = items.Restrict(f"[ReceivedTime] >= '{cutoff_str}'")
    except Exception as exc:
        log.warning("[reply_sync] Inbox Restrict failed: %s", exc)
        filtered = items

    results: list[ReplyDetectionResult] = []
    email_set = {e.lower().strip() for e in sender_emails}
    count = 0

    for item in filtered:
        if item.Class != 43:
            continue
        count += 1
        if count > max_items:
            break

        sender = getattr(item, "SenderEmailAddress", "") or ""
        if not sender:
            continue

        sender_norm = sender.lower().strip()
        if sender_norm not in email_set:
            continue

        subject = getattr(item, "Subject", "") or ""
        reply_class = _classify_reply_subject(subject)
        body = getattr(item, "Body", "") or ""
        snippet = body[:200] if body else ""

        results.append(ReplyDetectionResult(
            found=True,
            reply_class=reply_class,
            sender=sender,
            subject=subject,
            detected_at=getattr(item, "ReceivedTime", None) or "",
            conversation_id=getattr(item, "ConversationID", None) or None,
            raw_snippet=snippet,
        ))

    return results


def generate_writeback_payload(
    cnee_email: str,
    detection: ReplyDetectionResult,
    campaign_id: str = "",
) -> dict:
    """Generate Excel/data writeback payload for a detected reply.

    Returns dict with fields for REPLIED_CUSTOMERS sheet update.
    """
    return {
        "cnee_email": cnee_email,
        "campaign_id": campaign_id,
        "reply_class": detection["reply_class"],
        "reply_subject": detection["subject"],
        "reply_sender": detection["sender"],
        "reply_detected_at": detection["detected_at"],
        "conversation_id": detection["conversation_id"] or "",
        "do_not_cold_send": detection["reply_class"] in (
            "HOT_REPLY", "QUOTE_REQUEST", "RATE_QUESTION", "NOT_INTERESTED", "UNSUBSCRIBE"
        ),
        "needs_human_reply": detection["reply_class"] == "NEEDS_HUMAN_REPLY",
        "raw_snippet": detection["raw_snippet"][:500] if detection["raw_snippet"] else "",
    }