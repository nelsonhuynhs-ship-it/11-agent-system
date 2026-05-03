# -*- coding: utf-8 -*-
"""admin_router.py — Token usage monitoring endpoints."""
from __future__ import annotations
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/token-usage")
def token_usage_current():
    """Return current in-process token usage stats."""
    from email_engine.core.minimax.token_tracker import get_usage
    return {"date": str(date.today()), "usage": get_usage()}


@router.get("/token-usage/history")
def token_usage_history():
    """Return historical token usage from parquet store."""
    from pathlib import Path
    import pandas as pd

    token_file = Path("D:/OneDrive/NelsonData/email/token_usage.parquet")
    if not token_file.exists():
        return {"date": str(date.today()), "history": [], "total": 0}
    df = pd.read_parquet(token_file)
    df = df[df["date"] >= str(date.today().replace(day=1))]
    return {"date": str(date.today()), "history": df.to_dict("records"), "total": len(df)}