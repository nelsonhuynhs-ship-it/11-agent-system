# -*- coding: utf-8 -*-
"""
llm_client.py — MiniMax HTTP wrapper for Shipment Brain  v1.0
==============================================================
Calls MiniMax 2.7 chatcompletion API to extract structured shipment
lifecycle events from raw email text.

Modes:
  - REAL mode  : MINIMAX_API_KEY env var is set → HTTP call to MiniMax
  - MOCK mode  : no API key → returns canned stub response (for CI / dry-run)

Usage:
    from email_engine.core.llm_client import extract

    result = extract("Subject: Booking Confirmed...\n\nBody: ...")
    # result = {"shipment_ref": "HPL2604001", "event_type": "BKG_ISSUED", ...}
    # result = {"shipment_ref": None}  if no event detected
    # result = None  if LLM call failed after retries
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ─── MiniMax endpoint ─────────────────────────────────────────────────────────
_DEFAULT_ENDPOINT = "https://api.minimax.io/v1/text/chatcompletion_v2"
_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2")  # Nelson key supports M2

# ─── Retry config ─────────────────────────────────────────────────────────────
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0   # seconds; exponential: 2s, 4s, 8s

# ─── Token usage tracker (in-process; reset per run) ─────────────────────────
_token_counter: dict[str, int] = {"requests": 0, "tokens_in": 0, "tokens_out": 0}

# ─── Prompt template ──────────────────────────────────────────────────────────
EXTRACTOR_PROMPT = """System: You extract shipment lifecycle events from freight forwarder emails. Output valid JSON only.
Schema: {shipment_ref, event_type, event_date (ISO 8601), confidence (0-1), risk_flag (bool), excerpt (max 200 chars verbatim)}
Event enum: BKG_ISSUED, DRAFT_BL_ISSUED, DRAFT_BL_CONFIRMED, LOADED, ATD, DN_SENT, INVOICE_ISSUED, PAYMENT_REQUESTED, PAYMENT_CONFIRMED, COMPLETED
Shipment ref regex: \\b[A-Z]{2,6}\\d{6,10}\\b
Risk keywords: delay, problem, complaint, urgent, issue, wait
If no event detected, output {\"shipment_ref\": null}."""

# ─── Mock canned response ─────────────────────────────────────────────────────
_MOCK_RESPONSE: dict = {
    "shipment_ref": "MOCK260001",
    "event_type": "BKG_ISSUED",
    "event_date": "2026-04-18T09:00:00",
    "confidence": 0.95,
    "risk_flag": False,
    "excerpt": "[MOCK] Booking confirmed for MOCK260001 vessel APL COLUMBIA.",
}


def _get_api_key() -> Optional[str]:
    return os.environ.get("MINIMAX_API_KEY")


def _get_endpoint() -> str:
    return os.environ.get("MINIMAX_API_URL", _DEFAULT_ENDPOINT)


def _call_minimax(email_text: str) -> Optional[dict]:
    """
    Single HTTP call to MiniMax chatcompletion API.
    Returns parsed JSON dict or None on HTTP/parse error.
    """
    api_key = _get_api_key()
    endpoint = _get_endpoint()

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": EXTRACTOR_PROMPT},
            {"role": "user", "content": email_text[:4000]},  # cap to avoid token overrun
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()

        # Track token usage if vendor returns it
        usage = data.get("usage", {})
        _token_counter["requests"] += 1
        _token_counter["tokens_in"] += usage.get("prompt_tokens", 0)
        _token_counter["tokens_out"] += usage.get("completion_tokens", 0)

        # Extract content from first choice
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        # Strip markdown code fences if model wraps JSON
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                l for l in lines if not l.startswith("```")
            ).strip()

        return json.loads(content)

    except httpx.HTTPStatusError as exc:
        log.warning("MiniMax HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
    except json.JSONDecodeError as exc:
        log.warning("MiniMax response not valid JSON: %s", exc)
    except Exception as exc:
        log.warning("MiniMax call error: %s", exc)

    return None


def _mock_extract(email_text: str) -> dict:
    """
    Return a canned mock response for testing without API key.
    Varies slightly based on input to allow unit test assertions.
    """
    stub = dict(_MOCK_RESPONSE)
    text_lower = email_text.lower()

    # Crude rule-based override so mock is somewhat realistic
    risk_words = ["delay", "problem", "urgent", "complaint", "issue", "wait"]
    stub["risk_flag"] = any(w in text_lower for w in risk_words)

    for etype in [
        "PAYMENT_CONFIRMED", "PAYMENT_REQUESTED", "INVOICE_ISSUED",
        "DN_SENT", "ATD", "LOADED", "DRAFT_BL_CONFIRMED",
        "DRAFT_BL_ISSUED", "BKG_ISSUED",
    ]:
        if etype.lower().replace("_", " ") in text_lower or etype.lower() in text_lower:
            stub["event_type"] = etype
            break

    log.debug("MOCK mode: returning stub event_type=%s", stub["event_type"])
    return stub


def extract(email_text: str) -> Optional[dict]:
    """
    Extract shipment event from email text.

    - If MINIMAX_API_KEY is set: calls real MiniMax API with retry + backoff.
    - Otherwise: returns mock response (for CI / dry-run).

    Returns:
        dict  with keys shipment_ref, event_type, event_date, confidence,
              risk_flag, excerpt  — or {"shipment_ref": None} if no event,
              or None if API failed after all retries.
    """
    api_key = _get_api_key()

    if not api_key:
        log.info("MOCK mode active (MINIMAX_API_KEY not set)")
        return _mock_extract(email_text)

    # Real mode with exponential backoff
    for attempt in range(1, _MAX_RETRIES + 1):
        result = _call_minimax(email_text)
        if result is not None:
            return result

        if attempt < _MAX_RETRIES:
            wait = _BACKOFF_BASE ** attempt
            log.warning(
                "MiniMax attempt %d/%d failed — retrying in %.0fs",
                attempt, _MAX_RETRIES, wait,
            )
            time.sleep(wait)
        else:
            log.error(
                "MiniMax extraction failed after %d attempts — skipping email",
                _MAX_RETRIES,
            )

    return None


def get_token_usage() -> dict[str, int]:
    """Return accumulated token usage stats for the current process run."""
    return dict(_token_counter)


def reset_token_counter() -> None:
    """Reset token counter (call at start of each batch run)."""
    _token_counter.update({"requests": 0, "tokens_in": 0, "tokens_out": 0})
