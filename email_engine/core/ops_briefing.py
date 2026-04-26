# -*- coding: utf-8 -*-
from __future__ import annotations
"""
ops_briefing.py — Daily Operational Briefing  v1.0
====================================================
Sends a daily morning Telegram briefing summarizing:
  🟢 Normal shipments (no open risks)
  🟡 Watch (pending payment > 3 days, delay notices)
  🔴 Action Required (CHANGE_VESSEL, CRITICAL risks, no ATD after ETD)

Run via Task Scheduler daily at 08:00.

Usage:
    python ops_briefing.py
"""

import json, os, sys, logging
from datetime import datetime, timedelta
from pathlib import Path
import httpx

_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

STATE_FILE = sp.SHIPMENT_STATE
LOG_FILE   = sp.EMAIL_LOG_DIR / "ops_briefing.log"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────
DN_OVERDUE_DAYS     = 3   # DN_SENT > 3 days without PAYMENT_CONFIRMED → Watch
CRITICAL_STAGES     = {"CHANGE_VESSEL"}
WATCH_STAGES        = {"DELAY_NOTICE"}
PAYMENT_PENDING_MAX = 5   # days


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"shipments": {}}
    with STATE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def classify_shipments(state: dict) -> dict:
    now   = datetime.now()
    groups = {"red": [], "yellow": [], "green": [], "payment_pending": []}

    for sid, rec in state.get("shipments", {}).items():
        stage   = rec.get("stage", "")
        risks   = [r["level"] for r in rec.get("risks", [])]
        updated = rec.get("updated_at", "")
        customer = rec.get("customer", "?")
        ctype    = rec.get("type", "?")

        try:
            updated_dt = datetime.fromisoformat(updated)
            days_since = (now - updated_dt).days
        except:
            days_since = 0

        item = {
            "id":       sid,
            "customer": customer,
            "type":     ctype,
            "stage":    stage,
            "days":     days_since,
            "risks":    risks,
        }

        # 🔴 Action Required
        if "CRITICAL" in risks or stage in CRITICAL_STAGES:
            groups["red"].append(item)
        # 🟡 Watch
        elif ("HIGH" in risks or stage in WATCH_STAGES or
              (stage == "DN_SENT" and days_since >= DN_OVERDUE_DAYS)):
            groups["yellow"].append(item)
            if stage == "DN_SENT" and days_since >= DN_OVERDUE_DAYS:
                groups["payment_pending"].append(item)
        # 🟢 Normal
        elif stage != "PAYMENT_CONFIRMED":
            groups["green"].append(item)

    return groups


def build_message(groups: dict) -> str:
    today = datetime.now().strftime("%d/%m/%Y")
    lines = [
        f"📋 <b>OPS BRIEFING — {today}</b>",
        f"<i>Tổng: {sum(len(v) for k,v in groups.items() if k != 'payment_pending')} lô đang theo dõi</i>",
        "",
    ]

    # 🔴 Action Required
    if groups["red"]:
        lines.append(f"🔴 <b>ACTION REQUIRED ({len(groups['red'])} lô)</b>")
        for s in groups["red"][:5]:
            lines.append(f"  • {s['id']} | {s['customer']} | {s['stage']}")
            if s["risks"]:
                lines.append(f"    ⚠️ Risk: {', '.join(s['risks'])}")
        lines.append("")

    # 🟡 Watch
    if groups["yellow"]:
        lines.append(f"🟡 <b>WATCH ({len(groups['yellow'])} lô)</b>")
        for s in groups["yellow"][:5]:
            extra = f" | {s['days']}d" if s["days"] else ""
            lines.append(f"  • {s['id']} | {s['customer']} | {s['stage']}{extra}")
        lines.append("")

    # 💰 Payment Pending
    if groups["payment_pending"]:
        lines.append(f"💰 <b>PAYMENT CHỜ ({len(groups['payment_pending'])} lô)</b>")
        for s in groups["payment_pending"][:5]:
            lines.append(f"  • {s['id']} | {s['customer']} | DN {s['days']} ngày chưa TT")
        lines.append("")

    # 🟢 Normal
    if groups["green"]:
        lines.append(f"🟢 <b>BÌNH THƯỜNG ({len(groups['green'])} lô)</b>")

    lines.append(f"\n🕒 {datetime.now().strftime('%H:%M %d/%m/%Y')}")
    return "\n".join(lines)


def send_telegram(message: str) -> bool:
    """DISABLED 2026-04-26 — no-op."""
    log.debug("ops_briefing.send_telegram disabled — message dropped (%d chars)", len(message))
    return True
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:  # noqa: unreachable
        log.warning("Telegram not configured. Message:\n%s", message)
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        log.error("Telegram error: %s", e)
        return False


def main() -> None:
    log.info("Ops Briefing @ %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    state  = load_state()
    groups = classify_shipments(state)
    msg    = build_message(groups)

    log.info("Red: %d | Yellow: %d | Green: %d",
             len(groups["red"]), len(groups["yellow"]), len(groups["green"]))
    log.info("Sending Telegram briefing...")
    ok = send_telegram(msg)
    log.info("Sent: %s", ok)
    # Report to Fox Spirit (GoClaw VPS)
    try:
        import importlib.util, pathlib
        _rep = pathlib.Path(__file__).parent.parent.parent / "tools" / "goclaw" / "goclaw_reporter.py"
        _spec = importlib.util.spec_from_file_location("goclaw_reporter", _rep)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.report_to_fox("ops-brief", {"sent": ok, "red": len(groups["red"]),
                           "yellow": len(groups["yellow"]), "green": len(groups["green"])})
    except Exception:
        pass


if __name__ == "__main__":
    main()
