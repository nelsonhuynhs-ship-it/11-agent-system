# -*- coding: utf-8 -*-
"""
rate_expiry_guardian.py — Bot v6 Feature #1
Proactive Rate Expiry Guardian — scans Parquet for rates expiring soon,
cross-checks against active jobs, sends prioritized Telegram alerts.

Usage:
  - Called by cron job at 06:00 daily via bot_v5.py scheduler
  - Also callable via /checkrates command
"""
import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

# ── Alert thresholds ──────────────────────────────────────────────────────────
CRITICAL_DAYS = 3   # Rate expires in ≤3 days AND has active job
HIGH_DAYS     = 7   # Rate expires in ≤7 days
MEDIUM_DAYS   = 14  # Rate expires in ≤14 days for watch list


def get_expiring_rates(df: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    """
    Filter Parquet DataFrame for rates expiring within `days`.
    Returns sorted DataFrame: soonest expiry first.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    today = pd.Timestamp(datetime.now().date())
    cutoff = today + timedelta(days=days)

    # Ensure Exp column is datetime
    if 'Exp' not in df.columns:
        return pd.DataFrame()

    exp_df = df.copy()
    exp_df['Exp'] = pd.to_datetime(exp_df['Exp'], errors='coerce')

    # Filter: expires between today and cutoff
    mask = (exp_df['Exp'] >= today) & (exp_df['Exp'] <= cutoff)
    expiring = exp_df[mask].copy()

    if expiring.empty:
        return pd.DataFrame()

    # Deduplicate: one row per Carrier+POL+Place combination
    dedup_cols = [c for c in ['Carrier', 'POL', 'Place', 'Container_Type'] if c in expiring.columns]
    expiring = (
        expiring
        .sort_values('Exp')
        .drop_duplicates(subset=dedup_cols, keep='first')
        .sort_values('Exp')
    )

    # Add days_left column
    expiring['days_left'] = (expiring['Exp'] - today).dt.days
    return expiring


def classify_alert(days_left: int, has_active_job: bool) -> str:
    """Classify alert level based on urgency."""
    if days_left <= CRITICAL_DAYS and has_active_job:
        return "CRITICAL"
    if days_left <= HIGH_DAYS:
        return "HIGH"
    if days_left <= MEDIUM_DAYS:
        return "MEDIUM"
    return "LOW"


def format_expiry_alert(expiring: pd.DataFrame, active_jobs: list) -> str:
    """
    Format expiring rates into a prioritized Telegram alert message.

    Args:
        expiring: DataFrame of expiring rates
        active_jobs: list of dicts from erp_reader.get_active_jobs()

    Returns:
        Formatted message string, or None if no alerts needed.
    """
    if expiring.empty:
        return None

    # Build set of active (carrier, route) combos
    active_set = set()
    for job in active_jobs:
        carrier = str(job.get('carrier', '')).upper()
        routing = str(job.get('routing', '')).upper()
        active_set.add((carrier, routing))

    alerts = {"CRITICAL": [], "HIGH": [], "MEDIUM": []}
    today = pd.Timestamp(datetime.now().date())

    for _, row in expiring.iterrows():
        carrier = str(row.get('Carrier', '')).upper()
        pol     = str(row.get('POL', ''))
        place   = str(row.get('Place', ''))
        exp_dt  = row.get('Exp')
        days    = int(row.get('days_left', 99))
        exp_str = exp_dt.strftime('%d/%m') if pd.notna(exp_dt) else '?'

        # Check if any active job uses this carrier
        has_job = any(
            carrier in j_carrier
            for j_carrier, _ in active_set
            for j_carrier in [carrier]
        )

        level = classify_alert(days, has_job)
        if level not in alerts:
            continue

        job_tag = " ⚠️ JOB ACTIVE!" if has_job else ""
        alerts[level].append(
            f"• {carrier} {pol}→{place}: hết hạn {exp_str} ({days} ngày){job_tag}"
        )

    # Build message
    lines = [f"⏰ RATE EXPIRY GUARDIAN — {datetime.now().strftime('%d/%m/%Y')}"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    total = sum(len(v) for v in alerts.values())
    if total == 0:
        return None

    lines.append(f"Phát hiện {total} rate sắp hết hạn:\n")

    if alerts["CRITICAL"]:
        lines.append(f"🔴 CRITICAL ({len(alerts['CRITICAL'])} routes — CÓ JOB ACTIVE):")
        lines.extend(alerts["CRITICAL"])
        lines.append("→ Hành động: Liên hệ hãng tàu NGAY để renew!\n")

    if alerts["HIGH"]:
        lines.append(f"🟡 HIGH ({len(alerts['HIGH'])} routes — hết hạn ≤7 ngày):")
        lines.extend(alerts["HIGH"])
        lines.append("→ Hành động: Schedule renew trong tuần này.\n")

    if alerts["MEDIUM"]:
        lines.append(f"🟢 WATCH ({len(alerts['MEDIUM'])} routes — hết hạn ≤14 ngày):")
        lines.extend(alerts["MEDIUM"])

    lines.append("\n💡 Dùng /quote để check giá thay thế nếu cần.")
    return "\n".join(lines)


async def run_expiry_check(bot, chat_id: int, parquet_df: pd.DataFrame, active_jobs: list):
    """
    Main entry point — called by scheduler or /checkrates command.
    Returns True if alerts were sent, False if all clear.
    """
    try:
        expiring = get_expiring_rates(parquet_df, days=MEDIUM_DAYS)

        if expiring.empty:
            logger.info("[Guardian] No rates expiring in next 14 days. All clear.")
            return False

        msg = format_expiry_alert(expiring, active_jobs)

        if msg:
            await bot.send_message(chat_id=chat_id, text=msg)
            logger.info(f"[Guardian] Sent expiry alert: {len(expiring)} rates flagged")
            return True

        return False

    except Exception as e:
        logger.error(f"[Guardian] Error: {e}")
        return False


def quick_summary(parquet_df: pd.DataFrame) -> str:
    """Quick one-liner summary for /status command."""
    expiring_7  = get_expiring_rates(parquet_df, days=7)
    expiring_14 = get_expiring_rates(parquet_df, days=14)
    n7  = len(expiring_7)
    n14 = len(expiring_14)
    if n7 == 0:
        return f"✅ Rates: {n14} rate hết hạn trong 14 ngày (không urgent)"
    return f"⚠️ Rates: {n7} hết hạn ≤7 ngày | {n14} hết hạn ≤14 ngày"
