# -*- coding: utf-8 -*-
"""
Unit tests for Pricing_Engine/one_group_resolver.py

Run:
    python -m pytest tests/test_one_group_resolver.py -v
    python Pricing_Engine/one_group_resolver.py --self-test
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Pricing_Engine.one_group_resolver import resolve_one_group_code, _pod_region


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def resolve(ct, commodity, note, pod):
    """Shorthand wrapper."""
    return resolve_one_group_code(ct, commodity, note, pod)


# ---------------------------------------------------------------------------
# Priority-1: FIX + GARMENT
# ---------------------------------------------------------------------------

class TestPriority1:

    def test_fix_garment_usa(self):
        code, label = resolve("FIX", "GARMENT", "", "USLAX")
        assert code == "990117", f"P1: expected 990117, got {code}"
        assert "GARMENT" in label.upper()

    def test_fix_garment_case_insensitive(self):
        code, _ = resolve("fix", "garment", "", "USLAX")
        assert code == "990117"

    def test_fix_garment_canada(self):
        # FIX GARMENT even in Canada port → P1 fires before region logic
        code, _ = resolve("FIX", "GARMENT", "", "CATOR")
        assert code == "990117"


# ---------------------------------------------------------------------------
# Priority-2: FIX + any
# ---------------------------------------------------------------------------

class TestPriority2:

    def test_fix_general_cargo(self):
        code, label = resolve("FIX", "GENERAL CARGO", "", "USLAX")
        assert code == "990104"
        assert "GDSGM" in label

    def test_fix_furniture(self):
        code, _ = resolve("FIX", "FURNITURE", "", "USLAX")
        assert code == "990104"

    def test_fix_empty_commodity(self):
        code, _ = resolve("FIX", "", "", "USLAX")
        assert code == "990104"


# ---------------------------------------------------------------------------
# Priority-3: FAK REEFER / FROZEN (and aliases)
# ---------------------------------------------------------------------------

class TestPriority3:

    def test_fak_reefer_frozen_explicit(self):
        """Test case 3 from spec."""
        code, label = resolve("FAK", "REEFER FROZEN", "", "USLAX")
        assert code == "1"
        assert "Frozen" in label or "FROZEN" in label.upper()

    def test_fak_seafood_alias(self):
        """Test case 4 — SEAFOOD → frozen alias."""
        code, _ = resolve("FAK", "SEAFOOD", "", "USLAX")
        assert code == "1"

    def test_fak_frozen_fish_alias(self):
        """Test case 5 — FROZEN FISH → frozen alias."""
        code, _ = resolve("FAK", "FROZEN FISH", "", "USLAX")
        assert code == "1"

    def test_fak_reefer_ambiguous_defaults_frozen(self):
        """Test case 6 — bare REEFER without FROZEN/CHILLED → Nelson default frozen."""
        code, _ = resolve("FAK", "REEFER", "", "USLAX")
        assert code == "1"

    def test_fak_fish_alias(self):
        """Bare FISH keyword → frozen alias → code 1."""
        code, _ = resolve("FAK", "FISH", "", "USLAX")
        assert code == "1"

    def test_fak_frozen_bare(self):
        """Bare FROZEN keyword → frozen alias → code 1."""
        code, _ = resolve("FAK", "FROZEN", "", "USLAX")
        assert code == "1"


# ---------------------------------------------------------------------------
# Priority-4: FAK REEFER CHILLED / FRESH
# ---------------------------------------------------------------------------

class TestPriority4:

    def test_fak_reefer_chilled_explicit(self):
        """Test case 7 — explicit CHILLED."""
        code, label = resolve("FAK", "REEFER CHILLED", "", "USLAX")
        assert code == "2"
        assert "Chilled" in label or "CHILLED" in label.upper()

    def test_fak_fresh_produce(self):
        """Test case 8 — FRESH keyword."""
        code, _ = resolve("FAK", "FRESH PRODUCE", "", "USLAX")
        assert code == "2"

    def test_fak_reefer_fresh(self):
        code, _ = resolve("FAK", "REEFER FRESH", "", "USLAX")
        assert code == "2"


# ---------------------------------------------------------------------------
# Priority-5: FAK + TANK/HAZ
# ---------------------------------------------------------------------------

class TestPriority5:

    def test_fak_tank_chemical_haz(self):
        """Test case 9."""
        code, label = resolve("FAK", "TANK CHEMICAL HAZ", "", "USLAX")
        assert code == "990302"
        assert "TANK" in label.upper() or "Chemical" in label

    def test_fak_hazard(self):
        code, _ = resolve("FAK", "HAZARD CARGO", "", "USLAX")
        assert code == "990302"

    def test_fak_chemical(self):
        code, _ = resolve("FAK", "CHEMICAL CARGO", "", "USLAX")
        assert code == "990302"


# ---------------------------------------------------------------------------
# Priority-6: FAK + GDSM SOC + SOC note
# ---------------------------------------------------------------------------

class TestPriority6:

    def test_fak_gdsm_soc_nac_soc_note(self):
        """Test case 10."""
        code, label = resolve("FAK", "GDSM SOC (NAC)", "SOC DIRECT", "USLAX")
        assert code == "990104"
        assert "NAC" in label or "GDSM" in label

    def test_fak_nac_group_soc_note(self):
        code, _ = resolve("FAK", "NAC GROUP CARGO", "SOC TRANSIT", "USLAX")
        assert code == "990104"

    def test_fak_gdsm_soc_no_note_skips_p6(self):
        # No SOC note → P6 skipped; commodity doesn't match P7 → falls through to P12
        code, _ = resolve("FAK", "GDSM SOC (NAC)", "", "USLAX")
        assert code == "990146"  # P12 USA catchall


# ---------------------------------------------------------------------------
# Priority-7: FAK + SHORT TERM GDSM / GDSM STRAIGHT
# ---------------------------------------------------------------------------

class TestPriority7:

    def test_fak_short_term_gdsm(self):
        """Test case 11."""
        code, label = resolve("FAK", "SHORT TERM GDSM", "", "USLAX")
        assert code == "990154"
        assert "GDSM" in label

    def test_fak_gdsm_straight(self):
        code, _ = resolve("FAK", "GDSM STRAIGHT CARGO", "", "USLAX")
        assert code == "990154"


# ---------------------------------------------------------------------------
# Priority-8: FAK + GARMENT + SOC note (TPE10)
# ---------------------------------------------------------------------------

class TestPriority8:

    def test_fak_garment_soc_direct(self):
        """Test case 12."""
        code, label = resolve("FAK", "GARMENT", "SOC DIRECT", "USLAX")
        assert code == "990117"
        assert "TPE10" in label or "Garment" in label

    def test_fak_garment_soc_transit(self):
        code, _ = resolve("FAK", "GARMENT", "SOC TRANSIT", "USLAX")
        assert code == "990117"


# ---------------------------------------------------------------------------
# Priority-9: FAK + S1/SOC/TPE9 + SOC note
# ---------------------------------------------------------------------------

class TestPriority9:

    def test_fak_s1_tpe9_soc_transit(self):
        """Test case 13."""
        code, label = resolve("FAK", "S1-TPE9", "SOC TRANSIT", "USLAX")
        assert code == "990132"
        assert "TPE9" in label or "S1" in label

    def test_fak_tpe9_soc_direct(self):
        code, _ = resolve("FAK", "TPE9 CARGO", "SOC DIRECT", "USLAX")
        assert code == "990132"


# ---------------------------------------------------------------------------
# Priority-10: FAK + CANADA + GARMENT
# ---------------------------------------------------------------------------

class TestPriority10:

    def test_fak_garment_canada_cator(self):
        """Test case 14 — CATOR = Toronto, Canada."""
        code, label = resolve("FAK", "GARMENT", "", "CATOR")
        assert code == "990117"
        assert "Canada" in label or "TPE3" in label

    def test_fak_garment_canada_cayvr(self):
        """CAYVR = Vancouver."""
        code, _ = resolve("FAK", "GARMENT", "", "CAYVR")
        assert code == "990117"


# ---------------------------------------------------------------------------
# Priority-11: FAK + CANADA + any (default single)
# ---------------------------------------------------------------------------

class TestPriority11:

    def test_fak_general_cargo_canada(self):
        """Test case 15 — default single 990131."""
        code, label = resolve("FAK", "GENERAL CARGO", "", "CATOR")
        assert code == "990131"
        assert "SINGLE" in label.upper() or "990131" in label

    def test_fak_furniture_canada(self):
        code, _ = resolve("FAK", "FURNITURE", "", "CAHFX")
        assert code == "990131"


# ---------------------------------------------------------------------------
# Priority-12: FAK + USA + any (catch-all)
# ---------------------------------------------------------------------------

class TestPriority12:

    def test_fak_general_cargo_usa(self):
        """Test case 16 — USA catchall."""
        code, label = resolve("FAK", "GENERAL CARGO", "", "USLAX")
        assert code == "990146"
        assert "TPE1" in label or "FAK" in label

    def test_fak_garment_no_soc_usa(self):
        """GARMENT, no SOC note, USA → P12 (P8 requires SOC note, P10 requires Canada)."""
        code, _ = resolve("FAK", "GARMENT", "", "USLAX")
        assert code == "990146"

    def test_fak_unknown_commodity_usa(self):
        code, _ = resolve("FAK", "MISC CARGO", "", "USNYC")
        assert code == "990146"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_cai_mep_not_canada(self):
        """Test case 17 — CAI MEP is Vietnam, not Canada.

        POD 'CAI MEP' starts with CA but has CAI prefix → region = USA.
        GARMENT with no SOC note and USA region → P12 catch-all 990146.
        """
        code, _ = resolve("FAK", "GARMENT", "", "CAI MEP")
        assert code == "990146", (
            "CAI MEP must be treated as Vietnam (not Canada). "
            "Expected P12 USA catchall 990146."
        )

    def test_cai_prefix_pods_are_usa(self):
        """Any port starting with CAI (Cai Mep area) must NOT be treated as Canada."""
        for pod in ["CAI MEP", "CAIMIT", "CAI"]:
            region = _pod_region(pod)
            assert region == "USA", f"POD {pod!r} should be USA region, got {region}"

    def test_canada_pods_detected(self):
        """Canonical Canadian ports must resolve to CANADA region."""
        for pod in ["CATOR", "CAYVR", "CAHFX", "CAMTR"]:
            region = _pod_region(pod)
            assert region == "CANADA", f"POD {pod!r} should be CANADA region, got {region}"

    def test_case_insensitive_contract_type(self):
        code, _ = resolve("fak", "SEAFOOD", "", "USLAX")
        assert code == "1"

    def test_case_insensitive_commodity(self):
        code, _ = resolve("FAK", "seafood", "", "USLAX")
        assert code == "1"

    def test_case_insensitive_pod(self):
        code, _ = resolve("FAK", "GENERAL CARGO", "", "cator")
        assert code == "990131"  # Canada default single

    def test_empty_note_no_soc_match(self):
        """Empty note should not trigger SOC-note-dependent rules (P6, P8, P9)."""
        code, _ = resolve("FAK", "GARMENT", "", "USLAX")
        assert code == "990146"  # P12, not P8

    def test_whitespace_stripped(self):
        code, _ = resolve("  FAK  ", "  GARMENT  ", "  SOC DIRECT  ", "  USLAX  ")
        assert code == "990117"  # P8


# ---------------------------------------------------------------------------
# Self-test CLI integration
# ---------------------------------------------------------------------------

class TestSelfTestCLI:

    def test_self_test_function_all_pass(self):
        """The built-in _run_self_test() must return 0 (all cases pass)."""
        from Pricing_Engine.one_group_resolver import _run_self_test
        result = _run_self_test()
        assert result == 0, "one_group_resolver --self-test reported failures"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
