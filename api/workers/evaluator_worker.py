# -*- coding: utf-8 -*-
"""
evaluator_worker.py — Daily System Self-Assessment
=====================================================
Runs daily evaluations:
- Rate expiry check (flag rates expiring within 48h)
- Shipment risk scan (delayed shipments, stale stages)
- System health metrics (data freshness, cache status)

Schedule: Daily 06:00 (configurable)
"""
import logging
import os
import sys
from datetime import datetime, date
from typing import Optional

import pandas as pd

log = logging.getLogger("nelson.workers.evaluator")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_bus import bus, Event
from data_access import dal


class EvaluatorWorker:
    """Daily system evaluator — rate expiry, risk scan, health check."""

    def __init__(self):
        self._scheduler = None
        self._last_run: Optional[datetime] = None
        self._last_report: dict = {}

    def start(self):
        """Start daily evaluation scheduler."""
        enabled = os.environ.get("EVALUATOR_ENABLED", "true").lower() == "true"
        if not enabled:
            log.info("Evaluator worker DISABLED")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                self.run_evaluation,
                'cron',
                hour=6, minute=0,
                id='daily_evaluation',
                name='Daily System Evaluation',
                max_instances=1,
            )
            self._scheduler.start()
            log.info("Evaluator worker started — daily at 06:00")
        except ImportError:
            log.warning("APScheduler not installed — evaluator will not auto-run")
        except Exception as e:
            log.error("Failed to start evaluator: %s", e)

    def stop(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    def run_evaluation(self) -> dict:
        """Execute full evaluation cycle."""
        log.info("Running daily evaluation...")
        report = {
            "timestamp": datetime.now().isoformat(),
            "rate_expiry": self._check_rate_expiry(),
            "shipment_risks": self._check_shipment_risks(),
            "system_health": self._check_system_health(),
        }

        # Publish system event
        bus.publish(Event(
            type="system.health_check",
            payload={
                "expiring_rates": report["rate_expiry"]["expiring_48h"],
                "at_risk_shipments": report["shipment_risks"]["at_risk"],
                "health_score": report["system_health"]["score"],
            },
            source="evaluator",
        ))

        self._last_run = datetime.now()
        self._last_report = report
        log.info("Daily evaluation complete — health score: %s/100",
                 report["system_health"]["score"])
        return report

    def _check_rate_expiry(self) -> dict:
        """Check for rates expiring within 48 hours."""
        df = dal.load_rates()
        if df is None:
            return {"total": 0, "expiring_48h": 0, "expiring_7d": 0}

        today = pd.Timestamp(date.today())
        in_48h = today + pd.Timedelta(hours=48)
        in_7d = today + pd.Timedelta(days=7)

        expiring_48h = df[df['Exp'] <= in_48h]
        expiring_7d = df[(df['Exp'] > in_48h) & (df['Exp'] <= in_7d)]

        # Publish alerts for critical expirations
        if len(expiring_48h) > 0:
            carriers_expiring = expiring_48h['Carrier'].unique().tolist()
            bus.publish(Event(
                type="rate.expired",
                payload={
                    "count": len(expiring_48h),
                    "carriers": carriers_expiring[:5],
                    "severity": "high" if len(expiring_48h) > 100 else "medium",
                },
                source="evaluator",
            ))

        return {
            "total": len(df),
            "expiring_48h": len(expiring_48h),
            "expiring_7d": len(expiring_7d),
            "carriers_expiring": expiring_48h['Carrier'].value_counts().head(5).to_dict()
                                 if len(expiring_48h) > 0 else {},
        }

    def _check_shipment_risks(self) -> dict:
        """Scan shipments for risks — delays, stale stages."""
        state = dal.load_shipment_state()
        shipments = state.get("shipments", {})

        at_risk = 0
        stale = 0
        delayed = 0
        today = date.today()

        for sid, rec in shipments.items():
            stage = rec.get("stage", "")
            if stage == "PAYMENT_CONFIRMED":
                continue

            # Check for risk records
            if rec.get("risks"):
                at_risk += 1

            # Check for stale (no update in 7+ days)
            updated = rec.get("updated_at", "")
            if updated:
                try:
                    last_update = datetime.fromisoformat(updated[:10]).date()
                    if (today - last_update).days > 7:
                        stale += 1
                except (ValueError, TypeError):
                    pass

            # Check for delays
            if rec.get("delay_count", 0) > 0:
                delayed += 1

        return {
            "total": len(shipments),
            "active": sum(1 for s in shipments.values()
                          if s.get("stage") != "PAYMENT_CONFIRMED"),
            "at_risk": at_risk,
            "stale": stale,
            "delayed": delayed,
        }

    def _check_system_health(self) -> dict:
        """Overall system health score."""
        checks = {}
        score = 100

        # 1. Parquet loaded?
        df = dal.load_rates()
        checks["parquet_loaded"] = df is not None
        if df is None:
            score -= 30

        # 2. Data freshness
        loaded_at = dal.rates_loaded_at
        checks["rates_cached"] = loaded_at is not None

        # 3. Shipment state accessible?
        try:
            state = dal.load_shipment_state()
            checks["shipment_state"] = bool(state)
        except Exception:
            checks["shipment_state"] = False
            score -= 20

        # 4. Quotes store working?
        try:
            quotes = dal.load_quotes_data()
            checks["quotes_store"] = bool(quotes)
        except Exception:
            checks["quotes_store"] = False
            score -= 15

        # 5. Customer rules loaded?
        try:
            rules = dal.get_customers_raw()
            checks["customer_rules"] = bool(rules)
        except Exception:
            checks["customer_rules"] = False
            score -= 10

        # 6. Event bus active?
        checks["event_bus"] = True
        checks["event_count"] = bus.stats["total_logged"]

        return {"score": max(0, score), "checks": checks}

    @property
    def status(self) -> dict:
        return {
            "enabled": os.environ.get("EVALUATOR_ENABLED", "true").lower() == "true",
            "schedule": "daily 06:00",
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_report": self._last_report,
            "scheduler_running": bool(self._scheduler and self._scheduler.running),
        }


# Singleton
evaluator_worker = EvaluatorWorker()
