"""Unit tests for ERP/jobs/transit_time.py — Feature 9 Transit Time Calculator.

Tests run pure-Python (no openpyxl file I/O, no OneDrive).
"""
from __future__ import annotations

import sys
import warnings
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ERP.jobs.transit_time import classify_route, estimate_eta, transit_window  # noqa: E402


# ===========================================================================
# classify_route — 8 cases covering every route class + edge cases
# ===========================================================================

class TestClassifyRoute:
    def test_wc_lgb_shortcode(self):
        assert classify_route("HPH", "USLGB") == "WC"

    def test_wc_lax_slash_lgb(self):
        assert classify_route("HPH", "LAX/LGB") == "WC"

    def test_wc_oakland(self):
        assert classify_route("HCM", "USOAK") == "WC"

    def test_ec_savannah_full_name(self):
        assert classify_route("HPH", "SAVANNAH, GA") == "EC"

    def test_ec_norfolk(self):
        assert classify_route("HPH", "NORFOLK") == "EC"

    def test_gulf_houston(self):
        assert classify_route("HCM", "HOUSTON, TX") == "GULF"

    def test_ca_wc_vancouver(self):
        assert classify_route("HPH", "VANCOUVER") == "CA_WC"

    def test_ca_ec_montreal(self):
        assert classify_route("HPH", "MONTREAL") == "CA_EC"

    def test_inland_wc_chicago(self):
        """Door address is Chicago (inland) while POD is USLAX — should be WC+INLAND."""
        result = classify_route("HCM", "USLAX", place="CHICAGO, IL")
        assert result == "WC+INLAND"

    def test_inland_ec_door_has_no_port_keyword(self):
        result = classify_route("HPH", "NORFOLK", place="RICHMOND, VA")
        assert result == "EC+INLAND"

    def test_no_inland_when_place_is_empty(self):
        assert classify_route("HPH", "USLGB", place="") == "WC"

    def test_unknown_pod_defaults_to_ec_with_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = classify_route("HPH", "UNKNOWN_PORT")
        assert result == "EC"
        assert len(w) == 1
        assert "defaulting to EC" in str(w[0].message)

    def test_case_insensitive_pod(self):
        assert classify_route("hph", "uslgb") == "WC"

    def test_case_insensitive_place(self):
        result = classify_route("hph", "uslax", place="chicago, il")
        assert result == "WC+INLAND"


# ===========================================================================
# transit_window — 6 base route classes + inland combos
# ===========================================================================

class TestTransitWindow:
    def test_wc(self):
        assert transit_window("WC") == (18, 20)

    def test_ec(self):
        assert transit_window("EC") == (40, 50)

    def test_gulf(self):
        assert transit_window("GULF") == (40, 50)

    def test_ca_wc(self):
        assert transit_window("CA_WC") == (18, 22)

    def test_ca_ec(self):
        assert transit_window("CA_EC") == (35, 45)

    def test_wc_inland(self):
        min_d, max_d = transit_window("WC+INLAND")
        assert min_d == 23
        assert max_d == 25

    def test_ec_inland(self):
        min_d, max_d = transit_window("EC+INLAND")
        assert min_d == 45
        assert max_d == 55

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown route class"):
            transit_window("MARS")


# ===========================================================================
# estimate_eta — range checks
# ===========================================================================

class TestEstimateEta:
    def test_wc_range(self):
        etd = datetime(2026, 4, 10)
        earliest, latest = estimate_eta(etd, "WC")
        assert earliest == datetime(2026, 4, 28)   # +18 days
        assert latest == datetime(2026, 4, 30)     # +20 days

    def test_ec_range(self):
        etd = datetime(2026, 4, 10)
        earliest, latest = estimate_eta(etd, "EC")
        assert earliest == datetime(2026, 5, 20)   # +40 days
        assert latest == datetime(2026, 5, 30)     # +50 days

    def test_wc_inland_range(self):
        etd = datetime(2026, 4, 10)
        earliest, latest = estimate_eta(etd, "WC+INLAND")
        assert earliest == datetime(2026, 5, 3)    # +23 days
        assert latest == datetime(2026, 5, 5)      # +25 days

    def test_ca_wc_range(self):
        etd = datetime(2026, 4, 10)
        earliest, latest = estimate_eta(etd, "CA_WC")
        assert earliest == datetime(2026, 4, 28)   # +18 days
        assert latest == datetime(2026, 5, 2)      # +22 days

    def test_median_is_floor_of_midpoint(self):
        """Verify median logic (min+max)//2 used in update_active_jobs."""
        min_d, max_d = transit_window("CA_EC")  # 35-45
        median = (min_d + max_d) // 2
        assert median == 40

    def test_estimate_returns_tuple_of_datetimes(self):
        result = estimate_eta(datetime(2026, 1, 1), "GULF")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(d, datetime) for d in result)
