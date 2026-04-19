# -*- coding: utf-8 -*-
"""
llm_extract_reply.py — LLM-powered reply context extractor  v1.0
=================================================================
Extracts structured sales intelligence from CNEE reply emails.

Reuses MiniMax client pattern from llm_client.py.

Modes:
  REAL mode  : MINIMAX_API_KEY set → HTTP call
  MOCK mode  : no key → returns canned stub (for CI / dry-run)

Public API:
    extract_reply_context(subject, body, cnee_email) -> dict | None

Output schema:
    {
        preferred_pods      : list[str]    e.g. ["USLAX", "USSAV"]
        preferred_carriers  : list[str]    e.g. ["HPL", "MSC"]
        preferred_markup    : int | null   USD per container
        volume_est          : str | null   e.g. "2 x 40HQ per month"
        urgency             : "high" | "medium" | "low"
        intent              : str          e.g. "price_inquiry", "booking_intent", "negotiating"
        sentiment           : str          e.g. "POSITIVE", "NEUTRAL", "NEGATIVE"
        quote_snippet       : str          ≤ 200 chars verbatim from email
    }
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ── MiniMax endpoint (reuse same config as llm_client.py) ────────────────────
_DEFAULT_ENDPOINT = "https://api.minimax.io/v1/text/chatcompletion_v2"
_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2")  # Nelson key supports M2
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0

# ── System prompt ─────────────────────────────────────────────────────────────
_REPLY_EXTRACTION_PROMPT = """You are a freight-sales intelligence analyst for a NVOCC (Nelson Freight, Vietnam→USA/Canada lane).
Extract structured shipping preferences from the customer's email reply. Output valid JSON only.

Schema (all fields required, use null if not mentioned):
{
  "preferred_pods": ["USLAX"|"USSAV"|"USNYC"|"USORF"|"USCHS"|"USHOU"|"USCHI"|"USTIW"|"USLGB"|"USBOS"|"CAVAN"|"CAMTR"],
  "preferred_carriers": ["HPL"|"MSC"|"COSCO"|"OOCL"|"EMC"|"ZIM"|"YML"|"ONE"|"PIL"|"WHL"|"SITC"],
  "preferred_markup": null,
  "volume_est": null,
  "urgency": "high"|"medium"|"low",
  "intent": "price_inquiry"|"booking_intent"|"negotiating"|"not_interested"|"requesting_info"|"complaint"|"general",
  "sentiment": "POSITIVE"|"NEUTRAL"|"NEGATIVE",
  "quote_snippet": ""
}

Rules:
- preferred_pods: only include if explicitly mentioned. Max 5.
- preferred_carriers: only include if explicitly mentioned. Max 5.
- preferred_markup: integer USD above base rate if customer mentions budget/target rate. null otherwise.
- volume_est: quoted string like "3 x 40HQ per month" if mentioned. null otherwise.
- urgency: "high" if words like urgent/asap/this week; "low" if no timeline; else "medium".
- intent: pick the single best match from the enum.
- sentiment: overall tone of the email.
- quote_snippet: most relevant verbatim excerpt, max 200 chars.

Output JSON only. No markdown. No explanation."""

# ── Mock response ─────────────────────────────────────────────────────────────
_MOCK_RESULT: dict = {
    "preferred_pods": [],
    "preferred_carriers": [],
    "preferred_markup": None,
    "volume_est": None,
    "urgency": "medium",
    "intent": "price_inquiry",
    "sentiment": "NEUTRAL",
    "quote_snippet": "[MOCK] Please send me your best rates for this lane.",
}


def _get_api_key() -> Optional[str]:
    return os.environ.get("MINIMAX_API_KEY")


def _get_endpoint() -> str:
    return os.environ.get("MINIMAX_API_URL", _DEFAULT_ENDPOINT)


def _call_api(text: str) -> Optional[dict]:
    """Single HTTP call. Returns parsed dict or None on failure."""
    api_key = _get_api_key()
    endpoint = _get_endpoint()

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _REPLY_EXTRACTION_PROMPT},
            {"role": "user", "content": text[:3000]},  # cap to avoid token overrun
        ],
        "temperature": 0.0,
        "max_tokens": 500,  # structured output is compact
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
                line for line in lines if not line.startswith("```")
            ).strip()

        return json.loads(content)

    except httpx.HTTPStatusError as exc:
        log.warning("MiniMax HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
    except json.JSONDecodeError as exc:
        log.warning("Reply extractor response not valid JSON: %s", exc)
    except Exception as exc:
        log.warning("Reply extractor call error: %s", exc)

    return None


def _mock_extract(body: str) -> dict:
    """Return canned mock with simple heuristic overrides for testing."""
    stub = dict(_MOCK_RESULT)
    body_low = body.lower()

    # Urgency
    if any(w in body_low for w in ("urgent", "asap", "immediately", "this week")):
        stub["urgency"] = "high"
    elif any(w in body_low for w in ("no rush", "later", "next month")):
        stub["urgency"] = "low"

    # Intent
    if any(w in body_low for w in ("book", "booking", "confirm", "proceed")):
        stub["intent"] = "booking_intent"
    elif any(w in body_low for w in ("not interested", "unsubscribe", "remove")):
        stub["intent"] = "not_interested"
    elif any(w in body_low for w in ("best rate", "price", "quote", "rate")):
        stub["intent"] = "price_inquiry"

    # Sentiment
    if any(w in body_low for w in ("thank", "great", "good", "excellent", "pleased")):
        stub["sentiment"] = "POSITIVE"
    elif any(w in body_low for w in ("complain", "issue", "problem", "disappointed")):
        stub["sentiment"] = "NEGATIVE"

    return stub


def extract_reply_context(
    subject: str,
    body: str,
    cnee_email: str = "",
) -> Optional[dict]:
    """Extract structured reply context from email.

    Args:
        subject     : Email subject line.
        body        : Email body (plain text preferred).
        cnee_email  : Sender email (for logging only).

    Returns:
        Structured dict or None if API failed after retries.
        In MOCK mode (no API key), always returns a dict.
    """
    # Combine subject + body for richer context
    email_text = f"Subject: {subject}\n\n{body}"

    api_key = _get_api_key()
    if not api_key:
        log.info("MOCK mode (MINIMAX_API_KEY not set) — extract_reply_context for %s", cnee_email)
        return _mock_extract(body)

    for attempt in range(1, _MAX_RETRIES + 1):
        result = _call_api(email_text)
        if result is not None:
            # Validate and normalise
            return _normalise(result)

        if attempt < _MAX_RETRIES:
            wait = _BACKOFF_BASE ** attempt
            log.warning(
                "extract_reply_context attempt %d/%d failed — retry in %.0fs",
                attempt, _MAX_RETRIES, wait,
            )
            time.sleep(wait)
        else:
            log.error(
                "extract_reply_context failed after %d attempts for %s",
                _MAX_RETRIES, cnee_email,
            )

    return None


def _normalise(raw: dict) -> dict:
    """Ensure all expected keys are present and typed correctly."""
    valid_urgency = {"high", "medium", "low"}
    valid_sentiment = {"POSITIVE", "NEUTRAL", "NEGATIVE"}
    valid_intent = {
        "price_inquiry", "booking_intent", "negotiating",
        "not_interested", "requesting_info", "complaint", "general",
    }

    return {
        "preferred_pods": _as_str_list(raw.get("preferred_pods")),
        "preferred_carriers": _as_str_list(raw.get("preferred_carriers")),
        "preferred_markup": _as_int_or_none(raw.get("preferred_markup")),
        "volume_est": _as_str_or_none(raw.get("volume_est")),
        "urgency": raw.get("urgency", "medium") if raw.get("urgency") in valid_urgency else "medium",
        "intent": raw.get("intent", "general") if raw.get("intent") in valid_intent else "general",
        "sentiment": raw.get("sentiment", "NEUTRAL") if raw.get("sentiment") in valid_sentiment else "NEUTRAL",
        "quote_snippet": str(raw.get("quote_snippet", ""))[:200],
    }


def _as_str_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip().upper() for x in v if x]
    return []


def _as_int_or_none(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_str_or_none(v) -> Optional[str]:
    if v is None or str(v).strip().lower() in ("", "null", "none"):
        return None
    return str(v).strip()
