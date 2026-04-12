"""
blacklist.py — Competitor blacklist system for FreightBrian.
Filters out competitor contacts from outreach campaigns.
"""
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
BLACKLIST_CONFIG = DATA_DIR / "email" / "blacklist_domains.yaml"
BLACKLIST_HITS_LOG = DATA_DIR / "email" / "blacklist_hits.csv"


def load_blacklist() -> dict:
    with open(BLACKLIST_CONFIG) as f:
        return yaml.safe_load(f)


def _get_domain(email: str) -> Optional[str]:
    if not email or not isinstance(email, str):
        return None
    match = re.search(r"@([\w.-]+)", email.strip().lower())
    return match.group(1) if match else None


def is_blacklisted(email: str, company: str = "") -> tuple[bool, str]:
    """Check if email/company is a competitor. Returns (is_blocked, reason)."""
    cfg = load_blacklist()

    domain = _get_domain(email)
    if domain:
        for entry in cfg.get("competitors", []):
            if domain.endswith(entry["domain"]):
                return True, f"Domain match: {entry['company']} ({entry['domain']})"

    company_lower = (company or "").lower()
    for kw in cfg.get("company_keywords", []):
        if kw.lower() in company_lower:
            return True, f"Company keyword match: '{kw}' in '{company}'"

    return False, ""


def apply_blacklist(
    df: pd.DataFrame,
    email_col: str = "EMAIL",
    company_col: str = "COMPANY",
) -> pd.DataFrame:
    """Apply blacklist to DataFrame. Sets ACTION=BLACKLISTED for matches."""
    df = df.copy()
    if "ACTION" not in df.columns:
        df["ACTION"] = "PENDING"
    if "BLACKLIST_REASON" not in df.columns:
        df["BLACKLIST_REASON"] = ""

    hits = []
    for idx, row in df.iterrows():
        blocked, reason = is_blacklisted(
            str(row.get(email_col, "")), str(row.get(company_col, ""))
        )
        if blocked:
            df.at[idx, "ACTION"] = "BLACKLISTED"
            df.at[idx, "BLACKLIST_REASON"] = reason
            hits.append({
                "timestamp": datetime.now().isoformat(),
                "email": row.get(email_col, ""),
                "company": row.get(company_col, ""),
                "reason": reason,
            })

    if hits:
        _log_hits(hits)

    return df


def _log_hits(hits: list[dict]):
    file_exists = BLACKLIST_HITS_LOG.exists()
    with open(BLACKLIST_HITS_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "email", "company", "reason"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(hits)
