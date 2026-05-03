# -*- coding: utf-8 -*-
"""ai_email.py — Email AI features using MiniMax + Nelson policy schema."""

from __future__ import annotations

import json
import logging
from typing import Optional

from .minimax import minimax
from .minimax.policy_loader import build_system_prompt

log = logging.getLogger(__name__)


def _parse_json_response(text: str) -> dict:
    """Try to parse JSON from model response; return empty dict on failure."""
    try:
        return json.loads(text)
    except Exception:
        log.warning("ai_email: failed to parse JSON response: %s", text[:100])
        return {}


def summarize_email(body: str, sender: str) -> dict:
    """
    Summarize email content.

    Returns: {summary: str, sentiment: str, action: str, urgency: str}
    Uses MiniMax-Text-01 with policy schema.
    """
    system = build_system_prompt("summarize_email")
    prompt = f"From: {sender}\n\n{body}"
    result = minimax.text(prompt, system=system, max_tokens=256, temperature=0.0)
    parsed = _parse_json_response(result)
    return {
        "summary": parsed.get("summary", result),
        "sentiment": parsed.get("sentiment", "neutral"),
        "action": parsed.get("action", "none"),
        "urgency": parsed.get("urgency", "normal"),
    }


def draft_reply(incoming_email: dict, cnee_context: dict) -> str:
    """
    Draft reply to incoming email using CNEE context.

    incoming_email: {subject, body, sender}
    cnee_context: {name, campaign, history, preferred_carriers, preferred_pods}
    Returns: reply body string
    """
    system = build_system_prompt("draft_reply")
    prompt = f"""
Incoming email:
Subject: {incoming_email.get('subject', '')}
From: {incoming_email.get('sender', '')}
Body: {incoming_email.get('body', '')}

CNEE Context:
Name: {cnee_context.get('name', '')}
Campaign: {cnee_context.get('campaign', '')}
Preferred PODs: {', '.join(cnee_context.get('preferred_pods', []))}
Preferred Carriers: {', '.join(cnee_context.get('preferred_carriers', []))}
    """.strip()
    return minimax.text(prompt, system=system, max_tokens=512, temperature=0.4)


def suggest_next_sentence(thread_history: list[str], draft_so_far: str) -> str:
    """
    Suggest next sentence given thread history and current draft.

    thread_history: list of message strings
    draft_so_far: current draft email text
    Returns: next sentence suggestion string
    """
    system = build_system_prompt("compose_suggestion")
    history_text = "\n".join(f"[{i}] {m}" for i, m in enumerate(thread_history[-5:]))
    prompt = f"""
Thread history (last 5 messages):
{history_text}

Current draft:
{draft_so_far}

Suggest the next sentence to continue this email professionally:
    """.strip()
    return minimax.text(prompt, system=system, max_tokens=128, temperature=0.4)