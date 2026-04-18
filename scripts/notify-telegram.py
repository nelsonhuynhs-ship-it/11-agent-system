#!/usr/bin/env python
"""
notify-telegram.py — Push notifications to Nelson's Telegram via @nelson_freight_bot.

One-way PUSH only. Never polls getUpdates (GoClaw owns the inbound channel).

Usage (from anything — deploy scripts, cron jobs, web_server hooks):
    python scripts/notify-telegram.py "Your message here"
    python scripts/notify-telegram.py --title "Deploy done" --body "Commit 5301e66 live on VPS"
    python scripts/notify-telegram.py --kpi  # auto KPI brief (next feature)

Env vars required (set once in Windows via [Environment]::SetEnvironmentVariable):
    BOT_TOKEN       — 8697753100:AAF0...
    ADMIN_CHAT_ID   — Nelson's Telegram user ID (from @userinfobot)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()


def send(text: str, parse_mode: str = "HTML", silent: bool = False) -> dict:
    """Send a message to Nelson's Telegram. Returns Telegram API response dict."""
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var not set")
    if not CHAT_ID:
        raise SystemExit("ADMIN_CHAT_ID env var not set (get from @userinfobot)")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text[:4000],  # Telegram limit 4096 chars; leave headroom
        "parse_mode": parse_mode,
        "disable_notification": "true" if silent else "false",
    }).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main() -> int:
    p = argparse.ArgumentParser(description="Push one-way Telegram notification")
    p.add_argument("message", nargs="?", help="Message body (or use --title/--body)")
    p.add_argument("--title", help="Optional bold title line")
    p.add_argument("--body", help="Message body (alternative to positional)")
    p.add_argument("--silent", action="store_true", help="Send without notification sound")
    p.add_argument("--dry-run", action="store_true", help="Print payload, don't send")
    args = p.parse_args()

    body = args.body or args.message or ""
    if args.title:
        text = f"<b>{args.title}</b>\n{body}" if body else f"<b>{args.title}</b>"
    else:
        text = body

    if not text.strip():
        p.error("no message content (pass message, --body, or --title)")

    if args.dry_run:
        print(f"[DRY-RUN] would send to chat {CHAT_ID}:")
        print(text)
        return 0

    r = send(text, silent=args.silent)
    if r.get("ok"):
        print(f"Sent (message_id={r.get('result', {}).get('message_id')})")
        return 0
    print(f"FAILED: {r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
