"""
policy_guard.py — Safety layer for auto-replies.
Classifies email intent and enforces company policy before responding.
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
POLICY_CONFIG = Path(__file__).parent / "policy_guard.yaml"


def _load_policy() -> dict:
    if POLICY_CONFIG.exists():
        with open(POLICY_CONFIG) as f:
            return yaml.safe_load(f) or {}
    return _default_policy()


def _default_policy() -> dict:
    return {
        "auto_respond": {
            "allowed_intents": ["INQUIRY", "RATE_REQUEST", "SERVICE_INFO"],
            "blocked_intents": ["NEGOTIATION", "COMPLAINT", "CONTRACT_DISCUSS", "LEGAL", "FINANCIAL"],
            "guardrails": {
                "max_auto_replies_per_day": 20,
                "max_auto_replies_per_contact": 1,
                "require_rate_in_system": True,
                "never_promise_delivery_date": True,
                "never_discuss_competitor": True,
                "always_cc_team": True,
            },
            "fallback": {
                "action": "hold_and_alert",
                "alert_channel": "telegram",
                "alert_to": "5398948978",
            },
        }
    }


# Intent classification keywords
_INTENT_PATTERNS = {
    "RATE_REQUEST": [
        r"(?i)(rate|pricing|quote|quotation|how much|price)\b.*\b(from|to|for|ship)",
        r"(?i)(can you|could you|please)\b.*\b(send|provide|share)\b.*\b(rate|price|quote)",
        r"(?i)(freight|shipping)\b.*\b(cost|charge|rate)",
    ],
    "INQUIRY": [
        r"(?i)(interested|looking for|need|require)\b.*\b(freight|shipping|logistics|forwarder)",
        r"(?i)(do you|can you)\b.*\b(handle|ship|transport|deliver)",
        r"(?i)(service|capability|capacity)\b",
    ],
    "SERVICE_INFO": [
        r"(?i)(what|which)\b.*\b(service|route|port|carrier)",
        r"(?i)(tell me|information|more about)\b.*\b(your|service|company)",
    ],
    "NEGOTIATION": [
        r"(?i)(too (high|expensive)|lower|discount|better (rate|price)|reduce)",
        r"(?i)(can you do|willing to|negotiate|counter.?offer)",
        r"(?i)(competitor|other.?forwarder|cheaper)",
    ],
    "COMPLAINT": [
        r"(?i)(delay|damage|lost|missing|problem|issue|complaint|unhappy|dissatisfied)",
        r"(?i)(where is|what happened|no update|still waiting)",
    ],
    "CONTRACT_DISCUSS": [
        r"(?i)(contract|agreement|annual|long.?term|commitment|volume.?commitment)",
    ],
    "LEGAL": [
        r"(?i)(lawyer|attorney|legal|lawsuit|liability|claim|insurance|indemnity)",
    ],
    "FINANCIAL": [
        r"(?i)(payment|invoice|overdue|outstanding|credit|debit|refund|billing)",
    ],
    "OOO": [
        r"(?i)(out of office|auto.?reply|away|vacation|holiday|will (return|be back))",
    ],
    "UNSUBSCRIBE": [
        r"(?i)(unsubscribe|remove|stop|opt.?out|do not (contact|email|send))",
    ],
    "BOUNCE": [
        r"(?i)(undeliverable|delivery.?failed|mailbox.?full|user.?unknown|no such user)",
    ],
}


def classify_intent(subject: str, body: str) -> str:
    """Classify email reply intent. Returns intent string."""
    text = f"{subject}\n{body}"

    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return intent

    return "UNKNOWN"


def check_policy(intent: str, contact_email: str = "", daily_count: int = 0) -> dict:
    """
    Check if auto-reply is allowed for this intent.

    Returns:
        {
            'allowed': bool,
            'action': 'auto_reply' | 'hold_and_alert',
            'reason': str,
            'alert_message': str (if blocked)
        }
    """
    policy = _load_policy()
    auto = policy.get("auto_respond", {})
    guardrails = auto.get("guardrails", {})
    fallback = auto.get("fallback", {})

    # Check intent
    allowed_intents = auto.get("allowed_intents", [])
    blocked_intents = auto.get("blocked_intents", [])

    if intent in blocked_intents:
        return {
            "allowed": False,
            "action": "hold_and_alert",
            "reason": f"Blocked intent: {intent}",
            "alert_message": f"Reply from {contact_email} needs your attention (intent: {intent})",
        }

    if intent not in allowed_intents:
        return {
            "allowed": False,
            "action": "hold_and_alert",
            "reason": f"Unknown/unallowed intent: {intent}",
            "alert_message": f"Reply from {contact_email} — unclassified intent: {intent}",
        }

    # Check guardrails
    max_daily = guardrails.get("max_auto_replies_per_day", 20)
    if daily_count >= max_daily:
        return {
            "allowed": False,
            "action": "hold_and_alert",
            "reason": f"Daily auto-reply limit reached ({max_daily})",
            "alert_message": f"Auto-reply limit reached. Reply from {contact_email} held.",
        }

    return {
        "allowed": True,
        "action": "auto_reply",
        "reason": f"Intent {intent} is allowed, guardrails passed",
        "cc_team": guardrails.get("always_cc_team", True),
        "require_rate": guardrails.get("require_rate_in_system", True),
    }
