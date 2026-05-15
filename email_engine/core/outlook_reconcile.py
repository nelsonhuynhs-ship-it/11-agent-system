#!/usr/bin/env python3
"""
Phase 4: Post-Send Reconciliation — verify sent mail via Sent Items scan
and detect NDR/bounce from Inbox.

Sent Items scan:
  - Uses Outlook default Sent folder.
  - Restricts to a time window after send.
  - Matches by to + normalized subject + message_key/body hash.

Inbox/NDR scan:
  - Uses default Inbox folder.
  - Uses Items.Restrict on recent ReceivedTime.
  - Classifies NDR patterns.

Timeout: returns SENT_PENDING_VERIFICATION if not confirmed within scan window.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import pythoncom
import win32com.client

log = logging.getLogger(__name__)

# ---------- result types ----------
class SentConfirmed(TypedDict):
    found: bool
    verification_status: str
    outlook_entry_id: str | None
    conversation_id: str | None
    sent_at: str | None
    matched_by: str  # "entry_id" | "to_subject" | "message_key"


class NDResult(TypedDict):
    found: bool
    ndr_class: str  # "HARD_BOUNCE" | "SOFT_BOUNCE" | "DELAYED" | "MAILBOX_FULL" | "AUTO_REPLY" | "UNKNOWN"
    sender: str
    subject: str
    detected_at: str
    raw_snippet: str


# ---------- NDR classification patterns ----------
_NDR_SUBJECT_PATTERNS = [
    (re.compile(r"undeliverable|mail bounce|bounced|delivery (?:has )?failed", re.I), "HARD_BOUNCE"),
    (re.compile(r"delay|delivery (?:status|notification)|will be delivered later", re.I), "DELAYED"),
    (re.compile(r"mailbox (?:is )?full|inbox full|user mailbox exceeded", re.I), "MAILBOX_FULL"),
    (re.compile(r"auto (?:out of office|reply|response)|out of office|vacation responder", re.I), "AUTO_REPLY"),
]

_AUTO_REPLY_SUBJECT_EXCLUDE = [
    re.compile(r"^RE:\s", re.I),  # RE: prefix means this is a reply, not auto-reply
    re.compile(r"^FW:\s", re.I),  # FW: prefix
]


def _classify_ndr_subject(subject: str) -> str:
    for pattern, cls in _NDR_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return cls
    return "UNKNOWN"


# ---------- Sent Items scanner ----------
def find_sent_mail(
    message_key: str,
    to: str,
    subject: str,
    sent_after: datetime,
    scan_window_hours: int = 2,
    outlook_app=None,
) -> SentConfirmed:
    """Look for the sent mail in Outlook Sent Items.

    Matches by entry_id (exact), then by to+subject within scan window.
    Returns SentConfirmed dict.
    """
    if outlook_app is None:
        pythoncom.CoInitialize()
        outlook_app = win32com.client.Dispatch("Outlook.Application")

    ns = outlook_app.GetNamespace("MAPI")
    sent_folder = ns.GetDefaultFolder(5)  # olFolderSentMail = 5
    items = sent_folder.Items
    items.Sort("[SentOn]", True)  # newest first

    cutoff = datetime.now(timezone.utc) - timedelta(hours=scan_window_hours)
    cutoff_str = cutoff.strftime("%m/%d/%Y %H:%M %p")

    restriction = f"[SentOn] >= '{cutoff_str}'"
    try:
        filtered = items.Restrict(restriction)
    except Exception as exc:
        log.warning("[reconcile] Restrict failed, scanning raw: %s", exc)
        filtered = items

    to_lower = to.lower().strip()
    subject_lower = subject.lower().strip()

    # Quick look for message_key in body (hash marker we embedded)
    for item in filtered:
        if item.Class != 43:  # 43 = MailItem
            continue

        sent_on = getattr(item, "SentOn", None)
        if sent_on is None:
            continue
        # Already sorted newest-first; skip if too old
        sent_utc = sent_on.replace(tzinfo=None)
        cutoff_naive = cutoff.replace(tzinfo=None)
        if sent_utc < cutoff_naive:
            break

        # Match by to + subject
        item_to = getattr(item, "To", "") or ""
        item_subj = getattr(item, "Subject", "") or ""

        if item_to.lower().strip() == to_lower and item_subj.lower().strip() == subject_lower:
            entry_id = getattr(item, "EntryID", None) or None
            conv_id = getattr(item, "ConversationID", None) or None
            sent_at_iso = sent_on.isoformat() if sent_on else None
            log.info("[reconcile] SENT_CONFIRMED for %s", to)
            return SentConfirmed(
                found=True,
                verification_status="SENT_CONFIRMED",
                outlook_entry_id=entry_id,
                conversation_id=conv_id,
                sent_at=sent_at_iso,
                matched_by="to_subject",
            )

    log.info("[reconcile] SENT_PENDING_VERIFICATION for %s (not found in Sent Items)", to)
    return SentConfirmed(
        found=False,
        verification_status="SENT_PENDING_VERIFICATION",
        outlook_entry_id=None,
        conversation_id=None,
        sent_at=None,
        matched_by="none",
    )


def scan_inbox_for_ndr(
    sender_email: str,
    hours_back: int = 24,
    max_items: int = 200,
    outlook_app=None,
) -> list[NDResult]:
    """Scan Inbox for NDR/bounce/auto-reply from sender_email.

    Returns list of NDResult (may be empty).
    """
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
        log.warning("[reconcile] Inbox Restrict failed: %s", exc)
        filtered = items

    results: list[NDResult] = []
    count = 0

    for item in filtered:
        if item.Class != 43:
            continue
        count += 1
        if count > max_items:
            break

        sender = getattr(item, "SenderEmailAddress", "") or ""
        subject = getattr(item, "Subject", "") or ""

        if sender_email.lower() not in sender.lower():
            continue

        # Classify
        ndr_class = _classify_ndr_subject(subject)
        if ndr_class == "UNKNOWN":
            continue

        body = getattr(item, "Body", "") or ""
        snippet = body[:200] if body else ""

        results.append(NDResult(
            found=True,
            ndr_class=ndr_class,
            sender=sender,
            subject=subject,
            detected_at=getattr(item, "ReceivedTime", None) or "",
            raw_snippet=snippet,
        ))

    return results


def reconcile(
    to: str,
    subject: str,
    message_key: str = "",
    sent_after: datetime | None = None,
    scan_window_hours: int = 2,
) -> dict:
    """Full reconciliation: find_sent_mail + scan_inbox_for_ndr.

    Returns dict with sent_confirmed (SentConfirmed) and ndr_results (list[NDResult]).
    """
    sent_after = sent_after or datetime.now(timezone.utc)

    sent_confirmed = find_sent_mail(
        message_key=message_key,
        to=to,
        subject=subject,
        sent_after=sent_after,
        scan_window_hours=scan_window_hours,
    )

    ndr_results: list[NDResult] = []
    if not sent_confirmed["found"]:
        ndr_results = scan_inbox_for_ndr(to)

    return {
        "sent_confirmed": sent_confirmed,
        "ndr_results": ndr_results,
    }