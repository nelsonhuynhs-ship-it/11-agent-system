# -*- coding: utf-8 -*-
"""
test_auto_rate_builder.py — Unit tests for Phase 2+3 of auto_rate_builder.

Phase 2: select_top3_distinct_carriers
Phase 3: resolve_inland_gateway + _query_carrier_rate

Mocked DataFrames only — no real Parquet access.
"""
import logging
import pandas as pd
import pytest
from unittest.mock import patch

# Adjust sys.path so the test can import from email_engine/core
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

from email_engine.core.auto_rate_builder import (
    select_top3_distinct_carriers,
    _validate_rate_type_matrix,
    RATE_TYPE_CARRIER_MATRIX,
    resolve_inland_gateway,
    clear_gateway_cache,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_rates(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame matching _query_best_rates output shape."""
    defaults = {
        "carrier": "",
        "rate_type": "FAK",
        "rate_40": 0.0,
        "rate_20": None,
        "exp": None,
        "eff": None,
        "note": "",
        "contract": "",
        "place": "",
        "pod": "",
    }
    records = [{**defaults, **r} for r in rows]
    return pd.DataFrame(records)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestTop3DistinctCarriersBasic:
    """5 carriers in → 3 cheapest returned."""

    def test_top3_distinct_carriers_basic(self):
        rates = _make_rates([
            {"carrier": "CMA",  "rate_type": "FAK",  "rate_40": 3200.0},
            {"carrier": "ONE",  "rate_type": "FAK",  "rate_40": 3100.0},
            {"carrier": "HMM",  "rate_type": "FAK",  "rate_40": 3000.0},
            {"carrier": "HPL",  "rate_type": "SCFI", "rate_40": 2988.0},
            {"carrier": "ZIM",  "rate_type": "FAK",  "rate_40": 3300.0},
        ])
        result = select_top3_distinct_carriers(rates)
        assert len(result) == 3
        carriers = list(result["carrier"])
        assert "HPL" in carriers  # cheapest
        assert "HMM" in carriers
        assert "ONE" in carriers
        assert "ZIM" not in carriers   # 4th cheapest, excluded
        assert "CMA" not in carriers   # 5th, excluded
        # Must be sorted price ASC
        assert list(result["rate_40"]) == sorted(result["rate_40"])


class TestScfiTiebreakWins:
    """HPL SCFI $2988 vs HPL FIX $2988 → SCFI row is kept."""

    def test_scfi_tiebreak_wins(self):
        rates = _make_rates([
            {"carrier": "HPL", "rate_type": "FIX",  "rate_40": 2988.0},
            {"carrier": "HPL", "rate_type": "SCFI", "rate_40": 2988.0},
        ])
        result = select_top3_distinct_carriers(rates)
        assert len(result) == 1
        assert result.iloc[0]["carrier"] == "HPL"
        assert result.iloc[0]["rate_type"] == "SCFI"


class TestFewerThan3Carriers:
    """2 distinct carriers → 2 rows (no padding)."""

    def test_fewer_than_3_carriers(self):
        rates = _make_rates([
            {"carrier": "ONE",  "rate_type": "FAK",  "rate_40": 3100.0},
            {"carrier": "HPL",  "rate_type": "SCFI", "rate_40": 2988.0},
        ])
        result = select_top3_distinct_carriers(rates)
        assert len(result) == 2
        assert set(result["carrier"]) == {"ONE", "HPL"}


class TestInvalidRateTypeRejected:
    """SCFI + Carrier=ONE → excluded with warning (only HPL can use SCFI)."""

    def test_invalid_rate_type_rejected(self, caplog):
        rates = _make_rates([
            {"carrier": "ONE",  "rate_type": "SCFI", "rate_40": 2800.0},  # INVALID
            {"carrier": "CMA",  "rate_type": "FAK",  "rate_40": 3100.0},
            {"carrier": "HPL",  "rate_type": "SCFI", "rate_40": 2988.0},
        ])
        with caplog.at_level(logging.WARNING, logger="auto_rate_builder"):
            result = select_top3_distinct_carriers(rates)

        # ONE SCFI should be dropped
        carriers = list(result["carrier"])
        assert "ONE" not in carriers
        assert "HPL" in carriers
        assert "CMA" in carriers
        # Warning logged
        assert any("INVALID" in msg for msg in caplog.messages)


class TestEmptyInput:
    """Empty DataFrame → empty returned without error."""

    def test_empty_returns_empty(self):
        result = select_top3_distinct_carriers(pd.DataFrame())
        assert result.empty


class TestMultipleRateTypesPerCarrier:
    """HPL has FAK + SCFI rows → keeps cheapest (SCFI at same price wins; else plain cheaper)."""

    def test_multiple_rate_types_per_carrier_keeps_cheapest(self):
        rates = _make_rates([
            {"carrier": "HPL", "rate_type": "FAK",  "rate_40": 3100.0},
            {"carrier": "HPL", "rate_type": "SCFI", "rate_40": 2900.0},  # cheaper
            {"carrier": "ONE", "rate_type": "FAK",  "rate_40": 3000.0},
        ])
        result = select_top3_distinct_carriers(rates)
        hpl_row = result[result["carrier"] == "HPL"]
        assert len(hpl_row) == 1
        assert hpl_row.iloc[0]["rate_40"] == 2900.0
        assert hpl_row.iloc[0]["rate_type"] == "SCFI"


# ── Phase 3: Gateway Routing Tests ──────────────────────────────────────────

def _mock_rate(amount_40: float, carrier: str = "HPL") -> dict:
    """Build a minimal rate dict matching _query_carrier_rate output."""
    return {
        "rate_40":   amount_40,
        "rate_20":   None,
        "exp":       pd.Timestamp("2026-05-31"),
        "eff":       pd.Timestamp("2026-04-01"),
        "rate_type": "FAK",
        "carrier":   carrier,
        "contract":  "",
        "note":      "",
        "place":     "ATLANTA, GA",
        "pod":       "SAVANNAH, GA",
    }


class TestResolveATLRipiViaSav:
    """USATL: RIPI primary succeeds via SAVANNAH, GA → label 'via SAV'."""

    def test_resolve_atl_ripi_via_sav(self):
        clear_gateway_cache()

        def _fake_query(pol, gateway_city, carrier, dest_city, df):
            if "SAVANNAH" in gateway_city.upper():
                return _mock_rate(3200.0, carrier)
            return None

        with patch("email_engine.core.auto_rate_builder._query_carrier_rate", side_effect=_fake_query):
            result = resolve_inland_gateway(pol="HPH", pod="USATL", carrier="HPL", df=pd.DataFrame())

        assert result is not None
        assert "SAVANNAH" in result["gateway_port"].upper()
        assert result["routing_label"] == "via SAV"
        assert result["rate_type_routing"] == "RIPI"
        assert result["rate_40"] == 3200.0


class TestResolveATLFallbackToIPI:
    """USATL: SAV/CHS/NOR all fail → falls back to IPI via LAX, label 'via LAX (IPI)'."""

    def test_resolve_atl_fallback_to_ipi(self):
        clear_gateway_cache()

        def _fake_query(pol, gateway_city, carrier, dest_city, df):
            if "LAX" in gateway_city.upper():
                return _mock_rate(3500.0, carrier)
            return None  # EC ports return None

        with patch("email_engine.core.auto_rate_builder._query_carrier_rate", side_effect=_fake_query):
            result = resolve_inland_gateway(pol="HPH", pod="USATL", carrier="HPL", df=pd.DataFrame())

        assert result is not None
        assert "LAX" in result["gateway_port"].upper()
        assert result["routing_label"] == "via LAX (IPI)"
        assert result["rate_type_routing"] == "IPI"
        assert result["rate_40"] == 3500.0


class TestResolveCHIIpiDefault:
    """USCHI: IPI via LAX-LGB → label '' (no suffix for IPI default)."""

    def test_resolve_chi_ipi_default(self):
        clear_gateway_cache()

        def _fake_query(pol, gateway_city, carrier, dest_city, df):
            if "LAX" in gateway_city.upper():
                return _mock_rate(2800.0, carrier)
            return None

        with patch("email_engine.core.auto_rate_builder._query_carrier_rate", side_effect=_fake_query):
            result = resolve_inland_gateway(pol="HPH", pod="USCHI", carrier="ONE", df=pd.DataFrame())

        assert result is not None
        assert result["routing_label"] == ""
        assert result["rate_type_routing"] == "IPI"
        assert result["rate_40"] == 2800.0


class TestResolveNoRateReturnsNone:
    """All gateway ports return None → resolve_inland_gateway returns None."""

    def test_resolve_no_rate_returns_none(self):
        clear_gateway_cache()

        with patch("email_engine.core.auto_rate_builder._query_carrier_rate", return_value=None):
            result = resolve_inland_gateway(pol="HPH", pod="USATL", carrier="ZIM", df=pd.DataFrame())

        assert result is None


class TestResolveNonInlandPod:
    """Non-inland POD (USLAX) → returns None immediately, no query attempted."""

    def test_resolve_non_inland_pod_returns_none(self):
        clear_gateway_cache()

        with patch("email_engine.core.auto_rate_builder._query_carrier_rate") as mock_q:
            result = resolve_inland_gateway(pol="HPH", pod="USLAX", carrier="HPL", df=pd.DataFrame())

        assert result is None
        mock_q.assert_not_called()
