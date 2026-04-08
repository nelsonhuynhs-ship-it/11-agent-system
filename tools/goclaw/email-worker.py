# -*- coding: utf-8 -*-
"""
Email Worker — Bridge between VPS email queue and local Outlook COM.
Runs on PC Home, polls VPS API every 10s for pending email jobs.
Flow: Poll → Pick job → Outlook COM send → Report status back to VPS

Reuses Outlook COM helpers from email_engine/outlook_send_agent.py.
"""
import sys
import os
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime

import requests

# ── Path setup ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Reuse Outlook COM helpers — do not duplicate
from email_engine.outlook_send_agent import get_outlook, send_via_outlook  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE        = os.getenv("API_URL", "http://14.225.207.145:8100")
POLL_INTERVAL   = int(os.getenv("POLL_INTERVAL", "10"))   # seconds
RETRY_LIMIT     = int(os.getenv("RETRY_LIMIT", "3"))
NET_RETRY_WAIT  = 30  # seconds to wait when VPS is unreachable
TELEGRAM_BAT    = Path(r"C:/Users/Nelson/5398948978/send-telegram.bat")
LOG_FILE        = REPO_ROOT / "tools" / "goclaw" / "logs" / "email-worker.log"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("email-worker")


# ── Telegram ─────────────────────────────────────────────────────────────────

def notify(message: str) -> None:
    """Send summary to Nelson via Telegram (Fox Spirit)."""
    if not TELEGRAM_BAT.exists():
        log.debug("Telegram bat not found — skip notify")
        return
    try:
        subprocess.run(
            [str(TELEGRAM_BAT), "--message", message],
            timeout=30, capture_output=True,
        )
    except Exception as e:
        log.debug("Telegram notify failed (non-critical): %s", e)


# ── API helpers ───────────────────────────────────────────────────────────────

def fetch_pending() -> list[dict]:
    """GET /api/email/queue/pending — returns list of pending email jobs."""
    resp = requests.get(f"{API_BASE}/api/email/queue/pending", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs", []) if isinstance(data, dict) else data


def mark_complete(job_id: str) -> None:
    requests.post(f"{API_BASE}/api/email/queue/{job_id}/complete", timeout=10)


def mark_failed(job_id: str, error: str) -> None:
    requests.post(
        f"{API_BASE}/api/email/queue/{job_id}/fail",
        json={"error_message": error[:500]},
        timeout=10,
    )


# ── Bounce & Reply Scanner ───────────────────────────────────────────────────
BOUNCE_SCAN_DELAY = 300  # 5 min after batch — let bounces arrive
SCAN_LOG_FILE = REPO_ROOT / "tools" / "goclaw" / "logs" / "bounce-scan.jsonl"

# Patterns for classification
_BOUNCE_SUBJECTS = [
    "undeliverable", "delivery has failed", "mail delivery subsystem",
    "returned mail", "delivery status notification", "failure notice",
    "mailer-daemon", "postmaster",
]
_AUTOREPLY_SUBJECTS = [
    "out of office", "automatic reply", "auto-reply", "autoreply",
    "ooo", "vacation", "away from", "on leave", "i am currently out",
]


def _classify_email(subject: str, sender: str) -> str:
    """Classify inbox email: bounce / auto-reply / human-reply."""
    subj_lower = (subject or "").lower()
    sender_lower = (sender or "").lower()

    if any(p in subj_lower or p in sender_lower for p in _BOUNCE_SUBJECTS):
        return "bounce"
    if any(p in subj_lower for p in _AUTOREPLY_SUBJECTS):
        return "auto-reply"
    return "human-reply"


def _extract_bounced_email(body: str) -> str:
    """Try to extract the original recipient from bounce message body."""
    import re
    # Common patterns: "user@domain.com" or <user@domain.com>
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', body or "")
    return match.group(0).lower() if match else ""


def _already_logged(email: str, classification: str) -> bool:
    """Check if this email+classification combo was already logged (dedupe)."""
    if not SCAN_LOG_FILE.exists():
        return False
    import json
    try:
        with open(SCAN_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("email") == email and entry.get("type") == classification:
                    return True
    except Exception:
        pass
    return False


def _log_scan_result(email: str, classification: str, subject: str, sender: str):
    """Append scan result to JSONL log (one line per entry)."""
    import json
    SCAN_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "email": email,
        "type": classification,
        "subject": subject[:100],
        "sender": sender,
        "scanned_at": datetime.now().isoformat(),
    }
    with open(SCAN_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def scan_inbox_bounces(outlook) -> dict:
    """
    Scan Outlook Inbox for bounces and replies to our campaign emails.
    Classifies as: bounce, auto-reply, human-reply.
    Deletes bounce emails after logging. Dedupes by email+type.
    Returns summary dict.
    """
    try:
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # 6 = olFolderInbox
    except Exception as e:
        log.warning("Cannot access Inbox: %s", e)
        return {"error": str(e)}

    stats = {"bounce": 0, "auto-reply": 0, "human-reply": 0, "skipped": 0, "deleted": 0}
    to_delete = []

    # Scan last 100 emails (most recent first)
    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    count = 0
    for msg in messages:
        if count >= 100:
            break
        count += 1

        try:
            subject = str(getattr(msg, "Subject", "") or "")
            sender = str(getattr(msg, "SenderEmailAddress", "") or "")
            body = str(getattr(msg, "Body", "") or "")[:2000]

            classification = _classify_email(subject, sender)
            bounced_email = _extract_bounced_email(body) if classification == "bounce" else ""

            log_email = bounced_email or sender

            if _already_logged(log_email, classification):
                stats["skipped"] += 1
                continue

            _log_scan_result(log_email, classification, subject, sender)
            stats[classification] += 1

            # Delete bounce emails from Inbox (clean up)
            if classification == "bounce":
                to_delete.append(msg)

        except Exception as e:
            log.debug("Skip message scan: %s", e)

    # Delete bounces (reverse order to avoid index shift)
    for msg in reversed(to_delete):
        try:
            msg.Delete()
            stats["deleted"] += 1
        except Exception:
            pass

    log.info("Inbox scan: bounce=%d auto-reply=%d human-reply=%d deleted=%d skipped=%d",
             stats["bounce"], stats["auto-reply"], stats["human-reply"],
             stats["deleted"], stats["skipped"])
    return stats


# ── Core send with retry ──────────────────────────────────────────────────────

def send_with_retry(outlook, job: dict) -> tuple[bool, str]:
    """Try sending via Outlook COM up to RETRY_LIMIT times."""
    last_err = "Unknown error"
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            ok = send_via_outlook(outlook, job)
            if ok:
                return True, ""
            last_err = "send_via_outlook returned False"
        except Exception as exc:
            last_err = str(exc)
            log.warning("Attempt %d/%d failed for %s: %s", attempt, RETRY_LIMIT, job.get("id"), exc)
        if attempt < RETRY_LIMIT:
            time.sleep(2)
    return False, last_err


# ── Poll cycle ────────────────────────────────────────────────────────────────

def run_cycle(outlook) -> tuple[int, int]:
    """
    One poll cycle.
    Returns (sent_count, failed_count).
    Raises on network error so caller can handle retry delay.
    """
    jobs = fetch_pending()
    if not jobs:
        return 0, 0

    log.info("Found %d pending job(s)", len(jobs))
    sent = failed = 0

    for job in jobs:
        jid = job.get("id", "unknown")
        ok, err = send_with_retry(outlook, job)
        try:
            if ok:
                mark_complete(jid)
                sent += 1
            else:
                mark_failed(jid, err)
                failed += 1
        except Exception as e:
            log.warning("Could not report status for job %s: %s", jid, e)

    return sent, failed


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 55)
    log.info("Email Worker started — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("VPS API: %s | Poll: %ds | Retry: %dx", API_BASE, POLL_INTERVAL, RETRY_LIMIT)
    log.info("=" * 55)

    outlook = get_outlook()
    if not outlook:
        log.error("Outlook not reachable — open Outlook first, then restart worker.")
        sys.exit(1)
    log.info("Outlook COM: connected")

    consecutive_net_errors = 0
    session_sent = session_failed = 0

    try:
        while True:
            try:
                sent, failed = run_cycle(outlook)
                consecutive_net_errors = 0

                if sent or failed:
                    session_sent += sent
                    session_failed += failed
                    log.info("Cycle done: sent=%d failed=%d | total sent=%d", sent, failed, session_sent)
                    summary = (
                        f"[Email Worker] Batch done: {sent} sent, {failed} failed "
                        f"(session total: {session_sent})"
                    )
                    notify(summary)

                # After sending, check if queue is now empty → trigger bounce scan
                try:
                    remaining = fetch_pending()
                except Exception:
                    remaining = []

                if sent > 0 and not remaining:
                    log.info("Queue empty — waiting %ds then scanning inbox for bounces...", BOUNCE_SCAN_DELAY)
                    time.sleep(BOUNCE_SCAN_DELAY)
                    scan_stats = scan_inbox_bounces(outlook)
                    scan_msg = (
                        f"[Bounce Scan] bounce={scan_stats.get('bounce',0)} "
                        f"auto-reply={scan_stats.get('auto-reply',0)} "
                        f"human-reply={scan_stats.get('human-reply',0)}"
                    )
                    notify(scan_msg)

            except requests.exceptions.ConnectionError:
                consecutive_net_errors += 1
                log.warning("VPS unreachable (attempt %d) — retrying in %ds", consecutive_net_errors, NET_RETRY_WAIT)
                time.sleep(NET_RETRY_WAIT)
                continue
            except requests.exceptions.HTTPError as e:
                log.warning("API HTTP error: %s — retrying in %ds", e, NET_RETRY_WAIT)
                time.sleep(NET_RETRY_WAIT)
                continue
            except Exception as e:
                log.error("Unexpected error in cycle: %s", e)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log.info("Email Worker stopped by user (Ctrl+C)")
        log.info("Session total: sent=%d failed=%d", session_sent, session_failed)
        if session_sent or session_failed:
            notify(f"[Email Worker] Stopped. Session: {session_sent} sent, {session_failed} failed.")


if __name__ == "__main__":
    main()
