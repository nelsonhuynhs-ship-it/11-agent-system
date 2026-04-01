# -*- coding: utf-8 -*-
"""
dashboard_router.py — Dashboard + KPI + Customer + Team + Status + Dataset Endpoints
=====================================================================================
"""
from __future__ import annotations

import json as _json
import os
import sys
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import dal, EMAIL_DIR
from routers.rate_router import _classify_region

router = APIRouter(prefix="/api", tags=["Dashboard"])


@router.get("/dashboard/charts")
def get_dashboard_charts():
    """Pre-computed chart data for dashboard."""
    charts = {}

    # 1. Shipment & Revenue timeline
    state = dal.load_shipment_state()
    shipments = state.get("shipments", {})
    monthly_revenue, monthly_profit, monthly_count = {}, {}, {}
    carrier_profit, customer_ships = {}, {}

    for sid, rec in shipments.items():
        created = rec.get("created_at", "")[:7]
        if not created:
            continue
        sell = rec.get("selling_rate", 0) or 0
        profit = rec.get("profit", 0) or 0
        carrier = rec.get("carrier", "UNKNOWN")
        customer = rec.get("customer", "UNKNOWN")
        monthly_revenue[created] = monthly_revenue.get(created, 0) + sell
        monthly_profit[created] = monthly_profit.get(created, 0) + profit
        monthly_count[created] = monthly_count.get(created, 0) + 1
        carrier_profit[carrier] = carrier_profit.get(carrier, 0) + profit
        customer_ships[customer] = customer_ships.get(customer, 0) + 1

    charts["revenue_timeline"] = [
        {"month": m, "revenue": monthly_revenue[m],
         "profit": monthly_profit.get(m, 0),
         "shipments": monthly_count.get(m, 0)}
        for m in sorted(monthly_revenue.keys())
    ]
    charts["carrier_profit"] = sorted(
        [{"carrier": k, "profit": round(v, 0)} for k, v in carrier_profit.items()],
        key=lambda x: -x["profit"])[:10]
    charts["customer_activity"] = sorted(
        [{"customer": k, "shipments": v} for k, v in customer_ships.items()],
        key=lambda x: -x["shipments"])[:10]

    # 2. Market sentiment
    try:
        mm_path = EMAIL_DIR / "memory" / "market_memory.parquet"
        if mm_path.exists():
            mm = pd.read_parquet(mm_path).sort_values("period")
            charts["market_timeline"] = _json.loads(
                mm[["period", "total_shipments", "total_profit",
                    "active_customers", "sentiment"]].to_json(orient="records"))
    except Exception:
        charts["market_timeline"] = []

    # 3. Carrier grades
    try:
        from carrier_scorer import score_all_carriers
        scores = score_all_carriers()
        charts["carrier_grades"] = _json.loads(_json.dumps(scores[:10], default=str))
    except Exception:
        charts["carrier_grades"] = []

    # 4. 4C summary
    try:
        from opportunity_detector import build_4c_report
        report = build_4c_report()
        charts["intelligence_4c"] = _json.loads(_json.dumps(report, default=str))
    except Exception:
        charts["intelligence_4c"] = {}

    # 5. Region summary
    df = dal.load_rates()
    if df is not None:
        df_hph = df[df['POL'].str.upper().str.strip() == 'HPH']
        df_hph_40 = df_hph[df_hph['Container_Type'] == '40HQ'].copy()
        df_hph_40['region'] = df_hph_40['POD'].apply(_classify_region)
        reg_stats = df_hph_40.groupby('region')['Amount'].agg(
            ['min', 'mean', 'count']).reset_index()
        charts["region_summary"] = reg_stats.rename(
            columns={"region": "name", "min": "min_price",
                      "mean": "avg_price", "count": "rates"}
        ).round(0).to_dict("records")

    return charts


@router.get("/customers")
def get_customers():
    """Get all customers enriched with shipment stats."""
    customers = dal.get_customers()
    return {"customers": customers, "total": len(customers)}


@router.get("/team")
def get_team():
    """Get team members."""
    members = dal.get_team()
    return {"members": members, "total": len(members)}


@router.get("/kpi")
def get_kpi():
    """Get KPI summary."""
    return dal.get_kpi()


@router.get("/datasets/status")
def get_dataset_status():
    """Return row counts for accumulated datasets."""
    return dal.get_dataset_status()


@router.get("/datasets/email")
def get_email_dataset(days: int = Query(30), customer: Optional[str] = None):
    """Query email dataset records."""
    records = dal.get_email_dataset(days, customer)
    return {"records": records, "total": len(records)}


@router.get("/status")
def get_status():
    """System health check."""
    return dal.get_system_status()
