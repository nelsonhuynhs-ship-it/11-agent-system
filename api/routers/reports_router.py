# -*- coding: utf-8 -*-
"""
reports_router.py — Monthly Sales P&L Report
===============================================
Endpoint: GET /api/reports/monthly?month=YYMM

Data source: DAL shipments (shipment_state.json)
Net Profit formula: Selling - Buying + ProfitShare + CarrierKB - Tax
Tax = CarrierKB × 26.9%
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import dal

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _parse_routing(routing: str) -> tuple[str, str, str]:
    """Parse routing string like 'HPH → USLAX → Denver' into (pol, pod, place)."""
    parts = [p.strip() for p in routing.replace("→", ">").replace("->", ">").split(">")]
    pol = parts[0] if len(parts) > 0 else ""
    pod = parts[1] if len(parts) > 1 else ""
    place = parts[-1] if len(parts) > 2 else pod
    return pol, pod, place


def _parse_container(container: str, quantity: int) -> tuple[int, int, int]:
    """Parse container type + quantity into (qty_20, qty_40, qty_hc)."""
    ct = (container or "").upper()
    if "20" in ct:
        return quantity, 0, 0
    elif "HC" in ct or "HQ" in ct or "45" in ct:
        return 0, 0, quantity
    elif "40" in ct:
        return 0, quantity, 0
    return 0, 0, quantity  # default to HC


@router.get("/monthly")
def get_monthly_sales(
    month: str = Query(..., description="Format YYMM, e.g. 2602 = February 2026"),
):
    """
    Monthly Sales P&L Report.

    Filters shipments by ETD matching the given month (YYMM format).
    Returns structured rows for the Sales Report table.

    Net Profit = Selling - Buying + ProfitShare + CarrierKB - Tax
    Tax = CarrierKB × 26.9%
    """
    try:
        yy = month[:2]
        mm = month[2:]
        year_month = f"20{yy}-{mm}"  # e.g. "2026-02"

        shipments = dal.get_shipments()
        rows = []

        for s in shipments:
            etd = s.get("etd", "")

            # Match by ETD month OR by job_no prefix (SE2602/...)
            etd_match = False
            if etd:
                try:
                    etd_dt = datetime.fromisoformat(etd.replace("Z", "+00:00")) if "T" in etd else datetime.strptime(etd[:10], "%Y-%m-%d")
                    etd_match = etd_dt.strftime("%Y-%m") == year_month
                except (ValueError, TypeError):
                    pass

            # Also match by shipment ID pattern (SE2602...)
            sid = s.get("id", "")
            job_match = f"SE{month}" in sid.upper() if sid else False

            if not etd_match and not job_match:
                continue

            # Parse routing
            routing = s.get("routing", "")
            pol, pod, place = _parse_routing(routing)

            # Parse containers
            container = s.get("container", "")
            quantity = s.get("quantity", 1)
            qty_20, qty_40, qty_hc = _parse_container(container, quantity)

            # Financial data
            buying = s.get("buying_rate", 0) or 0
            selling = s.get("selling_rate", 0) or 0
            profit_share = s.get("profit_share", 0) or 0
            carrier_kb = s.get("carrier_kb", 0) or 0
            tax = round(carrier_kb * 0.269, 2)
            net_profit = round(selling - buying + profit_share + carrier_kb - tax, 2)

            rows.append({
                "shipper": s.get("customer", ""),
                "pol": pol,
                "pod": pod,
                "final_dest": place,
                "etd": etd[:10] if len(etd) >= 10 else etd,
                "eta": (s.get("eta", "") or "")[:10],
                "carrier": s.get("carrier", ""),
                "hbl": sid,  # shipment ID serves as BL reference
                "job_no": s.get("job_no", "") or sid,
                "qty_20": qty_20,
                "qty_40": qty_40,
                "qty_hc": qty_hc,
                "buying": buying,
                "selling": selling,
                "profit_share": profit_share,
                "carrier_kb": carrier_kb,
                "tax": tax,
                "net_profit": net_profit,
            })

        # Sort by ETD ascending
        rows.sort(key=lambda r: r.get("etd", ""))

        # Compute totals
        totals = {
            "buying": round(sum(r["buying"] for r in rows), 2),
            "selling": round(sum(r["selling"] for r in rows), 2),
            "profit_share": round(sum(r["profit_share"] for r in rows), 2),
            "carrier_kb": round(sum(r["carrier_kb"] for r in rows), 2),
            "tax": round(sum(r["tax"] for r in rows), 2),
            "net_profit": round(sum(r["net_profit"] for r in rows), 2),
        }

        return {
            "rows": rows,
            "month": month,
            "year_month": year_month,
            "count": len(rows),
            "totals": totals,
        }

    except Exception as e:
        return {
            "rows": [],
            "month": month,
            "count": 0,
            "error": str(e),
        }
