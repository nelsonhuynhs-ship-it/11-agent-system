# -*- coding: utf-8 -*-
"""
intelligence_worker.py — Quote Intelligence Background Worker
================================================================
Subscribes to quote events and runs intelligence calculations:
- Win probability scoring on new quotes
- Price alert detection
- Customer pattern analysis

Triggered by: event_bus events (quote.created, quote.status_changed)
Also callable manually for batch recalculation.
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional

log = logging.getLogger("nelson.workers.intelligence")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_bus import bus, Event
from data_access import dal


class IntelligenceWorker:
    """
    Reacts to quote events and enriches quotes with intelligence data.
    Subscribes to event bus for real-time processing.
    """

    def __init__(self):
        self._qi_module = None
        self._last_run: Optional[datetime] = None

    def start(self):
        """Register event handlers."""
        bus.subscribe("quote.created", self._on_quote_created)
        bus.subscribe("quote.status_changed", self._on_status_changed)
        bus.subscribe("quote.converted", self._on_quote_converted)
        log.info("Intelligence worker started — 3 event subscriptions")

    def _get_intelligence(self):
        """Lazy import quote_intelligence module."""
        if self._qi_module is None:
            try:
                import quote_intelligence
                self._qi_module = quote_intelligence
            except ImportError:
                log.warning("quote_intelligence not available")
        return self._qi_module

    def _on_quote_created(self, event: Event):
        """Handle new quote — calculate initial win probability."""
        quote_id = event.payload.get("quote_id", "")
        customer = event.payload.get("customer", "")
        log.info("Intelligence: processing new quote %s (customer: %s)", quote_id, customer)

        qi = self._get_intelligence()
        if not qi:
            return

        try:
            # Get quote data
            quote = dal.get_quote(quote_id)
            if not quote:
                return

            # Check for price alerts
            alerts = qi.check_price_alerts(quote) if hasattr(qi, 'check_price_alerts') else []
            if alerts:
                bus.publish(Event(
                    type="alert.triggered",
                    payload={
                        "type": "PRICE_ALERT",
                        "quote_id": quote_id,
                        "alerts": alerts,
                        "severity": "warning",
                    },
                    source="intelligence",
                ))
        except Exception as e:
            log.error("Intelligence processing failed for %s: %s", quote_id, e)

    def _on_status_changed(self, event: Event):
        """Track status transitions for win/loss analysis."""
        quote_id = event.payload.get("quote_id", "")
        new_status = event.payload.get("to_status", "")
        log.info("Intelligence: quote %s → %s", quote_id, new_status)

        if new_status in ("REJECTED", "CONVERTED"):
            self._record_outcome(quote_id, new_status)

    def _on_quote_converted(self, event: Event):
        """Track conversion for KPI."""
        quote_id = event.payload.get("quote_id", "")
        carrier = event.payload.get("carrier", "")
        log.info("Intelligence: quote %s converted (carrier: %s)", quote_id, carrier)

    def _record_outcome(self, quote_id: str, outcome: str):
        """Record win/loss for future analysis."""
        bus.publish(Event(
            type="system.intelligence_update",
            payload={
                "quote_id": quote_id,
                "outcome": outcome,
                "timestamp": datetime.now().isoformat(),
            },
            source="intelligence",
        ))

    def recalculate_all(self) -> dict:
        """Batch recalculation of all quote intelligence."""
        qi = self._get_intelligence()
        if not qi:
            return {"error": "Intelligence module not available"}

        try:
            quotes = dal.list_quotes()
            report = qi.get_intelligence_report(quotes) if hasattr(qi, 'get_intelligence_report') else {}
            self._last_run = datetime.now()
            return {
                "recalculated": len(quotes),
                "timestamp": self._last_run.isoformat(),
                "report_keys": list(report.keys()) if report else [],
            }
        except Exception as e:
            return {"error": str(e)}

    @property
    def status(self) -> dict:
        return {
            "enabled": True,
            "subscriptions": ["quote.created", "quote.status_changed", "quote.converted"],
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "intelligence_available": self._qi_module is not None,
        }


# Singleton
intelligence_worker = IntelligenceWorker()
