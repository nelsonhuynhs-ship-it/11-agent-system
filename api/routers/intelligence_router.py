# -*- coding: utf-8 -*-
"""
intelligence_router.py — Intelligence Endpoints
=================================================
Memory, carrier scoring, 4C, opportunities, market, news, churn.
"""
from __future__ import annotations

import json as _json
import os
import sys
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import EMAIL_DIR

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence"])

# Ensure email engine is importable
sys.path.insert(0, str(EMAIL_DIR))


@router.get("/memory")
def get_intelligence_memory():
    """Memory Layer status — all datasets."""
    try:
        from memory_writer import get_memory_status
        status = get_memory_status()
        total = sum(v.get("rows", 0) for v in status.values() if v.get("rows", 0) > 0)
        return {"memory": status, "total_rows": total}
    except Exception as e:
        return {"error": str(e)}


@router.get("/carriers")
def get_intelligence_carriers(carrier: Optional[str] = Query(None)):
    """Carrier reliability ranking or detail report."""
    try:
        from carrier_scorer import score_all_carriers, get_carrier_report
        if carrier:
            report = get_carrier_report(carrier)
            if report:
                report = _json.loads(_json.dumps(report, default=str))
                return {"carrier": report}
            return {"error": "Carrier not found"}
        scores = score_all_carriers()
        scores = _json.loads(_json.dumps(scores, default=str))
        return {"carriers": scores, "total": len(scores)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/4c")
def get_intelligence_4c():
    """4C Freight Intelligence report."""
    try:
        from opportunity_detector import build_4c_report
        report = build_4c_report()
        return {"report": report}
    except Exception as e:
        return {"error": str(e)}


@router.get("/opportunities")
def get_intelligence_opportunities():
    """Detected business opportunities from 4C analysis."""
    try:
        from opportunity_detector import detect_opportunities
        opps = detect_opportunities()
        by_type = {}
        for o in opps:
            by_type[o["type"]] = by_type.get(o["type"], 0) + 1
        return {"opportunities": opps, "total": len(opps), "by_type": by_type}
    except Exception as e:
        return {"error": str(e)}


@router.get("/market")
def get_intelligence_market():
    """Market memory trends + sentiment."""
    try:
        mm_path = EMAIL_DIR / "memory" / "market_memory.parquet"
        if not mm_path.exists():
            return {"error": "No market memory"}
        df = pd.read_parquet(mm_path).sort_values("period")
        records = df.to_dict("records")
        latest = records[-1] if records else {}
        return {"trends": records, "latest": latest, "total_periods": len(records)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/news")
def get_intelligence_news(days: int = Query(7), signals_only: bool = Query(False)):
    """Recent logistics news with market signals."""
    try:
        from news_ingester import get_recent_news, news_status
        articles = get_recent_news(days=days, signals_only=signals_only)
        status = news_status()
        return {"articles": articles, "total": len(articles), "status": status}
    except Exception as e:
        return {"error": str(e)}


@router.get("/churn")
def get_intelligence_churn():
    """Customer churn risk analysis."""
    try:
        cm_path = EMAIL_DIR / "memory" / "customer_memory.parquet"
        if not cm_path.exists():
            return {"error": "No customer memory"}
        df = pd.read_parquet(cm_path)
        latest_period = df["period"].max()
        latest = df[df["period"] == latest_period].sort_values(
            "days_since_last_order", ascending=False)
        records = latest.to_dict("records")
        risk_dist = latest["churn_risk"].value_counts().to_dict()
        return {"customers": records, "total": len(records),
                "risk_distribution": risk_dist, "period": latest_period}
    except Exception as e:
        return {"error": str(e)}
