# -*- coding: utf-8 -*-
"""
SENTINEL — Self-waking monitor agent for N.E.L.S.O.N v2.0
===========================================================
Inspired by GoClaw Heartbeat pattern.
Runs daily checks and pushes summary to Nelson via Telegram.

Checks:
  1. Rate anomalies (from alert_dispatcher)
  2. Shipment deadlines / expiring rates
  3. Mentee activity (from Oracle)
  4. Pending tasks (from Oracle task queue)
  5. Rate forecast (from rate_predictor)
  6. Recent email signals (from shipments.db nelson_alerts)

Usage:
    from agents.sentinel import Sentinel
    s = Sentinel()
    s.morning_briefing()  # called by scheduler at 08:00
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Path setup
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "TelegramBot"))

log = logging.getLogger(__name__)


class Sentinel:
    """
    Proactive monitor agent — checks anomalies, deadlines, mentee activity.
    Pushes consolidated morning briefing to Nelson's Telegram.
    """

    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv(ROOT / "TelegramBot" / ".env")
        self.bot_token = os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("ADMIN_CHAT_ID")
        self._oracle = None
        try:
            from memory.oracle import Oracle
            self._oracle = Oracle()
        except Exception:
            pass

    @property
    def oracle(self):
        return self._oracle

    def _send(self, message: str) -> bool:
        """Send message to Nelson via Telegram."""
        import requests
        if not self.bot_token or not self.chat_id:
            log.error("[SENTINEL] Missing BOT_TOKEN or ADMIN_CHAT_ID")
            return False
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message,
                      "parse_mode": "HTML"},
                timeout=10,
            )
            return resp.json().get("ok", False)
        except Exception as e:
            log.error("[SENTINEL] Send failed: %s", e)
            return False

    # ── Morning Briefing ─────────────────────────────────────────────────

    def morning_briefing(self) -> dict:
        """
        08:00 Mon-Fri push to Nelson's Telegram.
        Assembles real data from all intelligence sources.
        """
        ts = datetime.now().strftime("%d/%m %H:%M")
        sections = []
        results = {}

        # 1. Rate anomalies (last 24h)
        anomaly_section, anomaly_data = self._check_anomalies_24h()
        if anomaly_section:
            sections.append(anomaly_section)
        results["anomalies"] = anomaly_data

        # 2. Expiring rates / shipment deadlines
        deadline_section, deadline_data = self._check_shipment_deadlines()
        if deadline_section:
            sections.append(deadline_section)
        results["deadlines"] = deadline_data

        # 3. Rate forecast
        forecast_section, forecast_data = self._check_rate_forecast()
        if forecast_section:
            sections.append(forecast_section)
        results["forecast"] = forecast_data

        # 4. Recent email alerts
        alert_section, alert_data = self._check_recent_alerts()
        if alert_section:
            sections.append(alert_section)
        results["alerts"] = alert_data

        # 5. Mentee activity
        mentee_section, mentee_data = self._check_mentee_activity()
        if mentee_section:
            sections.append(mentee_section)
        results["mentees"] = mentee_data

        # 6. Pending tasks + Oracle stats
        task_section, task_data = self._check_pending_tasks()
        if task_section:
            sections.append(task_section)
        results["tasks"] = task_data

        # Oracle stats footer
        if self._oracle:
            stats = self._oracle.stats()
            sections.append(
                f"\n<i>Oracle: {stats['total_messages']} msgs | "
                f"{stats['unique_users']} users | "
                f"{stats['db_size_kb']}KB</i>"
            )

        # Build and send
        if sections:
            header = f"<b>🌅 SENTINEL Morning Briefing — {ts}</b>"
            message = header + "\n" + "\n".join(sections)
            results["sent"] = self._send(message)
        else:
            results["sent"] = self._send(
                f"<b>🌅 SENTINEL — {ts}</b>\n\n"
                f"✅ All clear. No issues detected.\n"
                f"Have a productive day, Sếp! 🚀"
            )

        log.info("[SENTINEL] Briefing complete: sent=%s", results.get("sent"))
        return results

    # ── Individual Checks ────────────────────────────────────────────────

    def _check_anomalies_24h(self) -> tuple:
        """Check rate anomalies from last 24h alert cycle."""
        data = {"checked": False, "count": 0}
        try:
            from intelligence.alert_dispatcher import run_alert_cycle
            result = run_alert_cycle()
            data["checked"] = True
            data["count"] = result.get("anomalies", 0)
            data["critical"] = result.get("critical", 0)
            data["warnings"] = result.get("warnings", 0)

            if data["count"] > 0:
                section = (
                    f"\n🚨 <b>Rate Anomalies:</b> {data['count']} total "
                    f"({data['critical']} critical, {data['warnings']} warning)"
                )
                return section, data
        except Exception as e:
            log.warning("[SENTINEL] Anomaly check failed: %s", e)
            data["error"] = str(e)
        return "", data

    def _check_shipment_deadlines(self) -> tuple:
        """Check rates expiring in next 3 days using Parquet."""
        data = {"checked": False, "urgent": 0}
        try:
            parquet_paths = [
                ROOT / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet",
                ROOT / "Pricing_Engine" / "Backup_parquet" / "Cleaned_Master_History.parquet",
            ]
            parquet_path = None
            for p in parquet_paths:
                if p.exists():
                    parquet_path = p
                    break

            if not parquet_path:
                return "", data

            import pandas as pd
            today = datetime.now().strftime("%Y-%m-%d")
            cutoff = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

            df = pd.read_parquet(
                parquet_path,
                columns=["Carrier", "POL", "POD", "Place", "Exp", "Container_Type", "Amount"],
                filters=[("Exp", ">=", today), ("Exp", "<=", cutoff)]
            )

            data["checked"] = True
            data["urgent"] = len(df)

            if len(df) > 0:
                carriers = df["Carrier"].value_counts().head(5)
                carrier_str = ", ".join(
                    f"{c}({n})" for c, n in carriers.items()
                )
                section = (
                    f"\n📅 <b>Expiring Rates (3 days):</b> {len(df)} rates\n"
                    f"  Top: {carrier_str}"
                )
                return section, data

        except Exception as e:
            log.warning("[SENTINEL] Deadline check failed: %s", e)
            data["error"] = str(e)
        return "", data

    def _check_rate_forecast(self) -> tuple:
        """Get rate trend forecast for core routes."""
        data = {"checked": False, "routes": 0}
        try:
            from intelligence.rate_predictor import RatePredictor
            predictor = RatePredictor()
            forecasts = predictor.top_routes_forecast()
            data["checked"] = True
            data["routes"] = len(forecasts)

            if forecasts:
                section = predictor.format_forecast_text(forecasts)
                return section, data

        except Exception as e:
            log.warning("[SENTINEL] Forecast check skipped: %s", e)
            data["error"] = str(e)
        return "", data

    def _check_recent_alerts(self) -> tuple:
        """Check nelson_alerts from shipments.db (last 24h)."""
        data = {"checked": False, "count": 0}
        try:
            db_path = ROOT / "email_engine" / "logs" / "shipments.db"
            if not db_path.exists():
                return "", data

            yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
            with sqlite3.connect(db_path) as c:
                c.row_factory = sqlite3.Row
                rows = c.execute("""
                    SELECT alert_type, risk_level, customer_name,
                           alert_reason, shipment_key
                    FROM nelson_alerts
                    WHERE created_at >= ?
                      AND is_resolved = 0
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (yesterday,)).fetchall()

            data["checked"] = True
            data["count"] = len(rows)

            if rows:
                lines = [f"\n📧 <b>Email Alerts (24h):</b> {len(rows)} unresolved"]
                for r in rows[:5]:
                    emoji = "🔴" if r["risk_level"] in ("CRITICAL", "HIGH") else "🟡"
                    customer = r["customer_name"] or "?"
                    reason = (r["alert_reason"] or "")[:40]
                    lines.append(
                        f"  {emoji} {customer}: {reason}"
                    )
                section = "\n".join(lines)
                return section, data

        except Exception as e:
            log.warning("[SENTINEL] Alert check failed: %s", e)
            data["error"] = str(e)
        return "", data

    def _check_mentee_activity(self) -> tuple:
        """Check mentee activity using Oracle + env MENTEE_TELEGRAM_IDS."""
        data = {"checked": False, "inactive": []}
        try:
            # Check by MENTEE_IDS environment variable
            mentee_ids = os.getenv("MENTEE_TELEGRAM_IDS", "").split(",")
            mentee_ids = [m.strip() for m in mentee_ids if m.strip()]

            oracle_db = Path(__file__).parent.parent / "memory" / "oracle.db"
            if not oracle_db.exists():
                return "", data

            data["checked"] = True
            today = datetime.now().strftime("%Y-%m-%d")

            if mentee_ids:
                # Check specific mentees
                with sqlite3.connect(oracle_db) as c:
                    for uid in mentee_ids:
                        row = c.execute(
                            "SELECT COUNT(*) FROM conversations "
                            "WHERE user_id=? AND DATE(ts)=?",
                            (uid, today)
                        ).fetchone()
                        if row[0] == 0:
                            data["inactive"].append(uid)

                if data["inactive"]:
                    section = (
                        f"\n👥 <b>Inactive mentees:</b> "
                        f"{len(data['inactive'])} haven't checked in today"
                    )
                    # Try to resolve names from Oracle profiles
                    names = []
                    for uid in data["inactive"][:5]:
                        if self._oracle:
                            profile = self._oracle.get_profile(uid)
                            names.append(profile.get("username", uid))
                        else:
                            names.append(uid)
                    section += "\n  " + ", ".join(names)
                    return section, data
            else:
                # No mentee IDs configured — report general stats
                from memory.oracle import Oracle
                oracle = Oracle(oracle_db)
                stats = oracle.stats()
                data["total_users"] = stats.get("unique_users", 0)
                data["total_messages"] = stats.get("total_messages", 0)

                if stats["total_messages"] > 0:
                    section = (
                        f"\n👥 <b>Activity:</b> {stats['unique_users']} users, "
                        f"{stats['total_messages']} messages tracked"
                    )
                    return section, data

        except Exception as e:
            log.warning("[SENTINEL] Mentee check failed: %s", e)
            data["error"] = str(e)
        return "", data

    def _check_pending_tasks(self) -> tuple:
        """Check pending tasks in Oracle task queue."""
        data = {"checked": False, "pending": 0}
        try:
            oracle_db = Path(__file__).parent.parent / "memory" / "oracle.db"
            if not oracle_db.exists():
                return "", data

            from memory.oracle import Oracle
            oracle = Oracle(oracle_db)
            pending = oracle.get_pending_tasks()
            data["checked"] = True
            data["pending"] = len(pending)

            if pending:
                types = {}
                for t in pending:
                    tt = t["task_type"]
                    types[tt] = types.get(tt, 0) + 1
                type_str = ", ".join(f"{t}({n})" for t, n in types.items())
                section = (
                    f"\n📋 <b>Task Queue:</b> {len(pending)} pending — {type_str}"
                )
                return section, data
        except Exception as e:
            log.warning("[SENTINEL] Task check failed: %s", e)
            data["error"] = str(e)
        return "", data


# ── Standalone runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    sentinel = Sentinel()
    result = sentinel.morning_briefing()
    print(f"\n=== Sentinel Result ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
