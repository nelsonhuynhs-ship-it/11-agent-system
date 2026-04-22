"""
typo_shield.py — Fuzzy domain typo detection for email addresses
================================================================
Phase 2 — Typo Shield

Catches domain typos (gmail.co → gmail.com, yaho.com → yahoo.com) using
RapidFuzz string similarity against top known-good domains.

Result actions:
  BLOCK  — high confidence typo (≥92%), auto-reject before send
  HOLD   — moderate similarity (85–91%), queue for Nelson review
  OK     — exact match or no similar domain found

Domain list: typo_domains.py
Usage:
    from email_engine.core.typo_shield import check_typo, bulk_check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from email_engine.core.typo_domains import TOP_DOMAINS

log = logging.getLogger(__name__)

_BLOCK_THRESHOLD = 92   # 92+ → auto-block
_HOLD_THRESHOLD  = 85   # 85–91 → hold for review


@dataclass
class TypoResult:
    email: str
    domain: str
    is_suspect: bool
    suggested_fix: Optional[str]       # corrected full email e.g. user@gmail.com
    suggested_domain: Optional[str]    # just the domain e.g. gmail.com
    confidence: float                  # 0-100 RapidFuzz ratio score
    action: str                        # "OK" | "HOLD" | "BLOCK"
    match_source: str = ""


def check_typo(email: str) -> TypoResult:
    """Check a single email address for domain typos.

    Always returns a TypoResult — never raises.
    Degrades gracefully if rapidfuzz not installed (all → OK).
    """
    try:
        from rapidfuzz import process as fz_process, fuzz
    except ImportError:
        log.warning("rapidfuzz not installed — typo_shield disabled. pip install rapidfuzz")
        return TypoResult(
            email=email, domain="", is_suspect=False,
            suggested_fix=None, suggested_domain=None,
            confidence=0.0, action="OK", match_source="no_rapidfuzz",
        )

    email = (email or "").strip().lower()
    if "@" not in email:
        return TypoResult(email=email, domain="", is_suspect=False,
                          suggested_fix=None, suggested_domain=None,
                          confidence=0.0, action="OK")

    local, _, domain = email.partition("@")
    if not domain:
        return TypoResult(email=email, domain=domain, is_suspect=False,
                          suggested_fix=None, suggested_domain=None,
                          confidence=0.0, action="OK")

    # Exact match → definitely OK
    if domain in set(TOP_DOMAINS):
        return TypoResult(email=email, domain=domain, is_suspect=False,
                          suggested_fix=None, suggested_domain=None,
                          confidence=100.0, action="OK")

    result = fz_process.extractOne(
        domain, TOP_DOMAINS, scorer=fuzz.ratio, score_cutoff=_HOLD_THRESHOLD
    )
    if result is None:
        return TypoResult(email=email, domain=domain, is_suspect=False,
                          suggested_fix=None, suggested_domain=None,
                          confidence=0.0, action="OK")

    matched_domain, score, _ = result
    action = "BLOCK" if score >= _BLOCK_THRESHOLD else "HOLD"

    log.debug("typo_shield: %s → %s (score=%.1f action=%s)", domain, matched_domain, score, action)
    return TypoResult(
        email=email, domain=domain, is_suspect=True,
        suggested_fix=f"{local}@{matched_domain}",
        suggested_domain=matched_domain,
        confidence=float(score), action=action,
        match_source=matched_domain,
    )


def bulk_check(emails: list[str]) -> dict:
    """Check a list of emails for domain typos.

    Returns:
        {
          "clean": [str],          OK emails
          "block": [TypoResult],   high-confidence typos → auto-reject
          "hold":  [TypoResult],   borderline → Nelson review
          "stats": {total, blocked, held, clean}
        }
    """
    clean, block, hold = [], [], []
    for email in emails:
        r = check_typo(email)
        if r.action == "BLOCK":
            block.append(r)
        elif r.action == "HOLD":
            hold.append(r)
        else:
            clean.append(email)

    stats = {"total": len(emails), "blocked": len(block), "held": len(hold), "clean": len(clean)}
    log.info("bulk_check: %s", stats)
    return {"clean": clean, "block": block, "hold": hold, "stats": stats}


def add_to_known_domains(domain: str) -> None:
    """Add a domain to TOP_DOMAINS at runtime (Nelson-reviewed legit domains)."""
    d = domain.strip().lower()
    if d not in TOP_DOMAINS:
        TOP_DOMAINS.append(d)
        log.info("typo_shield: added %s to known domains", d)
