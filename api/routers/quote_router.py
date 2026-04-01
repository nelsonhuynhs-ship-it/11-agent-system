# -*- coding: utf-8 -*-
"""
quote_router.py — Quote Endpoints
====================================
All quote-related endpoints using quote_store module.
"""
from __future__ import annotations

import sys
import os
from typing import Optional

from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/quotes", tags=["Quotes"])

# Lazy imports for optional modules
_quote_store = None
_quote_intelligence = None


def _get_quote_store():
    global _quote_store
    if _quote_store is None:
        try:
            import quote_store
            _quote_store = quote_store
        except ImportError:
            return None
    return _quote_store


def _get_intelligence():
    global _quote_intelligence
    if _quote_intelligence is None:
        try:
            import quote_intelligence
            _quote_intelligence = quote_intelligence
        except ImportError:
            return None
    return _quote_intelligence


@router.get("")
def get_quotes(status: Optional[str] = Query(None)):
    """List all quotes, optionally filtered by status."""
    qs = _get_quote_store()
    if not qs:
        return {"quotes": [], "stats": {}, "error": "Quote store not loaded"}
    quotes = qs.list_quotes(status)
    stats = qs.get_quote_stats()
    return {"quotes": quotes, "stats": stats, "total": len(quotes)}


@router.post("")
def create_quote(payload: dict):
    """Create a new multi-carrier/container quote."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded"}
    try:
        quote = qs.create_quote(payload)
        return {"quote": quote, "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}


@router.get("/intelligence")
def get_quote_intelligence():
    """Get full intelligence dashboard."""
    qs = _get_quote_store()
    qi = _get_intelligence()
    if not qs:
        return {"error": "Quote store not loaded"}
    if not qi:
        return {"error": "Intelligence engine not loaded"}
    try:
        quotes = qs.list_quotes()
        report = qi.get_intelligence_report(quotes)
        return report
    except Exception as e:
        return {"error": str(e), "quotes": [], "alerts": [], "price_changes": []}


@router.get("/{quote_id}")
def get_quote(quote_id: str):
    """Get a single quote by ID."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded"}
    quote = qs.get_quote(quote_id)
    if not quote:
        return {"error": "Quote not found"}
    return {"quote": quote}


@router.put("/{quote_id}")
def update_quote(quote_id: str, payload: dict):
    """Update a quote's editable fields."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded"}
    quote = qs.update_quote(quote_id, payload)
    if not quote:
        return {"error": "Quote not found or already converted"}
    return {"quote": quote, "success": True}


@router.patch("/{quote_id}/status")
def patch_quote_status(quote_id: str, payload: dict):
    """Change quote status."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded"}
    new_status = payload.get("status", "")
    quote = qs.update_status(quote_id, new_status)
    if not quote:
        return {"error": "Quote not found or invalid status"}
    return {"quote": quote, "success": True}


@router.post("/{quote_id}/convert")
def convert_quote(quote_id: str, payload: dict = None):
    """Convert an ACCEPTED quote into a tracked shipment."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded", "success": False}
    winning_carrier = ""
    if payload:
        winning_carrier = payload.get("winning_carrier", "")
    result = qs.convert_to_shipment(quote_id, winning_carrier)
    return result


@router.post("/{quote_id}/requote")
def requote(quote_id: str, payload: dict = None):
    """Create a new version of a quote with updated rates."""
    qs = _get_quote_store()
    if not qs:
        return {"error": "Quote store not loaded"}
    new_carriers = None
    if payload:
        new_carriers = payload.get("carriers")
    quote = qs.requote(quote_id, new_carriers)
    if not quote:
        return {"error": "Quote not found"}
    return {"quote": quote, "success": True}


@router.get("/{quote_id}/versions")
def get_quote_versions(quote_id: str):
    """Get all versions (history) of a quote chain."""
    qs = _get_quote_store()
    if not qs:
        return {"versions": [], "error": "Quote store not loaded"}
    versions = qs.get_quote_versions(quote_id)
    return {"versions": versions, "total": len(versions)}


# ══════════════════════════════════════════════════════════════════════════════
# nelson-flow: QUOTE BUILDER endpoints
# ══════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel
from typing import Dict


class QuoteBuildRequest(BaseModel):
    """Input for Quote Builder flow (nelson-flow Step 2)."""
    rate_data: dict                          # Single rate from /api/pricing/check
    customer: str                            # Customer name/code
    customer_segment: str = "BCO"            # BCO / Agent / Direct
    margin_pct: Optional[float] = None       # Margin as % (e.g. 10 = +10%)
    margin_fixed: Optional[float] = None     # Fixed margin (e.g. 150 = +$150)
    surcharges: Optional[Dict[str, float]] = None  # {"THC": 150, "DOC": 50}
    valid_days: int = 14


class QuoteSendRequest(BaseModel):
    """Input for sending a quote to customer."""
    channel: str = "telegram"  # telegram | email
    customer_id: Optional[str] = None
    message: Optional[str] = None


@router.post("/build")
def build_quote(req: QuoteBuildRequest):
    """
    Build a quote from pricing data — nelson-flow core endpoint.

    Input: rate_data (from /api/pricing/check) + margin + surcharges
    Output: buying, selling, profit, AJ cost breakdown, quote_id

    Used by: Telegram Bot, WebApp, ERP Excel (same data, different display)
    """
    try:
        from services.quote_builder import build_quote as _build, format_quote_telegram

        quote = _build(
            rate_data=req.rate_data,
            customer=req.customer,
            customer_segment=req.customer_segment,
            margin_pct=req.margin_pct,
            margin_fixed=req.margin_fixed,
            surcharges=req.surcharges,
            valid_days=req.valid_days,
        )

        # Also persist to quote store if available
        qs = _get_quote_store()
        if qs:
            try:
                stored = qs.create_quote({
                    "customer": req.customer,
                    "pol": quote["pol"],
                    "pod": quote["pod"],
                    "place": quote.get("place", ""),
                    "service_type": "CY-CY",
                })
                if stored:
                    quote["store_quote_id"] = stored.get("quote_id")
            except Exception:
                pass  # Store is optional

        # Telegram-ready format
        quote["telegram_text"] = format_quote_telegram(quote)

        # Publish event
        try:
            from event_bus import bus, Event
            bus.publish(Event(
                type="quote.built",
                payload={
                    "quote_id": quote["quote_id"],
                    "customer": req.customer,
                    "carrier": quote["carrier"],
                    "selling_rate": quote["selling_rate"],
                },
                source="api",
            ))
        except Exception:
            pass

        return {"quote": quote, "success": True}

    except Exception as e:
        return {"error": str(e), "success": False}


@router.post("/{quote_id}/send")
def send_quote(quote_id: str, req: QuoteSendRequest):
    """
    Send a quote to customer via Telegram or Email.

    First retrieves the quote, then formats and sends via chosen channel.
    """
    try:
        from services.quote_builder import format_quote_telegram, format_quote_email

        # Get quote from store
        qs = _get_quote_store()
        if not qs:
            return {"error": "Quote store not loaded", "success": False}

        quote = qs.get_quote(quote_id)
        if not quote:
            return {"error": f"Quote {quote_id} not found", "success": False}

        if req.channel == "telegram":
            formatted = format_quote_telegram(quote)
            return {
                "success": True,
                "channel": "telegram",
                "formatted_text": formatted,
                "quote_id": quote_id,
                "note": "Use Bot API to send this text to customer",
            }

        elif req.channel == "email":
            email_draft = format_quote_email(quote)
            return {
                "success": True,
                "channel": "email",
                "email": email_draft,
                "quote_id": quote_id,
            }

        else:
            return {"error": f"Unknown channel: {req.channel}", "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}
