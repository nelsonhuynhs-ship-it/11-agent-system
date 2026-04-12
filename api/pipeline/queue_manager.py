"""
queue_manager.py — Email queue manager with dry-run, rate limiting, nightly auto-send.
Interfaces with the existing email_queue_router.py via PostgreSQL.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from .blacklist import is_blacklisted
from .template_engine import render_email

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
MASTER_FILE = DATA_DIR / "email" / "cnee_master_v2_final.xlsx"

# Queue configuration
RATE_LIMIT_PER_HOUR = 100
SEND_WINDOW_START = 20  # 8PM local
SEND_WINDOW_END = 6     # 6AM local
MAX_PER_NIGHT = 1000
BOUNCE_THRESHOLD = 0.05  # 5% bounce rate → auto-pause


def prepare_batch(
    campaign_id: str = None,
    tier: str = None,
    template_category: str = "cold",
    template_name: str = "generic",
    limit: int = 100,
    dry_run: bool = True,
    context_overrides: dict = None,
) -> list[dict]:
    """
    Prepare a batch of emails for sending.

    Args:
        campaign_id: filter by campaign (e.g., 'CANDLE')
        tier: filter by tier (e.g., 'HOT', 'VIP', 'WARM_A')
        template_category: 'cold', 'followup', 'transactional'
        template_name: template to use
        limit: max emails in batch
        dry_run: if True, preview only (don't mark as queued)
        context_overrides: extra template variables

    Returns:
        List of email dicts: {to, subject, body_html, template, status}
    """
    df = pd.read_excel(MASTER_FILE)

    # Filter eligible contacts
    mask = df["ACTION"] == "SEND_NOW"
    if "SEQ_STATUS" in df.columns:
        mask &= df["SEQ_STATUS"] != "BOUNCED"
    if campaign_id:
        mask &= df["CAMPAIGN_ID"] == campaign_id
    if tier:
        mask &= df["TIER"] == tier

    eligible = df[mask].head(limit)
    batch = []

    for _, row in eligible.iterrows():
        # Double-check blacklist
        blocked, reason = is_blacklisted(str(row.get("EMAIL", "")), str(row.get("COMPANY", "")))
        if blocked:
            continue

        # Build template context
        ctx = {
            "company": row.get("COMPANY", ""),
            "pic": row.get("PIC", row.get("GREETING", "")),
            "pol": row.get("POL", "Vietnam"),
            "destination": row.get("DESTINATION", "US"),
            "pod": row.get("DESTINATION", ""),
            "commodity": row.get("CAMPAIGN_ID", "general cargo"),
            "carrier": row.get("CARRIER", ""),
            "total_shipment": row.get("TOTAL_SHIPMENT", ""),
            "container": "40HQ",
        }
        if context_overrides:
            ctx.update(context_overrides)

        # Render email
        email = render_email(template_category, template_name, ctx)

        batch.append({
            "to": row["EMAIL"],
            "company": ctx["company"],
            "subject": email["subject"],
            "body_html": email["body_html"],
            "template": email["template"],
            "variant": email["variant"],
            "campaign_id": row.get("CAMPAIGN_ID", ""),
            "tier": row.get("TIER", ""),
            "status": "DRY_RUN" if dry_run else "PENDING",
        })

    return batch


def approve_batch(batch: list[dict]) -> list[dict]:
    """Move batch from DRY_RUN to PENDING (ready for Outlook worker to pick up)."""
    for item in batch:
        item["status"] = "PENDING"
        item["queued_at"] = datetime.now().isoformat()
    return batch


def get_nightly_stats(batch_results: list[dict]) -> dict:
    """Calculate stats for nightly send report."""
    total = len(batch_results)
    sent = sum(1 for r in batch_results if r.get("status") == "SENT")
    failed = sum(1 for r in batch_results if r.get("status") == "FAILED")
    bounced = sum(1 for r in batch_results if r.get("status") == "BOUNCED")
    bounce_rate = bounced / total if total > 0 else 0

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "bounced": bounced,
        "bounce_rate": f"{bounce_rate:.1%}",
        "paused": bounce_rate > BOUNCE_THRESHOLD,
        "timestamp": datetime.now().isoformat(),
        "message": f"Sent {sent}/{total}. {bounced} bounced. {'PAUSED — bounce rate too high!' if bounce_rate > BOUNCE_THRESHOLD else 'OK'}",
    }


def preview_batch(
    campaign_id: str = None,
    tier: str = "HOT",
    template_name: str = "rate-focused",
    limit: int = 5,
) -> None:
    """Print preview of email batch to console."""
    batch = prepare_batch(
        campaign_id=campaign_id,
        tier=tier,
        template_category="cold",
        template_name=template_name,
        limit=limit,
        dry_run=True,
    )

    print(f"\n=== Email Batch Preview ({len(batch)} emails) ===\n")
    for i, email in enumerate(batch, 1):
        print(f"--- Email {i} ---")
        print(f"To: {email['to']} ({email['company']})")
        print(f"Subject: {email['subject']}")
        print(f"Template: {email['template']} (variant {email['variant']})")
        print(f"Campaign: {email['campaign_id']} | Tier: {email['tier']}")
        print(f"Status: {email['status']}")
        print()
