"""
bounce_harvest_v2.py — 2-way auto-reply scanner: OOO + LEFT detection
=====================================================================
Phase 2 — Bounce Harvest v2

Scans incoming auto-reply emails for two patterns:
  OOO  (Out-Of-Office)  → DEFER_UNTIL = return_date parsed from body
  LEFT (No longer here) → mark EMAIL_STATUS=DEAD + harvest replacement contact

Replacement contacts are extracted from the reply body, filtered against
the sender's own domain, and queued for Nelson's review before master insert.

Patterns are in harvest_patterns.py to keep this file under 200 lines.

Usage:
    from email_engine.core.bounce_harvest_v2 import scan
    result = scan(subject, body, sender_email)
    # result.kind = "OOO" | "LEFT" | "UNKNOWN"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from email_engine.core.harvest_patterns import (
    OOO_SUBJECT_RX, OOO_BODY_PATTERNS, RETURN_DATE_PATTERNS,
    LEFT_PATTERNS, EMAIL_RX, POSITION_KEYWORDS, SKIP_LOCAL_PREFIXES,
)

log = logging.getLogger(__name__)


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class ReplacementContact:
    email: str
    position: str           # PRICING | BOOKING | OPS | SALES | GENERAL
    context_snippet: str    # ~80 chars around the email mention
    confidence: float       # 0.0-1.0


@dataclass
class HarvestResult:
    kind: str                                   # OOO | LEFT | UNKNOWN
    original_email: str
    sender_domain: str
    defer_until: Optional[datetime] = None      # OOO: when to resume
    raw_return_text: str = ""
    replacements: list[ReplacementContact] = field(default_factory=list)
    matched_pattern: str = ""
    notes: str = ""


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_return_date(body: str) -> tuple[Optional[datetime], str]:
    """Extract return date from OOO body. Returns (datetime|None, raw_text)."""
    try:
        from dateutil import parser as date_parser
        from dateutil.parser import ParserError
    except ImportError:
        log.warning("python-dateutil not installed — date parsing disabled. pip install python-dateutil")
        return None, ""

    for rx in RETURN_DATE_PATTERNS:
        m = rx.search(body)
        if not m:
            continue
        raw = m.group(1).strip() if m.lastindex else m.group(0).strip()
        try:
            dt = date_parser.parse(raw, default=datetime.now(timezone.utc), fuzzy=True)
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < now:
                dt = dt.replace(year=now.year + 1)
            return dt, raw
        except (ParserError, ValueError, OverflowError):
            continue

    return None, ""


# ── Replacement extractor ─────────────────────────────────────────────────────

def _extract_replacements(body: str, sender_domain: str) -> list[ReplacementContact]:
    """Extract replacement contact emails from reply body (max 3).

    Excludes: same-domain system addresses, daemon prefixes.
    """
    results: list[ReplacementContact] = []
    seen: set[str] = set()

    for m in EMAIL_RX.finditer(body):
        candidate = m.group(0).lower().strip()
        if candidate in seen or "@" not in candidate:
            continue
        seen.add(candidate)

        local, _, domain = candidate.partition("@")
        if any(candidate.startswith(p) for p in SKIP_LOCAL_PREFIXES):
            continue
        if domain == sender_domain.lower():
            continue

        start = max(0, m.start() - 80)
        end   = min(len(body), m.end() + 80)
        context = body[start:end].replace("\n", " ").strip()
        context_lower = context.lower()

        position = "GENERAL"
        for pos, keywords in POSITION_KEYWORDS.items():
            if any(kw in context_lower for kw in keywords):
                position = pos
                break

        results.append(ReplacementContact(
            email=candidate,
            position=position,
            context_snippet=context[:160],
            confidence=0.8 if position != "GENERAL" else 0.5,
        ))

    return results[:3]


# ── Main scan function ────────────────────────────────────────────────────────

def scan(subject: str, body: str, sender_email: str) -> HarvestResult:
    """Analyse an incoming reply for OOO or LEFT signals.

    Args:
        subject:       Email subject line
        body:          Plain text email body
        sender_email:  From address of the auto-reply

    Returns HarvestResult with kind=OOO|LEFT|UNKNOWN.
    """
    subject = (subject or "").strip()
    body    = (body or "").strip()
    sender_email = (sender_email or "").lower().strip()
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""

    # LEFT check first — permanent signal, higher value
    for rx in LEFT_PATTERNS:
        if rx.search(body) or rx.search(subject):
            reps = _extract_replacements(body, sender_domain)
            log.info("harvest_v2 LEFT: %s | replacements=%d", sender_email, len(reps))
            return HarvestResult(
                kind="LEFT", original_email=sender_email,
                sender_domain=sender_domain, replacements=reps,
                matched_pattern=rx.pattern[:80],
                notes=f"LEFT pattern; {len(reps)} replacement(s) found",
            )

    # OOO check
    subject_match = bool(OOO_SUBJECT_RX.search(subject))
    body_match    = any(rx.search(body) for rx in OOO_BODY_PATTERNS)

    if subject_match or body_match:
        defer_until, raw_text = _parse_return_date(body)
        if defer_until is None:
            defer_until = datetime.now(timezone.utc) + timedelta(days=7)
            raw_text = "(no date found — defaulted to +7d)"
        log.info("harvest_v2 OOO: %s | defer_until=%s", sender_email, defer_until.date())
        return HarvestResult(
            kind="OOO", original_email=sender_email,
            sender_domain=sender_domain, defer_until=defer_until,
            raw_return_text=raw_text,
            matched_pattern="subject" if subject_match else "body",
            notes=f"Defer until {defer_until.strftime('%Y-%m-%d')}",
        )

    return HarvestResult(
        kind="UNKNOWN", original_email=sender_email,
        sender_domain=sender_domain,
        notes="No OOO or LEFT pattern matched",
    )


# ── Master update helpers (called from handlers.py) ──────────────────────────

def apply_ooo_to_master(result: HarvestResult, update_fn) -> bool:
    """Set DEFER_UNTIL on master. update_fn(email, updates_dict) -> bool."""
    if result.kind != "OOO" or not result.defer_until:
        return False
    try:
        update_fn(result.original_email, {
            "DEFER_UNTIL":   result.defer_until.isoformat(),
            "LAST_OOO_AT":   datetime.now(timezone.utc).isoformat(),
            "OOO_RAW_RETURN": result.raw_return_text,
        })
        log.info("apply_ooo: %s defer_until=%s", result.original_email, result.defer_until.date())
        return True
    except Exception as exc:
        log.warning("apply_ooo_to_master failed: %s", exc)
        return False


def apply_left_to_master(result: HarvestResult, update_fn) -> bool:
    """Mark original email DEAD. Replacements go to review queue only."""
    if result.kind != "LEFT":
        return False
    try:
        update_fn(result.original_email, {
            "EMAIL_STATUS": "DEAD",
            "DEAD_REASON":  "LEFT_COMPANY",
            "DEAD_AT":      datetime.now(timezone.utc).isoformat(),
        })
        log.info(
            "apply_left: %s marked DEAD | %d replacements queued",
            result.original_email, len(result.replacements),
        )
        return True
    except Exception as exc:
        log.warning("apply_left_to_master failed: %s", exc)
        return False
