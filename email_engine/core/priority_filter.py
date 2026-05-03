"""
priority_filter.py — Single source of truth for "priority contact" guard.

A priority contact is anyone who Nelson has invested personal attention in,
or anyone who has replied (human). They MUST NEVER be included in bulk
rotation / Quick Send blasts — only the Priority tab may contact them.

Applied at every bulk entry point:
  - /api/prospects           (web_server.py)
  - /api/bulk/build          (web_server.py)
  - rotation_helpers         (_get_eligible_candidates)

Why centralised: rules were scattered (only TIER filtered in /api/prospects,
nothing filtered in rotation). This module unifies the definition so a
future rule change touches one place.
"""
from __future__ import annotations

import pandas as pd

PRIORITY_REPLY_STATUS: frozenset[str] = frozenset({"HUMAN_REPLY"})
PRIORITY_TIER:         frozenset[str] = frozenset({"VIP", "HOT"})
PRIORITY_ACTION:       frozenset[str] = frozenset({"PERSONALIZED", "FOLLOW_UP"})


def _norm(val) -> str:
    return str(val or "").strip().upper()


def is_priority_row(row) -> bool:
    """Return True if this contact must be excluded from bulk blasts.

    Accepts a dict-like row (pd.Series or dict). Safe when columns missing.
    """
    try:
        if _norm(row.get("REPLY_STATUS")) in PRIORITY_REPLY_STATUS:
            return True
        if _norm(row.get("TIER")) in PRIORITY_TIER:
            return True
        if _norm(row.get("ACTION")) in PRIORITY_ACTION:
            return True
    except Exception:
        return False
    return False


def drop_priority(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with priority contacts removed. No-op if df is empty."""
    if df is None or df.empty:
        return df
    mask = pd.Series(False, index=df.index)
    if "REPLY_STATUS" in df.columns:
        mask |= df["REPLY_STATUS"].astype(str).str.upper().str.strip().isin(PRIORITY_REPLY_STATUS)
    if "TIER" in df.columns:
        mask |= df["TIER"].astype(str).str.upper().str.strip().isin(PRIORITY_TIER)
    if "ACTION" in df.columns:
        mask |= df["ACTION"].astype(str).str.upper().str.strip().isin(PRIORITY_ACTION)
    return df[~mask]


def priority_reason(row) -> str:
    """Human-readable reason for skip logs."""
    reasons = []
    if _norm(row.get("REPLY_STATUS")) in PRIORITY_REPLY_STATUS:
        reasons.append(f"reply={_norm(row.get('REPLY_STATUS'))}")
    if _norm(row.get("TIER")) in PRIORITY_TIER:
        reasons.append(f"tier={_norm(row.get('TIER'))}")
    if _norm(row.get("ACTION")) in PRIORITY_ACTION:
        reasons.append(f"action={_norm(row.get('ACTION'))}")
    return ",".join(reasons) or "priority"
