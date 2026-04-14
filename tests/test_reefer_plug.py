"""tests/test_reefer_plug.py — Unit tests for ERP/jobs/reefer_plug.py (Feature 7).

All tests are pure Python — no Excel I/O, no OneDrive access.
YAML config is provided inline via a fixture (no file I/O needed).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ERP.jobs.reefer_plug import plug_cost, optimal_drop_date  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture — inline rules dict (mirrors reefer_freetime.yaml)
# ---------------------------------------------------------------------------

@pytest.fixture
def rules():
    return {
        "terminals": {
            "USLGB": {"freetime_days": 4, "daily_fee_20RF": 150, "daily_fee_40RF": 200},
            "USLAX": {"freetime_days": 4, "daily_fee_20RF": 160, "daily_fee_40RF": 210},
            "USNYC": {"freetime_days": 5, "daily_fee_20RF": 180, "daily_fee_40RF": 230},
            "default": {"freetime_days": 4, "daily_fee_20RF": 150, "daily_fee_40RF": 200},
        },
        "demurrage": {
            "freetime_days": 7,
            "daily_fee_20RF": 100,
            "daily_fee_40RF": 140,
        },
    }


ETA = date(2026, 4, 1)  # Base date for all tests


# ===========================================================================
# plug_cost — core logic
# ===========================================================================

class TestPlugCost:
    def test_drop_within_freetime_zero_cost(self, rules):
        """Drop day 4 = last free day — $0 plug, $0 demurrage."""
        drop = ETA + __import__("datetime").timedelta(days=4)
        result = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert result["plug_days"] == 0
        assert result["plug_fee"] == 0
        assert result["demurrage_days"] == 0
        assert result["total"] == 0

    def test_drop_day5_one_plug_day(self, rules):
        """Drop on day 5 at USLGB 40RF: 1 plug day × $200 = $200."""
        drop = ETA + __import__("datetime").timedelta(days=5)
        result = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert result["plug_days"] == 1
        assert result["plug_fee"] == 200
        assert result["demurrage_days"] == 0
        assert result["total"] == 200

    def test_drop_day5_at_lgb_40rf(self, rules):
        """Spec test: eta+5 days at USLGB 40RF → plug_days=1, plug_fee=200."""
        drop = ETA + __import__("datetime").timedelta(days=5)
        r = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r["plug_days"] == 1
        assert r["plug_fee"] == 200

    def test_drop_day10_at_lgb_40rf(self, rules):
        """Spec test: eta+10 days → plug_days=6, plug_fee=1200, dem_days=3, dem_fee=420."""
        drop = ETA + __import__("datetime").timedelta(days=10)
        r = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r["plug_days"] == 6
        assert r["plug_fee"] == 1200
        assert r["demurrage_days"] == 3
        assert r["demurrage_fee"] == 420
        assert r["total"] == 1620

    def test_drop_same_day_zero_cost(self, rules):
        """Picked up on arrival day: 0 days at terminal."""
        r = plug_cost(ETA, ETA, "USLGB", "20RF", rules)
        assert r["plug_fee"] == 0
        assert r["total"] == 0

    def test_20rf_vs_40rf_different_daily_rate(self, rules):
        """20RF and 40RF have different daily fees — verify both correct."""
        drop = ETA + __import__("datetime").timedelta(days=5)
        r20 = plug_cost(ETA, drop, "USLGB", "20RF", rules)
        r40 = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r20["plug_fee"] == 150
        assert r40["plug_fee"] == 200

    def test_usnyc_has_5_freetime_days(self, rules):
        """USNYC has 5 freetime days — day 5 should still be free."""
        drop = ETA + __import__("datetime").timedelta(days=5)
        r = plug_cost(ETA, drop, "USNYC", "40RF", rules)
        assert r["plug_days"] == 0
        assert r["plug_fee"] == 0

    def test_usnyc_day6_one_plug_day(self, rules):
        """USNYC: day 6 → 1 plug day at $230/day for 40RF."""
        drop = ETA + __import__("datetime").timedelta(days=6)
        r = plug_cost(ETA, drop, "USNYC", "40RF", rules)
        assert r["plug_days"] == 1
        assert r["plug_fee"] == 230

    def test_unknown_pod_falls_back_to_default(self, rules):
        """Unknown POD uses default terminal config (4 free days)."""
        drop = ETA + __import__("datetime").timedelta(days=5)
        r = plug_cost(ETA, drop, "USUNK", "40RF", rules)
        # default = 200/day for 40RF, 4 free days → 1 plug day
        assert r["plug_days"] == 1
        assert r["plug_fee"] == 200

    def test_invalid_cont_type_raises(self, rules):
        drop = ETA + __import__("datetime").timedelta(days=5)
        with pytest.raises(ValueError, match="40RF"):
            plug_cost(ETA, drop, "USLGB", "40GP", rules)

    def test_total_equals_plug_plus_demurrage(self, rules):
        drop = ETA + __import__("datetime").timedelta(days=10)
        r = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r["total"] == r["plug_fee"] + r["demurrage_fee"]


# ===========================================================================
# optimal_drop_date
# ===========================================================================

class TestOptimalDropDate:
    def test_lgb_optimal_is_eta_plus_4(self, rules):
        """USLGB freetime=4 days → optimal = ETA + 4."""
        result = optimal_drop_date(ETA, "USLGB", "40RF", rules)
        assert result["optimal_date"] == ETA + __import__("datetime").timedelta(days=4)

    def test_nyc_optimal_is_eta_plus_5(self, rules):
        """USNYC freetime=5 days → optimal = ETA + 5."""
        result = optimal_drop_date(ETA, "USNYC", "40RF", rules)
        assert result["optimal_date"] == ETA + __import__("datetime").timedelta(days=5)

    def test_cost_at_optimal_is_zero_plug(self, rules):
        """At the optimal drop date, plug cost should be exactly $0."""
        result = optimal_drop_date(ETA, "USLGB", "40RF", rules)
        assert result["cost_at_optimal"]["plug_fee"] == 0
        assert result["cost_at_optimal"]["plug_days"] == 0

    def test_freetime_days_returned(self, rules):
        result = optimal_drop_date(ETA, "USLGB", "40RF", rules)
        assert result["freetime_days"] == 4

    def test_daily_plug_fee_returned_correctly(self, rules):
        r40 = optimal_drop_date(ETA, "USLGB", "40RF", rules)
        r20 = optimal_drop_date(ETA, "USLGB", "20RF", rules)
        assert r40["daily_plug_fee"] == 200
        assert r20["daily_plug_fee"] == 150

    def test_unknown_pod_uses_default_freetime(self, rules):
        result = optimal_drop_date(ETA, "USUNK", "40RF", rules)
        assert result["optimal_date"] == ETA + __import__("datetime").timedelta(days=4)
        assert result["freetime_days"] == 4

    def test_20rf_lgb_optimal(self, rules):
        result = optimal_drop_date(ETA, "USLGB", "20RF", rules)
        assert result["optimal_date"] == ETA + __import__("datetime").timedelta(days=4)
        assert result["daily_plug_fee"] == 150


# ===========================================================================
# Edge cases — boundary values
# ===========================================================================

class TestEdgeCases:
    def test_drop_before_eta_treated_as_zero(self, rules):
        """If drop_date < eta (data error), treat as 0 days — no fees."""
        drop = ETA + __import__("datetime").timedelta(days=-1)
        r = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r["plug_fee"] == 0
        assert r["total"] == 0

    def test_very_late_drop_large_fees(self, rules):
        """30 days at USLGB 40RF: plug=26d×200=$5200, dem=23d×140=$3220."""
        drop = ETA + __import__("datetime").timedelta(days=30)
        r = plug_cost(ETA, drop, "USLGB", "40RF", rules)
        assert r["plug_days"] == 26
        assert r["plug_fee"] == 5200
        assert r["demurrage_days"] == 23
        assert r["demurrage_fee"] == 3220
        assert r["total"] == 8420
