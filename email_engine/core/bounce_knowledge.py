"""
bounce_knowledge.py — Bounce Learning Knowledge Base
=====================================================
Sprint 1 v3: Bounce Learning System

Self-improving KB that learns from real bounces → auto-filters new imports.

Usage:
    from email_engine.core.bounce_knowledge import learn_from_bounce, filter_emails
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from filelock import FileLock

log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
# Canonical: OneDrive (primary source of truth)
_KB_CANONICAL = Path("D:/OneDrive/NelsonData/email/competitor_blacklist.json")
# Mirror: repo copy (kept in sync on every save)
_KB_MIRROR = Path(__file__).resolve().parent.parent / "data" / "competitor_blacklist.json"

# Use canonical if available, fallback to mirror
KB_PATH: Path = _KB_CANONICAL if _KB_CANONICAL.exists() else _KB_MIRROR
LOCK_PATH: Path = KB_PATH.with_suffix(".lock")

# ── Thresholds ────────────────────────────────────────────────────────────────
DEAD_THRESHOLD_BOUNCE_RATE = 0.8   # ≥80% bounce + min sends → DEAD
DEAD_THRESHOLD_MIN_SENDS   = 3     # need at least N sends to classify
RISKY_THRESHOLD_BOUNCE_RATE = 0.3  # 30-80% bounce → RISKY

# ── Common role-based local parts ─────────────────────────────────────────────
_COMMON_ROLE_WORDS: frozenset[str] = frozenset({
    "info", "admin", "support", "sales", "contact", "help",
    "noreply", "no-reply", "mailer", "postmaster",
    "orderdesk", "documents", "apinvoices", "webmaster",
    "marketing", "billing", "accounting", "enquiry",
})

# ── Disposable source ─────────────────────────────────────────────────────────
_DISPOSABLE_URL = (
    "https://raw.githubusercontent.com/disposable-email-domains/"
    "disposable-email-domains/master/disposable_email_blocklist.conf"
)


# ── Core I/O ──────────────────────────────────────────────────────────────────

def load_kb() -> dict:
    """Load the knowledge base JSON with file lock."""
    with FileLock(str(LOCK_PATH)):
        with open(KB_PATH, encoding="utf-8") as f:
            return json.load(f)


def save_kb(kb: dict) -> None:
    """Save KB to canonical + mirror, updating last_updated timestamp."""
    kb.setdefault("_meta", {})["last_updated"] = datetime.now().isoformat()

    with FileLock(str(LOCK_PATH)):
        # Write canonical
        with open(KB_PATH, "w", encoding="utf-8") as f:
            json.dump(kb, f, indent=2, ensure_ascii=False)

        # Sync mirror (best-effort)
        try:
            mirror = _KB_MIRROR
            if mirror != KB_PATH and mirror.parent.exists():
                with open(mirror, "w", encoding="utf-8") as f:
                    json.dump(kb, f, indent=2, ensure_ascii=False)
        except Exception as sync_err:
            log.warning("KB mirror sync failed: %s", sync_err)


# ── Send count helper ─────────────────────────────────────────────────────────

def count_sends_to_domain(domain: str) -> int:
    """Count total sent emails to a domain from email_log.csv."""
    import pandas as pd

    log_path = Path(__file__).resolve().parent.parent / "logs" / "email_log.csv"
    if not log_path.exists():
        return 0
    try:
        # email_log.csv uses lowercase 'email' column; may have malformed rows
        df = pd.read_csv(log_path, on_bad_lines="skip", engine="python")
        # Normalize: find the email column regardless of case
        email_col = next(
            (c for c in df.columns if c.lower() == "email"),
            None,
        )
        if email_col is None:
            return 0
        df["_domain"] = df[email_col].astype(str).str.split("@").str[-1].str.lower().str.strip()
        return int((df["_domain"] == domain.lower()).sum())
    except Exception as exc:
        log.warning("count_sends_to_domain failed for %s: %s", domain, exc)
        return 0


# ── Learn from bounce ─────────────────────────────────────────────────────────

def learn_from_bounce(
    email: str,
    bounce_type: str,
    source_subject: str = "",
) -> None:
    """Learn from a bounce event. Called from handlers.handle_bounce().

    Only learns from HARD bounces (permanent failures).
    Updates auto_dead_domains and auto_role_prefixes in KB.
    """
    if (bounce_type or "").upper() != "HARD":
        return

    email = (email or "").lower().strip()
    if not email or "@" not in email:
        return

    local, _, domain = email.partition("@")
    domain = domain.strip()
    if not domain:
        return

    try:
        kb = load_kb()

        # Ensure fields exist
        kb.setdefault("auto_dead_domains", {})
        kb.setdefault("auto_role_prefixes", {})

        # Count sends from email_log
        sends_total = count_sends_to_domain(domain)

        # Init domain entry if new
        if domain not in kb["auto_dead_domains"]:
            kb["auto_dead_domains"][domain] = {
                "bounces": 0,
                "sends_total": sends_total,
                "bounce_rate": 0.0,
                "first_bounce": datetime.now().isoformat(),
                "last_bounce": "",
                "classification": "LEARNING",
                "evidence_emails": [],
            }

        entry = kb["auto_dead_domains"][domain]
        entry["bounces"] += 1
        entry["sends_total"] = max(sends_total, entry["bounces"])  # at least as many as bounces
        entry["last_bounce"] = datetime.now().isoformat()
        entry["bounce_rate"] = round(entry["bounces"] / entry["sends_total"], 4)

        # Track evidence (up to 5 unique emails)
        if email not in entry["evidence_emails"]:
            entry["evidence_emails"].append(email)
            entry["evidence_emails"] = entry["evidence_emails"][:5]

        # Classify
        n_sends = entry["sends_total"]
        br = entry["bounce_rate"]
        if n_sends >= DEAD_THRESHOLD_MIN_SENDS:
            if br >= DEAD_THRESHOLD_BOUNCE_RATE:
                entry["classification"] = "DEAD"
            elif br >= RISKY_THRESHOLD_BOUNCE_RATE:
                entry["classification"] = "RISKY"
            else:
                entry["classification"] = "LEARNING"
        # else: stay LEARNING until enough data

        # Learn role prefix patterns
        if local in _COMMON_ROLE_WORDS:
            kb["auto_role_prefixes"].setdefault(local, 0)
            kb["auto_role_prefixes"][local] += 1

        save_kb(kb)
        log.info(
            "KB learned: domain=%s classification=%s bounces=%d sends=%d rate=%.1f%% local=%s",
            domain,
            entry["classification"],
            entry["bounces"],
            entry["sends_total"],
            entry["bounce_rate"] * 100,
            local if local in _COMMON_ROLE_WORDS else "-",
        )

    except Exception as exc:
        log.error("learn_from_bounce failed for %s: %s", email, exc)


# ── Filter emails ─────────────────────────────────────────────────────────────

def filter_emails(emails: list[str]) -> dict:
    """Filter a list of emails using the learned KB.

    Returns:
        {
            'accepted': [str],                        # clean, proceed
            'dropped':  [{'email': str, 'reason': str}],  # blocked entirely
            'flagged':  [{'email': str, 'reason': str}],  # keep but LOW priority
        }

    Drop reasons: INVALID_FORMAT, COMPETITOR_DOMAIN, COMPETITOR_EMAIL,
                  AUTO_DEAD_DOMAIN, DISPOSABLE
    Flag reasons: RISKY_DOMAIN, ROLE_BASED
    """
    try:
        kb = load_kb()
    except Exception as exc:
        log.error("filter_emails: failed to load KB — rejecting import for safety: %s", exc)
        raise RuntimeError(f"KB load failed: {exc}") from exc

    # Build lookup sets
    manual_domains  = {d.lower().strip() for d in kb.get("domains", []) if d}
    manual_emails   = {e.lower().strip() for e in kb.get("emails", []) if e}
    whitelist       = {d.lower().strip() for d in kb.get("whitelist_domains", [])} | {"pudongprime.vn"}
    disposable      = {d.lower().strip() for d in kb.get("disposable_domains", [])}

    auto_dead  = kb.get("auto_dead_domains", {})
    dead_set   = {d for d, m in auto_dead.items() if m.get("classification") == "DEAD"}
    risky_set  = {d for d, m in auto_dead.items() if m.get("classification") == "RISKY"}

    role_set = set(kb.get("auto_role_prefixes", {}).keys())
    # Always include common role words even if not yet seen in bounces
    role_set |= _COMMON_ROLE_WORDS

    result: dict = {"accepted": [], "dropped": [], "flagged": []}

    for email in emails:
        e = (email or "").lower().strip()

        if not e or "@" not in e:
            result["dropped"].append({"email": email, "reason": "INVALID_FORMAT"})
            continue

        local, _, domain = e.partition("@")
        domain = domain.strip()

        # Whitelist bypass — never block internal domain
        if domain in whitelist:
            result["accepted"].append(email)
            continue

        # Manual competitor exact email
        if e in manual_emails:
            result["dropped"].append({"email": email, "reason": "COMPETITOR_EMAIL"})
            continue

        # Manual competitor domain
        if domain in manual_domains:
            result["dropped"].append({"email": email, "reason": "COMPETITOR_DOMAIN"})
            continue

        # Auto-learned DEAD domain
        if domain in dead_set:
            result["dropped"].append({"email": email, "reason": "AUTO_DEAD_DOMAIN"})
            continue

        # Disposable domain
        if domain in disposable:
            result["dropped"].append({"email": email, "reason": "DISPOSABLE"})
            continue

        # Auto-learned RISKY → flag, keep with LOW priority
        if domain in risky_set:
            result["flagged"].append({"email": email, "reason": "RISKY_DOMAIN"})
            continue

        # Role-based local part → flag, keep with LOW priority
        if local in role_set:
            result["flagged"].append({"email": email, "reason": "ROLE_BASED"})
            continue

        result["accepted"].append(email)

    return result


def filter_company_name(company: str) -> tuple[bool, Optional[str]]:
    """Check if company name contains a competitor keyword.

    Returns (blocked: bool, matched_keyword: str | None).
    """
    try:
        kb = load_kb()
    except Exception:
        return False, None

    company_upper = (company or "").upper()
    for kw in kb.get("keywords_in_company", []):
        if kw and kw.upper() in company_upper:
            return True, kw
    return False, None


# ── Disposable sync ───────────────────────────────────────────────────────────

def sync_disposable_domains(timeout: int = 30) -> int:
    """Download fresh disposable domain list from GitHub and persist to KB.

    Returns the count of domains synced, or 0 on failure.
    """
    try:
        with urllib.request.urlopen(_DISPOSABLE_URL, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")

        domains = sorted({
            line.strip().lower()
            for line in content.splitlines()
            if line.strip() and not line.startswith("#")
        })

        kb = load_kb()
        kb["disposable_domains"] = domains
        kb["disposable_domains_last_sync"] = datetime.now().isoformat()
        save_kb(kb)

        log.info("sync_disposable_domains: synced %d domains", len(domains))
        return len(domains)

    except Exception as exc:
        log.error("sync_disposable_domains failed: %s", exc)
        return 0


# ── KB summary (used by API endpoints) ───────────────────────────────────────

def get_kb_summary() -> dict:
    """Return counts per category for the summary API."""
    kb = load_kb()
    auto_domains = kb.get("auto_dead_domains", {})
    return {
        "dead_domains":    sum(1 for m in auto_domains.values() if m.get("classification") == "DEAD"),
        "risky_domains":   sum(1 for m in auto_domains.values() if m.get("classification") == "RISKY"),
        "learning_domains": sum(1 for m in auto_domains.values() if m.get("classification") == "LEARNING"),
        "disposable":      len(kb.get("disposable_domains", [])),
        "role_prefixes":   len(kb.get("auto_role_prefixes", {})),
        "manual_domains":  len(kb.get("domains", [])),
        "manual_emails":   len(kb.get("emails", [])),
        "disposable_last_sync": kb.get("disposable_domains_last_sync", ""),
        "kb_version":      kb.get("_meta", {}).get("version", 0),
    }
