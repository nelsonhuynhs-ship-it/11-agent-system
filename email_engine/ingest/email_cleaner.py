# -*- coding: utf-8 -*-
"""
email_cleaner.py — 8-Pass Email Corruption Cleaner
===================================================
Fixes Panjiva-specific corruption patterns discovered in 43 source files.

Pass 1: Split multi-email fields (~1,039 cases)
Pass 2: Strip label prefixes (~93 cases)
Pass 3: Extract from angle brackets (~10 cases)
Pass 4: Strip Panjiva prefix corruption (~1,253 cases — BIGGEST)
Pass 5: Clean phone/number prefix (~28 cases)
Pass 6: Standard RFC validation + quality scoring

Usage:
    from email_engine.ingest.email_cleaner import clean_panjiva_email, validate_email
    emails = clean_panjiva_email("eminfo@company.com,sales@other.com")
    email, score = validate_email("info@company.com")
"""

from __future__ import annotations
import re

# ── Regex patterns ────────────────────────────────────────────────────────────

# Standard email validation regex
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Extract email from within a longer string (for angle brackets / phone prefix)
_EMAIL_FIND_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Angle bracket extraction: "Name <email>" → email
_ANGLE_RE = re.compile(r"<([^>]+@[^>]+)>")

# Phone/number prefix: "339-1729,email@..." or "tel:+1234,email@..."
_PHONE_PREFIX_RE = re.compile(r"^[\d\-\+\(\)\s]+,\s*", re.ASCII)

# ── Constants ─────────────────────────────────────────────────────────────────

# Pass 2: label prefixes to strip (longest first to avoid partial matches)
_LABEL_PREFIXES = [
    "teemail:", "ememail:", "emial:", "e-mail;", "email;",
    "e-mail:", "mailto:", "contact:", "email:", "fax:",
]

# Pass 4: "em" prefix — do NOT strip if word starts with any of these
_EM_WHITELIST = frozenset([
    "email", "emma", "emerald", "emily", "emile", "emm",
    "embassy", "empire", "employ", "empower",
])

# Pass 4: "te" prefix — do NOT strip if starts with
_TE_WHITELIST = frozenset([
    "team", "tech", "tel", "temp", "ten", "ter", "test", "tex",
    "ted@", "tee@",
])

# Pass 4: "me" prefix — do NOT strip if starts with
_ME_WHITELIST = frozenset([
    "mega", "mel", "mem", "men", "mer", "met", "mex",
    "media", "meet",
])

# Quality scoring constants
FREE_DOMAINS = frozenset([
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "live.com", "msn.com", "ymail.com",
])

VN_DOMAINS = frozenset([
    "gmail.com.vn", "yahoo.com.vn", "vnn.vn", "fpt.vn",
    "vietnamnet.vn", "viettel.vn", "vnpt.vn",
])

GENERIC_LOCALS = frozenset([
    "info", "sales", "contact", "admin", "support", "cs",
    "service", "hello", "mail", "office", "team", "noreply",
    "no-reply", "donotreply", "inquiries", "inquiry",
])

BAD_PATTERNS = frozenset([
    "noreply", "no-reply", "mailer-daemon", "postmaster",
    "bounce", "donotreply", "do-not-reply",
])


# ── Pass helpers ──────────────────────────────────────────────────────────────

def _pass1_split(raw: str) -> list[str]:
    """Split field containing multiple emails separated by ,/;/newline/slash."""
    parts = re.split(r"[,;\n\r/]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _pass2_strip_labels(value: str) -> str:
    """Remove common label prefixes before the email address."""
    v = value.lower().strip()
    for prefix in _LABEL_PREFIXES:
        if v.startswith(prefix):
            return value[len(prefix):].strip()
    return value.strip()


def _pass3_angle_brackets(value: str) -> str:
    """Extract email from 'Name <email@domain.com>' format."""
    m = _ANGLE_RE.search(value)
    if m:
        return m.group(1).strip()
    return value


def _pass4_panjiva_prefix(local: str) -> str:
    """
    Strip Panjiva-injected em/te/me prefixes from local part of email.

    Panjiva corrupts ~1,253 emails by inserting these 2-letter prefixes.
    We strip them ONLY when the result would still be a plausible local part,
    and the original is NOT a legitimate word starting with that prefix.
    """
    for prefix, whitelist in [("em", _EM_WHITELIST), ("te", _TE_WHITELIST), ("me", _ME_WHITELIST)]:
        if not local.startswith(prefix):
            continue
        if len(local) <= len(prefix) + 1:
            continue  # too short to strip safely

        # Check whitelist: if it starts with any whitelisted word, don't strip
        in_whitelist = False
        for word in whitelist:
            if word.endswith("@"):
                # exact match check (e.g., "ted@")
                if local == word[:-1]:
                    in_whitelist = True
                    break
            elif local.startswith(word):
                in_whitelist = True
                break

        if not in_whitelist:
            stripped = local[len(prefix):].lstrip("._-")
            if stripped and "@" not in stripped:  # stripped must be valid local part
                return stripped

    return local


def _pass5_phone_prefix(value: str) -> str:
    """Remove phone/number prefix before email: '339-1729,email@x.com' → 'email@x.com'."""
    m = _PHONE_PREFIX_RE.match(value)
    if m:
        return value[m.end():].strip()
    # Also handle 'tel:+xxx email@...' style
    if re.match(r"^tel:", value, re.IGNORECASE):
        found = _EMAIL_FIND_RE.search(value)
        if found:
            return found.group(0)
    return value


# ── Public API ────────────────────────────────────────────────────────────────

def clean_panjiva_email(raw_value) -> list[str]:
    """
    Clean a raw email cell value through all 5 pre-validation passes.

    Returns list of candidate email strings (may be multiple from split).
    Candidates are not yet validated — call validate_email() on each.

    Args:
        raw_value: Raw cell value (str, float, None, etc.)

    Returns:
        list[str]: Zero or more candidate email strings after cleaning.
    """
    if not isinstance(raw_value, str):
        return []
    raw = raw_value.strip()
    if not raw:
        return []

    # Pass 1: split multi-email fields
    parts = _pass1_split(raw)

    results = []
    for part in parts:
        # Pass 2: strip label prefixes
        part = _pass2_strip_labels(part)
        # Pass 3: extract from angle brackets
        part = _pass3_angle_brackets(part)
        # Pass 5: strip phone/number prefix (before checking @)
        part = _pass5_phone_prefix(part)

        part = part.strip().lower()
        if not part or "@" not in part:
            # Try regex extraction as last resort
            found = _EMAIL_FIND_RE.search(part)
            if found:
                part = found.group(0)
            else:
                continue

        # Pass 4: fix Panjiva prefix corruption on local part
        if "@" in part:
            local, domain = part.split("@", 1)
            local = local.lstrip("._-")
            local = _pass4_panjiva_prefix(local)
            part = f"{local}@{domain}"

        results.append(part)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for e in results:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def validate_email(email: str) -> tuple[str, int]:
    """
    Validate a cleaned email string and return (cleaned_email, quality_score).

    Quality scores:
        100 = VALID corporate email
         80 = GENERIC local part (info@, sales@) but valid domain
         50 = FREE provider (gmail, yahoo, etc.)
         30 = VN_SHIPPER (Vietnamese email domain)
          0 = INVALID (bad format, bad pattern, or empty)

    Args:
        email: Email string (should already be cleaned by clean_panjiva_email)

    Returns:
        tuple[str, int]: (normalized_email, score). Empty string + 0 if invalid.
    """
    if not isinstance(email, str) or not email.strip():
        return "", 0

    email = email.strip().lower()

    # Must match regex
    if not _EMAIL_RE.match(email):
        return "", 0

    local, domain = email.split("@", 1)

    # Reject bad patterns
    if any(bp in local for bp in BAD_PATTERNS):
        return "", 0

    # Must have valid TLD (no .local, no IP-like patterns)
    if ".local" in domain or re.match(r"^\d+\.\d+", domain):
        return "", 0

    # Score
    if domain in VN_DOMAINS:
        return email, 30
    if domain in FREE_DOMAINS:
        return email, 50
    if local in GENERIC_LOCALS:
        return email, 80
    return email, 100


def clean_and_validate(raw_value) -> list[tuple[str, int]]:
    """
    Convenience function: clean then validate in one call.

    Returns list of (email, score) tuples with score > 0 only.
    """
    candidates = clean_panjiva_email(raw_value)
    results = []
    for candidate in candidates:
        email, score = validate_email(candidate)
        if score > 0:
            results.append((email, score))
    return results
