# -*- coding: utf-8 -*-
"""
quote_builder.py — Quote Builder Business Logic (nelson-flow)
===============================================================
Core business logic for building quotes from pricing data.

Formula: Selling = Buying + Margin
         Buying  = Base O/F + HDL Fee
         Profit  = Selling - Buying

Used by: POST /api/quotes/build
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def build_quote(
    rate_data: dict,
    customer: str,
    customer_segment: str = "BCO",
    margin_pct: Optional[float] = None,
    margin_fixed: Optional[float] = None,
    surcharges: Optional[Dict[str, float]] = None,
    valid_days: int = 14,
) -> dict:
    """
    Build a quote from pricing check result.

    Args:
        rate_data: Single rate from POST /api/pricing/check result
        customer: Customer name/code
        customer_segment: BCO / Agent / Direct
        margin_pct: Margin as percentage (e.g. 10 = 10%)
        margin_fixed: Fixed margin amount (e.g. 150 = $150)
        surcharges: Additional surcharges {"name": amount}
        valid_days: Quote validity in days

    Returns:
        Complete quote with buying, selling, profit, cost breakdown
    """
    # Base values from rate
    base_of = float(rate_data.get("amount", 0))
    hdl_fee = float(rate_data.get("hdl_fee", 0))

    # Buying = Base O/F + HDL Fee
    buying = base_of + hdl_fee

    # Calculate margin
    if margin_fixed is not None:
        margin = margin_fixed
    elif margin_pct is not None:
        margin = round(buying * (margin_pct / 100), 2)
    else:
        # Default: 10% margin
        margin = round(buying * 0.10, 2)

    # Total surcharges
    total_surcharges = sum((surcharges or {}).values())

    # Selling = Buying + Margin + Surcharges
    selling = buying + margin + total_surcharges

    # Profit = Selling - Buying
    profit = selling - buying

    # Generate quote ID
    quote_id = f"Q{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    # Validity
    now = datetime.now()
    valid_until = now + timedelta(days=valid_days)

    # Cost breakdown (AJ column format for ERP)
    cost_breakdown = build_cost_breakdown(
        base_of=base_of,
        hdl_fee=hdl_fee,
        margin=margin,
        surcharges=surcharges or {},
        carrier=rate_data.get("carrier", ""),
    )

    return {
        "quote_id": quote_id,
        "customer": customer,
        "customer_segment": customer_segment,
        "carrier": rate_data.get("carrier", ""),
        "pol": rate_data.get("pol", ""),
        "pod": rate_data.get("pod", ""),
        "place": rate_data.get("place", ""),
        "container": rate_data.get("container", ""),
        "is_soc": rate_data.get("is_soc", False),
        # Pricing
        "base_ocean_freight": base_of,
        "hdl_fee": hdl_fee,
        "buying_rate": round(buying, 2),
        "margin": round(margin, 2),
        "margin_pct": margin_pct,
        "surcharges": surcharges or {},
        "total_surcharges": round(total_surcharges, 2),
        "selling_rate": round(selling, 2),
        "profit": round(profit, 2),
        "profit_pct": round((profit / buying * 100), 1) if buying > 0 else 0,
        # Cost breakdown for ERP (AJ format)
        "cost_breakdown": cost_breakdown,
        # Metadata
        "rate_type": rate_data.get("rate_type", ""),
        "transit": rate_data.get("transit", ""),
        "freetime": rate_data.get("freetime_det", ""),
        "rate_effective": rate_data.get("effective", ""),
        "rate_expiry": rate_data.get("expiry", ""),
        "valid_until": valid_until.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "status": "DRAFT",
    }


def build_cost_breakdown(
    base_of: float,
    hdl_fee: float,
    margin: float,
    surcharges: Dict[str, float],
    carrier: str = "",
) -> List[dict]:
    """
    Build AJ-column cost breakdown for ERP Excel.

    Format matches ERP columns:
    S/C | COST | HDL FEE | CAR COM
    """
    breakdown = [
        {"item": "O/F (Ocean Freight)", "amount": base_of, "type": "COST"},
        {"item": "HDL Fee", "amount": hdl_fee, "type": "HDL FEE"},
    ]

    for name, amount in surcharges.items():
        breakdown.append({
            "item": name, "amount": amount, "type": "S/C"
        })

    breakdown.append({
        "item": "Markup/Commission", "amount": margin, "type": "CAR COM"
    })

    total = sum(item["amount"] for item in breakdown)
    breakdown.append({
        "item": "TOTAL SELLING", "amount": round(total, 2), "type": "TOTAL"
    })

    return breakdown


def format_quote_telegram(quote: dict) -> str:
    """Format quote for Telegram message output."""
    soc_tag = " [SOC]" if quote.get("is_soc") else ""
    lines = [
        f"📊 {quote['pol']} → {quote.get('place') or quote['pod']} | {quote['customer']}",
        "━" * 30,
        f"🚢 {quote['carrier']}{soc_tag}",
        f"📦 {quote['container']}",
        "",
        f"  O/F:     ${quote['base_ocean_freight']:,.0f}",
        f"  HDL:     ${quote['hdl_fee']:,.0f}",
        f"  Buying:  ${quote['buying_rate']:,.0f}",
        f"  Margin:  ${quote['margin']:,.0f} ({quote.get('profit_pct', 0):.0f}%)",
    ]

    if quote.get("surcharges"):
        for name, amt in quote["surcharges"].items():
            lines.append(f"  {name}: ${amt:,.0f}")

    lines.extend([
        f"  ─────────────",
        f"  Selling: ${quote['selling_rate']:,.0f}",
        f"  Profit:  ${quote['profit']:,.0f}",
        "",
        f"⏰ Valid until: {quote['valid_until']}",
        f"🆔 {quote['quote_id']}",
    ])

    if quote.get("transit"):
        lines.append(f"🚢 Transit: {quote['transit']}")
    if quote.get("freetime"):
        lines.append(f"📅 Freetime: {quote['freetime']}")

    return "\n".join(lines)


def format_quote_email(quote: dict) -> dict:
    """Format quote as email draft."""
    subject = (
        f"Rate Offer - {quote['carrier']} "
        f"{quote['pol']}→{quote.get('place') or quote['pod']} "
        f"{quote['container']}"
    )

    body = f"""Dear {quote['customer']},

Please find our rate offer below:

Carrier: {quote['carrier']}
Routing: {quote['pol']} → {quote.get('place') or quote['pod']}
Container: {quote['container']}
Rate: USD {quote['selling_rate']:,.0f} / {quote['container']}
Transit: {quote.get('transit', 'TBA')}
Freetime: {quote.get('freetime', 'As per tariff')}
Valid until: {quote['valid_until']}

Please let us know if you'd like to proceed with a booking.

Best regards,
Nelson Freight
"""

    return {
        "subject": subject,
        "body": body,
        "quote_id": quote["quote_id"],
    }
