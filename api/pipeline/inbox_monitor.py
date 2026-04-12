"""
inbox_monitor.py — Monitor email replies and classify for auto-response or hold.
Designed to be called by GoClaw cron every 15 minutes.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .policy_guard import classify_intent, check_policy
from .template_engine import render_email

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
MONITOR_LOG = DATA_DIR / "email" / "inbox_monitor.log"


def process_reply(
    sender_email: str,
    sender_company: str,
    subject: str,
    body: str,
    daily_auto_count: int = 0,
) -> dict:
    """
    Process an incoming email reply through the policy guard.

    Returns:
        {
            'intent': str,
            'action': 'auto_reply' | 'hold_and_alert',
            'allowed': bool,
            'reason': str,
            'response': dict (if auto_reply) | None,
            'alert_message': str (if hold),
        }
    """
    # Classify intent
    intent = classify_intent(subject, body)

    # Handle special intents immediately
    if intent == "OOO":
        return {
            "intent": "OOO",
            "action": "update_status",
            "allowed": False,
            "reason": "Out-of-office auto-reply detected",
            "status_update": {"reply_status": "AUTO_REPLY", "action": "COOLDOWN"},
        }

    if intent == "BOUNCE":
        return {
            "intent": "BOUNCE",
            "action": "update_status",
            "allowed": False,
            "reason": "Bounce/undeliverable detected",
            "status_update": {"seq_status": "BOUNCED", "action": "SKIP"},
        }

    if intent == "UNSUBSCRIBE":
        return {
            "intent": "UNSUBSCRIBE",
            "action": "update_status",
            "allowed": False,
            "reason": "Unsubscribe request",
            "status_update": {"action": "SKIP", "reply_status": "UNSUBSCRIBED"},
        }

    # Check policy
    policy = check_policy(intent, sender_email, daily_auto_count)

    result = {
        "intent": intent,
        "action": policy["action"],
        "allowed": policy["allowed"],
        "reason": policy["reason"],
        "sender": sender_email,
        "company": sender_company,
        "subject": subject,
        "timestamp": datetime.now().isoformat(),
    }

    if policy["allowed"]:
        # Would generate auto-reply here
        # In production, this calls template_engine + pricing_engine
        result["response"] = {
            "template": "transactional/quote",
            "note": "Auto-reply with matching rates from pricing engine",
            "cc_team": policy.get("cc_team", True),
        }
    else:
        result["alert_message"] = policy.get("alert_message", f"Reply from {sender_email} needs review")

    # Log
    _log_event(result)

    return result


def _log_event(event: dict):
    """Append event to monitor log."""
    MONITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(MONITOR_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def generate_alert_message(result: dict) -> str:
    """Format Telegram alert message for held replies."""
    if result["allowed"]:
        return f"Auto-replied to {result.get('company', result['sender'])}: {result.get('subject', '')}"

    intent = result["intent"]
    sender = result.get("company", result["sender"])
    subject = result.get("subject", "")

    if intent in ("NEGOTIATION", "COMPLAINT", "CONTRACT_DISCUSS", "LEGAL", "FINANCIAL"):
        return f"Reply from {sender} needs your attention (intent: {intent}): {subject}"
    else:
        return f"New reply from {sender}: {subject} — intent: {intent}"
