"""
email_engine.scanner.classifier
===============================
Rule-based 4+1 class classifier for Outlook Inbox items.

Labels:
    BOUNCE        - postmaster / DSN
    AUTO_REPLY    - OOO / vacation
    UNSUBSCRIBE   - explicit opt-out
    REAL_REPLY    - sender exists in cnee_master_v2
    IRRELEVANT    - anything else (noise/spam/not-a-CNEE)

Entry points:
    classify(item)                 -> str label
    load_patterns(yaml_path=None)  -> dict (also caches in module)

`item` is duck-typed: anything with
    .SenderEmailAddress (str), .Subject (str), .Body (str)
works -- real Outlook MailItem, a test dict-wrapper, or a SimpleNamespace.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Config paths
# -------------------------------------------------------------------
_PKG_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_YAML = _PKG_ROOT / "config" / "scanner.yaml"
try:
    from shared.paths import SCANNER_CFG as _SCANNER_CFG
    DEFAULT_YAML = _SCANNER_CFG if _SCANNER_CFG.exists() else _LOCAL_YAML
except Exception:
    DEFAULT_YAML = _LOCAL_YAML

# Module-level pattern cache. `load_patterns()` fills this.
_PATTERNS: dict | None = None


# Fallback minimal patterns — used ONLY if yaml fails to load.
_FALLBACK_PATTERNS: dict = {
    "bounce": {
        "postmaster_patterns": ["postmaster@", "mailer-daemon@"],
        "subject_patterns": [
            "delivery status notification",
            "undelivered mail",
            "mail delivery failed",
            "undeliverable",
        ],
    },
    "auto_reply": {
        "subject_patterns": [
            "out of office",
            "automatic reply",
            "i am on vacation",
            "currently out of",
        ],
    },
    "unsubscribe": {
        "patterns": [
            "unsubscribe",
            "stop email",
            "remove me",
            "do not email",
            "không nhận email",
        ],
    },
    "scan": {"window_minutes": 35, "max_items": 200, "processed_category": "Nelson-Scanned"},
    "bounce_regex": [
        r'(?:could not be delivered|undelivered|failed).*?([\w\.\-]+@[\w\.\-]+)',
        r'Final-Recipient:\s*rfc822;\s*([\w\.\-]+@[\w\.\-]+)',
    ],
    "telegram": {"batch_window_seconds": 300, "rate_limit_per_minute": 20},
}


def load_patterns(yaml_path: str | Path | None = None) -> dict:
    """Load patterns from YAML. Cached on module. Returns dict.

    Safe to call from tests with a synthetic yaml; pass None to use default.
    """
    global _PATTERNS

    path = Path(yaml_path) if yaml_path else DEFAULT_YAML
    if _PATTERNS is not None and yaml_path is None:
        return _PATTERNS

    try:
        import yaml  # pyyaml in requirements
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        # Merge with fallback so missing keys never crash.
        merged = {**_FALLBACK_PATTERNS, **data}
        if yaml_path is None:
            _PATTERNS = merged
        return merged
    except FileNotFoundError:
        log.warning("scanner.yaml not found at %s — using fallback patterns", path)
    except Exception as exc:  # pragma: no cover -- malformed yaml
        log.warning("Failed to load scanner.yaml (%s) — using fallback", exc)

    _PATTERNS = _FALLBACK_PATTERNS
    return _FALLBACK_PATTERNS


# -------------------------------------------------------------------
# CNEE master lookup (lazy)
# -------------------------------------------------------------------
# 2026-04-24: updated paths from v2 → v7. Root cause of "scanner missed
# real reply": scanner loaded stale v2 master (22,230 rows) but Nelson's
# active pool is v7 (22,854 rows). New CNEE sent yesterday wasn't in v2 →
# classifier returned IRRELEVANT → replies_new=0.
_CNEE_CACHE: set[str] | None = None
_CNEE_PATHS = [
    # OneDrive v7 (authoritative 2026-04-23+)
    Path(r"D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx"),
    # v5 fallback
    Path(r"D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx"),
    Path(r"D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx"),
    # Repo fallback
    _PKG_ROOT / "data" / "contact_unified_v7.xlsx",
    _PKG_ROOT / "data" / "cnee_master_v2.xlsx",
    _PKG_ROOT / "data" / "cnee_master.xlsx",
]


def _load_cnee_emails() -> set[str]:
    """Return lowercase set of emails from v7 master (or v5 fallback). Cached.

    Best-effort: if no file, returns empty set and REAL_REPLY will be IRRELEVANT.
    """
    global _CNEE_CACHE
    if _CNEE_CACHE is not None:
        return _CNEE_CACHE

    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        log.warning("pandas missing — REAL_REPLY detection disabled")
        _CNEE_CACHE = set()
        return _CNEE_CACHE

    for path in _CNEE_PATHS:
        if not path.exists():
            continue
        try:
            # v7 has multi-sheet (CNEE + SHIPPER) — read both when possible
            emails: set[str] = set()
            try:
                xls = pd.ExcelFile(path)
                sheet_names = xls.sheet_names
            except Exception:
                sheet_names = [0]
            for sheet in sheet_names:
                try:
                    df = pd.read_excel(path, sheet_name=sheet)
                    df.columns = df.columns.str.strip().str.upper()
                    for col in ("EMAIL", "CNEE_EMAIL", "SHIPPER_EMAIL", "CONTACT_EMAIL"):
                        if col in df.columns:
                            s = df[col].dropna().astype(str).str.lower().str.strip()
                            emails.update(e for e in s if "@" in e)
                except Exception as exc:
                    log.debug("skip sheet %s in %s: %s", sheet, path.name, exc)
            if emails:
                _CNEE_CACHE = emails
                log.info("Loaded %d CNEE emails from %s", len(emails), path.name)
                return _CNEE_CACHE
        except Exception as exc:
            log.warning("Could not read %s: %s", path, exc)

    _CNEE_CACHE = set()
    return _CNEE_CACHE


def reset_cnee_cache() -> None:
    """Tests call this to force reload."""
    global _CNEE_CACHE
    _CNEE_CACHE = None


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _safe_str(obj: Any, attr: str) -> str:
    try:
        v = getattr(obj, attr, "") or ""
        return str(v)
    except Exception:
        return ""


def _sender(item: Any) -> str:
    for attr in ("SenderEmailAddress", "sender", "from_address"):
        v = _safe_str(item, attr)
        if v:
            return v.lower().strip()
    return ""


# -------------------------------------------------------------------
# Main API
# -------------------------------------------------------------------
def classify(item: Any, patterns: dict | None = None, cnee_emails: set[str] | None = None) -> str:
    """Return one of: BOUNCE | AUTO_REPLY | REAL_REPLY | UNSUBSCRIBE | IRRELEVANT.

    Parameters
    ----------
    item        : object exposing SenderEmailAddress/Subject/Body
    patterns    : pattern dict (defaults to load_patterns())
    cnee_emails : pre-computed cnee set (defaults to _load_cnee_emails())
    """
    p = patterns or load_patterns()

    # 0) SHORT-CIRCUIT: Microsoft ReportItem (olReport, Class 46) = ALWAYS NDR
    # Exchange delivers bounces as ReportItem, not MailItem. Subject always
    # starts with "Undeliverable:". No sender, no ReceivedTime — so classifier
    # must recognize by Class alone.
    msg_class = getattr(item, "Class", None)
    if msg_class == 46:
        return "BOUNCE"

    sender = _sender(item)
    subject = _safe_str(item, "Subject").lower()
    body = _safe_str(item, "Body")
    body_lower = body[:2000].lower()  # cap for perf on huge DSNs

    # 1) BOUNCE — postmaster sender or DSN subject
    bounce_cfg = p.get("bounce", {})
    for pm in bounce_cfg.get("postmaster_patterns", []):
        if pm.lower() in sender:
            return "BOUNCE"
    for sp in bounce_cfg.get("subject_patterns", []):
        if sp.lower() in subject:
            return "BOUNCE"

    # 2) UNSUBSCRIBE — explicit opt-out wins over auto-reply (they sometimes co-occur)
    unsub_cfg = p.get("unsubscribe", {})
    for kw in unsub_cfg.get("patterns", []):
        kwl = kw.lower()
        if kwl in subject or kwl in body_lower:
            return "UNSUBSCRIBE"

    # 3) AUTO_REPLY — subject patterns OR carrier sender domains
    # 2026-04-24: sender_domains covers YML/Maersk/MSC etc tracking bots.
    # Nelson subscribes to carrier tracking → daily reports flood inbox.
    # Not real CNEE replies, should classify as AUTO_REPLY (no Telegram ping).
    auto_cfg = p.get("auto_reply", {})
    for sp in auto_cfg.get("subject_patterns", []):
        if sp.lower() in subject:
            return "AUTO_REPLY"
    for dom in auto_cfg.get("sender_domains", []):
        if sender.endswith("@" + dom.lower()):
            return "AUTO_REPLY"

    # 4) REAL_REPLY — sender is a known CNEE
    known = cnee_emails if cnee_emails is not None else _load_cnee_emails()
    if sender and sender in known:
        return "REAL_REPLY"

    # 5) fallthrough
    return "IRRELEVANT"


def classify_bounce_severity(body: str, patterns: dict | None = None) -> str:
    """Given an NDR body, return 'HARD' or 'SOFT'. Default HARD to be safe."""
    p = patterns or load_patterns()
    body_lower = body.lower()
    for kw in p.get("bounce", {}).get("soft_keywords", []):
        if kw.lower() in body_lower:
            return "SOFT"
    for kw in p.get("bounce", {}).get("hard_keywords", []):
        if kw.lower() in body_lower:
            return "HARD"
    return "HARD"
