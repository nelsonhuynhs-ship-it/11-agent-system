"""
test_rule_engine.py — 10 scenarios for rule_engine.resolve_config

Run: pytest tests/test_rule_engine.py -v
Expected: 10/10 PASS
"""

import pytest
from email_engine.core.rule_engine import resolve_config, ARB_MAPPING, SUBJECT_TEMPLATES


# ── Helpers ──────────────────────────────────────────────────────────────────

def _row(**kwargs) -> dict:
    """Build a minimal v6-schema row."""
    return {
        "EMAIL": kwargs.get("email", "test@example.com"),
        "ORIGIN_COUNTRY": kwargs.get("country", "VN"),
        "POL": kwargs.get("pol", ""),
        "DESTINATION": kwargs.get("destination", ""),
        "COMMODITY_CATEGORY": kwargs.get("commodity", "FLOORING"),
        "TIER": kwargs.get("tier", "B"),
        "COMPANY": kwargs.get("company", "Test Co"),
        "PIC": kwargs.get("pic", "Alice"),
    }


# ── Test cases ────────────────────────────────────────────────────────────────

def test_01_vn_defaults():
    """VN contact with no POL → POL=HCM, ARB=None."""
    cfg = resolve_config(_row(country="VN"), subject_seed=1)
    assert cfg["pol"] == "HCM", f"Expected HCM, got {cfg['pol']}"
    assert cfg["arb_origin"] is None, f"Expected None, got {cfg['arb_origin']}"
    assert cfg["country"] == "VN"


def test_02_my_empty_pol_gets_pkg():
    """Malaysia contact with empty POL → POL=PKG, ARB=port_klang."""
    cfg = resolve_config(_row(country="MY", pol=""), subject_seed=1)
    assert cfg["pol"] == "PKG", f"Expected PKG, got {cfg['pol']}"
    assert cfg["arb_origin"] == "port_klang", f"Expected port_klang, got {cfg['arb_origin']}"


def test_03_th_contact():
    """Thailand contact → POL=BKK, ARB=lat_krabang."""
    cfg = resolve_config(_row(country="TH"), subject_seed=1)
    assert cfg["pol"] == "BKK"
    assert cfg["arb_origin"] == "lat_krabang"


def test_04_cn_sha():
    """China SHA contact → ARB=shanghai."""
    cfg = resolve_config(_row(country="CN", pol="SHA"), subject_seed=1)
    assert cfg["pol"] == "SHA"
    assert cfg["arb_origin"] == "shanghai"


def test_05_cn_ngb_variant():
    """China NGB port → ARB key overrides to 'ningbo'."""
    cfg = resolve_config(_row(country="CN", pol="NGB"), subject_seed=1)
    assert cfg["pol"] == "NGB"
    assert cfg["arb_origin"] == "ningbo", f"Expected ningbo, got {cfg['arb_origin']}"


def test_06_kh_transit_hcm():
    """Cambodia → POL=HCM (transit), ARB=phnom_penh."""
    cfg = resolve_config(_row(country="KH"), subject_seed=1)
    assert cfg["pol"] == "HCM", f"Expected HCM (transit), got {cfg['pol']}"
    assert cfg["arb_origin"] == "phnom_penh", f"Expected phnom_penh, got {cfg['arb_origin']}"


def test_07_empty_country_fallback():
    """Empty ORIGIN_COUNTRY → falls back to VN defaults."""
    row = _row(country="VN")
    row["ORIGIN_COUNTRY"] = ""
    cfg = resolve_config(row, subject_seed=1)
    assert cfg["country"] == "VN"
    assert cfg["pol"] == "HCM"
    assert cfg["arb_origin"] is None


def test_08_unknown_country_fallback():
    """Unknown country code 'XX' → falls back to VN defaults."""
    cfg = resolve_config(_row(country="XX"), subject_seed=1)
    assert cfg["country"] == "XX"
    # ARB_MAPPING falls back to VN rule → arb_key = None
    assert cfg["arb_origin"] is None
    assert cfg["pol"] == "HCM"  # VN default pol


def test_09_v5_schema_adapter():
    """Legacy v5 schema (CNEE_EMAIL, CNEE_NAME, CNEE_PIC) → adapter resolves correctly."""
    v5_row = {
        "CNEE_EMAIL": "legacy@example.com",
        "CNEE_NAME":  "Legacy Corp",
        "CNEE_PIC":   "Bob",
        "ORIGIN_COUNTRY": "MY",
        "POL": "",
        "DESTINATION": "",
        "COMMODITY_CATEGORY": "FURNITURE",
        "TIER": "A",
    }
    cfg = resolve_config(v5_row, user_markup=30, subject_seed=1)
    assert cfg["email"] == "legacy@example.com", f"email adapter failed: {cfg['email']}"
    assert cfg["company"] == "Legacy Corp"
    assert cfg["pic"] == "Bob"
    assert cfg["pol"] == "PKG"
    assert cfg["arb_origin"] == "port_klang"
    assert cfg["markup"] == 30


def test_10_markup_respected_and_subjects_vary():
    """user_markup stored in output; running 10 times yields >=3 unique subjects."""
    row = _row(country="VN", pol="HCM")
    subjects = set()
    for seed in range(10):
        cfg = resolve_config(row, user_markup=45, subject_seed=seed)
        assert cfg["markup"] == 45, "markup not stored in config"
        subjects.add(cfg["subject"])

    assert len(subjects) >= 3, (
        f"Expected >=3 unique subjects from 10 runs, got {len(subjects)}: {subjects}"
    )


# ── Extra edge-case guards (not counted in 10 above) ─────────────────────────

def test_destination_fallback():
    """Missing DESTINATION → defaults to USLAX,USLGB."""
    row = _row(country="VN")
    row["DESTINATION"] = ""
    cfg = resolve_config(row, subject_seed=1)
    assert cfg["destination"] == "USLAX,USLGB"


def test_vn_port_no_arb():
    """VN contact with explicit HPH → ARB still None (domestic, no surcharge)."""
    cfg = resolve_config(_row(country="VN", pol="HPH"), subject_seed=1)
    assert cfg["pol"] == "HPH"
    assert cfg["arb_origin"] is None


def test_nan_country_treated_as_vn():
    """'NaN' string in ORIGIN_COUNTRY → treated as VN."""
    row = _row()
    row["ORIGIN_COUNTRY"] = "NaN"
    cfg = resolve_config(row, subject_seed=1)
    assert cfg["country"] == "VN"
    assert cfg["pol"] == "HCM"
