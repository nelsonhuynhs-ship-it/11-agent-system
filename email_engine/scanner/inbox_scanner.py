"""
email_engine.scanner.inbox_scanner
==================================
Graph API fallback scanner (Phase 1 Graph Migration v8).

Replaces win32com-based Outlook COM scan with Microsoft Graph API polling.
Used as fallback when webhook push notifications are delayed (>5 min).

Interval: 1 hour (configurable via GRAPH_POLL_INTERVAL_MINUTES env var).
Webhook is primary — this poll is backup only.

Entry points:
    run_scan()          -> dict of counters (scanned / bounces / ...)
    start_scheduler()   -> BackgroundScheduler (caller keeps reference)

Standalone usage:
    python -m email_engine.scanner.inbox_scanner
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

from . import handlers
from .classifier import _load_cnee_emails, classify, load_patterns

log = logging.getLogger(__name__)

# Graph API config
GRAPH_POLL_INTERVAL_MINUTES = int(
    __import__("os").environ.get("GRAPH_POLL_INTERVAL_MINUTES", "60")
)
_BASE_URL = "https://graph.microsoft.com/v1.0"


# -------------------------------------------------------------------
# Graph API access
# -------------------------------------------------------------------
def _get_graph_token() -> str:
    """Acquire Graph access token."""
    from email_engine.senders.graph_sender import get_token as _gt
    return _gt()


def _graph_get(endpoint: str, params: dict | None = None) -> Optional[dict]:
    """GET Graph API endpoint. Returns parsed JSON or None on error."""
    try:
        token = _get_graph_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{_BASE_URL}{endpoint}"
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code not in (200, 201):
            log.warning("_graph_get %s failed %s: %s", endpoint, resp.status_code, resp.text[:200])
            return None
        return resp.json()
    except Exception as e:
        log.error("_graph_get %s exception: %s", endpoint, e)
        return None


def _fetch_inbox_messages(hours_back: int = 60) -> list[dict]:
    """Fetch messages from inbox within the last N hours via Graph API."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    # Graph OData filter on receivedDateTime
    filter_str = f"receivedDateTime ge {cutoff.isoformat().replace('+00:00', 'Z')}"
    params = {
        "$filter": filter_str,
        "$orderby": "receivedDateTime desc",
        "$top": "100",
        "$select": "id,subject,from,toRecipients,receivedDateTime,"
                  "internetMessageHeaders,conversationId,body",
    }
    data = _graph_get("/me/mailFolders/inbox/messages", params)
    if not data:
        return []
    return data.get("value", [])


# -------------------------------------------------------------------
# Message normalization — bridge Graph message format to scanner pattern
# -------------------------------------------------------------------
class _GraphMessage:
    """Wrapper that makes a Graph API message dict look like an Outlook item.

    Used so classifier.classify() and handler functions receive a uniform interface
    without needing to change their signatures.
    """
    def __init__(self, msg: dict):
        self._msg = msg

    @property
    def Subject(self) -> str:
        return self._msg.get("subject", "") or ""

    @property
    def SenderEmailAddress(self) -> str:
        from_list = self._msg.get("from", {}).get("emailAddress", {}) or {}
        return from_list.get("address", "") or ""

    @property
    def Body(self) -> str:
        body = self._msg.get("body", {}) or {}
        return body.get("content", "") or ""

    @property
    def ReceivedTime(self):
        raw = self._msg.get("receivedDateTime", "")
        if not raw:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    @property
    def Class(self) -> int:
        # Class 43 = olMail. We treat Graph messages as mail.
        return 43

    def get(self, key: str, default: Any = None) -> Any:
        return self._msg.get(key, default)


def _already_processed_graph(message_id: str, cutoff: datetime) -> bool:
    """Check if message was already processed using a local tracking file.

    Stores processed message IDs in data/graph_poll_tracking.json to avoid
    re-processing on polling cycles.
    """
    import json
    from pathlib import Path
    tracking_file = Path(__file__).parent.parent / "data" / "graph_poll_tracking.json"
    try:
        if tracking_file.exists():
            entries = json.loads(tracking_file.read_text(encoding="utf-8"))
            # Keep only entries within 7 days
            cutoff_days = datetime.now(timezone.utc) - timedelta(days=7)
            entries = [
                e for e in entries
                if datetime.fromisoformat(e["processed_at"].replace("Z", "+00:00")) > cutoff_days
            ]
        else:
            entries = []
    except Exception:
        entries = []

    for e in entries:
        if e["id"] == message_id:
            return True

    # Record this message
    entries.append({
        "id": message_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        tracking_file.parent.mkdir(parents=True, exist_ok=True)
        tracking_file.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning("Could not update poll tracking file: %s", exc)
    return False


# -------------------------------------------------------------------
# Main scan
# -------------------------------------------------------------------
def run_scan(hours: int | None = None, force: bool = False) -> dict:
    """One polling cycle. Returns a counter dict.

    Args:
        hours: Override poll window (default: 60 min = 1h fallback).
        force: If True, re-process messages even if already tagged.

    Counters: scanned, bounces, auto_replies, real_replies, unsubs, irrelevant, errors.
    """
    counters = {
        "scanned": 0,
        "bounces": 0,
        "auto_replies": 0,
        "real_replies": 0,
        "unsubs": 0,
        "irrelevant": 0,
        "errors": 0,
    }
    try:
        return _run_scan_inner(hours, force, counters)
    except Exception as exc:
        log.error("run_scan fatal error: %s", exc)
        counters["errors"] += 1
        return counters


def _run_scan_inner(hours: int | None, force: bool, counters: dict) -> dict:
    """Actual scan logic using Graph API."""
    patterns = load_patterns()
    cnee_set = _load_cnee_emails()

    window_hours = hours if hours is not None and hours > 0 else 1
    max_items = 200

    log.info("run_scan (Graph): window=%dh, force=%s", window_hours, force)

    messages = _fetch_inbox_messages(hours_back=window_hours)
    if not messages:
        log.info("run_scan: no messages in inbox for last %dh", window_hours)
        return counters

    log.info("run_scan: fetched %d messages from Graph", len(messages))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    for msg_dict in messages:
        if counters["scanned"] >= max_items:
            break

        msg_id = msg_dict.get("id", "")
        if not msg_id:
            continue

        if not force and _already_processed_graph(msg_id, cutoff):
            log.debug("run_scan: already processed %s, skipping", msg_id)
            continue

        counters["scanned"] += 1

        # Wrap in Outlook-like interface
        msg = _GraphMessage(msg_dict)

        try:
            label = classify(msg, patterns=patterns, cnee_emails=cnee_set)
        except Exception as exc:
            log.warning("run_scan: classify error for %s: %s", msg_id, exc)
            counters["errors"] += 1
            continue

        sender = msg.SenderEmailAddress.lower().strip()

        if label == "BOUNCE":
            body = msg.Body
            target = handlers.extract_bounced_email(body) or ""
            handlers.handle_bounce(msg, target)
            counters["bounces"] += 1

        elif label == "AUTO_REPLY":
            handlers.handle_auto_reply(msg, sender)
            counters["auto_replies"] += 1

        elif label == "UNSUBSCRIBE":
            handlers.handle_unsubscribe(msg, sender)
            counters["unsubs"] += 1

        elif label == "REAL_REPLY":
            from email_engine.scanner.inbox_scanner import _cnee_lookup
            row = _cnee_lookup(sender)
            handlers.handle_real_reply(msg, row)
            counters["real_replies"] += 1

        else:
            counters["irrelevant"] += 1

    log.info(
        "run_scan done (Graph): %s",
        ", ".join(f"{k}={v}" for k, v in counters.items()),
    )
    return counters


def _cnee_lookup(email: str) -> dict:
    """Return minimal CNEE row dict for handlers."""
    try:
        from email_engine.intel.memory import get_cnee_summary  # type: ignore
        row = get_cnee_summary(email) or {}
        row.setdefault("EMAIL", email)
        return row
    except Exception:
        return {"EMAIL": email}


# -------------------------------------------------------------------
# Scheduler wiring (fallback only — webhook is primary)
# -------------------------------------------------------------------
def start_scheduler():
    """Create BackgroundScheduler with GRAPH_POLL_INTERVAL_MINUTES scan.

    Returns the scheduler; caller is responsible for keeping a reference.
    Note: webhook is primary. This poll fires only when webhook is delayed.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError(
            "APScheduler missing — pip install apscheduler"
        ) from exc

    from .daily_report import send_daily_report

    scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
    scheduler.add_job(
        run_scan,
        trigger="interval",
        minutes=GRAPH_POLL_INTERVAL_MINUTES,
        id="inbox_scan_graph",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        send_daily_report,
        trigger="cron",
        hour=21,
        minute=0,
        id="daily_report",
        replace_existing=True,
    )
    scheduler.start()
    log.info(
        "APScheduler (Graph fallback) started — run_scan@%dmin, daily_report@21:00 Asia/Ho_Chi_Minh",
        GRAPH_POLL_INTERVAL_MINUTES,
    )
    return scheduler


# -------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------
def _main() -> None:  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    scheduler = start_scheduler()

    def _shutdown(*_args) -> None:
        log.info("Shutting down scheduler...")
        try:
            scheduler.shutdown(wait=False)
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # Run once immediately so activity is visible on startup.
    try:
        run_scan()
    except Exception as exc:
        log.error("initial run_scan failed: %s", exc)

    while True:
        time.sleep(60)


if __name__ == "__main__":  # pragma: no cover
    _main()