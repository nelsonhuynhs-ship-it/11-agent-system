"""
bounce_handler.py — RFC 3464 DSN Parser + Bounce Knowledge Base
================================================================
Schema: bounce_kb.db
    bounces(id, email, status_code, action, reason, bounce_class,
            source, received_at, created_at)
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from email.policy import default as email_policy
from pathlib import Path
from typing import Optional

log = logging.getLogger("bounce_handler")

# ── Paths ──────────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent / "data"
_BOUNCE_DB = _DATA_DIR / "bounce_kb.db"
_LOG_DIR = Path(__file__).parent.parent / "logs"

# ── Email regex ─────────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")

# ── NDR subject keywords (fallback) ──────────────────────────────────────────────
NDR_SUBJECTS = [
    "undeliverable", "delivery status notification", "mail delivery failed",
    "returned mail", "failure notice", "delivery failure", "not found",
]

# ── Hard/soft keyword heuristics (last-resort fallback) ───────────────────────────
HARD_KEYWORDS = [
    "does not exist", "unknown user", "invalid address", "no such user",
    "rejected", "user unknown", "address rejected", "not found",
    "invalid recipient", "mailbox not found", "destination host",
]
SOFT_KEYWORDS = [
    "mailbox full", "temporarily unavailable", "try again later",
    "quota exceeded", "over quota", "service unavailable",
    "too many connections", "connection refused", "timeout",
    "deferred", "delay", "greylisted",
]

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_BOUNCE_DB), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create bounce_kb.db schema if not exists."""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bounces (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT NOT NULL,
            status_code     TEXT,
            action          TEXT,
            reason          TEXT,
            bounce_class    TEXT,
            source          TEXT NOT NULL DEFAULT 'dsn_auto',
            received_at     TEXT,
            created_at      TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bounces_email ON bounces(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bounces_class ON bounces(bounce_class)")
    conn.commit()
    conn.close()
    log.info("bounce_kb.db initialized")


# ─────────────────────────────────────────────────────────────────────────────
# RFC 3464 DSN Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _classify(status: str) -> str:
    """5.x.x=hard, 4.x.x=soft, 2.x.x=delivered, else=unknown."""
    if not status:
        return "unknown"
    first = status.split(".")[0]
    return {"5": "hard", "4": "soft", "2": "delivered"}.get(first, "unknown")


def _extract_multipart_boundary(body: str) -> Optional[str]:
    """Extract boundary from Content-Type header found in body."""
    m = re.search(r'boundary=["\']?([^"\'\s]+)["\']?', body, re.I)
    if m:
        return m.group(1)
    return None


def _split_multipart(body: str, boundary: str) -> list[tuple[str, str]]:
    """Split multipart body into [(content_type, content)] parts."""
    parts = []
    # MIME boundary format: --boundary or --boundary--
    pattern = re.compile(
        r"--" + re.escape(boundary) + r"(?:--)?\s*\r?\n",
        re.MULTILINE,
    )
    segments = pattern.split(body)
    for seg in segments:
        if not seg.strip():
            continue
        # Each segment: headers\n\nbody
        header_end = seg.find("\n\n")
        if header_end == -1:
            header_end = seg.find("\r\n\r\n")
        if header_end == -1:
            continue
        headers = seg[:header_end]
        content = seg[header_end + 2 :].strip()

        # Extract Content-Type
        ct_match = re.search(r"Content-Type:\s*([^;\s]+)", headers, re.I)
        ct = ct_match.group(1).strip() if ct_match else "text/plain"
        parts.append((ct, content))
    return parts


def _extract_dsn_fields(content: str) -> dict:
    """Parse a message/delivery-status block into per-recipient dict."""
    rec: dict = {}
    # Split on blank lines (parper RFC 3464 record separation)
    for line in content.splitlines():
        line = line.rstrip()
        if line.startswith("Final-Recipient:"):
            # Format: Final-Recipient: rfc822; user@domain.com
            parts = line.split(";", 1)
            if len(parts) == 2:
                rec["email"] = parts[1].strip().lower()
        elif line.startswith("Action:"):
            rec["action"] = line.split(":", 1)[1].strip()
        elif line.startswith("Status:"):
            rec["status_code"] = line.split(":", 1)[1].strip()
        elif line.startswith("Diagnostic-Code:"):
            # Format: Diagnostic-Code: smtp; 550 5.1.1 User unknown
            parts = line.split(";", 1)
            if len(parts) == 2:
                rec["reason"] = parts[1].strip()
    return rec


def _parse_multipart_dsn(body: str) -> list[dict]:
    """Parse RFC 3464 multipart/report message body. Returns list of bounce records."""
    bounces = []

    boundary = _extract_multipart_boundary(body)
    if not boundary:
        log.debug("No boundary found in multipart body")
        return []

    parts = _split_multipart(body, boundary)

    delivery_status_parts = [
        (ct, c) for ct, c in parts if ct.lower() == "message/delivery-status"
    ]

    for _ct, dsn_content in delivery_status_parts:
        # Each delivery-status block may contain multiple recipient blocks
        # separated by blank lines
        raw_blocks = re.split(r"\n\s*\n", dsn_content)
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue
            rec = _extract_dsn_fields(block)
            if not rec.get("email"):
                continue
            status = rec.get("status_code", "")
            rec["bounce_class"] = _classify(status)
            bounces.append(rec)

    return bounces


def _fallback_subject_parse(msg: dict) -> list[dict]:
    """Fallback: extract email from subject + body when DSN is not multipart/report."""
    bounces = []
    subject = msg.get("subject", "") or ""
    body = msg.get("body", {}).get("content", "") or ""

    # Try to find failed email
    failed_email: Optional[str] = None

    # Pattern 1: Final-Recipient in body
    m = re.search(r"Final-Recipient[:\s]+rfc822;\s*([^\s]+)", body, re.I)
    if m:
        failed_email = m.group(1).strip().lower()

    # Pattern 2: "to <email>" in subject/body
    if not failed_email:
        m = re.search(r"(?:to|for|recipient)[:\s]+([^\s<>]+@[^\s<>]+)", body, re.I)
        if m:
            failed_email = m.group(1).strip().lower()

    # Pattern 3: any email in body not daemon/postmaster
    if not failed_email:
        candidates = EMAIL_RE.findall(body)
        for c in candidates:
            c = c.lower()
            if not any(s in c for s in ["mailer-daemon", "postmaster", "noreply"]):
                failed_email = c
                break

    if not failed_email:
        log.debug("fallback_subject_parse: no email found in %s", subject[:60])
        return []

    # Determine bounce class from subject/body
    combined = (subject + " " + body).lower()
    bounce_class = "hard"  # default to hard for safety

    for kw in SOFT_KEYWORDS:
        if kw in combined:
            bounce_class = "soft"
            break

    # Override with hard keywords
    for kw in HARD_KEYWORDS:
        if kw in combined:
            bounce_class = "hard"
            break

    # If bounce class is still unknown but subject suggests NDR → treat as hard
    if bounce_class == "unknown":
        if any(kw in subject.lower() for kw in NDR_SUBJECTS):
            bounce_class = "hard"

    bounces.append({
        "email": failed_email,
        "status_code": "",
        "action": "failed",
        "reason": f"fallback parse | subject: {subject[:100]}",
        "bounce_class": bounce_class,
    })
    return bounces


def parse_dsn_from_outlook_item(item) -> list[dict]:
    """Parse DSN/NDR from Outlook MailItem. Returns list of bounce records."""
    body = getattr(item, 'Body', '') or getattr(item, 'htmlBody', '') or ''
    subject = getattr(item, 'Subject', '') or ''
    received_at = getattr(item, 'ReceivedTime', '') or ''

    if "message/delivery-status" in body:
        bounces = _parse_multipart_dsn(body)
        if bounces:
            for b in bounces:
                b["received_at"] = received_at
            return bounces

    msg = {"subject": subject, "body": {"content": body}}
    bounces = _fallback_subject_parse(msg)
    for b in bounces:
        b["received_at"] = received_at
    return bounces


# ─────────────────────────────────────────────────────────────────────────────
# Auto-suppression
# ─────────────────────────────────────────────────────────────────────────────

def _add_to_suppression_list(email: str, reason: str, source: str = "dsn_auto") -> None:
    """Add hard-bounced email to suppression list via bounce_knowledge."""
    try:
        from email_engine.core.bounce_knowledge import learn_from_bounce
        learn_from_bounce(email, "HARD", reason)
        log.info("Auto-suppressed %s after hard bounce", email)
    except Exception as exc:
        log.warning("learn_from_bounce failed for %s: %s", email, exc)


def _get_soft_count(email: str) -> int:
    """Return count of soft bounces for this email."""
    conn = _get_db()
    row = conn.execute(
        "SELECT COUNT(*) FROM bounces WHERE email=? AND bounce_class='soft'",
        (email.lower(),),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def _insert_bounce(b: dict, source: str = "dsn_auto") -> None:
    """Insert a single bounce record into bounce_kb.db."""
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO bounces (email, status_code, action, reason, bounce_class,
                             source, received_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            b.get("email", "").lower(),
            b.get("status_code", ""),
            b.get("action", ""),
            b.get("reason", ""),
            b.get("bounce_class", "unknown"),
            source,
            b.get("received_at", ""),
            now,
        ),
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def handle_bounce(item) -> dict:
    """Process an NDR message: parse DSN, save to KB, auto-suppress.

    Args:
        item: Outlook MailItem object

    Returns:
        dict with keys: processed (int), bounced_emails (list),
                        hard_bounces (int), soft_bounces (int)
    """
    # Ensure schema exists
    init_db()

    bounces = parse_dsn_from_outlook_item(item)
    if not bounces:
        subject = getattr(item, 'Subject', '') or "?"
        log.debug("handle_bounce: no bounces parsed from item %s", subject[:60])
        return {"processed": 0, "bounced_emails": [], "hard_bounces": 0, "soft_bounces": 0}

    hard_count = 0
    soft_count = 0
    processed_emails = []

    for b in bounces:
        email = b.get("email", "")
        if not email:
            continue

        # 1. Save to bounce_kb.db
        _insert_bounce(b)

        # 2. Auto-suppression logic
        bounce_class = b.get("bounce_class", "unknown")
        reason = b.get("reason", "no diag")

        if bounce_class == "hard":
            _add_to_suppression_list(email, f"hard_bounce: {reason}")
            hard_count += 1
        elif bounce_class == "soft":
            soft_count += 1
            count = _get_soft_count(email)
            if count >= 3:
                _add_to_suppression_list(
                    email, f"3 soft bounces (last: {reason})"
                )
                log.info("Auto-suppressed %s after 3 soft bounces", email)
            else:
                log.info(
                    "Soft bounce %s for %s (count=%d, suppress at 3)",
                    b.get("status_code", ""), email, count,
                )

        processed_emails.append(email)

    log.info(
        "handle_bounce: %d email(s) processed — hard=%d soft=%d",
        len(processed_emails), hard_count, soft_count,
    )

    return {
        "processed": len(processed_emails),
        "bounced_emails": processed_emails,
        "hard_bounces": hard_count,
        "soft_bounces": soft_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Outlook COM Scanner
# ─────────────────────────────────────────────────────────────────────────────

def scan_bounces() -> list[dict]:
    """Scan Outlook Inbox for NDR/bounce emails. Returns list of bounce records."""
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)  # olFolderInbox = 6
    items = inbox.Items
    results = []
    for item in items:
        subject = getattr(item, 'Subject', '') or ''
        if not any(kw in subject.lower() for kw in NDR_SUBJECTS):
            continue
        bounces = parse_dsn_from_outlook_item(item)
        for b in bounces:
            results.append(b)
    return results


def update_cnee_master(bounces: list[dict]) -> dict:
    """DEPRECATED — kept for backwards compatibility.

    Old update_cnee_master() wrote to cnee_master_v2.xlsx.
    Now a no-op stub. Bounce KB is now the source of truth.
    """
    log.warning("update_cnee_master() is deprecated — bounce KB is now source of truth")
    return {"updated": 0, "hard": 0, "soft": 0, "error": "deprecated"}


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("bounce_kb.db ready at", _BOUNCE_DB)
