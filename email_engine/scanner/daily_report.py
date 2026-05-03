"""
email_engine.scanner.daily_report
=================================
21:00 summary of the last 24h of intel events.

Reads from email_engine.intel.memory (sqlite). Falls back gracefully if the
intel module isn't wired yet — sends a minimal "scanner alive" message so
Nelson knows the cron is breathing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from . import telegram as tg

log = logging.getLogger(__name__)


def _fetch_events_last_24h() -> list[dict]:
    """Best-effort event fetch from intel.memory. Returns [] on any failure."""
    try:
        from email_engine.intel.memory import fetch_events  # type: ignore
    except Exception:
        log.debug("intel.memory.fetch_events unavailable — daily report runs in stub mode")
        return []

    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = fetch_events(since=since.isoformat()) or []
        # Normalise to plain dicts
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("fetch_events failed: %s", exc)
        return []


def _count(events: list[dict], key: str, value: Any) -> int:
    return sum(1 for e in events if str(e.get(key, "")).upper() == str(value).upper())


def _top_companies(events: list[dict], event_type: str, limit: int = 5) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for e in events:
        if str(e.get("event_type", "")).upper() != event_type.upper():
            continue
        name = (e.get("company") or e.get("email") or "(unknown)").strip()
        counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def generate_summary() -> str:
    """Format a Telegram-ready 24h summary. HTML mode (<b>, <i>)."""
    events = _fetch_events_last_24h()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not events:
        return (
            f"<b>Nelson Scanner — Daily Report {now}</b>\n"
            f"<i>No intel events in the last 24h.</i>\n"
            f"(Scanner is alive; intel DB empty or not yet wired.)"
        )

    bounces = _count(events, "event_type", "BOUNCE")
    replies = _count(events, "event_type", "REPLY")
    auto_replies = _count(events, "event_type", "AUTO_REPLY")
    unsubs = _count(events, "event_type", "UNSUBSCRIBE")
    promotions = _count(events, "tier_change", "PROMOTED")
    demotions = _count(events, "tier_change", "DEMOTED")

    hot = [e for e in events
           if str(e.get("event_type", "")).upper() == "REPLY"
           and str(e.get("intent", "")).lower() in ("booking_intent", "negotiating")]

    lines = [
        f"<b>Nelson Scanner — Daily Report {now}</b>",
        "",
        f"  Replies:        <b>{replies}</b>",
        f"  Hot leads:      <b>{len(hot)}</b> (booking/negotiating)",
        f"  Auto-replies:   {auto_replies}",
        f"  Bounces:        {bounces}",
        f"  Unsubscribes:   {unsubs}",
        f"  Tier promotions: {promotions}   demotions: {demotions}",
    ]

    top_replies = _top_companies(events, "REPLY", limit=5)
    if top_replies:
        lines.append("")
        lines.append("<b>Top replying CNEEs:</b>")
        for name, n in top_replies:
            lines.append(f"  - {name}: {n}")

    if hot:
        lines.append("")
        lines.append("<b>Hot leads (act today):</b>")
        for e in hot[:5]:
            company = e.get("company") or e.get("email") or "(unknown)"
            intent = e.get("intent", "?")
            lines.append(f"  * {company} — {intent}")

    return "\n".join(lines)


def send_daily_report() -> bool:
    """Called by APScheduler at 21:00. DISABLED 2026-05-03."""
    log.debug("daily_report.send_daily_report disabled — no Telegram")
    return True
