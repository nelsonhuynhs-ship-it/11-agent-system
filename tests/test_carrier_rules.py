# -*- coding: utf-8 -*-
"""
Unit tests for carrier_rules loader and text_normalize module.
Run: python -m pytest tests/test_carrier_rules.py -v
"""
import pytest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Pricing_Engine.carrier_rules import (
    load_carrier, load_all, get_puc_carriers,
    get_commodity_shortcuts, get_note_shortcuts,
    get_booking_template, clear_cache,
    KNOWN_CARRIERS
)
from Pricing_Engine.normalization.text_normalize import (
    normalize_notes, normalize_text_data,
    normalize_commodity_display, normalize_container_types
)


# ── Loader tests ────────────────────────────────────────────────────────────

class TestCarrierLoader:

    def setup_method(self):
        clear_cache()

    def test_load_carrier_one_required_keys(self):
        rule = load_carrier("ONE")
        assert rule["carrier_code"] == "ONE"
        assert "version" in rule
        assert "source_files_merged_from" in rule

    def test_load_carrier_case_insensitive(self):
        rule1 = load_carrier("one")
        rule2 = load_carrier("ONE")
        assert rule1["carrier_code"] == rule2["carrier_code"]

    def test_load_all_returns_all_known(self):
        all_rules = load_all()
        for code in KNOWN_CARRIERS:
            assert code in all_rules, f"Missing carrier: {code}"

    def test_puc_carriers_set(self):
        puc = get_puc_carriers()
        assert "CMA" in puc
        assert "ONE" in puc
        assert "YML" in puc
        assert "HPL" in puc
        assert "ZIM" not in puc
        assert "MSC" not in puc

    def test_one_puc_handling(self):
        rule = load_carrier("ONE")
        puc = rule.get("puc_handling", {})
        assert puc.get("strip_from_soc_tof") is True
        assert "Total Ocean Freight" in puc.get("target_charges", [])

    def test_zim_no_puc(self):
        rule = load_carrier("ZIM")
        puc = rule.get("puc_handling", {})
        assert puc.get("strip_from_soc_tof") is False

    def test_cma_booking_payment_term(self):
        tmpl = get_booking_template("CMA")
        extra = tmpl.get("extra_fields", {})
        assert "payment_term" in extra
        assert extra["payment_term"] == "PREPAID"

    def test_common_rules_in_merged(self):
        # _common.json booking_template should appear in merged rule
        rule = load_carrier("ONE")
        booking = rule.get("booking_template", {})
        assert "greeting" in booking
        assert "pol_config" in booking

    def test_missing_carrier_no_crash(self):
        rule = load_carrier("XYZFAKE")
        assert rule["carrier_code"] == "XYZFAKE"
        assert rule.get("_missing") is True

    def test_load_carrier_cache(self):
        r1 = load_carrier("MSC")
        r2 = load_carrier("MSC")
        assert r1 is r2  # same object from cache


# ── normalize_notes tests ───────────────────────────────────────────────────

class TestNormalizeNotes:

    def _make_df(self, notes, carriers):
        return pd.DataFrame({"Note": notes, "Carrier": carriers})

    def test_soc_transit(self):
        df = self._make_df(["SOC via YANTIAN"], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SOC TRANSIT"

    def test_transit_no_soc(self):
        df = self._make_df(["via KAOHSIUNG"], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "TRANSIT"

    def test_soc_direct(self):
        df = self._make_df(["SOC DIRECT from HPH"], ["HPL"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SOC DIRECT"

    def test_direct_haiphong_no_soc(self):
        df = self._make_df(["HAI PHONG direct"], ["CMA"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "DIRECT"

    def test_direct_haiphong_with_soc(self):
        df = self._make_df(["SOC HAI PHONG direct"], ["HPL"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SOC DIRECT"

    def test_cai_mep_soc(self):
        df = self._make_df(["SOC via CAI MEP"], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SOC Cai Mep (EC3)"

    def test_cai_mep_no_soc(self):
        df = self._make_df(["CAI MEP"], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "Cai Mep (EC3)"

    def test_z7s_plain(self):
        df = self._make_df(["Z7S service code"], ["ZIM"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "Z7S"

    def test_z7s_ows_extra(self):
        df = self._make_df(["Z7S SUBJECT TO OWS UP TO 18 tons"], ["ZIM"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "Z7S OWS EXTRA [!OWS<22T:18.0t]"

    def test_z7s_ows_incl(self):
        df = self._make_df(["Z7S OWS INCLUSIVE"], ["ZIM"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "Z7S OWS INCL"

    def test_zxb_plain(self):
        df = self._make_df(["ZXB service"], ["ZIM"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "ZXB"

    def test_ows_catchall_extra(self):
        df = self._make_df(["SUBJECT TO OWS 20GP"], ["ZIM"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "ZIM OWS EXTRA"

    def test_emc_cmep_pctf_stf(self):
        df = self._make_df(["TRF PCTF + STF via CMEP"], ["EMC"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "via CMEP PCTF/STF"

    def test_emc_pcs_no_cmep(self):
        df = self._make_df(["PCS SUEZ channel"], ["EMC"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "PCS/SUEZ"

    def test_cosco_nile(self):
        df = self._make_df(["M/V CMA CGM NILE service"], ["COSCO"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "NILE/P-NOIRE"

    def test_msc_america_group(self):
        df = self._make_df(["America Empire Amberjack service"], ["MSC"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "AMR/EMP/AMB/EMR/ELE/SAN/LION [ref:SvcGroup1]"

    def test_cma_service_split(self):
        df = self._make_df(["service : SAX CS DEVELOPMENT"], ["CMA"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SAX CS"

    def test_empty_note(self):
        df = self._make_df([""], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == ""

    def test_nan_note(self):
        df = pd.DataFrame({"Note": [None], "Carrier": ["ONE"]})
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == ""

    def test_unrecognized_kept(self):
        df = self._make_df(["SOME RANDOM NOTE"], ["ONE"])
        r = normalize_notes(df)
        assert r["Note"].iloc[0] == "SOME RANDOM NOTE"

    def test_ows_tonnage_no_warn_above_22(self):
        df = self._make_df(["Z7S SUBJECT TO OWS UP TO 25 tons"], ["ZIM"])
        r = normalize_notes(df)
        # 25 >= 22, no warning
        assert "[!OWS" not in r["Note"].iloc[0]


# ── normalize_text_data tests ───────────────────────────────────────────────

class TestNormalizeTextData:

    def _make_df(self, commodities, carriers):
        return pd.DataFrame({"Commodity": commodities, "Carrier": carriers})

    def test_fak_incl_garment(self):
        df = self._make_df(["FAK (INCLUDING GARMENT)"], ["MSC"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "FAK INCL GARMENT"

    def test_fak_excl_garment(self):
        df = self._make_df(["FAK (EXCLUDING GARMENT)"], ["ONE"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "FAK EXCL GARMENT"

    def test_one_reefer(self):
        df = self._make_df(["REEFER FAK (NOT VALID FOR SEASONAL)"], ["ONE"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "REEFER FAK"

    def test_one_gdsm(self):
        df = self._make_df(["GDSM Straight General Department"], ["ONE"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "SHORT TERM GDSM"

    def test_yml_group_a_fak(self):
        df = self._make_df(["GROUP A : FAK (NON-HAZ, EXCLUDING REEFER/SHIPS)"], ["YML"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "GROUP A : FAK"

    def test_yml_vehicles(self):
        df = self._make_df(["SHIPS/ BOATS/ VEHICLES/ CARS"], ["YML"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "VEHICLES/CARS"

    def test_cma_panama(self):
        df = self._make_df(["subject to Panama surcharge"], ["CMA"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "PANAMA SURCHG"

    def test_zim_ows_20gp(self):
        df = self._make_df(["SUBJECT TO OWS for 20GP"], ["ZIM"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "OWS 20GP"

    def test_whl_frozen(self):
        df = self._make_df(["FROZEN SEAFOOD"], ["WHL"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "FROZEN FOOD"

    def test_emc_rate_1(self):
        df = self._make_df(["RATE 1 - GENERAL CARGO, STRAIGHT OR MIXED"], ["EMC"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "RATE 1"

    def test_cosco_garment_no_fak(self):
        df = self._make_df(["Garments/Textile/Consol"], ["COSCO"])
        r = normalize_text_data(df)
        assert r["Commodity"].iloc[0] == "GARMENT"

    def test_cosco_garment_with_fak_unchanged(self):
        df = self._make_df(["FAK INCLUDING GARMENT"], ["COSCO"])
        r = normalize_text_data(df)
        # Universal rule fires: FAK INCL GARMENT
        assert r["Commodity"].iloc[0] == "FAK INCL GARMENT"


# ── normalize_commodity_display tests ──────────────────────────────────────

class TestNormalizeCommodityDisplay:

    def test_reefer_shortened(self):
        df = pd.DataFrame({"Commodity": ["REEFER FAK (NOT VALID FOR SEASONAL COMMODITIES)\n"]})
        r = normalize_commodity_display(df)
        assert r["Commodity"].iloc[0] == "REEFER"

    def test_paren_stripped(self):
        df = pd.DataFrame({"Commodity": ["FAK (Excluding Garment)"]})
        r = normalize_commodity_display(df)
        assert r["Commodity"].iloc[0] == "FAK"

    def test_plain_kept(self):
        df = pd.DataFrame({"Commodity": ["GROUP A : FAK"]})
        r = normalize_commodity_display(df)
        assert r["Commodity"].iloc[0] == "GROUP A : FAK"


# ── normalize_container_types tests ────────────────────────────────────────

class TestNormalizeContainerTypes:

    def test_45hq_fixed(self):
        df = pd.DataFrame({"Container_Type": ["45'HQ", "40HQ", "20GP", "45HQ"]})
        r = normalize_container_types(df)
        assert list(r["Container_Type"]) == ["45HQ", "40HQ", "20GP", "45HQ"]

    def test_no_container_col(self):
        df = pd.DataFrame({"OtherCol": [1, 2]})
        r = normalize_container_types(df)
        assert "Container_Type" not in r.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
