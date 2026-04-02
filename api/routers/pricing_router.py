# -*- coding: utf-8 -*-
"""
pricing_router.py — Unified Pricing Endpoints (nelson-flow)
============================================================
Facade endpoints matching nelson-flow.jsx Check Pricing flow.
Delegates to existing rate_router/FreightDB logic.

Endpoints:
  POST /api/pricing/check     — unified pricing check
  GET  /api/pricing/carriers   — list active carriers
  GET  /api/pricing/ports      — list available POL/POD/Place
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel

# ── Imports ───────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import dal

# DuckDB engine
_ENGINE_TEST_DIR = Path(__file__).parent.parent.parent  # Engine_test/ (kept for sys.path)
if str(_ENGINE_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_TEST_DIR))
from shared import paths as _sp
from db.duckdb_engine import FreightDB

# ── FreightDB Singleton ──────────────────────────────────────────────────────
_PARQUET_PATH = _sp.PARQUET_FILE
freight_db = FreightDB(_PARQUET_PATH)

router = APIRouter(prefix="/api/pricing", tags=["Pricing"])


# ── Request Models ───────────────────────────────────────────────────────────

class PricingCheckRequest(BaseModel):
    """Input for Check Pricing flow (nelson-flow Step 1)."""
    pol: str = "HPH"
    pod: Optional[str] = None
    place: Optional[str] = None
    carrier: Optional[str] = None
    container: str = "40HQ"
    rate_type: Optional[str] = None  # FAK / SCFI / FIX
    top: int = 20


# ══════════════════════════════════════════════════════════════════════════════
# 1. CHECK PRICING — POST /api/pricing/check
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/check")
def check_pricing(req: PricingCheckRequest):
    """
    Unified pricing check — nelson-flow core endpoint.

    Input: POL, POD/Place, Carrier, Container, Rate type
    Output: Rate breakdown with HDL fees, validity, SOC/COC flags, surcharges

    Used by: Telegram Bot, WebApp, ERP Excel (same data, different display)
    """
    import pandas as pd

    # Query via DuckDB
    df = freight_db.query_rates(
        pol=req.pol, pod=req.pod,
        container_type=req.container, days=90
    )

    if df is None or df.empty:
        return {"rates": [], "total": 0, "query": req.model_dump(), "error": "No rates found"}

    result = df.copy()

    # Additional filters
    if req.carrier:
        result = result[result['Carrier'].str.upper().str.contains(
            req.carrier.upper(), na=False)]
    if req.rate_type:
        result = result[result['Rate_Type'].str.upper().str.contains(
            req.rate_type.upper(), na=False)]
    if req.place:
        mask = pd.Series(False, index=result.index)
        for col in ['Place', 'POD']:
            if col in result.columns:
                mask |= result[col].astype(str).str.upper().str.contains(
                    req.place.upper(), na=False)
        result = result[mask]

    if result.empty:
        return {"rates": [], "total": 0, "query": req.model_dump()}

    # Best rate per carrier
    best = (
        result.sort_values('Amount')
              .drop_duplicates(subset=['Carrier', 'Note'], keep='first')
              .sort_values('Amount')
              .head(req.top)
    )

    # Enrich with carrier rules
    carrier_rules = dal.get_carrier_rules()
    rates = []
    for _, row in best.iterrows():
        c = str(row.get('Carrier', '')).strip().upper()
        cr = carrier_rules.get(c, {})
        is_soc = 'SOC' in str(row.get('Note', '')).upper()

        rates.append({
            "carrier":        row.get('Carrier', ''),
            "pol":            row.get('POL', ''),
            "pod":            row.get('POD', ''),
            "place":          row.get('Place', ''),
            "container":      row.get('Container_Type', ''),
            "amount":         float(row.get('Amount', 0)),
            "rate_type":      row.get('Rate_Type', ''),
            "transit":        row.get('Transit', '') if 'Transit' in row.index else '',
            "note":           row.get('Note', ''),
            "commodity":      row.get('Commodity', ''),
            "effective":      str(row.get('Eff', '')),
            "expiry":         str(row.get('Exp', '')),
            "is_soc":         is_soc,
            "is_direct":      'DIRECT' in str(row.get('Note', '')).upper(),
            "freetime_det":   cr.get("DET", ""),
            "freetime_dem":   cr.get("DEM", ""),
            # nelson-flow: HDL fee per carrier
            "hdl_fee":        cr.get("HDL", 0),
        })

    return {
        "rates": rates,
        "total": len(rates),
        "query": req.model_dump(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. CARRIERS — GET /api/pricing/carriers
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/carriers")
def get_carriers():
    """List all active carriers with rate counts (last 90 days)."""
    df = freight_db.query_rates(days=90)
    if df is None or df.empty:
        return {"carriers": []}

    carrier_rules = dal.get_carrier_rules()
    counts = df['Carrier'].value_counts().to_dict()

    carriers = []
    for name, rate_count in counts.items():
        cr = carrier_rules.get(str(name).strip().upper(), {})
        carriers.append({
            "name": name,
            "rates": rate_count,
            "freetime_det": cr.get("DET", ""),
            "freetime_dem": cr.get("DEM", ""),
            "is_soc_capable": cr.get("SOC", False),
        })

    carriers.sort(key=lambda x: x["rates"], reverse=True)
    return {"carriers": carriers, "total": len(carriers)}


# ══════════════════════════════════════════════════════════════════════════════
# 3. PORTS — GET /api/pricing/ports
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/ports")
def get_ports(
    type: str = Query("all", description="pol, pod, place, or all"),
):
    """
    List available ports/places from Parquet data.

    Used for: dropdowns in WebApp, autocomplete in Bot, validation in ERP.
    """
    con = freight_db._connect()
    try:
        ports_data = {}

        if type in ("all", "pol"):
            pols = con.execute(f"""
                SELECT DISTINCT TRIM(POL) as port
                FROM read_parquet('{freight_db._parquet}')
                WHERE {freight_db._date_filter(90)}
                  AND POL IS NOT NULL AND TRIM(POL) != ''
                ORDER BY port
            """).fetchdf()
            ports_data["pol"] = pols['port'].tolist() if not pols.empty else []

        if type in ("all", "pod"):
            pods = con.execute(f"""
                SELECT DISTINCT TRIM(POD) as port, COUNT(*) as rate_count
                FROM read_parquet('{freight_db._parquet}')
                WHERE {freight_db._date_filter(90)}
                  AND POD IS NOT NULL AND TRIM(POD) != ''
                GROUP BY TRIM(POD)
                ORDER BY rate_count DESC
            """).fetchdf()
            ports_data["pod"] = [
                {"code": row['port'], "rates": int(row['rate_count'])}
                for _, row in pods.iterrows()
            ] if not pods.empty else []

        if type in ("all", "place"):
            places = con.execute(f"""
                SELECT DISTINCT TRIM(Place) as place, COUNT(*) as rate_count
                FROM read_parquet('{freight_db._parquet}')
                WHERE {freight_db._date_filter(90)}
                  AND Place IS NOT NULL AND TRIM(Place) != ''
                GROUP BY TRIM(Place)
                ORDER BY rate_count DESC
            """).fetchdf()
            ports_data["place"] = [
                {"name": row['place'], "rates": int(row['rate_count'])}
                for _, row in places.iterrows()
            ] if not places.empty else []

    finally:
        con.close()

    return {"ports": ports_data, "filter": type}
