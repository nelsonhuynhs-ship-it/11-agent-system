"""Unit tests for Pricing_Engine.market_report.schemas."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from Pricing_Engine.market_report.schemas import (
    CapacitySignal,
    Catalyst,
    CostingItem,
    ForecastScenario,
)


# ── CostingItem ────────────────────────────────────────────────────────────────

def test_costing_item_create_and_serialize():
    c = CostingItem(
        lane="WC",
        carrier="ONE",
        rate_type="FIX",
        container="40HC",
        price=1835.0,
        valid_from=date(2026, 4, 1),
        valid_to=date(2026, 4, 8),
        is_pudong_best=True,
        spread_vs_lane_avg=-150.0,
    )
    assert c.lane == "WC"
    assert c.carrier == "ONE"
    d = c.to_dict()
    assert d["price"] == 1835.0
    # Dates should be ISO strings
    assert d["valid_from"] == "2026-04-01"
    assert d["valid_to"] == "2026-04-08"
    assert d["is_pudong_best"] is True


def test_costing_item_optional_dates():
    c = CostingItem(
        lane="EC",
        carrier="HPL",
        rate_type="SCFI",
        container="40HC",
        price=2839.0,
        valid_from=None,
        valid_to=None,
    )
    d = c.to_dict()
    assert d["valid_from"] is None
    assert d["valid_to"] is None


# ── CapacitySignal ─────────────────────────────────────────────────────────────

def test_capacity_signal_valid():
    s = CapacitySignal(
        week="2026-W15",
        carrier="ONE",
        lane="WC",
        dimension="space",
        status="OPEN",
        score=4,
        notes="accepting spot",
        entered_by="CS_team",
        entered_at=datetime(2026, 4, 10, 9, 0),
    )
    assert s.score == 4
    d = s.to_dict()
    assert d["entered_at"] == "2026-04-10T09:00:00"


@pytest.mark.parametrize("bad_score", [0, 6, -1, 100])
def test_capacity_signal_score_out_of_range(bad_score):
    with pytest.raises(ValueError, match="score must be 1..5"):
        CapacitySignal(
            week="2026-W15",
            carrier="ONE",
            lane="WC",
            dimension="space",
            status="OPEN",
            score=bad_score,
        )


def test_capacity_signal_score_boundary():
    # 1 and 5 must be allowed
    CapacitySignal(week="2026-W15", carrier="X", lane="ALL",
                   dimension="space", status="OPEN", score=1)
    CapacitySignal(week="2026-W15", carrier="X", lane="ALL",
                   dimension="space", status="OPEN", score=5)


# ── Catalyst ───────────────────────────────────────────────────────────────────

def test_catalyst_basic():
    c = Catalyst(
        source="Panjiva",
        category="surcharge",
        headline="HPL EFS $320/40HC",
        body="HPL announces emergency fuel surcharge on TP lanes.",
        impact_direction="UP",
        impact_magnitude="MED",
        affected_lanes=["WC", "EC"],
        affected_carriers=["HPL"],
        effective_date=date(2026, 3, 23),
        confidence=0.85,
        url="https://example.com",
    )
    d = c.to_dict()
    assert d["source"] == "Panjiva"
    assert d["category"] == "surcharge"
    assert d["effective_date"] == "2026-03-23"
    assert "HPL" in d["affected_carriers"]


@pytest.mark.parametrize("bad_conf", [-0.1, 1.5, 2.0])
def test_catalyst_confidence_out_of_range(bad_conf):
    with pytest.raises(ValueError, match="confidence must be 0..1"):
        Catalyst(
            source="Manual",
            category="policy",
            headline="x",
            body="x",
            impact_direction="FLAT",
            impact_magnitude="LOW",
            confidence=bad_conf,
        )


# ── ForecastScenario ───────────────────────────────────────────────────────────

def test_forecast_scenario_invariant_holds():
    f = ForecastScenario(
        lane="WC",
        week="2026-W16",
        container="40HC",
        low_case=1700.0,
        base_case=1900.0,
        high_case=2100.0,
        confidence=0.6,
        rationale="Demand steady, fuel surcharge pending",
    )
    assert f.low_case <= f.base_case <= f.high_case


@pytest.mark.parametrize(
    "low,base,high",
    [
        (2000, 1900, 2100),  # low > base
        (1700, 2200, 2100),  # base > high
        (2100, 1900, 1700),  # fully inverted
    ],
)
def test_forecast_scenario_invariant_violated(low, base, high):
    with pytest.raises(ValueError, match="low<=base<=high"):
        ForecastScenario(
            lane="WC",
            week="2026-W16",
            container="40HC",
            low_case=low,
            base_case=base,
            high_case=high,
        )


def test_forecast_scenario_confidence_validation():
    with pytest.raises(ValueError, match="confidence must be 0..1"):
        ForecastScenario(
            lane="EC",
            week="2026-W16",
            container="40HC",
            low_case=2500,
            base_case=2700,
            high_case=2900,
            confidence=1.5,
        )
