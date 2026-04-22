"""
harvest_patterns.py — Compiled regex patterns for bounce_harvest_v2
====================================================================
Extracted to keep bounce_harvest_v2.py under 200 lines.

DO NOT import this file directly — use via bounce_harvest_v2.
"""

import re

# ── OOO (Out-Of-Office) subject match ────────────────────────────────────────
OOO_SUBJECT_RX = re.compile(
    r"(?:out of office|automatic reply|auto[- ]?reply|away from office"
    r"|on vacation|on leave|currently away|not in office)",
    re.IGNORECASE,
)

# ── OOO body patterns ─────────────────────────────────────────────────────────
OOO_BODY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(?:i am|i'?m|i will be|i'?ll be)\s+(?:out of|away from|not in)\s+(?:the\s+)?office",
        r"out of (?:the\s+)?office",
        r"will (?:return|be back|respond)\s+(?:on|by|after)",
        r"(?:return|back)\s+(?:on|to the office on)\s+([A-Za-z]+\s+\d{1,2})",
        r"available (?:again )?(?:on|from)\s+([A-Za-z]+\s+\d{1,2})",
        r"(?:on\s+)?(?:annual|maternity|paternity|sick)\s+leave",
    ]
]

# ── Return date extraction ─────────────────────────────────────────────────────
RETURN_DATE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(?:return|back|available|respond)\s+(?:on|by|from|after)\s+([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{4})?)",
        r"(?:returning|back)\s+([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{4})?)",
        r"(?:until|through)\s+([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{4})?)",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
]

# ── LEFT (no longer employed) patterns ───────────────────────────────────────
LEFT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(?:is\s+)?no longer (?:with|at|employed by|working for)",
        r"(?:has?\s+)?left (?:the company|our organization|our team|this position)",
        r"no longer (?:work(?:s|ing)?|employed)",
        r"(?:email address|account|mailbox) (?:has been\s+)?(?:deactivated|disabled|closed|removed)",
        r"(?:is\s+)?not (?:longer\s+)?(?:with|at|employed)",
        r"(?:email is\s+)?no longer (?:valid|active|in use)",
        r"(?:has\s+)?(?:departed|resigned|retired)",
        r"left our (?:company|organization|firm)",
    ]
]

# ── Email finder in body ──────────────────────────────────────────────────────
EMAIL_RX = re.compile(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

# ── Position keywords ─────────────────────────────────────────────────────────
POSITION_KEYWORDS: dict[str, list[str]] = {
    "PRICING":  ["pricing", "rate", "rates", "quotation", "quote", "freight"],
    "BOOKING":  ["booking", "reservation", "shipment", "cargo", "logistics"],
    "OPS":      ["operations", "ops", "coordination", "customs", "clearance"],
    "SALES":    ["sales", "account", "manager", "representative", "contact"],
    "GENERAL":  ["contact", "reach", "assist", "help", "enquir"],
}

# ── Daemon address prefixes to skip ──────────────────────────────────────────
SKIP_LOCAL_PREFIXES: frozenset[str] = frozenset([
    "mailer-daemon", "postmaster", "noreply", "no-reply",
    "bounce", "auto-reply", "donotreply",
])
