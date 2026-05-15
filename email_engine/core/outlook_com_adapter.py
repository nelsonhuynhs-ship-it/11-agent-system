#!/usr/bin/env python3
"""
Phase 1: Outlook COM Adapter — unified send adapter.
Replaces direct win32com calls in web_server.py::_send_email_html and
queue_worker_outlook.py::OutlookSender.send with a single, observable adapter.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import TypedDict

import pythoncom
import win32com.client

log = logging.getLogger(__name__)


class OutlookSendResult(TypedDict):
    ok: bool
    message_key: str
    to: str
    subject: str
    sent_at: str
    outlook_entry_id: str | None
    conversation_id: str | None
    verification_status: str
    error: str | None


def create_message_key(to: str, subject: str, campaign_id: str, body_hash: str) -> str:
    """Generate a stable local message key before send.

    EntryID is not stable before save/send, so we generate a local key
    that can be used for post-send reconciliation with Sent Items.
    """
    raw = f"{to}:{subject}:{campaign_id}:{body_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def body_hash(html_body: str) -> str:
    return hashlib.md5(html_body.encode()).hexdigest()[:16]


def get_outlook_app() -> win32com.client.CDispatch:
    """Get a shared Outlook Application instance (thread-safe).

    Uses pythoncom.CoInitialize per thread — safe to call from
    background worker threads.
    """
    pythoncom.CoInitialize()
    return win32com.client.Dispatch("Outlook.Application")


def create_mail(
    app: win32com.client.CDispatch,
    to: str,
    subject: str,
    html_body: str,
    cc: str = "",
    bcc: str = "",
) -> win32com.client.CDispatch:
    """Create an Outlook MailItem and populate To/CC/BCC/Subject/HTMLBody."""
    m = app.CreateItem(0)
    m.To = to
    m.Subject = subject
    m.HTMLBody = html_body
    if cc:
        m.CC = cc
    if bcc:
        m.BCC = bcc
    return m


def resolve_recipients(mail: win32com.client.CDispatch) -> bool:
    """Call Recipients.ResolveAll(). Return True if all resolved."""
    return bool(mail.Recipients.ResolveAll())


def send_mail(
    to: str,
    subject: str,
    html_body: str,
    campaign_id: str = "",
    cc: str = "",
    bcc: str = "",
) -> OutlookSendResult:
    """Send one HTML email via Outlook COM. Returns full verification result.

    Resolution failure prevents send — no silent delivery of unresolvable
    recipients.
    """
    sent_at = datetime.now(timezone.utc).isoformat()
    message_key = create_message_key(to, subject, campaign_id, body_hash(html_body))

    try:
        app = get_outlook_app()
    except Exception as exc:
        log.error("[outlook-com-adapter] Outlook COM unavailable: %s", exc)
        return OutlookSendResult(
            ok=False,
            message_key=message_key,
            to=to,
            subject=subject,
            sent_at=sent_at,
            outlook_entry_id=None,
            conversation_id=None,
            verification_status="COM_UNAVAILABLE",
            error=str(exc),
        )

    try:
        mail = create_mail(app, to, subject, html_body, cc=cc, bcc=bcc)
        if not resolve_recipients(mail):
            log.warning("[outlook-com-adapter] Recipients could not be resolved: %s", to)
            return OutlookSendResult(
                ok=False,
                message_key=message_key,
                to=to,
                subject=subject,
                sent_at=sent_at,
                outlook_entry_id=None,
                conversation_id=None,
                verification_status="RESOLUTION_FAILED",
                error="One or more recipients could not be resolved",
            )
        mail.Send()
        log.info("[outlook-com-adapter] SENT %s", to)
        return OutlookSendResult(
            ok=True,
            message_key=message_key,
            to=to,
            subject=subject,
            sent_at=sent_at,
            outlook_entry_id=None,  # reconcile from Sent Items after send
            conversation_id=None,
            verification_status="SENT_PENDING_VERIFICATION",
            error=None,
        )
    except Exception as exc:
        log.error("[outlook-com-adapter] Send failed for %s: %s", to, exc)
        return OutlookSendResult(
            ok=False,
            message_key=message_key,
            to=to,
            subject=subject,
            sent_at=sent_at,
            outlook_entry_id=None,
            conversation_id=None,
            verification_status="SEND_FAILED",
            error=str(exc),
        )


# ---------- sentinel for workers that need a re-initializable sender ----------
class OutlookSender:
    """Thread-safe Outlook COM sender backed by outlook_com_adapter.

    Use this from queue_worker_outlook.py instead of direct COM calls.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._app: win32com.client.CDispatch | None = None

    def _get_app(self) -> win32com.client.CDispatch:
        with self._lock:
            if self._app is None:
                pythoncom.CoInitialize()
                self._app = win32com.client.Dispatch("Outlook.Application")
            return self._app

    def send(self, to: str, subject: str, html_body: str) -> bool:
        result = send_mail(to, subject, html_body)
        return result["ok"]

    def close(self):
        with self._lock:
            self._app = None