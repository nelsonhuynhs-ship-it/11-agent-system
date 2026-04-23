"""
rotation_helpers.py — Internal helpers for Daily Rotation Engine
=================================================================
Split from rotation_engine.py to keep each file under 200 lines.

Exports:
    load_quota_config()
    load_excluded_emails()
    load_master_df()
    _get_eligible_candidates()
    _compute_cycle_info()
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger("rotation_engine")

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE       = Path(__file__).parent.parent        # email_engine/
_ONEDRIVE   = Path("D:/OneDrive/NelsonData/email")
# v7 primary (22,854 CNEE × 62 cols). Fallback v6 only if v7 missing on this machine.
_V7 = _ONEDRIVE / "contact_unified_v7.xlsx"
_V6 = _ONEDRIVE / "contact_unified_v6.xlsx"
MASTER_FILE = _V7 if _V7.exists() else _V6
QUOTA_FILE  = _BASE / "config" / "rotation_quota.json"
EXCL_FILE   = _BASE / "data" / "excluded_customers.json"
PLANS_DIR   = _BASE / "data" / "daily_plans"
PLANS_DIR.mkdir(parents=True, exist_ok=True)


# ── Config loaders ────────────────────────────────────────────────────────────

def load_quota_config() -> dict:
    """Load rotation_quota.json; return defaults on any error."""
    _defaults = {
        "daily_total": 700,
        "by_commodity": {
            "FLOORING": 150, "FURNITURE_INDOOR": 150, "CANDLE": 100,
            "RUBBER": 100, "PLASTIC": 100, "PLYWOOD": 50,
            "FOOD_AMBIENT": 30, "OTHERS": 20,
        },
        "cooldown_days": 7,
        "hard_limit_count": 3,
        "hard_limit_window_days": 30,
    }
    try:
        raw = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
        _defaults.update(raw)
        return _defaults
    except Exception as exc:
        log.warning("load_quota_config: %s — using defaults", exc)
        return _defaults


def load_excluded_emails() -> set[str]:
    """Return set of lowercase excluded emails."""
    try:
        data = json.loads(EXCL_FILE.read_text(encoding="utf-8"))
        return {e.lower().strip() for e in data.get("excluded", {}).keys() if e}
    except Exception as exc:
        log.warning("load_excluded_emails: %s — returning empty set", exc)
        return set()


_MASTER_CACHE: dict = {"df": None, "mtime": 0.0}


def load_master_df() -> pd.DataFrame:
    """Load contact_unified_v6.xlsx sheet CNEE; raise FileNotFoundError if missing.

    Caches in-process using file mtime — re-reads only when file changes on disk.
    Uses xlsx_read_lock to prevent reading while a concurrent write is in progress.
    """
    from email_engine.core.xlsx_lock import xlsx_read_lock  # inline import avoids circular

    if not MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Master file not found: {MASTER_FILE}. "
            "Ensure OneDrive is synced."
        )
    mtime = MASTER_FILE.stat().st_mtime
    if _MASTER_CACHE["df"] is not None and _MASTER_CACHE["mtime"] == mtime:
        return _MASTER_CACHE["df"]
    with xlsx_read_lock(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, sheet_name="CNEE")
    df.columns = df.columns.str.strip().str.upper()
    _MASTER_CACHE["df"] = df
    _MASTER_CACHE["mtime"] = mtime
    log.debug("load_master_df: reloaded %d rows (mtime changed)", len(df))
    return df


# ── Candidate filtering ───────────────────────────────────────────────────────

def _get_eligible_candidates(
    df: pd.DataFrame,
    commodity: str,
    excluded_emails: set[str],
    cooldown_days: int,
    hard_limit: int,
    hard_limit_window_days: int,
    today: date,
) -> pd.DataFrame:
    """Return eligible rows for a given commodity, sorted for priority pick.

    Eligibility rules:
    1. COMMODITY_CATEGORY == commodity (or category is in OTHERS catch-all)
    2. EMAIL not in excluded_emails
    3. SEND_COUNT < hard_limit (3 sends within window)
    4. LAST_SENT_DATE is NULL  OR  > cooldown_days ago
    """
    cutoff_cooldown = pd.Timestamp(today - timedelta(days=cooldown_days))
    cutoff_window   = pd.Timestamp(today - timedelta(days=hard_limit_window_days))

    # Commodity filter — handle OTHERS as catch-all
    defined_commodities = set()  # populated by caller when needed
    if commodity == "OTHERS":
        # Include all rows whose COMMODITY_CATEGORY is not in the main quota keys
        # We pass this externally via df already pre-filtered.
        cdf = df[df.get("_is_others", pd.Series(False, index=df.index))]
    else:
        col = "COMMODITY_CATEGORY"
        if col not in df.columns:
            log.warning("COMMODITY_CATEGORY column missing — returning empty")
            return pd.DataFrame()
        cdf = df[df[col].str.upper().str.strip() == commodity.upper().strip()]

    # Email column normalisation
    email_col = "EMAIL" if "EMAIL" in cdf.columns else "CNEE_EMAIL"
    if email_col not in cdf.columns:
        log.warning("No email column found in master — returning empty")
        return pd.DataFrame()

    cdf = cdf.copy()
    cdf["_email_lower"] = cdf[email_col].astype(str).str.lower().str.strip()

    # Filter excluded
    cdf = cdf[~cdf["_email_lower"].isin(excluded_emails)]

    # SEND_COUNT filter
    if "SEND_COUNT" in cdf.columns:
        sc = pd.to_numeric(cdf["SEND_COUNT"], errors="coerce").fillna(0)
        cdf = cdf[sc < hard_limit]

    # Cooldown filter (LAST_SENT_DATE)
    if "LAST_SENT_DATE" in cdf.columns:
        lsd = pd.to_datetime(cdf["LAST_SENT_DATE"], errors="coerce")  # Timestamp series
        eligible_mask = lsd.isna() | (lsd < cutoff_cooldown)
        cdf = cdf[eligible_mask]

    # EMAIL_STATUS filter — skip HARD_BOUNCE / UNSUBSCRIBED
    if "EMAIL_STATUS" in cdf.columns:
        bad_status = {"HARD_BOUNCE", "UNSUBSCRIBED", "SPAM", "INVALID"}
        cdf = cdf[~cdf["EMAIL_STATUS"].astype(str).str.upper().isin(bad_status)]

    # Sort: SEND_COUNT ASC, LAST_SENT_DATE ASC NULLS FIRST
    sort_keys: list[str] = []
    if "SEND_COUNT" in cdf.columns:
        cdf["_sc_sort"] = pd.to_numeric(cdf["SEND_COUNT"], errors="coerce").fillna(0)
        sort_keys.append("_sc_sort")
    if "LAST_SENT_DATE" in cdf.columns:
        cdf["_lsd_sort"] = pd.to_datetime(cdf["LAST_SENT_DATE"], errors="coerce")
        sort_keys.append("_lsd_sort")

    if sort_keys:
        cdf = cdf.sort_values(sort_keys, ascending=True, na_position="first")

    return cdf.reset_index(drop=True)


# ── Cycle info ────────────────────────────────────────────────────────────────

def _compute_cycle_info(df: pd.DataFrame, daily_total: int) -> dict[str, Any]:
    """Compute rotation cycle progress info.

    Cycle = one pass through all unsent contacts (~22,842).
    Assumes 5d/week delivery.
    """
    try:
        email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
        total_contacts = len(df)

        # Approximate sent = rows with SEND_COUNT >= 1
        sent_any = 0
        if "SEND_COUNT" in df.columns:
            sc = pd.to_numeric(df["SEND_COUNT"], errors="coerce").fillna(0)
            sent_any = int((sc >= 1).sum())

        remaining = max(0, total_contacts - sent_any)
        days_per_week = 5
        emails_per_week = daily_total * days_per_week

        weeks_to_finish = round(remaining / emails_per_week, 1) if emails_per_week > 0 else 0.0
        weeks_elapsed   = round(sent_any / emails_per_week, 1) if emails_per_week > 0 else 0.0
        # cycle number: 1-indexed, advances after full pass
        cycle_number = int(sent_any / total_contacts) + 1 if total_contacts > 0 else 1
        week_in_cycle = max(1, int(weeks_elapsed % (remaining / emails_per_week + 0.001)) + 1) if emails_per_week > 0 else 1

        return {
            "cycle_number": cycle_number,
            "week_in_cycle": max(1, week_in_cycle),
            "weeks_total_estimate": weeks_to_finish,
            "total_contacts": total_contacts,
            "sent_any": sent_any,
            "total_unsent_remaining": remaining,
        }
    except Exception as exc:
        log.error("_compute_cycle_info error: %s", exc)
        return {
            "cycle_number": 1, "week_in_cycle": 1,
            "weeks_total_estimate": 0.0,
            "total_contacts": 0, "sent_any": 0,
            "total_unsent_remaining": 0,
        }
