# -*- coding: utf-8 -*-
"""
outlook_send_agent.py — Local Outlook COM Send Agent
=====================================================
Polls API queue → Sends via Outlook COM → Reports back status.

Run on PC Home (must have Outlook open):
    python email_engine/outlook_send_agent.py

Auto-start with Windows:
    Add shortcut to shell:startup pointing to run_outlook_agent.bat
"""
import time
import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

import requests

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_URL", "http://14.225.207.145:8100")
POLL_INTERVAL = 5  # seconds
COMPANY_PDF = Path(__file__).parent / "assets" / "PUDONG PRIME PROFILE.pdf"
LOG_FILE = Path(__file__).parent / "logs" / "outlook_agent.log"

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
log = logging.getLogger("outlook_agent")


def get_outlook():
    """Get Outlook COM object. Outlook must be running."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        # Test connection
        _ = outlook.GetNamespace("MAPI")
        return outlook
    except Exception as e:
        log.error("Cannot connect to Outlook: %s", e)
        log.error("Make sure Outlook is open!")
        return None


def send_via_outlook(outlook, email_data: dict) -> bool:
    """Send a single email via Outlook COM."""
    try:
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = email_data["to"]
        if email_data.get("cc"):
            mail.CC = "; ".join(email_data["cc"])
        mail.Subject = email_data["subject"]
        mail.HTMLBody = email_data["html_body"]

        # Attach company PDF
        if email_data.get("attach_pdf", True) and COMPANY_PDF.exists():
            mail.Attachments.Add(str(COMPANY_PDF))

        mail.Send()
        log.info("SENT: %s | %s", email_data["to"], email_data["subject"][:50])
        return True
    except Exception as e:
        log.error("SEND FAILED: %s | %s", email_data["to"], e)
        return False


def poll_and_send():
    """One poll cycle: fetch pending → send → report."""
    try:
        resp = requests.get(f"{API_BASE}/api/email-rate/queue/pending", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("API poll failed: %s", e)
        return 0

    pending = data.get("emails", [])
    if not pending:
        return 0

    log.info("Found %d pending email(s)", len(pending))
    outlook = get_outlook()
    if not outlook:
        log.error("Outlook not available — skipping this cycle")
        return 0

    sent_count = 0
    for email in pending:
        eid = email["id"]
        success = send_via_outlook(outlook, email)

        try:
            if success:
                requests.post(f"{API_BASE}/api/email-rate/queue/mark-sent/{eid}", timeout=10)
                sent_count += 1
            else:
                requests.post(
                    f"{API_BASE}/api/email-rate/queue/mark-failed/{eid}",
                    params={"error": "Outlook COM send failed"},
                    timeout=10,
                )
        except Exception as e:
            log.warning("Failed to report status for %s: %s", eid, e)

    return sent_count


def main():
    log.info("=" * 50)
    log.info("Outlook Send Agent started")
    log.info("API: %s", API_BASE)
    log.info("Poll interval: %ds", POLL_INTERVAL)
    log.info("Company PDF: %s (%s)", COMPANY_PDF, "OK" if COMPANY_PDF.exists() else "MISSING")
    log.info("=" * 50)

    # Check Outlook on startup
    outlook = get_outlook()
    if outlook:
        log.info("Outlook connection: OK")
    else:
        log.error("Outlook connection: FAILED — start Outlook first!")
        sys.exit(1)

    # Main loop
    while True:
        try:
            sent = poll_and_send()
            if sent > 0:
                log.info("Cycle complete: %d email(s) sent", sent)
        except KeyboardInterrupt:
            log.info("Agent stopped by user")
            break
        except Exception as e:
            log.error("Unexpected error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
