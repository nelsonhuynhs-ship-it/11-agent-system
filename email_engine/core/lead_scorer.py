"""
lead_scorer.py — LEAD_SCORE recalculation + priority contact retrieval
=======================================================================
Base: 50 | Reply <7d: +30 | Reply <30d: +15 | Shipment: +20
Cold (step>=2, no reply): -10 | Bounce: -20 | Invalid: -50
Clamped 0-100.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_engine_dir = Path(__file__).parent.parent  # email_engine/
CNEE_V2 = _engine_dir / "data" / "cnee_master_v2.xlsx"
SUPPRESSED = {"HARD_BOUNCE", "INVALID", "NO_MX"}


def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Recalculate LEAD_SCORE for all rows in df. Returns updated df."""
    today = pd.Timestamp.now()

    # Parse dates
    last_reply = pd.to_datetime(df.get("LAST_REPLY", pd.Series(dtype="object")), errors="coerce")
    days_since_reply = (today - last_reply).dt.days

    score = pd.Series(50, index=df.index, dtype=float)

    # Reply bonuses
    score += (days_since_reply <= 7).fillna(False) * 30
    score += ((days_since_reply > 7) & (days_since_reply <= 30)).fillna(False) * 15

    # Shipment activity
    if "TOTAL_SHIPMENT" in df.columns:
        total_ship = pd.to_numeric(df["TOTAL_SHIPMENT"], errors="coerce").fillna(0)
        score += (total_ship > 0) * 20

    # Cold lead penalty: step >= 2 and no reply
    if "SEQ_STEP" in df.columns:
        seq_step = pd.to_numeric(df["SEQ_STEP"], errors="coerce").fillna(0)
        no_reply = last_reply.isna()
        score -= ((seq_step >= 2) & no_reply) * 10

    # Bounce penalty
    if "BOUNCE_COUNT" in df.columns:
        bounce = pd.to_numeric(df["BOUNCE_COUNT"], errors="coerce").fillna(0)
        score -= (bounce > 0) * 20

    # Invalid email penalty
    if "EMAIL_STATUS" in df.columns:
        invalid_mask = df["EMAIL_STATUS"].astype(str).str.upper().isin(SUPPRESSED)
        score -= invalid_mask * 50

    df = df.copy()
    df["LEAD_SCORE"] = score.clip(0, 100).astype(int)
    return df


def recalculate_and_save() -> int:
    """Reload cnee_master_v2, recalculate all scores, save. Returns row count."""
    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip().str.upper()
    df = calculate_scores(df)
    df.to_excel(CNEE_V2, index=False)
    return len(df)


def get_priority_contacts(campaign_id: str, top_n: int = 50) -> list[dict]:
    """Return top N contacts by LEAD_SCORE for a campaign, excluding suppressed."""
    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip().str.upper()

    # Filter campaign
    if campaign_id and "CAMPAIGN_ID" in df.columns:
        df = df[df["CAMPAIGN_ID"].astype(str).str.upper() == campaign_id.upper()]

    # Exclude suppressed
    if "EMAIL_STATUS" in df.columns:
        df = df[~df["EMAIL_STATUS"].astype(str).str.upper().isin(SUPPRESSED)]
    if "SEQ_STATUS" in df.columns:
        df = df[~df["SEQ_STATUS"].astype(str).str.upper().isin({"OPTED_OUT"})]

    # Sort by score
    if "LEAD_SCORE" in df.columns:
        df = df.sort_values("LEAD_SCORE", ascending=False)

    results = []
    for _, row in df.head(top_n).iterrows():
        results.append({
            "email":       str(row.get("EMAIL", "")),
            "company":     str(row.get("COMPANY", "")),
            "campaign_id": str(row.get("CAMPAIGN_ID", "")),
            "lead_score":  int(pd.to_numeric(row.get("LEAD_SCORE", 0), errors="coerce") or 0),
            "seq_step":    int(pd.to_numeric(row.get("SEQ_STEP", 0), errors="coerce") or 0),
            "seq_status":  str(row.get("SEQ_STATUS", "")),
            "last_reply":  str(row.get("LAST_REPLY", "")),
        })
    return results
