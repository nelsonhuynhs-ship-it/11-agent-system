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
    return data.get("emails", data) if isinstance(data, dict) else data


def mark_complete(job_id: str) -> None:
    requests.post(f"{API_BASE}/api/email/queue/{job_id}/complete", timeout=10)


def mark_failed(job_id: str, error: str) -> None:
    requests.post(
        f"{API_BASE}/api/email/queue/{job_id}/fail",
        json={"error": error[:500]},
        timeout=10,
    )


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
