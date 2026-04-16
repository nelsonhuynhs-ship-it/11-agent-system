"""
Reply Analyzer — Cross-reference sales replies with Panjiva data
================================================================
UPGRADED 2026-04-16 (Phase 04):
    - Adds analyze_sentiment / classify_intent / analyze_reply primitives
      used by email_engine.scanner.handlers.handle_real_reply.
    - Keeps enrich_reply() unchanged for backward compat with any existing
      dashboard callers.

Generates enriched context for Nelson's dashboard.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)


# =========================================================
# Intent rules (shared with core/process_reply.py)
# Keep in sync — intentionally duplicated to avoid circular import.
# =========================================================
_INTENT_RULES: list[tuple[str, int, list[str]]] = [
    ("booking_intent", 5, [
        "please book", "please proceed", "go ahead", "confirm booking",
        "let's proceed", "proceed to book", "place the booking",
        "we would like to book", "book this shipment", "confirmed",
    ]),
    ("negotiating", 4, [
        "better rate", "can you do better", "competitor offer",
        "beat the price", "match the rate", "lower the rate",
        "reduce the price", "can you offer", "best rate", "what is your best",
    ]),
    ("price_inquiry", 3, [
        "your rate", "freight rate", "quote", "how much", "what is the price",
        "provide rate", "rate request", "pricing", "cost for",
        "shipping cost", "sea freight", "ocean freight", "fcl rate", "lcl rate",
        "transit time", "etd", "eta", "free time", "demurrage",
        "chào giá", "báo giá", "giá cước",
    ]),
    ("gratitude", 2, [
        "thank you", "thanks", "thank u", "appreciate", "cảm ơn",
        "noted with thanks", "noted", "well received", "received",
        "đã nhận", "đã xem",
    ]),
    ("objection", 1, [
        "too high", "not competitive", "no need", "not interested",
        "already have", "pass on this", "decline", "not suitable",
        "don't need", "không cần", "thôi", "không phù hợp",
    ]),
]

_POSITIVE_CUES = [
    "thank", "appreciate", "great", "perfect", "please proceed",
    "go ahead", "confirmed", "sounds good", "let's", "cảm ơn", "tốt",
    "proceed to book", "we would like to book",
]
_NEGATIVE_CUES = [
    "too high", "not competitive", "not interested", "decline",
    "unsubscribe", "remove me", "stop email", "không cần", "không phù hợp",
    "expensive", "can't", "cannot afford", "no thanks", "no thank",
]


def analyze_sentiment(text: str) -> str:
    """Return POSITIVE | NEUTRAL | NEGATIVE | UNKNOWN.

    Simple keyword tally — fast, deterministic, zero deps.
    """
    if not text:
        return "UNKNOWN"
    t = text.lower()
    pos = sum(1 for kw in _POSITIVE_CUES if kw in t)
    neg = sum(1 for kw in _NEGATIVE_CUES if kw in t)
    if pos == 0 and neg == 0:
        return "NEUTRAL"
    if pos > neg:
        return "POSITIVE"
    if neg > pos:
        return "NEGATIVE"
    return "NEUTRAL"


def classify_intent(subject: str, body: str) -> str:
    """Return highest-ranked intent found in subject+body.

    One of: booking_intent | negotiating | price_inquiry | gratitude | objection | general
    """
    text = f"{subject or ''} {(body or '')[:800]}".lower()
    best_rank = -1
    best_intent = "general"
    for intent_name, rank, keywords in _INTENT_RULES:
        for kw in keywords:
            if kw in text:
                if rank > best_rank:
                    best_rank = rank
                    best_intent = intent_name
                break
    return best_intent


def analyze_reply(subject: str, body: str) -> dict:
    """Combined sentiment + intent + rough confidence.

    Confidence = (# keyword hits for winning intent) / 5, capped at 1.0.
    """
    subject = subject or ""
    body = body or ""
    text = f"{subject} {body[:800]}".lower()

    intent = classify_intent(subject, body)
    sentiment = analyze_sentiment(text)

    # Count keyword hits for the winning intent (for confidence signal)
    hits = 0
    for name, _rank, kws in _INTENT_RULES:
        if name == intent:
            hits = sum(1 for kw in kws if kw in text)
            break
    confidence = min(hits / 5.0, 1.0) if intent != "general" else 0.2

    return {
        "sentiment": sentiment,
        "intent": intent,
        "confidence": round(confidence, 2),
    }


# =========================================================
# Legacy enrichment (unchanged signature for backward compat)
# =========================================================
def enrich_reply(reply_record: dict, cnee_master_path: Path) -> dict:
    """
    Given a sales_reply record, lookup customer in cnee_master.xlsx.
    Returns enriched dict with Panjiva context + recommendation text.

    Parameters
    ----------
    reply_record     : dict from sales_replies table
    cnee_master_path : Path to cnee_master.xlsx (Panjiva data)

    Returns
    -------
    dict — original record + panjiva_* fields + recommendation
    """
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed. Run: pip install pandas openpyxl")
        return {**reply_record, 'recommendation': 'Install pandas to enrich.'}

    customer = (reply_record.get('customer_name') or '').upper().strip()
    intent   = reply_record.get('intent', 'UNKNOWN')

    # Lookup in cnee_master
    panjiva_context: dict = {}
    if cnee_master_path.exists() and customer:
        try:
            df = pd.read_excel(cnee_master_path)
            df['COMPANY_UPPER'] = df['COMPANY'].astype(str).str.upper().str.strip()
            match = df[df['COMPANY_UPPER'] == customer]

            if not match.empty:
                row = match.iloc[0]
                panjiva_context = {
                    'vol_month':    row.get('TOTAL_SHIPMENT', 0),
                    'carrier':      row.get('CARRIER', ''),
                    'destination':  row.get('DESTINATION', ''),
                    'already_sent': row.get('ALREADY_SENT', 'N'),
                }
        except Exception as e:
            log.warning("Could not read cnee_master: %s", e)

    # Recommendation logic
    carrier_note = (
        f"Đang dùng {panjiva_context.get('carrier', '')} — cơ hội chuyển sang HPL."
        if panjiva_context.get('carrier') else ''
    )
    dest_note = panjiva_context.get('destination', 'họ đang dùng')
    vol_note  = panjiva_context.get('vol_month', '?')

    rec_map = {
        'HOT': (
            f"CALL NOW — {customer} đang quan tâm. {carrier_note}"
        ),
        'WARM': (
            f"Email hôm nay — gửi HPL schedule tuyến {dest_note}."
        ),
        'PRICE_FIGHT': (
            f"Kiểm tra SC — {customer} đang so sánh giá. "
            f"Volume: {vol_note} cont/tháng — đáng chase."
        ),
        'TIMING':       "Schedule follow-up sau 30 ngày.",
        'WRONG_PERSON': "Update contact trong contact_master.xlsx — tìm đúng người.",
        'REFERRAL':     "Email ngay người được giới thiệu — warm lead.",
        'NEGATIVE':     "Mark UNSUBSCRIBE trong cnee_master.",
        'AUTO_REPLY':   "Chờ họ về, kiểm tra replacement contact.",
    }

    enriched = {
        **reply_record,
        **{f'panjiva_{k}': v for k, v in panjiva_context.items()},
        'recommendation': rec_map.get(intent, 'Review manually'),
    }

    return enriched
