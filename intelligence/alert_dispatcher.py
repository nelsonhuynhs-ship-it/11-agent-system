# -*- coding: utf-8 -*-
"""
alert_dispatcher.py — Rate Anomaly → Telegram Alerts
======================================================
Scans latest rates via FreightDB, runs AnomalyDetector,
pushes WARNING/CRITICAL alerts to Nelson via Telegram.

Runs on VPS (requires Parquet file).
Consumers: Task Scheduler, bot_v5 /scan_anomalies command.

Usage:
    python -m intelligence.alert_dispatcher
    # Or from bot: from intelligence.alert_dispatcher import run_alert_cycle
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# ── Path setup ──
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "TelegramBot" / ".env")

# Lazy imports — duckdb + parquet only available on VPS
# Import inside run_alert_cycle() to avoid crash on laptop
FreightDB = None
AnomalyDetector = None
AnomalyResult = None

log = logging.getLogger(__name__)

# ── Config ──
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PARQUET_PATH = ROOT / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"

# Most traded routes to scan
SCAN_ROUTES = [
    {"pol": "HCM", "pod": "LAX", "ct": "20GP"},
    {"pol": "HCM", "pod": "LAX", "ct": "40HQ"},
    {"pol": "HCM", "pod": "NY",  "ct": "20GP"},
    {"pol": "HCM", "pod": "NY",  "ct": "40HQ"},
    {"pol": "HPH", "pod": "LAX", "ct": "20GP"},
    {"pol": "HPH", "pod": "LAX", "ct": "40HQ"},
    {"pol": "HPH", "pod": "NY",  "ct": "20GP"},
    {"pol": "HPH", "pod": "NY",  "ct": "40HQ"},
    {"pol": "HCM", "pod": "SAV", "ct": "40HQ"},
    {"pol": "HCM", "pod": "HOU", "ct": "40HQ"},
    {"pol": "HPH", "pod": "DEN", "ct": "20GP"},
    {"pol": "HPH", "pod": "DEN", "ct": "40HQ"},
    {"pol": "HPH", "pod": "ELP", "ct": "20GP"},
    {"pol": "HPH", "pod": "ELP", "ct": "40HQ"},
]


def send_telegram(message: str) -> bool:
    """Send message via Telegram Bot API. DISABLED 2026-04-26 — no-op."""
    log.debug("alert_dispatcher.send_telegram disabled — message dropped (%d chars)", len(message))
    return True
    import requests  # noqa: unreachable
    if not BOT_TOKEN or not CHAT_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        return resp.json().get("ok", False)
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


def scan_all_routes(db: FreightDB, detector: AnomalyDetector) -> list[AnomalyResult]:
    """
    Scan SCAN_ROUTES: for each route, get per-carrier rates
    and check each against the route median.
    """
    anomalies: list[AnomalyResult] = []

    for route in SCAN_ROUTES:
        pol, pod, ct = route["pol"], route["pod"], route["ct"]

        # Get all carrier rates for this route
        df = db.query_rates(pol=pol, pod=pod, container_type=ct, days=30)
        if df.empty:
            continue

        # Check each carrier's latest rate
        for carrier, group in df.groupby("Carrier"):
            latest = group.iloc[0]  # Already sorted by Amount ASC
            result = detector.check_rate(
                carrier=str(carrier),
                pol=pol,
                pod=pod,
                container_type=ct,
                quoted_rate=float(latest["Amount"]),
                days=30,
            )
            if result.is_anomaly:
                anomalies.append(result)

    return anomalies


def format_alert(anomalies: list[AnomalyResult]) -> str:
    """Format anomalies into a Telegram-friendly message."""
    critical = [a for a in anomalies if a.severity == "critical"]
    warnings = [a for a in anomalies if a.severity == "warning"]

    ts = datetime.now().strftime("%d/%m %H:%M")
    lines = [f"<b>🚨 Rate Anomaly Alert — {ts}</b>"]
    lines.append(f"Scanned {len(SCAN_ROUTES)} routes | "
                 f"Found {len(anomalies)} anomalies")

    if critical:
        lines.append(f"\n🔴 <b>CRITICAL ({len(critical)}):</b>")
        for a in critical[:8]:
            direction = "⬆️" if a.deviation_pct > 0 else "⬇️"
            lines.append(
                f"  {direction} {a.carrier} {a.pol}→{a.pod}/{a.container_type}: "
                f"${a.quoted_rate:,.0f} ({a.deviation_pct:+.1f}% vs median ${a.route_median:,.0f})"
            )

    if warnings:
        lines.append(f"\n⚠️ <b>WARNING ({len(warnings)}):</b>")
        for a in warnings[:8]:
            direction = "⬆️" if a.deviation_pct > 0 else "⬇️"
            lines.append(
                f"  {direction} {a.carrier} {a.pol}→{a.pod}/{a.container_type}: "
                f"${a.quoted_rate:,.0f} ({a.deviation_pct:+.1f}% vs median ${a.route_median:,.0f})"
            )

    lines.append(f"\n💡 /quote [route] to see full pricing")
    return "\n".join(lines)


def run_alert_cycle() -> dict:
    """
    Main entry point:
    1. Init FreightDB + AnomalyDetector
    2. Scan all routes
    3. Push Telegram alert if anomalies found
    
    Returns: {"anomalies": N, "critical": N, "warnings": N, "sent": bool}
    """
    # Validate Parquet exists
    if not PARQUET_PATH.exists():
        log.warning("Parquet not found at %s — skipping anomaly scan", PARQUET_PATH)
        return {"anomalies": 0, "critical": 0, "warnings": 0, "sent": False,
                "error": "Parquet file not found (only available on VPS)"}

    # Lazy import — duckdb only on VPS
    from db.duckdb_engine import FreightDB
    from intelligence.anomaly_detector import AnomalyDetector

    db = FreightDB(PARQUET_PATH)
    detector = AnomalyDetector(freight_db=db)

    # Scan
    anomalies = scan_all_routes(db, detector)

    result = {
        "anomalies": len(anomalies),
        "critical": len([a for a in anomalies if a.severity == "critical"]),
        "warnings": len([a for a in anomalies if a.severity == "warning"]),
        "sent": False,
    }

    if not anomalies:
        log.info("No anomalies detected across %d routes", len(SCAN_ROUTES))
        return result

    # Format & send
    message = format_alert(anomalies)
    result["sent"] = send_telegram(message)
    log.info("Alert dispatched: %d anomalies (%d critical, %d warning) — sent=%s",
             result["anomalies"], result["critical"], result["warnings"], result["sent"])

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    result = run_alert_cycle()
    print(f"\n=== Alert Cycle Result ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
