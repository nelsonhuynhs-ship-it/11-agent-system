"""
test_cost_addons.py — Unit tests for ERP Feature 10: cost_addons.py
====================================================================
Tests:
  - commission_for: known customer, unknown customer, zero profit, PAID guard
  - insurance_premium: class A default, class A reefer, class B/C, invalid class
  - trucking_fee: CY-DOOR known zone, port-direct (0), CY-CY forced off, 20GP factor
  - compute_net_profit: 3 integration scenarios
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure ERP package is importable from repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ERP.intelligence.cost_addons import (
    commission_for,
    compute_net_profit,
    insurance_premium,
    load_rules,
    trucking_fee,
)

# ---------------------------------------------------------------------------
# Inline rules fixture — no filesystem dependency
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rules() -> dict:
    """Canonical rules dict used across all tests."""
    return {
        "default_commission_rate": 0.50,
        "customer_commission": {
            "VIFON EXPORT": 0.40,
            "NAFOODS": 0.45,
            "SIRI": 0.50,
            "PANDA DAD": 0.50,
        },
        "insurance_rates": {
            "A": {"default": 0.0015, "REEFER": 0.0020},
            "B": {"default": 0.0010},
            "C": {"default": 0.0005},
        },
        "trucking": {
            "zones": {
                "CHICAGO, IL": 1800,
                "DENVER, CO": 1400,
                "SALT LAKE CITY, UT": 1600,
                "ATLANTA, GA": 2200,
                "HOUSTON, TX": 2000,
                "DALLAS, TX": 1900,
                "LOS ANGELES, CA": 0,
                "LONG BEACH, CA": 0,
                "NEW YORK, NY": 0,
                "SAVANNAH, GA": 0,
            },
            "factor_20GP": 0.6,
            "factor_40HC": 1.0,
            "tthq_fee": 150,
        },
        "withholding_tax_rate": 0.03,
    }


# ---------------------------------------------------------------------------
# commission_for
# ---------------------------------------------------------------------------

class TestCommissionFor:
    def test_vifon_export_gross_1000(self, rules):
        """VIFON EXPORT rate=0.40: pool=400, net_co=600, tax=600*0.03=18."""
        res = commission_for("VIFON EXPORT", 1000.0, rules)
        assert res["client"] == pytest.approx(400.0)
        assert res["carrier"] == pytest.approx(0.0)
        assert res["tax"] == pytest.approx(18.0)       # 600 * 0.03
        assert res["net_company"] == pytest.approx(582.0)  # 600 - 18

    def test_nafoods_rate_045(self, rules):
        """NAFOODS rate=0.45: pool=450, net_co=550, tax=550*0.03=16.50."""
        res = commission_for("NAFOODS", 1000.0, rules)
        assert res["client"] == pytest.approx(450.0)
        assert res["tax"] == pytest.approx(16.50)
        assert res["net_company"] == pytest.approx(533.50)

    def test_unknown_customer_uses_default(self, rules):
        """Unknown customer falls back to default 0.50."""
        res = commission_for("SOME NEW CLIENT", 500.0, rules)
        assert res["client"] == pytest.approx(250.0)   # 500 * 0.50
        assert res["tax"] == pytest.approx(7.50)       # 250 * 0.03
        assert res["net_company"] == pytest.approx(242.50)

    def test_zero_gross_returns_zeros(self, rules):
        res = commission_for("SIRI", 0.0, rules)
        assert all(v == 0.0 for v in res.values())

    def test_negative_gross_returns_zeros(self, rules):
        res = commission_for("SIRI", -100.0, rules)
        assert all(v == 0.0 for v in res.values())

    def test_case_insensitive_lookup(self, rules):
        """customer key is uppercased internally, so both cases resolve to same rate."""
        lower = commission_for("vifon export", 1000.0, rules)
        upper = commission_for("VIFON EXPORT", 1000.0, rules)
        # Both normalise to "VIFON EXPORT" → rate 0.40
        assert lower["client"] == pytest.approx(400.0)
        assert upper["client"] == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# insurance_premium
# ---------------------------------------------------------------------------

class TestInsurancePremium:
    def test_class_a_default(self, rules):
        """ICC-A default rate 0.15% on non-reefer."""
        assert insurance_premium(10_000, "40HC", "A", rules) == pytest.approx(15.0)

    def test_class_a_reefer_40rf(self, rules):
        """ICC-A reefer surcharge 0.20% on 40RF."""
        assert insurance_premium(10_000, "40RF", "A", rules) == pytest.approx(20.0)

    def test_class_a_reefer_20rf(self, rules):
        """20RF also triggers REEFER rate."""
        assert insurance_premium(10_000, "20RF", "A", rules) == pytest.approx(20.0)

    def test_class_b_default(self, rules):
        assert insurance_premium(10_000, "40HC", "B", rules) == pytest.approx(10.0)

    def test_class_c_default(self, rules):
        assert insurance_premium(10_000, "40HC", "C", rules) == pytest.approx(5.0)

    def test_zero_cargo_value(self, rules):
        assert insurance_premium(0, "40HC", "A", rules) == 0.0

    def test_invalid_class_raises(self, rules):
        with pytest.raises(ValueError, match="Unknown insurance class"):
            insurance_premium(10_000, "40HC", "D", rules)


# ---------------------------------------------------------------------------
# trucking_fee
# ---------------------------------------------------------------------------

class TestTruckingFee:
    def test_chicago_40hc_cy_door(self, rules):
        """Chicago CY-DOOR: $1,800 + $150 TTHQ = $1,950."""
        fee = trucking_fee("CHICAGO, IL", "40HC", rules, cy_door=True)
        assert fee == pytest.approx(1950.0)

    def test_chicago_20gp_cy_door(self, rules):
        """20GP gets 0.6 factor: 1800*0.6 + 150 = 1,230."""
        fee = trucking_fee("CHICAGO, IL", "20GP", rules, cy_door=True)
        assert fee == pytest.approx(1230.0)

    def test_la_port_direct_zero(self, rules):
        """Los Angeles zone = 0 → no trucking even CY-DOOR."""
        fee = trucking_fee("LOS ANGELES, CA", "40HC", rules, cy_door=True)
        assert fee == 0.0

    def test_cy_cy_forced_zero(self, rules):
        """CY-CY flag forces 0 regardless of destination."""
        fee = trucking_fee("CHICAGO, IL", "40HC", rules, cy_door=False)
        assert fee == 0.0

    def test_unknown_destination_zero(self, rules):
        """Destination not in zones → 0 trucking."""
        fee = trucking_fee("SOMEWHERE, AK", "40HC", rules, cy_door=True)
        assert fee == 0.0

    def test_dest_without_comma_normalised(self, rules):
        """'CHICAGO IL' (no comma) normalises to 'CHICAGO, IL'."""
        fee = trucking_fee("CHICAGO IL", "40HC", rules, cy_door=True)
        assert fee == pytest.approx(1950.0)

    def test_atlanta_40hc(self, rules):
        """Atlanta $2,200 + $150 = $2,350."""
        fee = trucking_fee("ATLANTA, GA", "40HC", rules, cy_door=True)
        assert fee == pytest.approx(2350.0)


# ---------------------------------------------------------------------------
# compute_net_profit — integration scenarios
# ---------------------------------------------------------------------------

class TestComputeNetProfit:
    def test_siri_2x40hq_paid_cy_cy(self, rules):
        """
        Scenario 1: SIRI, gross $1,200, PAID, CY-CY, no insurance.
        KB pool = 50% = 600, net_co = 600, tax = 18.
        trucking = 0 (CY-CY), insurance = 0.
        net_profit = 1200 - 600 - 0 - 0 = 600.
        """
        job = {
            "CRM_ID": "SIRI",
            "Quantity": 2,
            "Container_Type": "40HQ",
            "Selling_Rate": 0,
            "Buying_Rate": 0,
            "Profit": 1200.0,
            "Status": "PAID",
            "SERVICE": "CY-CY",
            "Door_Address": "",
            "cargo_value": 0,
            "insurance_class": "",
        }
        r = compute_net_profit(job, rules)
        assert r["gross_profit"] == pytest.approx(1200.0)
        assert r["kb_client"] == pytest.approx(600.0)
        assert r["kb_carrier"] == pytest.approx(0.0)
        assert r["kb_tax"] == pytest.approx(18.0)
        assert r["trucking"] == pytest.approx(0.0)
        assert r["insurance"] == pytest.approx(0.0)
        assert r["net_profit"] == pytest.approx(600.0)

    def test_nafoods_40rf_reefer_insurance(self, rules):
        """
        Scenario 2: NAFOODS, 1x40RF, gross $2,000, PAID, CY-CY.
        Insurance ICC-A reefer on $50,000 cargo = 50000*0.002 = $100.
        KB pool = 45% of 2000 = 900. net_co = 1100. tax = 33.
        net_profit = 2000 - 900 - 100 = 1000.
        """
        job = {
            "CRM_ID": "NAFOODS",
            "Quantity": 1,
            "Container_Type": "40RF",
            "Selling_Rate": 0,
            "Buying_Rate": 0,
            "Profit": 2000.0,
            "Status": "PAID",
            "SERVICE": "CY-CY",
            "Door_Address": "",
            "cargo_value": 50_000,
            "insurance_class": "A",
        }
        r = compute_net_profit(job, rules)
        assert r["gross_profit"] == pytest.approx(2000.0)
        assert r["kb_client"] == pytest.approx(900.0)
        assert r["insurance"] == pytest.approx(100.0)
        assert r["net_profit"] == pytest.approx(1000.0)

    def test_cy_door_chicago_with_commission(self, rules):
        """
        Scenario 3: SIRI CY-DOOR Chicago IL, gross $1,200, PAID, 40HC.
        KB = 50% of 1200 = 600.
        Trucking = 1800 + 150 = 1950.
        Insurance = 0.
        net_profit = 1200 - 600 - 1950 = -1350.
        """
        job = {
            "CRM_ID": "SIRI",
            "Quantity": 1,
            "Container_Type": "40HC",
            "Selling_Rate": 0,
            "Buying_Rate": 0,
            "Profit": 1200.0,
            "Status": "PAID",
            "SERVICE": "CY-DOOR",
            "Door_Address": "CHICAGO, IL",
            "cargo_value": 0,
            "insurance_class": "",
        }
        r = compute_net_profit(job, rules)
        assert r["gross_profit"] == pytest.approx(1200.0)
        assert r["kb_client"] == pytest.approx(600.0)
        assert r["trucking"] == pytest.approx(1950.0)
        assert r["net_profit"] == pytest.approx(-1350.0)

    def test_unpaid_status_no_commission(self, rules):
        """Status != PAID => no KB, net = gross - trucking - insurance."""
        job = {
            "CRM_ID": "SIRI",
            "Quantity": 1,
            "Container_Type": "40HC",
            "Selling_Rate": 0,
            "Buying_Rate": 0,
            "Profit": 800.0,
            "Status": "CONFIRMED",
            "SERVICE": "CY-CY",
            "Door_Address": "",
            "cargo_value": 0,
            "insurance_class": "",
        }
        r = compute_net_profit(job, rules)
        assert r["kb_client"] == 0.0
        assert r["net_profit"] == pytest.approx(800.0)

    def test_profit_computed_from_rates_if_missing(self, rules):
        """When Profit key absent, fallback to (sell-buy)*qty."""
        job = {
            "CRM_ID": "SIRI",
            "Quantity": 2,
            "Container_Type": "40HC",
            "Selling_Rate": 1500,
            "Buying_Rate": 900,
            "Profit": None,
            "Status": "PAID",
            "SERVICE": "CY-CY",
            "Door_Address": "",
            "cargo_value": 0,
            "insurance_class": "",
        }
        r = compute_net_profit(job, rules)
        # gross = (1500-900)*2 = 1200
        assert r["gross_profit"] == pytest.approx(1200.0)


# ---------------------------------------------------------------------------
# load_rules smoke test
# ---------------------------------------------------------------------------

def test_load_rules_returns_dict():
    """load_rules() should return a dict with expected top-level keys."""
    r = load_rules()
    assert isinstance(r, dict)
    assert "default_commission_rate" in r
    assert "insurance_rates" in r
    assert "trucking" in r
