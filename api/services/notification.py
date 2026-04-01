# -*- coding: utf-8 -*-
"""
notification.py — Alert Dispatch Service
==========================================
Sends alerts to configured channels:
- Telegram (via existing bot)
- WebSocket (future — real-time WebApp alerts)
- Email (future)

Subscribes to event bus for alert.triggered events.
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional

log = logging.getLogger("nelson.notification")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_bus import bus, Event

# Telegram config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "")

# Alert history (in-memory → will be PostgreSQL)
_alert_history: list[dict] = []
MAX_HISTORY = 200


class NotificationService:
    """
    Multi-channel notification dispatch.
    Currently supports: Telegram.
    Future: WebSocket push, Email.
    """

    def __init__(self):
        self._telegram_available = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    def start(self):
        """Subscribe to alert events."""
        bus.subscribe("alert.triggered", self._on_alert)
        bus.subscribe("rate.expired", self._on_rate_expired)
        log.info("Notification service started (telegram=%s)",
                 "ready" if self._telegram_available else "not configured")

    def _on_alert(self, event: Event):
        """Handle generic alert events."""
        payload = event.payload
        alert = {
            "type": payload.get("type", "UNKNOWN"),
            "severity": payload.get("severity", "info"),
            "detail": payload,
            "timestamp": event.timestamp,
            "dispatched": False,
        }
        _alert_history.append(alert)
        if len(_alert_history) > MAX_HISTORY:
            _alert_history.pop(0)

        # Dispatch to Telegram for high-severity alerts
        if payload.get("severity") in ("high", "critical"):
            self._send_telegram(self._format_alert(payload))
            alert["dispatched"] = True

    def _on_rate_expired(self, event: Event):
        """Handle rate expiry events."""
        count = event.payload.get("count", 0)
        carriers = event.payload.get("carriers", [])
        severity = event.payload.get("severity", "medium")

        msg = (f"⚠️ Rate Expiry Alert\n"
               f"━━━━━━━━━━━━━━━\n"
               f"Rates expiring in 48h: {count}\n"
               f"Carriers: {', '.join(carriers)}\n"
               f"Action: Update pricing from carriers")

        _alert_history.append({
            "type": "RATE_EXPIRY",
            "severity": severity,
            "detail": event.payload,
            "timestamp": event.timestamp,
            "dispatched": severity in ("high", "critical"),
        })

        if severity in ("high", "critical"):
            self._send_telegram(msg)

    def _format_alert(self, payload: dict) -> str:
        """Format alert payload as Telegram message."""
        alert_type = payload.get("type", "ALERT")
        severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}
        emoji = severity_emoji.get(payload.get("severity", "info"), "ℹ️")

        lines = [f"{emoji} {alert_type}", "━━━━━━━━━━━━━━━"]
        for key, val in payload.items():
            if key not in ("type", "severity"):
                lines.append(f"{key}: {val}")
        return "\n".join(lines)

    def _send_telegram(self, message: str):
        """Send message via Telegram Bot API."""
        if not self._telegram_available:
            log.info("Telegram alert (not configured): %s", message[:100])
            return

        try:
            import httpx
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = httpx.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=5.0)
            if resp.status_code == 200:
                log.info("Telegram alert sent")
            else:
                log.warning("Telegram alert failed: %s", resp.text)
        except Exception as e:
            log.error("Telegram send failed: %s", e)

    @staticmethod
    def get_alert_history(limit: int = 50, severity: Optional[str] = None) -> list:
        """Get recent alert history."""
        alerts = _alert_history
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        return alerts[-limit:]

    @property
    def status(self) -> dict:
        return {
            "telegram_configured": self._telegram_available,
            "total_alerts": len(_alert_history),
            "high_severity": sum(1 for a in _alert_history
                                 if a.get("severity") in ("high", "critical")),
            "dispatched": sum(1 for a in _alert_history if a.get("dispatched")),
        }


# Singleton
notification_service = NotificationService()
