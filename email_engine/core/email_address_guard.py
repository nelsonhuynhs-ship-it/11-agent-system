#!/usr/bin/env python3
"""
Phase 2: EmailAddressGuard — pre-send validation and prefix shield.
Blocks bad recipients BEFORE Outlook COM gets them.

Usage:
    from email_engine.core.email_address_guard import EmailAddressGuard, guard_email

Result model — EmailGuardResult:
    input: str
    normalized: str
    is_sendable: bool
    reason_code: str
    severity: str
    suggested_fix: str | None
    evidence: list[str]
"""
from __future__ import annotations

import email
import logging
import re
from pathlib import Path
from typing import TypedDict

log = logging.getLogger(__name__)

# ---------- config loader ----------
_CONFIG: dict | None = None

def _load_config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        import yaml
        path = Path(__file__).parent.parent / "config" / "email_address_guard.yaml"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _CONFIG = yaml.safe_load(f)
        else:
            _CONFIG = {}
    return _CONFIG


class EmailGuardResult(TypedDict):
    input: str
    normalized: str
    is_sendable: bool
    reason_code: str
    severity: str
    suggested_fix: str | None
    evidence: list[str]


class EmailAddressGuard:
    """Pre-send email validator with prefix shield and typo integration."""

    def __init__(self):
        cfg = _load_config()
        self._prefix_role: list[str] = cfg.get("BAD_PREFIX_CLASSES", {}).get("BAD_PREFIX_ROLE", [
            "info@", "noreply@", "no-reply@", "unknown@", "test@", "admin@", "fax@", "tel@",
        ])
        self._prefix_corrupt: list[str] = cfg.get("BAD_PREFIX_CLASSES", {}).get("BAD_PREFIX_CORRUPT", [
            "em@", "te@", "me@", "xx@", "yy@", "zz@",
        ])
        self._prefix_stripped: list[str] = cfg.get("BAD_PREFIX_CLASSES", {}).get("BAD_PREFIX_STRIPPED", [])
        self._reason_codes: dict = cfg.get("REASON_CODES", {})
        self._quarantine_first: bool = cfg.get("QUARANTINE_FIRST", True)
        self._typo_min_score: int = cfg.get("TYPO_MIN_SCORE", 85)

    # ---- public API ----

    def guard(self, raw_email: str) -> EmailGuardResult:
        """Run all checks on a single email. Returns EmailGuardResult."""
        original = (raw_email or "").strip()
        normalized = self._normalize(original)
        reasons: list[str] = []
        severity = "info"
        suggested_fix: str | None = None
        evidence: list[str] = []

        # Step 1: format check
        fmt_result = self._check_format(normalized)
        if not fmt_result["ok"]:
            return EmailGuardResult(
                input=original,
                normalized=normalized,
                is_sendable=False,
                reason_code="INVALID_FORMAT",
                severity="error",
                suggested_fix=None,
                evidence=fmt_result["evidence"],
            )

        # Step 2: prefix checks
        prefix_result = self._check_prefix(normalized)
        if prefix_result["blocked"]:
            return EmailGuardResult(
                input=original,
                normalized=normalized,
                is_sendable=False,
                reason_code=prefix_result["reason_code"],
                severity=prefix_result["severity"],
                suggested_fix=None,
                evidence=prefix_result["evidence"],
            )

        # Step 3: typo check (via typo_shield if available)
        typo_result = self._check_typo(normalized)
        if typo_result["blocked"]:
            return EmailGuardResult(
                input=original,
                normalized=normalized,
                is_sendable=False,
                reason_code="TYPO_SUSPECT",
                severity="warning",
                suggested_fix=typo_result["suggested_fix"],
                evidence=typo_result["evidence"],
            )

        return EmailGuardResult(
            input=original,
            normalized=normalized,
            is_sendable=True,
            reason_code="OK",
            severity="info",
            suggested_fix=None,
            evidence=[],
        )

    def bulk_guard(self, emails: list[str]) -> dict:
        """Run guard on a list of emails. Returns summary + quarantined list."""
        results: list[EmailGuardResult] = []
        quarantined: list[EmailGuardResult] = []
        sendable_count = 0

        for email_addr in emails:
            result = self.guard(email_addr)
            results.append(result)
            if result["is_sendable"]:
                sendable_count += 1
            else:
                quarantined.append(result)

        blocked_by_reason: dict[str, int] = {}
        for r in quarantined:
            rc = r["reason_code"]
            blocked_by_reason[rc] = blocked_by_reason.get(rc, 0) + 1

        return {
            "results": results,
            "sendable_count": sendable_count,
            "quarantine_count": len(quarantined),
            "blocked_by_reason": blocked_by_reason,
            "needs_manual_review": [
                r for r in quarantined if r["severity"] in ("warning", "info")
            ],
        }

    # ---- internal helpers ----

    def _normalize(self, raw: str) -> str:
        """Lowercase, strip, IDNA-encode domain."""
        raw = raw.strip().lower()
        try:
            parts = raw.split("@")
            if len(parts) == 2:
                import idna
                domain = idna.encode(parts[1]).decode("ascii")
                raw = f"{parts[0]}@{domain}"
        except Exception:
            pass
        return raw

    def _check_format(self, email_addr: str) -> dict:
        """Structural validation. Returns {'ok': bool, 'evidence': list}."""
        evidence: list[str] = []
        try:
            # parseaddr returns (realname, addr) or ('', email_addr)
            parsed = email.utils.parseaddr(email_addr)
            if not parsed[1]:
                evidence.append("empty after parse")
                return {"ok": False, "evidence": evidence}

            # Must have exactly one @
            if email_addr.count("@") != 1:
                evidence.append(f"@ count={email_addr.count('@')}")
                return {"ok": False, "evidence": evidence}

            local, domain = email_addr.split("@")

            if not local or not domain:
                evidence.append("empty local or domain")
                return {"ok": False, "evidence": evidence}

            if " " in local or " " in domain:
                evidence.append("space in local or domain")
                return {"ok": False, "evidence": evidence}

            if "." not in domain or domain.startswith(".") or domain.endswith("."):
                evidence.append(f"domain malformed: {domain}")
                return {"ok": False, "evidence": evidence}

            if ".." in domain:
                evidence.append("consecutive dots in domain")
                return {"ok": False, "evidence": evidence}

            return {"ok": True, "evidence": []}
        except Exception as exc:
            evidence.append(f"parse exception: {exc}")
            return {"ok": False, "evidence": evidence}

    def _check_prefix(self, email_addr: str) -> dict:
        """Check for role/no-reply/corrupt prefixes. Returns blocked dict."""
        if "@" not in email_addr:
            return {"blocked": False}

        local = email_addr.split("@")[0].lower()

        for prefix in self._prefix_role:
            p = prefix.lower().rstrip("@")
            if local == p or local.startswith(p):
                return {
                    "blocked": True,
                    "reason_code": "ROLE_OR_NO_REPLY",
                    "severity": "warning",
                    "evidence": [f"role prefix matched: {prefix}"],
                }

        for prefix in self._prefix_corrupt:
            p = prefix.lower().rstrip("@").rstrip("_")
            if local == p or local.startswith(prefix.lower()):
                return {
                    "blocked": True,
                    "reason_code": "BAD_PREFIX",
                    "severity": "error",
                    "evidence": [f"corrupt prefix suspected: {prefix}"],
                }

        for prefix in self._prefix_stripped:
            if local.startswith(prefix.lower()):
                return {
                    "blocked": True,
                    "reason_code": "BAD_PREFIX",
                    "severity": "warning",
                    "evidence": [f"stripped prefix: {prefix}"],
                }

        return {"blocked": False}

    def _check_typo(self, email_addr: str) -> dict:
        """Run typo_shield if available. Returns {'blocked': bool, 'suggested_fix': str, 'evidence': list}."""
        try:
            from email_engine.core.typo_shield import check_typo
        except ImportError:
            return {"blocked": False, "suggested_fix": None, "evidence": []}

        result = check_typo(email_addr)
        if result.action in ("BLOCK", "HOLD") and result.suggested_fix:
            return {
                "blocked": True,
                "suggested_fix": result.suggested_fix,
                "evidence": [f"typo score={result.confidence:.0f} suggested={result.suggested_domain}"],
            }
        return {"blocked": False, "suggested_fix": None, "evidence": []}


# ---------- module-level convenience ----------
_guard: EmailAddressGuard | None = None

def guard_email(raw_email: str) -> EmailGuardResult:
    global _guard
    if _guard is None:
        _guard = EmailAddressGuard()
    return _guard.guard(raw_email)