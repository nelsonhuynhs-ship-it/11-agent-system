# -*- coding: utf-8 -*-
"""
batch_send_outlook.py — Batch Email Sender via COM Outlook
==========================================================
Sends cold emails from cnee_master_v2.xlsx via Outlook COM.
Outlook MUST be open on the machine.

Usage:
    python -m email_engine.ingest.batch_send_outlook --count 50 --dry-run
    python -m email_engine.ingest.batch_send_outlook --count 500
    python -m email_engine.ingest.batch_send_outlook --tier VIP --count 10

Features:
  - Reads SEND_NOW / FOLLOW_UP / PERSONALIZED contacts from cnee_master_v2
  - Generates personalized subject + body using GREETING + CAMPAIGN_ID
  - Sends via win32com Outlook COM (no SMTP/admin needed)
  - Logs every send to email_log.csv
  - Updates cnee_master_v2 SEND_COUNT + LAST_SENT_DATE
  - Batch 50 → pause 60s → next batch
  - Random delay 2-5s between emails
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

_repo = str(Path(__file__).parent.parent.parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
from shared import paths as sp

log = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
CNEE_V2 = sp.EMAIL_DATA / "cnee_master_v2.xlsx"
EMAIL_LOG = sp.EMAIL_LOG
COMPANY_PDF = sp.COMPANY_PDF
BATCH_SIZE = 50
BATCH_PAUSE = 60  # seconds between batches
EMAIL_DELAY_MIN = 2
EMAIL_DELAY_MAX = 5


# ── Email templates ──────────────────────────────────────────────────────────

def build_subject(rec: dict) -> str:
    """Generate personalized subject line."""
    campaign = str(rec.get("CAMPAIGN_ID", "")).strip()
    company = str(rec.get("COMPANY", "")).strip()
    pol = str(rec.get("POL", "")).strip()
    dest = str(rec.get("DESTINATION", "")).strip()

    # Build route string
    route = ""
    if pol and pol.lower() not in ("nan", "none", ""):
        route = pol
    if dest and dest.lower() not in ("nan", "none", ""):
        first_dest = dest.split(",")[0].strip()
        route = f"{route}→{first_dest}" if route else first_dest

    week = datetime.now().isocalendar()[1]

    if route:
        return f"{route} rates for {campaign} // NELSON WEEK {week}"
    elif campaign:
        return f"Vietnam freight rates for {campaign} // NELSON WEEK {week}"
    else:
        return f"Competitive ocean freight from Vietnam // NELSON WEEK {week}"


def build_body(rec: dict) -> str:
    """Generate plain-text email body (<125 words)."""
    greeting = str(rec.get("GREETING", "Dear Import Team"))
    company = str(rec.get("COMPANY", "")).strip()
    campaign = str(rec.get("CAMPAIGN_ID", "")).strip()
    carrier = str(rec.get("CARRIER", "")).strip()

    # Clean nan values
    if campaign.lower() in ("nan", "none", ""):
        campaign = "general cargo"
    if carrier.lower() in ("nan", "none", ""):
        carrier = ""

    carrier_line = f" via {carrier.split(',')[0].strip()}" if carrier else ""

    body = f"""{greeting},

Quick note — we handle {campaign} shipments from Vietnam to the US{carrier_line}, and rates are competitive this week.

Most importers keep 2-3 forwarders for backup. If you ever need a second option or a quick comparison, happy to send a sample quote for your next shipment.

No commitment — just a rate to benchmark against.

Best regards,
Nelson Huynh
Pudong Prime Shipping Co., Ltd
nelson@pudongprime.vn | pudongprime.vn"""

    return body


# ── Outlook COM ──────────────────────────────────────────────────────────────

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


def send_one(outlook, to: str, subject: str, body: str, attach_pdf: bool = True) -> bool:
    """Send a single email via Outlook COM."""
    try:
        mail = outlook.CreateItem(0)
        mail.To = to
        mail.Subject = subject
        mail.Body = body  # Plain text, not HTML

        if attach_pdf and COMPANY_PDF.exists():
            mail.Attachments.Add(str(COMPANY_PDF))

        mail.Send()
        return True
    except Exception as e:
        log.error("SEND FAILED: %s | %s", to, e)
        return False


# ── Logging ──────────────────────────────────────────────────────────────────

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


# ── Main batch logic ─────────────────────────────────────────────────────────

def load_send_queue(tier_filter: str = "", count: int = 500) -> pd.DataFrame:
    """Load contacts from cnee_master_v2 that are ready to send."""
    if not CNEE_V2.exists():
        log.error("cnee_master_v2.xlsx not found. Run build_master.py first.")
        sys.exit(1)

    df = pd.read_excel(CNEE_V2)
    log.info("Loaded %d contacts from cnee_master_v2", len(df))

    # Filter by action
    sendable = df[df["ACTION"].isin(["SEND_NOW", "FOLLOW_UP", "PERSONALIZED"])]

    # Optional tier filter
    if tier_filter:
        tiers = [t.strip().upper() for t in tier_filter.split(",")]
        sendable = sendable[sendable["TIER"].isin(tiers)]

    # Sort: VIP first, then HOT, WARM_A, WARM_B, COOL
    tier_order = {"VIP": 0, "HOT": 1, "WARM_A": 2, "WARM_B": 3, "COOL": 4}
    sendable = sendable.copy()
    sendable["_sort"] = sendable["TIER"].map(tier_order).fillna(9)
    sendable = sendable.sort_values(["_sort", "PRIORITY_SCORE"], ascending=[True, False])
    sendable = sendable.drop(columns=["_sort"])

    # Limit count
    sendable = sendable.head(count)
    log.info("Send queue: %d contacts (tier=%s)", len(sendable), tier_filter or "all")

    return sendable


def run_batch(count: int = 500, tier: str = "", dry_run: bool = False):
    """Execute batch send."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    queue = load_send_queue(tier_filter=tier, count=count)
    if queue.empty:
        log.info("No contacts to send. Done.")
        return

    if not dry_run:
        outlook = get_outlook()
        if not outlook:
            log.error("Outlook not running. Start Outlook first!")
            sys.exit(1)
        log.info("Outlook connected OK")
    else:
        outlook = None
        log.info("DRY RUN mode — no emails will be sent")

    sent = 0
    failed = 0
    total = len(queue)

    for i, (_, rec) in enumerate(queue.iterrows()):
        email = rec["EMAIL"]
        subject = build_subject(rec)
        body = build_body(rec)

        if dry_run:
            log.info("[DRY] %d/%d | %s | %s", i + 1, total, email, subject[:60])
            sent += 1
        else:
            ok = send_one(outlook, email, subject, body)
            if ok:
                log_send(email, subject, str(rec.get("CAMPAIGN_ID", "")))
                sent += 1
                log.info("SENT %d/%d | %s", i + 1, total, email)
            else:
                log_send(email, subject, str(rec.get("CAMPAIGN_ID", "")), "FAILED")
                failed += 1

        # Batch pause every BATCH_SIZE
        if (i + 1) % BATCH_SIZE == 0 and (i + 1) < total:
            log.info("--- Batch %d done. Pausing %ds ---",
                     (i + 1) // BATCH_SIZE, BATCH_PAUSE)
            if not dry_run:
                time.sleep(BATCH_PAUSE)

        # Random delay between emails
        if not dry_run and (i + 1) < total:
            delay = random.uniform(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
            time.sleep(delay)

    log.info("=" * 50)
    log.info("BATCH COMPLETE: %d sent, %d failed, %d total", sent, failed, total)
    log.info("=" * 50)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch send cold emails via Outlook COM")
    parser.add_argument("--count", type=int, default=50, help="Number of emails to send")
    parser.add_argument("--tier", type=str, default="", help="Filter by tier: VIP,HOT,WARM_A")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending")
    args = parser.parse_args()

    run_batch(count=args.count, tier=args.tier, dry_run=args.dry_run)
