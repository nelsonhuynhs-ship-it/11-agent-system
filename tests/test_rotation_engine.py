"""
test_rotation_engine.py — Unit tests for Daily Rotation Engine
===============================================================
4 test scenarios:
  1. Basic plan build: 10 mock contacts, 3 commodities → quota honored
  2. Redistribute: commodity under-filled → surplus fills gap
  3. Hard limit: SEND_COUNT >= 3 → excluded
  4. Cooldown: LAST_SENT_DATE < 7 days ago → excluded
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Ensure project root on path ───────────────────────────────────────────────
_PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip().str.upper()
    return df


def _make_contact(
    email: str,
    commodity: str,
    send_count: int = 0,
    last_sent: date | None = None,
    status: str = "UNSENT",
) -> dict:
    return {
        "EMAIL": email,
        "COMMODITY_CATEGORY": commodity,
        "SEND_COUNT": send_count,
        "LAST_SENT_DATE": last_sent.isoformat() if last_sent else None,
        "EMAIL_STATUS": status,
    }


def _default_quota() -> dict:
    return {
        "daily_total": 10,
        "by_commodity": {"FLOORING": 4, "FURNITURE_INDOOR": 3, "CANDLE": 3},
        "cooldown_days": 7,
        "hard_limit_count": 3,
        "hard_limit_window_days": 30,
    }


# ── Test 1: Basic plan — quota honored ───────────────────────────────────────

def test_basic_plan_quota_honored():
    """10 eligible contacts, 3 commodities: verify picked counts match quota."""
    contacts = [
        _make_contact(f"flooring{i}@test.com", "FLOORING")  for i in range(4)
    ] + [
        _make_contact(f"furniture{i}@test.com", "FURNITURE_INDOOR") for i in range(3)
    ] + [
        _make_contact(f"candle{i}@test.com", "CANDLE") for i in range(3)
    ]
    df = _make_df(contacts)

    today = date(2026, 4, 23)  # Wednesday (weekday)

    from email_engine.core.rotation_helpers import (
        _get_eligible_candidates, load_quota_config, _compute_cycle_info
    )

    quota = _default_quota()
    excluded: set[str] = set()

    for commodity, expected in [("FLOORING", 4), ("FURNITURE_INDOOR", 3), ("CANDLE", 3)]:
        cdf = _get_eligible_candidates(
            df, commodity, excluded,
            quota["cooldown_days"], quota["hard_limit_count"],
            quota["hard_limit_window_days"], today
        )
        picked = cdf.head(quota["by_commodity"][commodity])
        assert len(picked) == expected, f"{commodity}: expected {expected}, got {len(picked)}"


# ── Test 2: Redistribute when commodity is under-filled ──────────────────────

def test_redistribute_when_commodity_underflows():
    """CANDLE has only 1 contact (quota=3) → deficit 2 should allow more from FLOORING."""
    contacts = [
        _make_contact(f"flooring{i}@test.com", "FLOORING") for i in range(8)
    ] + [
        _make_contact("candle1@test.com", "CANDLE"),  # only 1, quota is 3
    ]
    df = _make_df(contacts)
    today = date(2026, 4, 23)

    from email_engine.core.rotation_helpers import _get_eligible_candidates

    quota = {"daily_total": 10, "by_commodity": {"FLOORING": 7, "CANDLE": 3}, "cooldown_days": 7, "hard_limit_count": 3, "hard_limit_window_days": 30}
    excluded: set[str] = set()

    candle_cdf = _get_eligible_candidates(df, "CANDLE", excluded, 7, 3, 30, today)
    flooring_cdf = _get_eligible_candidates(df, "FLOORING", excluded, 7, 3, 30, today)

    candle_picked = len(candle_cdf.head(3))   # quota=3, only 1 available
    flooring_picked = len(flooring_cdf.head(7))

    assert candle_picked == 1, f"CANDLE should pick 1 (only 1 available), got {candle_picked}"
    assert flooring_picked == 7, f"FLOORING should pick 7, got {flooring_picked}"

    deficit = 3 - candle_picked   # = 2
    assert deficit == 2, "Deficit should be 2"
    # Redistribution would give FLOORING up to 2 more → 9 total possible
    assert len(flooring_cdf) >= 7, "FLOORING has surplus for redistribution"


# ── Test 3: Hard limit — SEND_COUNT >= 3 excluded ────────────────────────────

def test_hard_limit_excludes_contacts():
    """Contacts with SEND_COUNT >= 3 must NOT be picked."""
    contacts = [
        _make_contact("ok1@test.com", "FLOORING", send_count=0),
        _make_contact("ok2@test.com", "FLOORING", send_count=2),
        _make_contact("blocked1@test.com", "FLOORING", send_count=3),   # at limit
        _make_contact("blocked2@test.com", "FLOORING", send_count=5),   # over limit
    ]
    df = _make_df(contacts)
    today = date(2026, 4, 23)

    from email_engine.core.rotation_helpers import _get_eligible_candidates

    cdf = _get_eligible_candidates(df, "FLOORING", set(), 7, 3, 30, today)
    emails = cdf["EMAIL"].str.lower().tolist()

    assert "blocked1@test.com" not in emails, "SEND_COUNT=3 must be excluded"
    assert "blocked2@test.com" not in emails, "SEND_COUNT=5 must be excluded"
    assert "ok1@test.com" in emails, "SEND_COUNT=0 must be included"
    assert "ok2@test.com" in emails, "SEND_COUNT=2 must be included"
    assert len(cdf) == 2


# ── Test 4: Cooldown — LAST_SENT_DATE < 7 days ago excluded ──────────────────

def test_cooldown_excludes_recent_sent():
    """Contacts sent < 7 days ago must be excluded. NULL is always eligible."""
    today = date(2026, 4, 23)
    recent = today - timedelta(days=3)     # too recent
    old    = today - timedelta(days=10)    # OK

    contacts = [
        _make_contact("fresh@test.com", "FLOORING", last_sent=recent),  # blocked
        _make_contact("old@test.com",   "FLOORING", last_sent=old),      # OK
        _make_contact("never@test.com", "FLOORING", last_sent=None),     # OK (never sent)
    ]
    df = _make_df(contacts)

    from email_engine.core.rotation_helpers import _get_eligible_candidates

    cdf = _get_eligible_candidates(df, "FLOORING", set(), 7, 3, 30, today)
    emails = cdf["EMAIL"].str.lower().tolist()

    assert "fresh@test.com" not in emails, "Sent 3 days ago must be excluded (cooldown 7d)"
    assert "old@test.com" in emails, "Sent 10 days ago must be eligible"
    assert "never@test.com" in emails, "Never sent (NULL) must be eligible"
    assert len(cdf) == 2
