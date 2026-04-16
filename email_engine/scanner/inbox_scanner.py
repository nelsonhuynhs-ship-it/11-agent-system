"""
email_engine.scanner.inbox_scanner
==================================
Main loop + APScheduler wiring.

Every 30 minutes:
    * Walk Outlook Inbox (last `scan.window_minutes` of mail, capped at max_items)
    * Skip items already tagged with `scan.processed_category`
    * classify -> dispatch handler -> tag -> save

At 21:00 local:
    * daily_report.send_daily_report()

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
from datetime import datetime, timedelta
from typing import Any

from . import handlers
from .classifier import _load_cnee_emails, classify, load_patterns

log = logging.getLogger(__name__)

_OUTLOOK_INBOX_ID = 6  # olFolderInbox


# -------------------------------------------------------------------
# Outlook access (win32com is win-only; stub for tests)
# -------------------------------------------------------------------
def _get_inbox():
    """Return (namespace, inbox). Raises RuntimeError on failure."""
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(f"pywin32 not available: {exc}")

    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(_OUTLOOK_INBOX_ID)
    return ns, inbox


def _already_processed(item: Any, tag: str) -> bool:
    try:
        cats = getattr(item, "Categories", "") or ""
        return tag in cats
    except Exception:
        return False


def _mark_processed(item: Any, tag: str) -> None:
    try:
        cats = getattr(item, "Categories", "") or ""
        if tag not in cats:
            new_cats = f"{cats};{tag}" if cats else tag
            item.Categories = new_cats
            item.Save()
    except Exception as exc:
        log.debug("Could not tag item: %s", exc)


def _cnee_lookup(email: str) -> dict:
    """Return minimal CNEE row dict for handlers. Prefers intel.memory.get_cnee_summary
    if available; else falls back to {EMAIL: ...}."""
    try:
        from email_engine.intel.memory import get_cnee_summary  # type: ignore
        row = get_cnee_summary(email) or {}
        row.setdefault("EMAIL", email)
        return row
    except Exception:
        return {"EMAIL": email}


# -------------------------------------------------------------------
# Main scan
# -------------------------------------------------------------------
def run_scan() -> dict:
    """One cycle. Returns a counter dict.

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
    patterns = load_patterns()
    cnee_set = _load_cnee_emails()

    scan_cfg = patterns.get("scan", {})
    window_min = int(scan_cfg.get("window_minutes", 35))
    max_items = int(scan_cfg.get("max_items", 200))
    tag = str(scan_cfg.get("processed_category", "Nelson-Scanned"))

    # Outlook MailItem.ReceivedTime comes back from pywin32 as an aware
    # datetime (local tz). Use an aware cutoff so comparisons don't blow up.
    cutoff = datetime.now().astimezone() - timedelta(minutes=window_min)

    try:
        _ns, inbox = _get_inbox()
    except Exception as exc:
        log.error("run_scan: Outlook unavailable: %s", exc)
        counters["errors"] += 1
        return counters

    try:
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)  # newest first
    except Exception as exc:
        log.error("run_scan: cannot read inbox items: %s", exc)
        counters["errors"] += 1
        return counters

    for msg in messages:
        if counters["scanned"] >= max_items:
            log.info("run_scan: hit max_items cap (%d)", max_items)
            break

        try:
            received = msg.ReceivedTime
            # Normalise naive<->aware comparisons both ways.
            try:
                if received < cutoff:
                    break
            except TypeError:
                # Fallback: try comparing as naive local times.
                try:
                    rec_naive = received.replace(tzinfo=None)
                    cut_naive = cutoff.replace(tzinfo=None)
                    if rec_naive < cut_naive:
                        break
                except Exception:
                    pass  # keep processing

            if _already_processed(msg, tag):
                continue

            counters["scanned"] += 1
            label = classify(msg, patterns=patterns, cnee_emails=cnee_set)

            if label == "BOUNCE":
                body = str(getattr(msg, "Body", "") or "")
                target = handlers.extract_bounced_email(body) or ""
                handlers.handle_bounce(msg, target)
                counters["bounces"] += 1

            elif label == "AUTO_REPLY":
                sender = str(getattr(msg, "SenderEmailAddress", "") or "").lower().strip()
                handlers.handle_auto_reply(msg, sender)
                counters["auto_replies"] += 1

            elif label == "UNSUBSCRIBE":
                sender = str(getattr(msg, "SenderEmailAddress", "") or "").lower().strip()
                handlers.handle_unsubscribe(msg, sender)
                counters["unsubs"] += 1

            elif label == "REAL_REPLY":
                sender = str(getattr(msg, "SenderEmailAddress", "") or "").lower().strip()
                row = _cnee_lookup(sender)
                handlers.handle_real_reply(msg, row)
                counters["real_replies"] += 1

            else:  # IRRELEVANT
                counters["irrelevant"] += 1

            _mark_processed(msg, tag)

        except Exception as exc:
            counters["errors"] += 1
            log.warning("run_scan: error processing item: %s", exc)

    log.info(
        "run_scan done: %s",
        ", ".join(f"{k}={v}" for k, v in counters.items()),
    )
    return counters


# -------------------------------------------------------------------
# Scheduler wiring
# -------------------------------------------------------------------
def start_scheduler():
    """Create BackgroundScheduler with 30-min scan + 21:00 daily report.

    Returns the scheduler; caller is responsible for keeping a reference.
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
        minutes=30,
        id="inbox_scan",
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
    log.info("APScheduler started — run_scan@30min, daily_report@21:00 Asia/Ho_Chi_Minh")
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

    # Run once immediately so Nelson sees activity on startup.
    try:
        run_scan()
    except Exception as exc:
        log.error("initial run_scan failed: %s", exc)

    while True:
        time.sleep(60)


if __name__ == "__main__":  # pragma: no cover
    _main()
