# -*- coding: utf-8 -*-
"""
test_normalization.py — Task 1.2.1: HDL Normalization Tests
==============================================================
Tests normalize_rate() for all 10 carriers + edge cases.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from Pricing_Engine.normalization.hdl_rules import normalize_rate, HDL_RULES
from Pricing_Engine.normalization.schema import NormalizedRate


def test_hpl_fak():
    """HPL FAK: HDL = $20."""
    r = normalize_rate("HPL", "FAK", 1800, "40HQ", "HCM")
    assert r.hdl_fee == 20
    assert r.normalized_amount == 1780
    assert r.carrier_commission == 35
    assert r.rate_basis == "FAK"
    print(f"  ✓ HPL FAK: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_hpl_fix_40():
    """HPL FIX 40HQ: HDL = $30."""
    r = normalize_rate("HPL", "FIX", 1800, "40HQ", "HCM")
    assert r.hdl_fee == 30
    assert r.normalized_amount == 1770
    print(f"  ✓ HPL FIX/40HQ: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_hpl_fix_20():
    """HPL FIX 20GP: HDL = $20."""
    r = normalize_rate("HPL", "FIX", 900, "20GP", "HCM")
    assert r.hdl_fee == 20
    assert r.normalized_amount == 880
    print(f"  ✓ HPL FIX/20GP: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_hpl_scfi():
    """HPL SCFI: HDL = $10."""
    r = normalize_rate("HPL", "SCFI", 2000, "40HQ", "HCM")
    assert r.hdl_fee == 10
    assert r.normalized_amount == 1990
    assert r.rate_basis == "SCFI"
    print(f"  ✓ HPL SCFI: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_one_fak():
    """ONE FAK: HDL = $20, CAR_COM = $35."""
    r = normalize_rate("ONE", "FAK", 1500, "40HQ", "HPH")
    assert r.hdl_fee == 20
    assert r.normalized_amount == 1480
    assert r.carrier_commission == 35
    print(f"  ✓ ONE FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_yml_fix():
    """YML FIX: HDL = $300."""
    r = normalize_rate("YML", "FIX", 2000, "40HQ", "HCM")
    assert r.hdl_fee == 300
    assert r.normalized_amount == 1700
    print(f"  ✓ YML FIX: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_cosco_dry():
    """COSCO DRY: HDL = $25."""
    r = normalize_rate("COSCO", "DRY", 1600, "40HQ", "HCM")
    assert r.hdl_fee == 25
    assert r.normalized_amount == 1575
    assert r.carrier_commission == 10
    print(f"  ✓ COSCO DRY: ${r.raw_amount} → ${r.normalized_amount}")


def test_cosco_reefer():
    """COSCO REEFER: HDL = $100 (edge case — reefer container)."""
    r = normalize_rate("COSCO", "FAK", 3500, "40RF", "HCM")
    assert r.hdl_fee == 100
    assert r.normalized_amount == 3400
    print(f"  ✓ COSCO REEFER: ${r.raw_amount} → ${r.normalized_amount} (HDL=${r.hdl_fee})")


def test_whl_hcm():
    """WHL HCM: HDL = $25, CAR_COM = $10."""
    r = normalize_rate("WHL", "FAK", 1400, "40HQ", "HCM")
    assert r.hdl_fee == 25
    assert r.normalized_amount == 1375
    assert r.carrier_commission == 10
    print(f"  ✓ WHL HCM: ${r.raw_amount} → ${r.normalized_amount} (CAR_COM=${r.carrier_commission})")


def test_whl_hph():
    """WHL HPH: HDL = $25, CAR_COM = $35 (different from HCM)."""
    r = normalize_rate("WHL", "FAK", 1400, "40HQ", "HPH")
    assert r.hdl_fee == 25
    assert r.normalized_amount == 1375
    assert r.carrier_commission == 35
    print(f"  ✓ WHL HPH: CAR_COM=${r.carrier_commission} (≠ HCM ${10})")


def test_cma_fak():
    """CMA FAK: HDL = $15."""
    r = normalize_rate("CMA", "FAK", 1700, "40HQ", "HCM")
    assert r.hdl_fee == 15
    assert r.normalized_amount == 1685
    print(f"  ✓ CMA FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_cma_fix_tp_pd():
    """CMA FIX TP-PD: HDL = $0 (edge case — no handling fee)."""
    r = normalize_rate("CMA", "FIX_TP_PD", 1700, "40HQ", "HCM")
    assert r.hdl_fee == 0
    assert r.normalized_amount == 1700
    print(f"  ✓ CMA FIX TP-PD: No HDL (${r.hdl_fee})")


def test_zim_fak():
    """ZIM FAK: HDL = $30, CAR_COM = $10."""
    r = normalize_rate("ZIM", "FAK", 2000, "40HQ", "HCM")
    assert r.hdl_fee == 30
    assert r.normalized_amount == 1970
    assert r.carrier_commission == 10
    print(f"  ✓ ZIM FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_hmm_fak():
    """HMM FAK: HDL = $40."""
    r = normalize_rate("HMM", "FAK", 1900, "40HQ", "HCM")
    assert r.hdl_fee == 40
    assert r.normalized_amount == 1860
    print(f"  ✓ HMM FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_hmm_fix():
    """HMM FIX: HDL = $100."""
    r = normalize_rate("HMM", "FIX", 2500, "40HQ", "HCM")
    assert r.hdl_fee == 100
    assert r.normalized_amount == 2400
    print(f"  ✓ HMM FIX: ${r.raw_amount} → ${r.normalized_amount}")


def test_emc_fak():
    """EMC FAK: HDL = $25."""
    r = normalize_rate("EMC", "FAK", 1600, "40HQ", "HCM")
    assert r.hdl_fee == 25
    assert r.normalized_amount == 1575
    print(f"  ✓ EMC FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_msc_fak():
    """MSC FAK: HDL = $25."""
    r = normalize_rate("MSC", "FAK", 1800, "40HQ", "HCM")
    assert r.hdl_fee == 25
    assert r.normalized_amount == 1775
    print(f"  ✓ MSC FAK: ${r.raw_amount} → ${r.normalized_amount}")


def test_unknown_carrier():
    """Unknown carrier: HDL = $0, no normalization."""
    r = normalize_rate("UNKNOWN", "FAK", 1500, "40HQ", "HCM")
    assert r.hdl_fee == 0
    assert r.normalized_amount == 1500
    print(f"  ✓ Unknown carrier: No normalization applied")


def test_normalized_rate_to_dict():
    """NormalizedRate.to_dict() returns correct structure."""
    r = normalize_rate("HPL", "FAK", 1800, "40HQ", "HCM")
    d = r.to_dict()
    assert isinstance(d, dict)
    assert d["raw_amount"] == 1800
    assert d["normalized_amount"] == 1780
    assert d["hdl_fee"] == 20
    print(f"  ✓ NormalizedRate.to_dict(): {len(d)} fields")


def test_all_carriers_have_rules():
    """Every carrier in HDL_RULES has valid entries."""
    expected = ["HPL", "ONE", "YML", "MSC", "MSK", "CMA", "COSCO", "ZIM", "WHL", "HMM", "EMC"]
    for carrier in expected:
        assert carrier in HDL_RULES, f"Missing HDL_RULES for {carrier}"
        rules = HDL_RULES[carrier]
        assert "CAR_COM" in rules or "CAR_COM_HCM" in rules, \
            f"{carrier} missing CAR_COM"
    print(f"  ✓ All {len(expected)} carriers have HDL rules")


if __name__ == "__main__":
    print("=" * 60)
    print("  HDL NORMALIZATION TESTS — Task 1.2.1")
    print("=" * 60)

    tests = [
        test_hpl_fak, test_hpl_fix_40, test_hpl_fix_20, test_hpl_scfi,
        test_one_fak, test_yml_fix,
        test_cosco_dry, test_cosco_reefer,
        test_whl_hcm, test_whl_hph,
        test_cma_fak, test_cma_fix_tp_pd,
        test_zim_fak,
        test_hmm_fak, test_hmm_fix,
        test_emc_fak, test_msc_fak,
        test_unknown_carrier,
        test_normalized_rate_to_dict,
        test_all_carriers_have_rules,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
    if failed > 0:
        sys.exit(1)
    print("\n✅ ALL TESTS PASSED")
