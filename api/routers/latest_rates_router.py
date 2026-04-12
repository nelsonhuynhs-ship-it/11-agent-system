# -*- coding: utf-8 -*-
"""
latest_rates_router.py — Latest Rates Query Endpoints
=======================================================
Query Parquet for latest valid rates per route, optimized for
customer-facing use (auto-quote, email campaigns, dashboards).

Unlike rate_router (full search), this focuses on:
  - Only Total Ocean Freight (selling rates)
  - Only currently valid (not expired)
  - Sorted by cheapest first
  - Per-customer route detection from customer_rules.json

Endpoints:
  GET  /api/rates/latest           — Latest rates by route
  GET  /api/rates/latest/customer  — Auto-detect routes from customer profile
  POST /api/rates/compare          — Compare carriers for same route
"""
from __future__ import annotations

import sys
import os
import json
import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

log = logging.getLogger("nelson.latest_rates")

# ── Paths ─────────────────────────────────────────────────────────────────────
import sys as _sys
_ENGINE_TEST = Path(__file__).parent.parent.parent  # Engine_test/ (kept for sys.path)
if str(_ENGINE_TEST) not in _sys.path:
    _sys.path.insert(0, str(_ENGINE_TEST))
from shared import paths as _sp

_PARQUET_FILE = _sp.PARQUET_FILE
_CUSTOMER_RULES = _sp.CUSTOMER_RULES
_PORT_MAP_FILE = _sp.PORT_MAP

router = APIRouter(prefix="/api/rates/latest", tags=["Latest Rates"])

# ── DuckDB Engine (replaces pandas read_parquet) ─────────────────────────────
import duckdb

_port_map = None
_cust_rules = None


def _load_parquet():
    """Return parquet path for DuckDB queries — no pandas load."""
    return str(_PARQUET_FILE) if _PARQUET_FILE.exists() else None


def _load_customer_rules():
    global _cust_rules
    if _cust_rules is None:
        if _CUSTOMER_RULES.exists():
            with open(_CUSTOMER_RULES, "r", encoding="utf-8") as f:
                _cust_rules = json.load(f)
        else:
            _cust_rules = {}
    return _cust_rules


def _load_port_map():
    global _port_map
    if _port_map is not None:
        return _port_map

    import pandas as pd
    # Try primary path (shared.paths), no legacy fallback needed
    for path in [_PORT_MAP_FILE]:
        if path.exists():
            df = pd.read_excel(path)
            df.columns = df.columns.str.strip()
            _port_map = {}
            for _, row in df.iterrows():
                code = str(row.get("PortCode", "")).strip().upper()
                name = str(row.get("PortName", "")).strip()
                if code and name:
                    _port_map[code] = name
            return _port_map

    _port_map = {}
    return _port_map


def _query_latest(
    parquet_path, pol: str, place: str, container: str = "40HQ", top_n: int = 5
) -> list[dict]:
    """Query latest valid rates via DuckDB — no pandas full load."""
    if not parquet_path:
        return []

    ct_norm = container.upper().replace("'", "")
    con = duckdb.connect()

    try:
        df = con.execute("""
            SELECT DISTINCT ON (Carrier)
                Carrier, POL, POD, Place,
                REPLACE(Container_Type, chr(39), '') AS Container_Type,
                ROUND(Amount, 2) AS Amount, Rate_Type, Note,
                Eff, Exp,
                CASE WHEN UPPER(COALESCE(Note, '')) LIKE '%SOC%' THEN true ELSE false END AS is_soc
            FROM read_parquet(?)
            WHERE Exp >= CURRENT_DATE
              AND Charge_Name IN ('ALL IN COST', 'Total Ocean Freight', 'Base Ocean Freight')
              AND UPPER(TRIM(POL)) = UPPER(TRIM(?))
              AND (UPPER(TRIM(Place)) LIKE '%' || UPPER(TRIM(?)) || '%'
                   OR UPPER(TRIM(POD)) LIKE '%' || UPPER(TRIM(?)) || '%')
              AND UPPER(REPLACE(Container_Type, chr(39), '')) = ?
              AND Amount > 0
            ORDER BY Carrier, Amount ASC
        """, [parquet_path, pol, place, place, ct_norm]).fetchdf()
    except Exception as e:
        log.error("DuckDB query error: %s", e)
        return []

    if df.empty:
        return []

    results = []
    for _, row in df.sort_values("Amount").head(top_n).iterrows():
        results.append({
            "carrier": str(row.get("Carrier", "")),
            "pol": str(row.get("POL", "")),
            "pod": str(row.get("POD", "")),
            "place": str(row.get("Place", "")),
            "container": str(row.get("Container_Type", "")),
            "amount": float(row.get("Amount", 0)),
            "rate_type": str(row.get("Rate_Type", "")),
            "note": str(row.get("Note", "")),
            "effective": str(row.get("Eff", "")),
            "expiry": str(row.get("Exp", "")),
            "is_soc": bool(row.get("is_soc", False)),
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 1. LATEST RATES — GET /api/rates/latest
# ══════════════════════════════════════════════════════════════════════════════

@router.get("")
def get_latest_rates(
    pol: str = Query("HPH", description="Port of Loading"),
    place: str = Query(..., description="Destination city (e.g. Chicago, Los Angeles)"),
    container: str = Query("40HQ", description="Container type: 20GP, 40HQ, 40GP"),
    top: int = Query(5, description="Max carriers to return"),
    markup: float = Query(0, description="Markup to add per container"),
):
    """
    Query latest valid rates for a specific route.

    Returns cheapest carriers with current valid rates (not expired).
    Optionally apply markup for selling price.
    """
    df = _load_parquet()
    rates = _query_latest(df, pol, place, container, top)

    if markup > 0:
        for r in rates:
            r["base_amount"] = r["amount"]
            r["amount"] = r["amount"] + markup
            r["markup"] = markup

    return {
        "rates": rates,
        "total": len(rates),
        "query": {"pol": pol, "place": place, "container": container, "markup": markup},
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. LATEST BY CUSTOMER — GET /api/rates/latest/customer
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/customer")
def get_latest_for_customer(
    name: str = Query(..., description="Customer name (SIRI, HML, PANDA, etc.)"),
    container: str = Query("40HQ"),
    top: int = Query(3),
    markup: float = Query(20),
):
    """
    Auto-detect customer routes from customer_rules.json and query latest rates.

    Looks up customer → finds their usual POL/destinations → returns rates.
    """
    rules = _load_customer_rules()
    port_map = _load_port_map()
    df = _load_parquet()

    # Find customer in rules
    customers = rules.get("customers", rules)
    customer_data = None

    if isinstance(customers, list):
        for c in customers:
            if c.get("name", "").upper() == name.upper():
                customer_data = c
                break
    elif isinstance(customers, dict):
        customer_data = customers.get(name.upper(), customers.get(name, None))

    if not customer_data:
        # Try fuzzy match
        name_upper = name.upper()
        if isinstance(customers, dict):
            for k, v in customers.items():
                if name_upper in k.upper():
                    customer_data = v
                    break

    if not customer_data:
        return {
            "error": f"Customer '{name}' not found in customer_rules.json",
            "available": list(customers.keys()) if isinstance(customers, dict) else [c.get("name", "") for c in customers] if isinstance(customers, list) else [],
        }

    # Extract routes
    pol = customer_data.get("pol", "HPH")
    destinations = customer_data.get("destinations", customer_data.get("routes", []))

    if isinstance(destinations, str):
        destinations = [d.strip() for d in destinations.split(",") if d.strip()]

    if not destinations:
        # Fallback: check if there are POD fields
        pods = customer_data.get("pods", customer_data.get("pod", []))
        if isinstance(pods, str):
            destinations = [pods]
        elif isinstance(pods, list):
            destinations = pods

    # Query rates for each destination
    all_rates = {}
    for dest in destinations:
        # Resolve port code to city name
        search = dest
        if dest.upper() in port_map:
            search = port_map[dest.upper()].split(",")[0].strip()

        rates = _query_latest(df, pol, search, container, top)

        if markup > 0:
            for r in rates:
                r["base_amount"] = r["amount"]
                r["amount"] = r["amount"] + markup
                r["markup"] = markup

        if rates:
            all_rates[dest] = rates

    return {
        "customer": name,
        "owner": customer_data.get("owner", ""),
        "pol": pol,
        "destinations": destinations,
        "routes_with_rates": len(all_rates),
        "routes": all_rates,
        "container": container,
        "markup": markup,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. COMPARE — POST /api/rates/compare
# ══════════════════════════════════════════════════════════════════════════════

class CompareRequest(BaseModel):
    pol: str = "HPH"
    destinations: List[str]  # ["USCHI", "USLAX", "USSAV"]
    containers: List[str] = ["20GP", "40HQ"]
    top_per_route: int = 5
    markup: float = 0


@router.post("/compare")
def compare_rates(req: CompareRequest):
    """
    Compare carriers across multiple routes and container types.

    Returns a matrix: route × carrier × container → rate.
    Useful for side-by-side comparison in email or dashboard.
    """
    df = _load_parquet()
    port_map = _load_port_map()

    comparison = {}
    all_carriers = set()

    for dest in req.destinations:
        search = dest
        if dest.upper() in port_map:
            search = port_map[dest.upper()].split(",")[0].strip()

        route_data = {}
        for ct in req.containers:
            rates = _query_latest(df, req.pol, search, ct, req.top_per_route)
            if req.markup > 0:
                for r in rates:
                    r["base_amount"] = r["amount"]
                    r["amount"] = r["amount"] + req.markup

            route_data[ct] = rates
            for r in rates:
                all_carriers.add(r["carrier"])

        comparison[dest] = route_data

    # Build carrier summary
    carrier_summary = {}
    for carrier in sorted(all_carriers):
        carrier_routes = 0
        for dest, ct_data in comparison.items():
            for ct, rates in ct_data.items():
                if any(r["carrier"] == carrier for r in rates):
                    carrier_routes += 1
        carrier_summary[carrier] = {"routes_covered": carrier_routes}

    return {
        "comparison": comparison,
        "carriers": carrier_summary,
        "total_routes": len(req.destinations),
        "total_carriers": len(all_carriers),
        "query": req.model_dump(),
    }
