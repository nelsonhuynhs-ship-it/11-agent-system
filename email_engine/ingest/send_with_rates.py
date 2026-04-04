# -*- coding: utf-8 -*-
"""
send-with-rates.py — Send emails with REAL rate tables via COM Outlook
======================================================================
Fetches HTML preview (with live rates) from API, sends via Outlook COM.
Outlook signature (logo, branding) is automatically appended by Outlook.

Usage:
    # Test 1 email to yourself
    python -m email_engine.ingest.send-with-rates --test nelson@pudongprime.vn

    # Dry run: show what would be sent (no actual send)
    python -m email_engine.ingest.send-with-rates --tier VIP --count 5 --dry-run

    # Send 10 VIP prospects
    python -m email_engine.ingest.send-with-rates --tier VIP --count 10

    # Send 50 across all tiers
    python -m email_engine.ingest.send-with-rates --count 50
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

_repo = str(Path(__file__).parent.parent.parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
from shared import paths as sp

log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE = "http://14.225.207.145:8100"  # VPS API (has fresh rates via rclone)
CNEE_V2 = sp.EMAIL_DATA / "cnee_master_v2.xlsx"
EMAIL_LOG = sp.EMAIL_LOG
COMPANY_PDF = sp.COMPANY_PDF
BATCH_SIZE = 50
BATCH_PAUSE = 60
DELAY_MIN = 2
DELAY_MAX = 5
MARKUP = 20  # USD default markup


# ── Fetch rate preview from API ─────────────────────────────────────────────

def fetch_preview(email: str, company: str, markup: int = MARKUP,
                  template: str = "plain") -> dict | None:
    """Call VPS API to generate HTML email with real rates."""
    payload = json.dumps({
        "email": email,
        "company": company,
        "template": template,
        "markup": markup,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_BASE}/api/email-rate/campaign/preview",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.error("API preview failed for %s: %s", email, e)
        return None


# ── COM Outlook ─────────────────────────────────────────────────────────────

def get_outlook():
    """Connect to running Outlook instance."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        _ = outlook.GetNamespace("MAPI")
        return outlook
    except Exception as e:
        log.error("Cannot connect to Outlook: %s", e)
        return None


def send_html_email(outlook, to: str, subject: str, html_body: str,
                    attach_pdf: bool = True) -> bool:
    """Send HTML email via Outlook COM. Outlook appends its own signature."""
    try:
        mail = outlook.CreateItem(0)
        mail.To = to
        mail.Subject = subject

        # Use HTMLBody — Outlook will append signature AFTER this content
        # Remove the hardcoded signature from API HTML (everything after closing </table>)
        mail.HTMLBody = html_body

        if attach_pdf and COMPANY_PDF.exists():
            mail.Attachments.Add(str(COMPANY_PDF))

        mail.Send()
        return True
    except Exception as e:
        log.error("SEND FAILED: %s | %s", to, e)
        return False


# ── Logging ─────────────────────────────────────────────────────────────────

def log_send(email: str, subject: str, campaign: str, status: str = "SENT"):
    """Append to email_log.csv."""
    EMAIL_LOG.parent.mkdir(parents=True, exist_ok=True)
    exists = EMAIL_LOG.exists()
    with open(EMAIL_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "email", "subject", "campaign_id", "status",
                         "reply_timestamp", "cycle_id"])
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        w.writerow([ts, email, subject, campaign, status, "", ""])


# ── Main ────────────────────────────────────────────────────────────────────

def run(count: int = 50, tier: str = "", dry_run: bool = False,
        test_email: str = "", markup: int = MARKUP):
    """Main send loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load cnee_master_v2
    if not CNEE_V2.exists():
        log.error("cnee_master_v2.xlsx not found at %s", CNEE_V2)
        sys.exit(1)

    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip()
    log.info("Loaded %d contacts", len(df))

    # Filter sendable
    sendable = df[df["ACTION"].isin(["SEND_NOW", "FOLLOW_UP", "PERSONALIZED"])]
    if tier:
        tiers = [t.strip().upper() for t in tier.split(",")]
        sendable = sendable[sendable["TIER"].isin(tiers)]

    # Sort: VIP first
    tier_order = {"VIP": 0, "HOT": 1, "WARM_A": 2, "WARM_B": 3, "COOL": 4}
    sendable = sendable.copy()
    sendable["_sort"] = sendable["TIER"].map(tier_order).fillna(9)
    sendable = sendable.sort_values(["_sort", "PRIORITY_SCORE"], ascending=[True, False])
    sendable = sendable.head(count)
    log.info("Queue: %d contacts (tier=%s)", len(sendable), tier or "all")

    if sendable.empty:
        log.info("No contacts to send.")
        return

    # Test mode: override all emails to test_email
    if test_email:
        log.info("TEST MODE: all emails → %s", test_email)

    # Connect Outlook
    if not dry_run:
        outlook = get_outlook()
        if not outlook:
            log.error("Start Outlook first!")
            sys.exit(1)
        log.info("Outlook connected")
    else:
        outlook = None
        log.info("DRY RUN — no emails sent")

    sent = 0
    failed = 0
    total = len(sendable)

    for i, (_, rec) in enumerate(sendable.iterrows()):
        email = rec["EMAIL"]
        company = str(rec.get("COMPANY", "")).strip()
        campaign = str(rec.get("CAMPAIGN_ID", "")).strip()

        # Fetch HTML with real rates from API
        log.info("[%d/%d] Fetching rates for %s (%s)...", i + 1, total, company[:30], email)
        preview = fetch_preview(email, company, markup=markup)

        if not preview or not preview.get("html"):
            log.warning("  No rates for %s — skipping", email)
            failed += 1
            continue

        subject = preview.get("subject", f"Vietnam freight rates // NELSON WEEK {datetime.now().isocalendar()[1]}")
        html_body = preview["html"]
        routes = preview.get("row_count", 0)

        if dry_run:
            log.info("  [DRY] %s | %d routes | %s", email, routes, subject[:60])
            sent += 1
        else:
            target = test_email if test_email else email
            ok = send_html_email(outlook, target, subject, html_body)
            if ok:
                log_send(email, subject, campaign)
                sent += 1
                log.info("  SENT → %s | %d routes", target, routes)
            else:
                log_send(email, subject, campaign, "FAILED")
                failed += 1

        # Batch pause
        if (i + 1) % BATCH_SIZE == 0 and (i + 1) < total:
            log.info("--- Batch %d done. Pausing %ds ---",
                     (i + 1) // BATCH_SIZE, BATCH_PAUSE)
            if not dry_run:
                time.sleep(BATCH_PAUSE)

        # Random delay
        if not dry_run and (i + 1) < total:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    log.info("=" * 50)
    log.info("DONE: %d sent, %d failed, %d total", sent, failed, total)
    log.info("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send emails with real rates via Outlook COM")
    parser.add_argument("--count", type=int, default=50, help="Number to send")
    parser.add_argument("--tier", type=str, default="", help="VIP,HOT,WARM_A")
    parser.add_argument("--markup", type=int, default=20, help="USD markup per container")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only")
    parser.add_argument("--test", type=str, default="", help="Send all to this email (test)")
    args = parser.parse_args()

    run(count=args.count, tier=args.tier, dry_run=args.dry_run,
        test_email=args.test, markup=args.markup)
