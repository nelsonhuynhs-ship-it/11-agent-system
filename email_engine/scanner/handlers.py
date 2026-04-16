"""
email_engine.scanner.handlers
=============================
Per-class handlers invoked by inbox_scanner.run_scan.

Each handler:
    1. Normalises the item (extracts what it needs)
    2. Logs an intel event via email_engine.intel.memory.log_event
    3. Re-evaluates tier via email_engine.intel.tier_engine.evaluate_event
    4. Writes back to cnee_master_v2 via email_engine.intel.writeback.update_master
    5. Emits a Telegram alert (batch-friendly)

Intel modules may not exist yet (being built in parallel by dev-intel).
We import them under try/except and fall back to no-op stubs so this
package still imports cleanly on a fresh checkout.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from . import telegram as tg
from .classifier import classify_bounce_severity, load_patterns

log = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Intel module imports with graceful stubs (Round 2 wires real modules)
# -------------------------------------------------------------------
try:
    from email_engine.intel.memory import log_event as _log_event  # type: ignore
    from email_engine.intel.memory import get_cnee_summary as _get_cnee_summary  # type: ignore
    _INTEL_MEMORY_AVAILABLE = True
except Exception:  # ImportError or sub-import failure
    _INTEL_MEMORY_AVAILABLE = False

    def _log_event(event_type: str, **fields) -> None:  # type: ignore
        log.debug("[STUB log_event] %s %s", event_type, fields)

    def _get_cnee_summary(email: str) -> dict:  # type: ignore
        return {}


try:
    from email_engine.intel.tier_engine import evaluate_event as _evaluate_event  # type: ignore
    _INTEL_TIER_AVAILABLE = True
except Exception:
    _INTEL_TIER_AVAILABLE = False

    def _evaluate_event(event_type: str, email: str, **fields) -> dict:  # type: ignore
        log.debug("[STUB evaluate_event] %s email=%s", event_type, email)
        return {"tier": None, "action": None, "changed": False}


try:
    from email_engine.intel.writeback import update_master as _update_master  # type: ignore
    _INTEL_WRITEBACK_AVAILABLE = True
except Exception:
    _INTEL_WRITEBACK_AVAILABLE = False

    def _update_master(email: str, updates: dict) -> bool:  # type: ignore
        log.debug("[STUB update_master] %s %s", email, updates)
        return True


# Reply analyzer (upgraded — see core/reply_analyzer.py)
try:
    from email_engine.core.reply_analyzer import analyze_reply as _analyze_reply  # type: ignore
except Exception:
    def _analyze_reply(subject: str, body: str) -> dict:  # type: ignore
        return {"sentiment": "UNKNOWN", "intent": "general", "confidence": 0.0}


# -------------------------------------------------------------------
# Public helpers
# -------------------------------------------------------------------
def extract_bounced_email(body: str) -> str | None:
    """Parse DSN body and return the failed recipient email, or None."""
    if not body:
        return None

    patterns = load_patterns().get(
        "bounce_regex",
        [
            r'(?:could not be delivered|undelivered|failed).*?([\w\.\-]+@[\w\.\-]+)',
            r'Final-Recipient:\s*rfc822;\s*([\w\.\-]+@[\w\.\-]+)',
        ],
    )
    for rx in patterns:
        m = re.search(rx, body, re.IGNORECASE | re.DOTALL)
        if m:
            candidate = m.group(1).strip().lower()
            if _is_plausible_email(candidate):
                return candidate

    # Last-ditch: find any email that isn't a daemon/postmaster.
    for m in re.finditer(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", body):
        c = m.group(0).lower()
        if any(s in c for s in ("mailer-daemon", "postmaster", "noreply", "no-reply")):
            continue
        return c
    return None


def _is_plausible_email(s: str) -> bool:
    if "@" not in s or s.count("@") != 1:
        return False
    local, _, domain = s.partition("@")
    return bool(local) and "." in domain


def _safe_attr(item: Any, attr: str, default: str = "") -> str:
    try:
        v = getattr(item, attr, default)
        return str(v) if v is not None else default
    except Exception:
        return default


# -------------------------------------------------------------------
# Handlers
# -------------------------------------------------------------------
def handle_bounce(item: Any, bounced_email: str) -> None:
    """Bounce / DSN handler.

    `bounced_email` is the failed recipient extracted from the NDR body.
    If caller hasn't extracted yet, they can pass "" — we'll try again here.
    """
    body = _safe_attr(item, "Body")
    subject = _safe_attr(item, "Subject")

    target = (bounced_email or extract_bounced_email(body) or "").lower().strip()
    if not target:
        log.warning("handle_bounce: could not extract recipient from NDR; subject=%r", subject[:120])
        return

    severity = classify_bounce_severity(body)  # HARD | SOFT

    _log_event(
        "BOUNCE",
        email=target,
        severity=severity,
        subject=subject,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event("BOUNCE", email=target, severity=severity) or {}
    _update_master(
        target,
        {
            "EMAIL_STATUS": "HARD_BOUNCE" if severity == "HARD" else "SOFT_BOUNCE",
            "LAST_BOUNCE_AT": datetime.now(timezone.utc).isoformat(),
            "LAST_BOUNCE_SEVERITY": severity,
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    tg.send_alert(
        f"<b>Bounce ({severity})</b>\n{target}\n<i>{subject[:140]}</i>"
    )


def handle_auto_reply(item: Any, cnee_email: str) -> None:
    """Out-of-office / automatic reply handler."""
    subject = _safe_attr(item, "Subject")
    body = _safe_attr(item, "Body")
    email = (cnee_email or "").lower().strip()

    _log_event(
        "AUTO_REPLY",
        email=email,
        subject=subject,
        body_preview=body[:400],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event("AUTO_REPLY", email=email) or {}
    _update_master(
        email,
        {
            "LAST_AUTO_REPLY_AT": datetime.now(timezone.utc).isoformat(),
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    # Low-priority alert — daily report is enough; don't spam Nelson mid-day.
    log.info("AUTO_REPLY logged for %s", email)


def handle_real_reply(item: Any, cnee_row: dict) -> None:
    """Real human reply from a known CNEE.

    `cnee_row` is a dict-like row from cnee_master_v2 (must contain EMAIL and
    optionally COMPANY / TIER / CAMPAIGN).
    """
    subject = _safe_attr(item, "Subject")
    body = _safe_attr(item, "Body")
    email = str(cnee_row.get("EMAIL") or cnee_row.get("email") or "").lower().strip()
    company = str(cnee_row.get("COMPANY") or cnee_row.get("company") or "").strip()

    analysis = _analyze_reply(subject, body)
    sentiment = analysis.get("sentiment", "UNKNOWN")
    intent = analysis.get("intent", "general")
    confidence = float(analysis.get("confidence", 0.0))

    _log_event(
        "REPLY",
        email=email,
        company=company,
        subject=subject,
        body_preview=body[:800],
        sentiment=sentiment,
        intent=intent,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event(
        "REPLY", email=email, sentiment=sentiment, intent=intent
    ) or {}
    _update_master(
        email,
        {
            "LAST_REPLY_AT": datetime.now(timezone.utc).isoformat(),
            "LAST_REPLY_INTENT": intent,
            "LAST_REPLY_SENTIMENT": sentiment,
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    # Hot-lead alert for booking / negotiating / price inquiry
    if intent in ("booking_intent", "negotiating", "price_inquiry"):
        hot_label = {
            "booking_intent": "HOT LEAD — booking",
            "negotiating": "HOT LEAD — negotiating",
            "price_inquiry": "WARM — price inquiry",
        }[intent]
        msg = (
            f"<b>{hot_label}</b>\n"
            f"{company or '(no company)'} &lt;{email}&gt;\n"
            f"Sentiment: {sentiment}  |  Intent: {intent}\n"
            f"<i>{subject[:140]}</i>"
        )
        tg.send_alert(msg)
    else:
        log.info("REPLY logged for %s (intent=%s, sentiment=%s)", email, intent, sentiment)


def handle_unsubscribe(item: Any, cnee_email: str) -> None:
    """Opt-out handler — suppress future sends."""
    subject = _safe_attr(item, "Subject")
    email = (cnee_email or "").lower().strip()

    _log_event(
        "UNSUBSCRIBE",
        email=email,
        subject=subject,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _evaluate_event("UNSUBSCRIBE", email=email)
    _update_master(
        email,
        {
            "EMAIL_STATUS": "UNSUBSCRIBED",
            "ACTION": "SUPPRESS",
            "UNSUBSCRIBED_AT": datetime.now(timezone.utc).isoformat(),
        },
    )
    tg.send_alert(f"<b>Unsubscribe</b>\n{email}\n<i>{subject[:140]}</i>")
