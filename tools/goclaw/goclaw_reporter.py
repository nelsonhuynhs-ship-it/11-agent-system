# -*- coding: utf-8 -*-
"""
goclaw-reporter.py — Shared module: report Windows task results to Fox Spirit (GoClaw VPS).

Usage in any tool script:
    from goclaw_reporter import report_to_fox
    result = run_something()
    report_to_fox("scan-outlook", result)   # fire-and-forget, never blocks
"""
import json
import os
from pathlib import Path
from datetime import datetime

# ── Load .env from same directory ────────────────────────────────────────────
_ENV_FILE = Path(__file__).parent / ".env"

def _load_env() -> dict:
    env = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

_cfg = _load_env()

GOCLAW_URL      = _cfg.get("GOCLAW_URL", "http://14.225.207.145:18790")
GATEWAY_TOKEN   = _cfg.get("GOCLAW_GATEWAY_TOKEN", "")
FOX_SPIRIT_ID   = _cfg.get("FOX_SPIRIT_ID", "fox-spirit")
TELEGRAM_CHAT   = _cfg.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOKEN  = _cfg.get("TELEGRAM_BOT_TOKEN", "")


def _format_message(task: str, result: dict) -> str:
    """Format result dict into a concise human-readable report for Fox Spirit."""
    ts = datetime.now().strftime("%H:%M %d/%m")
    machine = os.environ.get("COMPUTERNAME", "LaptopVP")

    # Build summary line based on common result keys
    status = "OK" if result.get("success") or not result.get("error") else "FAILED"
    lines = [f"[{machine}] [{ts}] Task: {task} — {status}"]

    # Add relevant metrics (skip raw/verbose keys)
    skip_keys = {"success", "dry_run", "stdout_lines", "errors", "rates", "alert_routes"}
    for k, v in result.items():
        if k not in skip_keys and v is not None and v != "" and v != []:
            lines.append(f"  {k}: {v}")

    # Show errors if any
    if result.get("error"):
        lines.append(f"  ERROR: {result['error']}")
    if result.get("errors") and result["errors"] != [""]:
        lines.append(f"  errors: {result['errors'][:2]}")

    return "\n".join(lines)


def report_to_fox(task: str, result: dict, blocking: bool = False) -> bool:
    """
    Send task result to Fox Spirit via GoClaw API.
    Non-blocking by default (fire-and-forget, timeout=5s).
    Falls back to Telegram direct if GoClaw unreachable.

    Returns True if sent successfully.
    """
    try:
        import requests
        msg = _format_message(task, result)

        resp = requests.post(
            f"{GOCLAW_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GATEWAY_TOKEN}",
                "Content-Type": "application/json",
                "X-GoClaw-User-Id": "system",
            },
            json={
                "model": FOX_SPIRIT_ID,
                "messages": [{"role": "user", "content": msg}],
                "stream": False,
            },
            timeout=5,
        )
        if resp.status_code in (200, 201):
            return True

        # GoClaw failed → fallback Telegram
        return _fallback_telegram(task, msg)

    except Exception:
        # Network down or GoClaw unavailable → silent fail (never crash the tool)
        return False


def _fallback_telegram(task: str, msg: str) -> bool:
    """Fallback: send directly to Nelson Telegram if GoClaw unreachable."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg},
            timeout=5,
        )
        return True
    except Exception:
        return False
