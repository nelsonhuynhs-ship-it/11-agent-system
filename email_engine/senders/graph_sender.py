"""
Microsoft Graph API sender — replacement cho Outlook COM.

App registration: "Email API" (single-tenant pudongprime.vn).
Permission: Mail.Send delegated. Public client flow enabled.

Token cache (refresh ~90 days) at email_engine/.cache/graph_token.bin.
First run requires device-code consent — see scripts/test_graph_send.py.

Usage:
    from email_engine.senders import send_html_via_graph
    send_html_via_graph(to="user@example.com", subject="...", html_body="<p>...</p>")
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import msal
import requests

log = logging.getLogger(__name__)

CLIENT_ID = "cfbd0059-2fc2-4570-a999-bae2698a04b7"
TENANT_ID = "e0f20ff4-ddc2-4926-82e7-23458569c8bb"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Send"]  # TODO: thêm Mail.Read sau khi 130 email batch xong + re-consent
GRAPH_SENDMAIL = "https://graph.microsoft.com/v1.0/me/sendMail"

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "graph_token.bin"

# Exchange Online cap: 30 messages/minute per mailbox (HARD limit, cannot be raised).
# Pace at 1 send / MIN_INTERVAL_SEC to stay safely under cap.
MIN_INTERVAL_SEC = 2.1  # ~28 emails/min — buffer below 30 cap
_pace_lock = threading.Lock()
_last_send_ts = [0.0]

_app: Optional[msal.PublicClientApplication] = None


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if CACHE_FILE.exists():
        cache.deserialize(CACHE_FILE.read_text(encoding="utf-8"))
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(cache.serialize(), encoding="utf-8")


def get_token(interactive_fallback: bool = False) -> str:
    """Acquire a Graph access token from cache (silent refresh).

    Args:
        interactive_fallback: If True and silent acquisition fails, run
            device-code flow (blocks waiting for user). Default False —
            production callers should rely on warm cache.

    Raises:
        RuntimeError: If no cached account and interactive_fallback=False.
    """
    cache = _load_cache()
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        if not interactive_fallback:
            raise RuntimeError(
                "No cached Graph token. Run scripts/test_graph_send.py once "
                "to perform device-code consent flow."
            )
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow init failed: {flow}")
        log.warning(f"Device code: {flow['user_code']} at {flow['verification_uri']}")
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache)

    if "access_token" not in result:
        raise RuntimeError(f"Token acquisition failed: {result}")
    return result["access_token"]


def _pace() -> None:
    """Enforce 1 send per MIN_INTERVAL_SEC across all threads."""
    with _pace_lock:
        now = time.time()
        wait = MIN_INTERVAL_SEC - (now - _last_send_ts[0])
        if wait > 0:
            time.sleep(wait)
        _last_send_ts[0] = time.time()


def send_html_via_graph(
    to: str,
    subject: str,
    html_body: str,
    save_to_sent: bool = True,
    timeout: int = 30,
    max_retries: int = 2,
) -> tuple[bool, str | None]:
    """Send an HTML email via Microsoft Graph as the authenticated user.

    - Paces at ~28 sends/min to stay under Exchange Online 30/min cap.
    - On HTTP 429: respects Retry-After header, retries up to max_retries.
    - Returns (True, messageId) on HTTP 202 where messageId is the Graph message-id
      from /me/sentItems/messages?$filter=... lookup. Raises RuntimeError on permanent failure.
    """
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": save_to_sent,
    }

    sent_at_iso = datetime.now(timezone.utc).isoformat()

    for attempt in range(max_retries + 1):
        _pace()
        token = get_token()
        resp = requests.post(
            GRAPH_SENDMAIL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 202:
            # Lookup messageId from Sent folder
            msg_id = _lookup_sent_message_id(token, to, subject, sent_at_iso)
            return True, msg_id
        if resp.status_code == 429 and attempt < max_retries:
            retry_after = int(resp.headers.get("Retry-After", "10"))
            log.warning(f"Graph 429 — retry after {retry_after}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_after)
            continue
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        raise RuntimeError(f"Graph sendMail HTTP {resp.status_code}: {json.dumps(err)[:500]}")

    raise RuntimeError(f"Graph sendMail failed after {max_retries} retries (last status: 429)")


def _lookup_sent_message_id(token: str, to: str, subject: str, since: str) -> str | None:
    """Find the message-id in Sent folder matching (to, subject, since)."""
    deadline = time.time() + 30
    poll_intervals = [2, 3, 5, 5, 10]

    for delay in poll_intervals:
        if time.time() >= deadline:
            break
        time.sleep(delay)
        safe_subject = subject.replace("'", "''")
        params = {
            "$filter": (
                f"sentDateTime ge '{since}' "
                f"and subject eq '{safe_subject}'"
            ),
            "$select": "id,sentDateTime,toRecipients",
            "$top": 5,
            "$orderby": "sentDateTime desc",
        }
        try:
            r = requests.get(
                GRAPH_SENT_FOLDER,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10,
            )
            if r.status_code != 200:
                continue
            messages = r.json().get("value", [])
            for msg in messages:
                recipients = msg.get("toRecipients", [])
                if any(
                    rcpt["emailAddress"]["address"].lower() == to.lower()
                    for rcpt in recipients
                ):
                    return msg["id"]
        except Exception as e:
            log.debug(f"_lookup_sent_message_id poll failed: {e}")
            continue
    return None


GRAPH_SENT_FOLDER = "https://graph.microsoft.com/v1.0/me/mailFolders/sentitems/messages"
# Well-known folder ID for Sent Items (used in parentFolderId check)
GRAPH_SENT_FOLDER_ID = "sentitems"


def verify_message_by_id(message_id: str, token: str | None = None) -> dict | None:
    """Fetch /me/messages/{id} — returns message dict or None if not found."""
    tok = token or get_token()
    try:
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {tok}"},
            params={"$select": "id,parentFolderId,sentDateTime,toRecipients"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def verify_in_sent_folder(to: str, subject: str, since: str, max_wait_sec: int = 30) -> str | None:
    """Poll Sent folder for matching message. Returns Graph message-id or None.

    Microsoft /sendMail returns 202 but no message-id. To verify actual delivery,
    poll Sent folder filtered by recipient + subject + receivedDateTime.

    Args:
        to: recipient email
        subject: exact subject string
        since: ISO timestamp lower bound
        max_wait_sec: total polling budget (default 30s)
    """
    import time
    token = get_token()
    deadline = time.time() + max_wait_sec
    poll_intervals = [2, 3, 5, 5, 10]  # progressive backoff

    for delay in poll_intervals:
        if time.time() >= deadline:
            break
        time.sleep(delay)
        params = {
            "$filter": (
                f"sentDateTime ge {since} "
                f"and subject eq '{subject.replace(chr(39), chr(39)*2)}'"
            ),
            "$select": "id,sentDateTime,toRecipients",
            "$top": 5,
            "$orderby": "sentDateTime desc",
        }
        try:
            r = requests.get(
                GRAPH_SENT_FOLDER,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10,
            )
            if r.status_code != 200:
                continue
            messages = r.json().get("value", [])
            for msg in messages:
                recipients = msg.get("toRecipients", [])
                if any(rcpt["emailAddress"]["address"].lower() == to.lower() for rcpt in recipients):
                    return msg["id"]
        except Exception as e:
            log.debug(f"verify_in_sent_folder poll failed: {e}")
            continue
    return None
