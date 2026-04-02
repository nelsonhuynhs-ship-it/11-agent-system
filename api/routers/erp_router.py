# -*- coding: utf-8 -*-
"""
erp_router.py — Excel ERP Integration Endpoints
==================================================
API endpoints designed for Excel VBA integration via erp_api_bridge.py.

These endpoints provide:
1. Rate matrix data (for ERP Pricing Dashboard refresh)
2. Quote sync (Excel quotes → API)
3. Job/shipment status lookup

Auth: API key via X-API-Key header (Phase 1)
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from data_access import dal

# ── Paths ─────────────────────────────────────────────────────────────────────
_ENGINE_TEST_DIR = Path(__file__).parent.parent.parent  # Engine_test/ (kept for sys.path)
if str(_ENGINE_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_TEST_DIR))
from shared import paths as _sp

router = APIRouter(prefix="/api/erp", tags=["ERP"])

# ── Auth (simple API key for ERP) ─────────────────────────────────────────────
ERP_API_KEY = os.environ.get("ERP_API_KEY", os.environ.get("NELSON_API_KEY", ""))
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_erp_key(api_key: str = Security(api_key_header)):
    """Verify ERP API key if configured."""
    if ERP_API_KEY and api_key != ERP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid ERP API key")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 1. RATE MATRIX — for Excel Pricing Dashboard refresh
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/rates-matrix")
async def erp_rates_matrix(
    pol: str = Query("HPH"),
    container: str = Query(None, description="20GP, 40GP, 40HQ — or ALL"),
    mode: str = Query("DRY", description="DRY or REEFER"),
    _auth=Security(_verify_erp_key),
):
    """
    Rate matrix for Excel ERP Pricing Dashboard.

    Returns structured data ready for openpyxl:
    - rows: [{carrier, place, container, amount, transit, freetime, eff, exp, ...}]
    - summary: {total_rates, carriers, places, last_updated}

    This replaces direct Parquet reading in refresh_erp_parquet.py
    """
    df = dal.load_rates()
    if df is None:
        raise HTTPException(status_code=503, detail="Rate data not available")

    # Filter by POL
    mask = df['POL'].str.contains(pol, case=False, na=False)

    # Filter by container type
    if container and container.upper() != "ALL":
        mask &= df['Container_Type'].str.contains(container, case=False, na=False)

    # Filter by mode (DRY vs REEFER)
    if mode.upper() == "REEFER":
        mask &= df['Container_Type'].str.contains('RF|REEFER|REF', case=False, na=False)
    else:
        mask &= ~df['Container_Type'].str.contains('RF|REEFER|REF', case=False, na=False)

    result = df[mask].copy()

    # Format for Excel
    rows = []
    for _, row in result.iterrows():
        rows.append({
            "carrier": str(row.get("Carrier", "")),
            "pol": str(row.get("POL", "")),
            "pod": str(row.get("POD", "")),
            "place": str(row.get("Place", row.get("POD", ""))),
            "container": str(row.get("Container_Type", "")),
            "amount": float(row.get("Amount", 0)),
            "charge_name": str(row.get("Charge_Name", "")),
            "transit": str(row.get("Transit", "")),
            "freetime": str(row.get("Freetime", "")),
            "effective": str(row.get("Eff", "")) if pd.notna(row.get("Eff")) else "",
            "expiry": str(row.get("Exp", "")) if pd.notna(row.get("Exp")) else "",
            "note": str(row.get("Note", "")),
        })

    # Sort by place → carrier → amount
    rows.sort(key=lambda r: (r["place"], r["carrier"], r["amount"]))

    # Summary stats
    carriers = sorted(set(r["carrier"] for r in rows))
    places = sorted(set(r["place"] for r in rows))

    return {
        "rows": rows,
        "summary": {
            "total_rates": len(rows),
            "carriers": carriers,
            "carrier_count": len(carriers),
            "places": places,
            "place_count": len(places),
            "pol": pol,
            "container_filter": container or "ALL",
            "mode": mode,
            "last_updated": dal.rates_loaded_at.isoformat() if dal.rates_loaded_at else None,
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. QUOTE SYNC — Excel → API
# ══════════════════════════════════════════════════════════════════════════════

class ERPQuotePayload(BaseModel):
    """Quote data from Excel ERP."""
    customer: str
    pol: str = "HPH"
    pod: str = ""
    place: str = ""
    carrier: str = ""
    container_type: str = "40HQ"
    ocean_freight: float = 0
    markup: float = 0
    sell_rate: float = 0
    transit: str = ""
    freetime: str = ""
    validity: str = ""
    note: str = ""


@router.post("/sync-quote")
async def erp_sync_quote(
    payload: ERPQuotePayload,
    _auth=Security(_verify_erp_key),
):
    """
    Sync a quote from Excel ERP to the API system.

    Excel VBA calls erp_api_bridge.py which calls this endpoint.
    Creates a quote in the central store for tracking and intelligence.
    """
    try:
        from quote_store import create_quote, add_carrier_to_quote

        # Create quote
        quote = create_quote(
            customer=payload.customer,
            pol=payload.pol,
            pod=payload.pod,
            place=payload.place,
            service_type="CY-CY",
        )

        if not quote:
            raise HTTPException(status_code=500, detail="Failed to create quote")

        quote_id = quote["quote_id"]

        # Add carrier
        add_carrier_to_quote(
            quote_id=quote_id,
            carrier=payload.carrier,
            containers={
                payload.container_type: {
                    "ocean_freight": payload.ocean_freight,
                    "markup": payload.markup,
                    "sell_rate": payload.sell_rate or (payload.ocean_freight + payload.markup),
                }
            },
            transit=payload.transit,
            freetime=payload.freetime,
            note=payload.note,
        )

        # Publish event
        from event_bus import bus, Event
        bus.publish(Event(
            type="quote.created",
            payload={
                "quote_id": quote_id,
                "customer": payload.customer,
                "source": "erp",
                "carrier": payload.carrier,
            },
            source="erp",
        ))

        return {
            "success": True,
            "quote_id": quote_id,
            "customer": payload.customer,
            "carrier": payload.carrier,
            "sell_rate": payload.sell_rate or (payload.ocean_freight + payload.markup),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Quote store not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 3. JOB STATUS — Check shipment/job status from Excel
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/job-status")
async def erp_job_status(
    customer: Optional[str] = Query(None),
    shipment_id: Optional[str] = Query(None),
    quote_id: Optional[str] = Query(None),
    _auth=Security(_verify_erp_key),
):
    """
    Check job/shipment status for Excel ERP.

    Can filter by: customer, shipment_id, or quote_id.
    Returns simplified status data for Excel display.
    """
    shipments = dal.get_shipments()

    if shipment_id:
        shipments = [s for s in shipments if s["id"] == shipment_id]
    elif quote_id:
        shipments = [s for s in shipments
                     if s.get("source") == "Quote" and
                     any(h.get("subject", "").find(quote_id) >= 0
                         for h in s.get("stage_history", []))]
    elif customer:
        shipments = [s for s in shipments
                     if s["customer"].upper() == customer.upper()]

    # Simplified for Excel
    jobs = []
    for s in shipments[:50]:
        jobs.append({
            "id": s["id"],
            "customer": s["customer"],
            "routing": s["routing"],
            "carrier": s["carrier"],
            "container": s.get("container", ""),
            "stage": s["stage"],
            "etd": s.get("etd", ""),
            "eta": s.get("eta", ""),
            "selling_rate": s.get("selling_rate", 0),
            "buying_rate": s.get("buying_rate", 0),
            "profit": s.get("profit", 0),
            "delay_count": s.get("delay_count", 0),
            "risk_level": s.get("risk_level"),
            "updated_at": s.get("updated_at", ""),
        })

    return {
        "jobs": jobs,
        "total": len(jobs),
        "filter": {
            "customer": customer,
            "shipment_id": shipment_id,
            "quote_id": quote_id,
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. COST BREAKDOWN — For Excel cost sheet
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/cost-breakdown")
async def erp_cost_breakdown(
    pol: str = Query("HPH"),
    place: str = Query(...),
    carrier: str = Query(...),
    container: str = Query("40HQ"),
    _auth=Security(_verify_erp_key),
):
    """
    Detailed cost breakdown for Excel.
    Returns all charge components (not just Total Ocean Freight).
    """
    df = dal.load_rates(full=True)
    if df is None:
        raise HTTPException(status_code=503, detail="Rate data not available")

    mask = (
        df['POL'].str.contains(pol, case=False, na=False) &
        df['Carrier'].str.contains(carrier, case=False, na=False) &
        df['Container_Type'].str.contains(container, case=False, na=False)
    )

    # Match place
    if 'Place' in df.columns:
        mask &= df['Place'].str.contains(place, case=False, na=False)
    else:
        mask &= df['POD'].str.contains(place, case=False, na=False)

    result = df[mask].copy()

    charges = []
    for _, row in result.iterrows():
        charges.append({
            "charge_name": str(row.get("Charge_Name", "")),
            "amount": float(row.get("Amount", 0)),
            "currency": str(row.get("Currency", "USD")),
            "unit": str(row.get("Unit", "Per Container")),
        })

    # Sort by amount descending
    charges.sort(key=lambda c: c["amount"], reverse=True)
    total = sum(c["amount"] for c in charges)

    return {
        "pol": pol,
        "place": place,
        "carrier": carrier,
        "container": container,
        "charges": charges,
        "total": total,
        "charge_count": len(charges),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. IMPORT RATES — Semi-automated from Outlook
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/import-rates")
async def erp_import_rates(
    days: int = Query(3, description="Look back N days in Outlook"),
    rate_type: Optional[str] = Query(None, description="FAK, SCFI, FIX, or ALL"),
    scan_only: bool = Query(False, description="Just scan, don't download/import"),
    import_pending: bool = Query(False, description="Import files already in incoming/"),
    _auth=Security(_verify_erp_key),
):
    """
    Semi-automated rate import from Outlook pricing emails.

    **Trigger this when Harry sends new rate files.**

    Flow:
    1. Scan Outlook for emails from pricing@pudongprime.vn
    2. Download .xlsx attachments → incoming/
    3. Classify (FAK/SCFI/FIX) and run master_loader pipeline
    4. Merge into Parquet with smart dedup
    5. Move processed files → processed/

    Special handling:
    - SCFI: keeps Contract (SC) + Group_Code (mr code)
    - FIX SOC HPL: applies PUC_SOC correction (same as FAK SOC)
    - Surcharge/Advisory emails → saved as knowledge items
    """
    pricing_engine_dir = str(_sp.PRICING_CODE)
    if pricing_engine_dir not in sys.path:
        sys.path.insert(0, pricing_engine_dir)

    try:
        from rate_importer import run_full_import, classify_and_import
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"rate_importer not available: {e}")

    try:
        if import_pending:
            result = classify_and_import()
        else:
            result = run_full_import(
                days=days,
                rate_type=rate_type if rate_type != "ALL" else None,
                scan_only=scan_only,
            )

        # Reload DAL cache after import
        if result.get("parquet_updated"):
            dal.invalidate_cache()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 7. SMART MARKUP SUGGEST — Auto-suggest margin based on history + rules
# ══════════════════════════════════════════════════════════════════════════════

_MARKUP_RULES = {
    "DIRECT": {"min": 40, "default": 50, "max": 80},
    "FWD":    {"min": 15, "default": 25, "max": 45},
    "CNEE":   {"min": 20, "default": 30, "max": 50},
    "KEY":    {"min": 10, "default": 20, "max": 35},
}


@router.get("/suggest-markup")
async def erp_suggest_markup(
    carrier: str = Query(...),
    pol: str = Query("HPH"),
    pod: str = Query(""),
    customer_type: str = Query("CNEE"),
    container: str = Query("40HQ"),
    _auth=Security(_verify_erp_key),
):
    """Suggest optimal markup based on customer type + route competition."""
    rules = _MARKUP_RULES.get(customer_type.upper(), _MARKUP_RULES["CNEE"])

    df = dal.load_rates()
    competition = 1
    if df is not None:
        route_mask = df['POL'].str.contains(pol, case=False, na=False)
        if pod:
            route_mask &= df['POD'].str.contains(pod, case=False, na=False)
        competition = max(1, df[route_mask]['Carrier'].nunique() if route_mask.any() else 1)

    if competition >= 8:
        suggested = rules["min"]
        reason = f"High competition ({competition} carriers)"
    elif competition >= 4:
        suggested = rules["default"]
        reason = f"Normal competition ({competition} carriers)"
    else:
        suggested = rules["max"]
        reason = f"Low competition ({competition} carriers)"

    return {
        "suggested_markup": suggested,
        "min": rules["min"],
        "max": rules["max"],
        "reason": reason,
        "customer_type": customer_type,
        "competition": competition,
        "markup_20gp": int(suggested * 0.7),
        "markup_40hq": suggested,
        "markup_40gp": int(suggested * 0.95),
        "markup_45hq": int(suggested * 1.1),
        "markup_20rf": int(suggested * 1.2),
        "markup_40rf": int(suggested * 1.3),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8. QUICK QUOTE — One-click quote from ERP ribbon
# ══════════════════════════════════════════════════════════════════════════════

class QuickQuoteRequest(BaseModel):
    customer: str
    customer_email: str = ""
    pol: str = "HPH"
    pod: str = ""
    place: str = ""
    carrier: str = ""
    container: str = "40HQ"
    buy_rate: float = 0
    markup: float = 30
    sell_rate: float = 0
    note: str = ""
    validity: str = ""


@router.post("/quick-quote")
async def erp_quick_quote(req: QuickQuoteRequest, _auth=Security(_verify_erp_key)):
    """One-click quote generation from ERP ribbon. Logs to Quote_History."""
    from datetime import datetime

    sell = req.sell_rate or (req.buy_rate + req.markup)
    profit = sell - req.buy_rate
    margin_pct = (profit / sell * 100) if sell > 0 else 0
    quote_id = f"Q{datetime.now().strftime('%y%m%d%H%M%S')}"

    quote_log = _sp.ERP_DATA / "Quote_History.xlsx"
    try:
        existing = pd.read_excel(quote_log) if quote_log.exists() else pd.DataFrame()
        new_row = pd.DataFrame([{
            "QuoteID": quote_id, "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Customer": req.customer, "POL": req.pol, "POD": req.pod,
            "Place": req.place, "Carrier": req.carrier, "Container": req.container,
            "Buy_Rate": req.buy_rate, "Markup": req.markup, "Sell_Rate": sell,
            "Profit": profit, "Margin_%": round(margin_pct, 1),
            "Note": req.note, "Validity": req.validity,
            "Status": "PENDING", "Source": "ERP_Ribbon",
        }])
        pd.concat([existing, new_row], ignore_index=True).to_excel(quote_log, index=False)
    except Exception:
        pass

    return {
        "success": True, "quote_id": quote_id,
        "customer": req.customer, "carrier": req.carrier,
        "routing": f"{req.pol} → {req.pod}" + (f" / {req.place}" if req.place else ""),
        "buy_rate": req.buy_rate, "markup": req.markup,
        "sell_rate": sell, "profit": profit, "margin_pct": round(margin_pct, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. REQUOTE ALERTS — Detect quotes needing re-price after FAK update
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/requote-alerts")
async def erp_requote_alerts(
    threshold: float = Query(30),
    _auth=Security(_verify_erp_key),
):
    """Compare pending quotes vs current rates. Alert when delta > threshold."""
    from datetime import datetime

    quote_log = _sp.ERP_DATA / "Quote_History.xlsx"
    if not quote_log.exists():
        return {"alerts": [], "total": 0}

    try:
        quotes_df = pd.read_excel(quote_log)
    except Exception:
        return {"alerts": [], "total": 0}

    pending = quotes_df[quotes_df.get("Status", pd.Series(dtype=str)).str.upper().isin(["PENDING", "SENT"])] if "Status" in quotes_df.columns else quotes_df
    if pending.empty:
        return {"alerts": [], "total": 0}

    df = dal.load_rates()
    if df is None:
        return {"alerts": [], "total": 0}

    alerts = []
    for _, q in pending.iterrows():
        carrier = str(q.get("Carrier", ""))
        pol = str(q.get("POL", ""))
        pod = str(q.get("POD", ""))
        old_buy = float(q.get("Buy_Rate", 0))
        if not carrier or old_buy == 0:
            continue

        mask = (
            df["POL"].str.contains(pol, case=False, na=False) &
            df["Carrier"].str.contains(carrier, case=False, na=False)
        )
        if pod:
            mask &= df["POD"].str.contains(pod, case=False, na=False)
        matched = df[mask]
        if matched.empty:
            continue

        current = matched["Amount"].min()
        delta = float(current - old_buy)
        if abs(delta) >= threshold:
            alerts.append({
                "quote_id": str(q.get("QuoteID", "")),
                "customer": str(q.get("Customer", "")),
                "carrier": carrier,
                "routing": f"{pol} → {pod}",
                "old_buy": old_buy,
                "current": float(current),
                "delta": delta,
                "action": "RE-QUOTE" if delta < 0 else "KEEP",
            })

    alerts.sort(key=lambda a: abs(a["delta"]), reverse=True)
    return {"alerts": alerts, "total": len(alerts), "threshold": threshold}
