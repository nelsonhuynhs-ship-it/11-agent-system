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
_ENGINE_TEST = Path(__file__).parent.parent.parent
_PARQUET_FILE = _ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
_CUSTOMER_RULES = _ENGINE_TEST / "email_engine" / "data" / "customer_rules.json"
_PORT_MAP_FILE = _ENGINE_TEST / "email_engine" / "data" / "Port_Code_Mapping_Final.xlsx"

router = APIRouter(prefix="/api/rates/latest", tags=["Latest Rates"])

# ── Cache ─────────────────────────────────────────────────────────────────────
_parquet_df = None
_parquet_loaded_at = None
_port_map = None
_cust_rules = None


def _load_parquet():
    """Load Parquet with 5-min cache."""
    global _parquet_df, _parquet_loaded_at
    import pandas as pd
    from datetime import datetime

    now = datetime.now()
    if _parquet_df is not None and _parquet_loaded_at:
        age = (now - _parquet_loaded_at).total_seconds()
        if age < 300:  # 5 min cache
            return _parquet_df

    if not _PARQUET_FILE.exists():
        log.error("Parquet not found: %s", _PARQUET_FILE)
        return pd.DataFrame()

    _parquet_df = pd.read_parquet(_PARQUET_FILE)
    _parquet_loaded_at = now
    log.info("Parquet loaded: %d rows", len(_parquet_df))
    return _parquet_df


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
    # Try email_engine path first, then Pricing_Engine path
    for path in [_PORT_MAP_FILE,
                 _ENGINE_TEST / "Pricing_Engine" / "data" / "Port_Code_Mapping_Final.xlsx"]:
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
    df, pol: str, place: str, container: str = "40HQ", top_n: int = 5
) -> list[dict]:
    """Query latest valid rates for a route, sorted by cheapest."""
    import pandas as pd

    if df is None or df.empty:
        return []

    # Filter: Total Ocean Freight only
    mask = df["Charge_Name"].astype(str).str.upper().str.contains("TOTAL", na=False)

    # POL filter
    mask &= df["POL"].astype(str).str.upper().str.contains(pol.upper(), na=False)

    # Place/POD filter
    place_upper = place.upper()
    mask &= (
        df["Place"].astype(str).str.upper().str.contains(place_upper, na=False)
        | df["POD"].astype(str).str.upper().str.contains(place_upper, na=False)
    )

    # Container filter
    ct_map = {
        "40HQ": ["40HQ", "40HC", "40HG"],
        "20GP": ["20GP", "20DC", "20"],
        "40GP": ["40GP"],
    }
    ct_values = ct_map.get(container.upper(), [container.upper()])
    mask &= df["Container_Type"].astype(str).str.upper().isin(ct_values)

    filtered = df[mask].copy()
    if filtered.empty:
        return []

    # Filter valid dates (not expired)
    if "Exp" in filtered.columns:
        try:
            filtered["_exp"] = pd.to_datetime(filtered["Exp"], errors="coerce")
            today = pd.Timestamp.now()
            valid = filtered[filtered["_exp"] >= today]
            if not valid.empty:
                filtered = valid
        except Exception:
            pass

    # Best rate per carrier
    best = (
        filtered.sort_values("Amount")
        .drop_duplicates(subset=["Carrier"], keep="first")
        .head(top_n)
    )

    results = []
    for _, row in best.iterrows():
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
            "is_soc": "SOC" in str(row.get("Note", "")).upper(),
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
