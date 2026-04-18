# -*- coding: utf-8 -*-
"""
brief_synthesizer.py — Build Telegram-friendly markdown brief for a shipment.

Two paths:
  1. LLM path  — calls llm_client.llm_call() if Phase-02 module is available
  2. Fallback  — deterministic template built from event list (no LLM)

The fallback guarantees a usable response even when LLM is down or Phase-02
is not yet deployed.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("brief_synthesizer")

# ── LLM import (graceful — Phase 02 may not exist yet) ───────────────────────
try:
    from email_engine.core.llm_client import llm_call as _llm_call  # type: ignore
    _LLM_AVAILABLE = True
except ImportError:
    try:
        from llm_client import llm_call as _llm_call  # type: ignore
        _LLM_AVAILABLE = True
    except ImportError:
        _LLM_AVAILABLE = False
        _llm_call = None  # type: ignore

# ── Prompt template ───────────────────────────────────────────────────────────
BRIEF_SYSTEM = (
    "Bạn là trợ lý freight forwarder của Nelson. "
    "Chỉ dùng thông tin được cung cấp, không suy đoán thêm."
)

BRIEF_PROMPT = """Given shipment events + vault context, produce a concise Telegram brief in Vietnamese.

Format EXACTLY:
📦 {shipment_ref} · {customer} · {pol}→{pod} · {carrier}
[For each event in chronological order:]
{emoji} {event_type} · ({date} — 1 line excerpt)
[If any risk_flag=true events, add:]
⚠ RISK: {risk details}
[Last line:]
💬 Last: "{latest excerpt}" ({date})

Emoji rules: ✅ completed / done  🟡 in progress  ⏳ pending / waiting  ⚠ risk / alert
Keep total ≤ 15 lines.
ONLY use facts from the provided data — do not invent details.

--- SHIPMENT DATA ---
{shipment_data}

--- VAULT CONTEXT (last 2000 chars) ---
{vault_text}
"""

# ── Fallback emoji map ────────────────────────────────────────────────────────
_EVENT_EMOJI = {
    "BKG":       "✅",
    "BOOKING":   "✅",
    "ATD":       "🟡",
    "DEPARTED":  "🟡",
    "ATA":       "✅",
    "ARRIVED":   "✅",
    "INVOICE":   "✅",
    "PAYMENT":   "✅",
    "HOLD":      "⚠",
    "DELAY":     "⚠",
    "RISK":      "⚠",
    "CHANGE":    "⚠",
    "PENDING":   "⏳",
    "WAITING":   "⏳",
}

def _event_emoji(event_type: str) -> str:
    key = (event_type or "").upper()
    for k, v in _EVENT_EMOJI.items():
        if k in key:
            return v
    return "⏳"


def _fmt_date(val: Any) -> str:
    """Format date value to YYYY-MM-DD string."""
    if not val:
        return "?"
    if isinstance(val, (datetime,)):
        return val.strftime("%Y-%m-%d")
    s = str(val)[:10]  # assume ISO prefix
    return s


def _fallback_brief(shipment_row: dict, events: list[dict], vault_text: str) -> str:
    """Build deterministic brief from structured data — no LLM required."""
    ref      = shipment_row.get("shipment_id") or shipment_row.get("shipment_ref", "?")
    customer = shipment_row.get("customer_id") or shipment_row.get("customer", "?")
    pol      = shipment_row.get("pol", "?")
    pod      = shipment_row.get("pod", "?")
    carrier  = shipment_row.get("carrier", "?")

    lines = [f"📦 {ref} · {customer} · {pol}→{pod} · {carrier}"]

    # Sort events chronologically
    def _sort_key(e: dict) -> str:
        return str(e.get("event_date") or e.get("created_at") or "")

    sorted_events = sorted(events, key=_sort_key)
    risks = []

    for ev in sorted_events:
        etype   = ev.get("event_type", "UPDATE")
        edate   = _fmt_date(ev.get("event_date") or ev.get("created_at"))
        excerpt = (ev.get("excerpt") or ev.get("body_excerpt") or ev.get("raw_text") or "")[:80]
        emoji   = _event_emoji(etype)
        if ev.get("risk_flag"):
            risks.append(f"{etype} ({edate}): {excerpt}")
        lines.append(f"{emoji} {etype} · ({edate} — {excerpt})")

    for r in risks:
        lines.append(f"⚠ RISK: {r}")

    if sorted_events:
        last = sorted_events[-1]
        last_excerpt = (last.get("excerpt") or last.get("body_excerpt") or last.get("raw_text") or "N/A")[:80]
        last_date    = _fmt_date(last.get("event_date") or last.get("created_at"))
        lines.append(f'💬 Last: "{last_excerpt}" ({last_date})')

    # Cap at 15 lines
    if len(lines) > 15:
        lines = lines[:14] + [f"... (+{len(lines)-14} more events)"]

    return "\n".join(lines)


async def synthesize(
    shipment_row: dict,
    events: list[dict],
    vault_text: str = "",
) -> str:
    """Return Telegram-markdown brief.

    Uses LLM if available, falls back to deterministic template otherwise.

    Args:
        shipment_row: Single row dict from `shipments` table.
        events:       List of row dicts from `shipment_events` table.
        vault_text:   Contents of vault file (last 2000 chars).

    Returns:
        Markdown string for Telegram.
    """
    if _LLM_AVAILABLE and _llm_call is not None:
        try:
            import json as _json
            shipment_data = _json.dumps(
                {"shipment": shipment_row, "events": events},
                ensure_ascii=False,
                default=str,
            )
            prompt = BRIEF_PROMPT.format(
                shipment_ref = shipment_row.get("shipment_id", "?"),
                customer     = shipment_row.get("customer_id", "?"),
                pol          = shipment_row.get("pol", "?"),
                pod          = shipment_row.get("pod", "?"),
                carrier      = shipment_row.get("carrier", "?"),
                shipment_data= shipment_data[:3000],
                vault_text   = (vault_text or "")[:2000],
            )
            result = _llm_call(prompt=prompt, system=BRIEF_SYSTEM)
            if result and len(result.strip()) > 10:
                return result.strip()
        except Exception as exc:
            log.warning(f"LLM call failed, using fallback: {exc}")

    return _fallback_brief(shipment_row, events, vault_text)


def synthesize_sync(
    shipment_row: dict,
    events: list[dict],
    vault_text: str = "",
) -> str:
    """Synchronous wrapper — for use outside async context (e.g. tests)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — call fallback directly
            return _fallback_brief(shipment_row, events, vault_text)
        return loop.run_until_complete(synthesize(shipment_row, events, vault_text))
    except Exception:
        return _fallback_brief(shipment_row, events, vault_text)
