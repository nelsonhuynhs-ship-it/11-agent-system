"""
email_engine.scanner.telegram
=============================
DISABLED 2026-04-26 per user request — scanner alerts no longer sent to Telegram.

Bot token + chat_id retained in env / .env files for other future use cases
(remote terminal task dispatch via Tailscale, etc.).

To re-enable: restore previous version from git history.

Contract preserved (no caller changes needed):
    send_alert(message: str) -> bool          # always returns True (silent no-op)
    send_batch_alert(alerts: list[str]) -> bool   # always returns True
"""
from __future__ import annotations

import logging
from typing import Iterable

log = logging.getLogger(__name__)


def send_alert(message: str) -> bool:
    """No-op stub. Logs at DEBUG only."""
    log.debug("scanner.telegram.send_alert disabled — message dropped (%d chars)", len(message))
    return True


def send_batch_alert(alerts: Iterable[str]) -> bool:
    """No-op stub. Logs at DEBUG only."""
    items = [a for a in alerts if a]
    log.debug("scanner.telegram.send_batch_alert disabled — %d alerts dropped", len(items))
    return True
