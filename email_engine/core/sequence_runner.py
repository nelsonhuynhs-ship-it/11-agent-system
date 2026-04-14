"""
sequence_runner.py — API-friendly wrapper around sequence_engine.py
====================================================================
Exposes get_due_contacts(), advance_step(), get_template() for web_server.py endpoints.
Reuses logic from sequence_engine.py — no duplication.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Path setup
_engine_dir = Path(__file__).parent.parent  # email_engine/
CNEE_V2 = _engine_dir / "data" / "cnee_master_v2.xlsx"

SKIP_STATUSES  = {"REPLIED", "OPTED_OUT"}
SKIP_EMAIL_STS = {"HARD_BOUNCE", "INVALID", "NO_MX"}

# Days to wait per step transition
STEP_DELAYS = {
    1: 3,   # step 0→1: 3 days after LAST_SENT_DATE
    2: 7,   # step 1→2: 7 days after SEQ_LAST_SENT
    3: 14,  # step 2→3: 14 days after SEQ_LAST_SENT
}

TEMPLATES = {
    1: {
        "subject": "Following up — {company} freight rates",
        "intro":   "Just checking if you had a chance to review our rates...",
    },
    2: {
        "subject": "Quick case study — how {industry} importers save on freight",
        "intro":   "Many {industry} companies are seeing savings of 15-20%...",
    },
    3: {
        "subject": "Last chance — special rates expiring for {destination}",
        "intro":   "We have limited availability at current pricing...",
    },
}


def _load_cnee() -> pd.DataFrame:
    df = pd.read_excel(CNEE_V2)
    df.columns = df.columns.str.strip().str.upper()
    return df


def get_due_contacts(campaign_id: str | None = None) -> list[dict]:
    """Return contacts due for next sequence step."""
    df = _load_cnee()

    # Skip opted-out / replied contacts
    if "SEQ_STATUS" in df.columns:
        df = df[~df["SEQ_STATUS"].str.upper().isin(SKIP_STATUSES)]

    # Skip suppressed emails
    if "EMAIL_STATUS" in df.columns:
        df = df[~df["EMAIL_STATUS"].str.upper().isin(SKIP_EMAIL_STS)]

    # Skip contacts who already replied
    if "LAST_REPLY" in df.columns:
        df = df[pd.to_datetime(df["LAST_REPLY"], errors="coerce").isna()]

    # Filter by campaign
    if campaign_id and "CAMPAIGN_ID" in df.columns:
        df = df[df["CAMPAIGN_ID"].astype(str).str.upper() == campaign_id.upper()]

    today = pd.Timestamp.now()
    due = []

    for _, row in df.iterrows():
        step = int(row.get("SEQ_STEP", 0) or 0)
        next_step = step + 1
        if next_step > 3:
            continue

        # Determine which date column to check
        if step == 0:
            sent_date = pd.to_datetime(row.get("LAST_SENT_DATE"), errors="coerce")
            delay = STEP_DELAYS[1]
        else:
            sent_date = pd.to_datetime(row.get("SEQ_LAST_SENT"), errors="coerce")
            delay = STEP_DELAYS.get(next_step, 7)

        if pd.isna(sent_date):
            continue  # No send date — skip

        days_since = (today - sent_date).days
        if days_since >= delay:
            email = str(row.get("EMAIL", "")).strip()
            if "@" not in email:
                continue
            tmpl = TEMPLATES[next_step]
            company   = str(row.get("COMPANY", "")).strip()
            industry  = str(row.get("INDUSTRY", "Freight")).strip() or "Freight"
            dest      = str(row.get("DESTINATION", "")).strip() or "destination"
            due.append({
                "email":      email,
                "company":    company,
                "campaign_id": str(row.get("CAMPAIGN_ID", "")),
                "current_step": step,
                "next_step":  next_step,
                "days_since": days_since,
                "subject":    tmpl["subject"].format(company=company, industry=industry, destination=dest),
                "intro":      tmpl["intro"].format(industry=industry),
            })

    return due


def advance_step(email: str, new_step: int) -> bool:
    """Update SEQ_STEP, SEQ_LAST_SENT, SEQ_STATUS in cnee_master_v2.xlsx."""
    try:
        df = pd.read_excel(CNEE_V2)
        df.columns = df.columns.str.strip().str.upper()
        mask = df["EMAIL"].astype(str).str.lower() == email.lower()
        if not mask.any():
            return False
        now_str = datetime.now().strftime("%Y-%m-%d")
        df.loc[mask, "SEQ_STEP"]     = new_step
        df.loc[mask, "SEQ_LAST_SENT"] = now_str
        df.loc[mask, "SEQ_STATUS"]   = "IN_SEQUENCE"
        df.to_excel(CNEE_V2, index=False)
        return True
    except Exception:
        return False


def get_template(step: int, company: str = "", industry: str = "Freight",
                 destination: str = "destination") -> dict:
    """Return subject + intro for a given sequence step."""
    tmpl = TEMPLATES.get(step, TEMPLATES[1])
    return {
        "subject": tmpl["subject"].format(company=company, industry=industry, destination=destination),
        "intro":   tmpl["intro"].format(industry=industry),
    }
