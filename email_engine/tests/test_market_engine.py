# -*- coding: utf-8 -*-
"""
Tests for email_engine.intelligence.market_engine.

Uses monkeypatch on `_fetch_rows` to inject synthetic rate data, avoiding
any dependency on the real Parquet file.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

# Allow running pytest from repo root OR inside email_engine/
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
sys.path.insert(0, str(_REPO))

from email_engine.intelligence import market_engine as me  # noqa: E402


# ─── Synthetic data generators ──────────────────────────────────────────────

def _rows_stable(n: int = 120) -> list[dict]:
    """Generate stable rates ~2000 USD over last 90 days."""
    base = dt.date.today() - dt.timedelta(days=85)
    out = []
    for i in range(n):
        out.append({
            "date": base + dt.timedelta(days=i * (85 // max(n, 1))),
            "amount": 2000.0 + (i % 5 - 2) * 10.0,  # tiny noise
        })
    return out


def _rows_urgent() -> list[dict]:
    """Current week ~5% higher than previous week, 100+ samples, low variance."""
    today = dt.date.today()
    # 3 weeks of history: older weeks ~2000, prev week ~2000, this week ~2100
    rows = []
    # Week-by-week ISO date keyed by monday of week
    this_monday = today - dt.timedelta(days=today.weekday())
    prev_monday = this_monday - dt.timedelta(days=7)
    wk3_monday = this_monday - dt.timedelta(days=14)
    wk4_monday = this_monday - dt.timedelta(days=21)

    for offset in range(5):  # 5 points per week
        rows.append({"date": wk4_monday + dt.timedelta(days=offset), "amount": 1995.0})
        rows.append({"date": wk3_monday + dt.timedelta(days=offset), "amount": 2000.0})
        rows.append({"date": prev_monday + dt.timedelta(days=offset), "amount": 2000.0})
        rows.append({"date": this_monday + dt.timedelta(days=offset), "amount": 2100.0})
    # Pad to reach >= 30 samples
    while len(rows) < 100:
        rows.append({"date": wk4_monday + dt.timedelta(days=len(rows) % 7), "amount": 2000.0})
    return rows


def _rows_declining() -> list[dict]:
    """Current week ~5% lower than previous week."""
    today = dt.date.today()
    this_monday = today - dt.timedelta(days=today.weekday())
    prev_monday = this_monday - dt.timedelta(days=7)
    wk3_monday = this_monday - dt.timedelta(days=14)
    rows = []
    for offset in range(5):
        rows.append({"date": wk3_monday + dt.timedelta(days=offset), "amount": 2000.0})
        rows.append({"date": prev_monday + dt.timedelta(days=offset), "amount": 2000.0})
        rows.append({"date": this_monday + dt.timedelta(days=offset), "amount": 1900.0})
    # pad
    while len(rows) < 60:
        rows.append({"date": wk3_monday + dt.timedelta(days=len(rows) % 7), "amount": 2000.0})
    return rows


def _rows_small_sample() -> list[dict]:
    """< 30 rows → must fall back to STABLE."""
    today = dt.date.today()
    return [
        {"date": today - dt.timedelta(days=i), "amount": 2000.0}
        for i in range(5)
    ]


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_cache():
    me.clear_cache()
    yield
    me.clear_cache()


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_state_URGENT(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_urgent())
    result = me.analyze_lane("HPH", "USLAX")
    assert result["state"] == "URGENT"
    assert result["delta_pct"] >= 3.0
    assert result["sample_size"] >= 30
    assert result["confidence"] >= 0.7
    assert result["current_rate_40hq"] is not None


def test_state_STABLE(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_stable(80))
    result = me.analyze_lane("HPH", "USSAV")
    assert result["state"] == "STABLE"
    assert abs(result["delta_pct"]) < 3.0


def test_state_DECLINING(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_declining())
    result = me.analyze_lane("HPH", "USLGB")
    assert result["state"] == "DECLINING"
    assert result["delta_pct"] <= -3.0


def test_fallback_small_sample(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_small_sample())
    result = me.analyze_lane("HPH", "USNYC")
    # Even if delta% spikes, must not report URGENT without enough sample
    assert result["state"] in ("STABLE", "DECLINING")
    assert result["sample_size"] < 30


def test_fallback_no_data(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: [])
    result = me.analyze_lane("HPH", "USLAX")
    assert result["state"] == "STABLE"
    assert result["sample_size"] == 0
    assert result["reason"] == "empty_query"


def test_cache_TTL(monkeypatch):
    """Second call within TTL must return cached value, not re-query."""
    call_count = {"n": 0}

    def _counter(pol, dest):
        call_count["n"] += 1
        return _rows_stable(60)

    monkeypatch.setattr(me, "_fetch_rows", _counter)
    me.analyze_lane("HPH", "USLAX")
    me.analyze_lane("HPH", "USLAX")
    me.analyze_lane("HPH", "USLAX")
    assert call_count["n"] == 1  # only first call hit fetch


def test_cache_different_keys(monkeypatch):
    """Different (pol, dest) pairs must NOT share cache."""
    call_count = {"n": 0}

    def _counter(pol, dest):
        call_count["n"] += 1
        return _rows_stable(40)

    monkeypatch.setattr(me, "_fetch_rows", _counter)
    me.analyze_lane("HPH", "USLAX")
    me.analyze_lane("HPH", "USSAV")
    me.analyze_lane("HCM", "USLAX")
    assert call_count["n"] == 3


def test_bad_args():
    """Empty pol/dest must not crash."""
    r1 = me.analyze_lane("", "")
    r2 = me.analyze_lane("HPH", "")
    assert r1["state"] == "STABLE"
    assert r2["state"] == "STABLE"


def test_forecast_produced(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_urgent())
    result = me.analyze_lane("HPH", "USLAX")
    assert result["forecast_next_week"] is not None
    assert result["forecast_next_week"] > 0


def test_mean_90d_computed(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _rows_stable(60))
    result = me.analyze_lane("HPH", "USLAX")
    assert result["mean_90d"] is not None
    assert 1950 < result["mean_90d"] < 2050
