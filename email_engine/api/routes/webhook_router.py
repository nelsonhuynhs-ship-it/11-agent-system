"""
webhook_router.py — Microsoft Graph Inbound Notification Handler
================================================================
Phase 1 — Graph Webhook Migration v8

Handles:
  1. Validation handshake (GET ?validationToken=xxx → plain text)
  2. Notification processing (POST /api/graph/webhook)

NDR detection: RFC 3464 headers + subject keywords.
Reply detection: conversationId matched against tracked conversations.

Tracked conversations are built from email_log.csv conversation IDs
at startup (inmemory set) and refreshed every 10 minutes.
"""
from __future__ import annotations

import csv
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-webhook"])

# ── Paths ────────────────────────────────────────────────────────────────────
_BASE_DIR   = Path(__file__).parent.parent.parent  # email_engine/
_DATA_DIR   = _BASE_DIR / "data"
_LOG_DIR    = _BASE_DIR / "logs"
_EMAIL_LOG  = _LOG_DIR  / "email_log.csv"
_REPLY_LOG  = _LOG_DIR  / "reply_log.csv"
_BOUNCE_LOG = _LOG_DIR  / "bounce_log.csv"

# clientState must match what subscription was created with
CLIENT_STATE = "nelson-freight-graph-v8"

# ── Conversation tracking ────────────────────────────────────────────────────
# {conversationId -> set of email addresses} — refreshed every 10 min
_tracked_conversations: dict[str, set[str]] = {}
_last_conversation_refresh: float = 0.0
_CONV_REFRESH_INTERVAL = 600  # 10 minutes


def _refresh_tracked_conversations() -> None:
    """Rebuild conversationId -> email set from email_log.csv."""
    global _tracked_conversations, _last_conversation_refresh
    if not _EMAIL_LOG.exists():
        _tracked_conversations = {}
        return
    try:
        df = pd.read_csv(_EMAIL_LOG, usecols=["conversation_id", "to_email"], dtype=str)
        df = df.dropna(subset=["conversation_id"])
        conv_map: dict[str, set[str]] = {}
        for _, row in df.iterrows():
            cid = str(row["conversation_id"]).strip()
            email = str(row.get("to_email", "")).strip().lower()
            if cid and email:
                conv_map.setdefault(cid, set()).add(email)
        _tracked_conversations = conv_map
        _last_conversation_refresh = time.time()
        log.info("[Webhook] tracked conversations refreshed: %d", len(conv_map))
    except Exception as e:
        log.warning("[Webhook] refresh_tracked_conversations failed: %s", e)


def _get_tracked_conversations() -> dict[str, set[str]]:
    """Lazily refresh conversation set every 10 minutes."""
    if time.time() - _last_conversation_refresh > _CONV_REFRESH_INTERVAL:
        _refresh_tracked_conversations()
    return _tracked_conversations


# ── Graph helpers ────────────────────────────────────────────────────────────
def _get_graph_token() -> str:
    from email_engine.senders.graph_sender import get_token as _gt
    return _gt()


def _fetch_message(message_id: str) -> Optional[dict]:
    """GET /me/messages/{id} via Graph API."""
    try:
        token = _get_graph_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}?$expand=internetMessageHeaders"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            log.warning("[Webhook] fetch_message %s failed %s", message_id, resp.status_code)
            return None
        return resp.json()
    except Exception as e:
        log.error("[Webhook] fetch_message %s exception: %s", message_id, e)
        return None


# ── NDR Detection (RFC 3464) ─────────────────────────────────────────────────
def is_ndr(msg: dict) -> bool:
    """Return True if message is a Non-Delivery Report (bounce)."""
    # 1. Auto-Submitted header
    headers = {}
    for h in msg.get("internetMessageHeaders", []):
        headers[h.get("name", "").lower()] = h.get("value", "")

    if headers.get("auto-submitted", "").lower() == "auto-replied":
        return True
    if "x-failed-recipients" in headers:
        return True
    ct = headers.get("content-type", "")
    if ct.startswith("multipart/report"):
        return True

    # 2. Sender pattern
    sender = (msg.get("from", {}) or {}).get("emailAddress", {}) or {}
    sender_addr = sender.get("address", "").lower()
    if any(s in sender_addr for s in ["postmaster", "mailer-daemon", "mail-daemon"]):
        return True

    # 3. Subject fallback
    subject = (msg.get("subject", "") or "").lower()
    ndr_keywords = ["undeliverable", "delivery status", "returned mail",
                    "failure notice", "mail delivery failed", "not found"]
    if any(kw in subject for kw in ndr_keywords):
        return True

    return False


def is_reply(msg: dict, tracked: dict[str, set[str]]) -> bool:
    """Return True if message is a reply from a tracked conversation."""
    conv_id = msg.get("conversationId", "")
    if not conv_id or conv_id not in tracked:
        return False
    sender = (msg.get("from", {}) or {}).get("emailAddress", {}) or {}
    sender_addr = sender.get("address", "").lower().strip()
    if sender_addr in tracked[conv_id]:
        return True
    return False


# ── Handlers ─────────────────────────────────────────────────────────────────
def _handle_bounce(msg: dict) -> None:
    """Log bounce to bounce_log.csv + feed bounce_handler.handle_bounce."""
    sender = (msg.get("from", {}) or {}).get("emailAddress", {}) or {}
    sender_email = sender.get("address", "")
    subject = msg.get("subject", "")
    msg_id   = msg.get("id", "")
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log.info("[Webhook] bounce detected: from=%s subject=%s", sender_email, subject[:80])

    # Append to bounce_log.csv
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    exists = _BOUNCE_LOG.exists()
    with open(_BOUNCE_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "msg_id", "sender", "subject"])
        w.writerow([now_str, msg_id, sender_email, subject])

    # Feed bounce_handler — parses RFC 3464 DSN, saves to bounce_kb.db, auto-suppresses
    try:
        from email_engine.core.bounce_handler import handle_bounce as _handle_bounce_impl
        result = _handle_bounce_impl(msg)
        log.info("[Webhook] bounce_handler: processed=%d hard=%d soft=%d",
                 result.get("processed", 0),
                 result.get("hard_bounces", 0),
                 result.get("soft_bounces", 0))
    except Exception as exc:
        log.warning("[Webhook] bounce_handler.handle_bounce failed: %s", exc)


def _handle_reply(msg: dict) -> None:
    """Log reply to reply_log.csv."""
    sender = (msg.get("from", {}) or {}).get("emailAddress", {}) or {}
    sender_email = sender.get("address", "")
    subject = msg.get("subject", "")
    conv_id = msg.get("conversationId", "")
    msg_id  = msg.get("id", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log.info("[Webhook] reply detected: from=%s conv=%s subject=%s",
             sender_email, conv_id, subject[:80])

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    exists = _REPLY_LOG.exists()
    with open(_REPLY_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "msg_id", "conversation_id", "sender", "subject"])
        w.writerow([now_str, msg_id, conv_id, sender_email, subject])

    # Also update reply status in cnee_master_v2 if present
    try:
        from email_engine.core.reply_detector import _log_reply as _log_reply_impl
        _log_reply_impl(sender_email, subject, "", now_str)
    except Exception:
        pass


# ── Routes ───────────────────────────────────────────────────────────────────
@router.get("/webhook")
async def graph_webhook_validation(request: Request):
    """Handle Graph subscription validation handshake (GET ?validationToken=xxx)."""
    token = request.query_params.get("validationToken")
    if token:
        log.info("[Webhook] validation handshake token received")
        return PlainTextResponse(content=token, status_code=200)
    return Response(status_code=400, content="missing validationToken")


@router.post("/webhook")
async def graph_webhook_notification(request: Request):
    """Handle Graph push notification (POST /api/graph/webhook)."""
    body = await request.json()
    notifications = body.get("value", [])
    if not notifications:
        return Response(status_code=200)

    tracked = _get_tracked_conversations()
    processed = 0

    for notif in notifications:
        # 1. Verify clientState
        notif_state = notif.get("clientState", "")
        if notif_state != CLIENT_STATE:
            log.warning("[Webhook] clientState mismatch — possible spoof (got=%s)", notif_state)
            continue

        # 2. Extract message ID from resource path
        resource = notif.get("resource", "")
        parts = resource.rstrip("/").split("/")
        message_id = parts[-1] if parts else ""
        if not message_id:
            log.warning("[Webhook] no message_id in resource=%s", resource)
            continue

        # 3. Fetch full message
        msg = _fetch_message(message_id)
        if not msg:
            log.warning("[Webhook] fetch_message returned None for %s", message_id)
            continue

        # 4. Classify and route
        if is_ndr(msg):
            _handle_bounce(msg)
            processed += 1
        elif is_reply(msg, tracked):
            _handle_reply(msg)
            processed += 1
        else:
            log.debug("[Webhook] unclassified message id=%s subject=%s",
                      message_id, (msg.get("subject") or "")[:60])

    log.info("[Webhook] processed %d notifications", processed)
    return Response(status_code=202)