"""
email_engine.scanner.telegram
=============================
Thin Telegram alerter. Reads credentials from env (falls back to email_engine/.env).

Contract:
    send_alert(message: str) -> bool
    send_batch_alert(alerts: list[str]) -> bool

No crash on missing env — returns False and logs a warning.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_MSG = 3900  # Telegram caps at 4096 chars; leave headroom


def _load_dotenv_if_present() -> None:
    """Best-effort .env loader (no python-dotenv dependency needed)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Do not override anything already set in the real env.
            os.environ.setdefault(k, v)
    except Exception as exc:  # pragma: no cover
        log.debug("dotenv parse failed: %s", exc)


def _get_creds() -> tuple[str, str]:
    _load_dotenv_if_present()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_NELSON_CHAT_ID", "").strip()
    return token, chat_id


def send_alert(message: str) -> bool:
    """POST a single message. Returns True on HTTP 200."""
    token, chat_id = _get_creds()
    if not token or not chat_id:
        log.warning("Telegram disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_NELSON_CHAT_ID missing")
        return False

    try:
        import httpx  # in requirements.txt
    except ImportError:  # pragma: no cover
        log.error("httpx not installed — pip install httpx")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message[:_MAX_MSG],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    url = _API_URL.format(token=token)

    try:
        r = httpx.post(url, json=payload, timeout=10.0)
        if r.status_code == 200:
            return True
        log.warning("Telegram sendMessage non-200: %s %s", r.status_code, r.text[:200])
        return False
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)
        return False


def send_batch_alert(alerts: Iterable[str]) -> bool:
    """Combine alerts into a single Telegram message (joined by blank line).

    If zero alerts -> no-op, returns True.
    If >1 alert -> merges up to Telegram's size cap and sends once.
    """
    items = [a for a in alerts if a]
    if not items:
        return True
    if len(items) == 1:
        return send_alert(items[0])

    header = f"[Nelson Scanner] {len(items)} alerts"
    body = "\n\n".join(f"{i+1}. {a}" for i, a in enumerate(items))
    msg = f"<b>{header}</b>\n\n{body}"
    return send_alert(msg)
