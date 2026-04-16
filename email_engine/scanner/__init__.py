"""
email_engine.scanner
====================
APScheduler-driven Outlook Inbox scanner for Nelson Freight.

Pipeline per item:
    1. classifier.classify(item)     -> label (BOUNCE|AUTO_REPLY|REAL_REPLY|UNSUBSCRIBE|IRRELEVANT)
    2. handlers.handle_<label>(item) -> emits intel event + tier re-evaluation + Telegram alert
    3. inbox_scanner.run_scan        -> marks item processed and moves on

Schedulers (see inbox_scanner.start_scheduler):
    * run_scan              every 30 min
    * daily_report.send...  21:00 local

Interface (re-exported for convenience):
    run_scan, start_scheduler, classify, handle_*, send_alert, generate_summary
"""
from __future__ import annotations

from .classifier import classify, load_patterns
from .handlers import (
    extract_bounced_email,
    handle_auto_reply,
    handle_bounce,
    handle_real_reply,
    handle_unsubscribe,
)
from .inbox_scanner import run_scan, start_scheduler
from .telegram import send_alert, send_batch_alert
from .daily_report import generate_summary, send_daily_report

__all__ = [
    "classify",
    "load_patterns",
    "run_scan",
    "start_scheduler",
    "handle_bounce",
    "handle_auto_reply",
    "handle_real_reply",
    "handle_unsubscribe",
    "extract_bounced_email",
    "send_alert",
    "send_batch_alert",
    "generate_summary",
    "send_daily_report",
]
