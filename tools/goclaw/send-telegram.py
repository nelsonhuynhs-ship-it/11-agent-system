# -*- coding: utf-8 -*-
"""
send-telegram.py — GoClaw Tool: Send Telegram message via Bot API.

Usage:
    python send-telegram.py --message "Hello Nelson"
    python send-telegram.py --message "<b>Alert</b>" --parse-mode HTML
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

# ── Load .env from tools/goclaw/.env or api/.env ─────────────────────────────
_env_candidates = [
    Path(__file__).parent / ".env",                          # tools/goclaw/.env
    Path(__file__).parent.parent.parent / "api" / ".env",   # api/.env
]
for _env_path in _env_candidates:
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                if _k.strip() not in os.environ:
                    os.environ[_k.strip()] = _v.strip()

# ── Config from environment ──────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_TOKEN", ""))
DEFAULT_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def send(message: str, chat_id: str = "", parse_mode: str = "HTML") -> dict:
    """Send a Telegram message. Returns {"sent": bool, "message_id": int}."""
    chat = chat_id or DEFAULT_CHAT
    if not TOKEN:
        return {"sent": False, "error": "TELEGRAM_BOT_TOKEN not set"}
    if not chat:
        return {"sent": False, "error": "TELEGRAM_CHAT_ID not set"}

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    resp = httpx.post(url, json={
        "chat_id": chat,
        "text": message,
        "parse_mode": parse_mode,
    }, timeout=15)
    data = resp.json()
    return {
        "sent": data.get("ok", False),
        "message_id": data.get("result", {}).get("message_id"),
        "error": data.get("description") if not data.get("ok") else None,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Send Telegram message")
    p.add_argument("--message", "-m", required=True, help="Message text")
    p.add_argument("--chat-id", default="", help="Override chat ID")
    p.add_argument("--parse-mode", default="HTML", choices=["HTML", "Markdown", "MarkdownV2"])
    args = p.parse_args()

    result = send(args.message, args.chat_id, args.parse_mode)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["sent"] else 1)
