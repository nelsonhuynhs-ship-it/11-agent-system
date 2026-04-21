"""tests/test_booking_parser.py — Unit tests for Pricing_Engine/booking_parser.py

All tests are pure Python — no Excel I/O, no OneDrive access.
15+ cases covering Direct flow, Keep Space flow, body parsing,
edge cases, and detect_booking_mail negative cases.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Pricing_Engine.booking_parser import (  # noqa: E402
    detect_booking_mail,
    parse_booking_body,
    parse_booking_subject,
)

# Fixed "today" for all date-resolution tests (avoids flaky year rollover)
_TODAY = date(2026, 4, 21)


# ===========================================================================
# Direct flow — standard example from Nelson
# ===========================================================================

class TestDirectSorachi:
    S = (
        "SORACHI BKG SGNG83555500 // HCM-TACOMA, WA // 1X40HC "
        "// ETD 1May - ETA 24May // NELSON // ONE // YM TOPMOST 024E // PO# LP-95"
    )

    def test_customer(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["customer"] == "SORACHI"

    def test_bkg_no(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["bkg_no"] == "SGNG83555500"

    def test_pol(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pol"] == "HCM"

    def test_pod(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pod"] == "TACOMA"

    def test_final_dest(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["final_dest"] == "TACOMA, WA"

    def test_container(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "40HC"

    def test_qty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["qty"] == 1

    def test_etd(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["etd"] == "2026-05-01"

    def test_eta(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["eta"] == "2026-05-24"

    def test_carrier(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["carrier"] == "ONE"

    def test_vessel(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["vessel"] == "YM TOPMOST"

    def test_voyage(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["voyage"] == "024E"

    def test_po_number(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["po_number"] == "LP-95"

    def test_not_keep_space(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["is_keep_space"] is False

    def test_sales(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["sales"] == "NELSON"

    def test_raw_subject(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["raw_subject"] == self.S


# ===========================================================================
# Keep Space — with customer name embedded
# ===========================================================================

class TestKeepSpaceSorachi:
    S = "[KEEP SPACE +SORACHI] | HCM-TACOMA, WA | 1X40HC | ONE | NELSON"

    def test_is_keep_space(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["is_keep_space"] is True

    def test_customer(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["customer"] == "SORACHI"

    def test_carrier(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["carrier"] == "ONE"

    def test_sales(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["sales"] == "NELSON"

    def test_pol(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pol"] == "HCM"

    def test_pod(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pod"] == "TACOMA"

    def test_container(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "40HC"


# ===========================================================================
# Keep Space — no customer name
# ===========================================================================

class TestKeepSpaceNoCustomer:
    S = "[KEEP SPACE] | HPH-LAX | 2X40HC | HPL | NELSON"

    def test_is_keep_space(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["is_keep_space"] is True

    def test_customer_empty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["customer"] == ""

    def test_qty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["qty"] == 2

    def test_pol(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pol"] == "HPH"

    def test_pod(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pod"] == "LAX"


# ===========================================================================
# Body parsing — SI cutoff + CY close
# ===========================================================================

class TestBodySiCy:
    BODY = (
        "Pls kindly send your SI and VGM\n"
        "• S/I cut off time: 14:00 APR 21\n"
        "• Deadline amendment: 11:00 APR 22\n"
        "Thanks"
    )

    def test_si_cutoff(self):
        r = parse_booking_body(self.BODY, today=_TODAY)
        assert r["si_cutoff"].startswith("2026-04-21T14:00")

    def test_cy_close(self):
        r = parse_booking_body(self.BODY, today=_TODAY)
        assert r["cy_close"].startswith("2026-04-22T11:00")


class TestBodyMissingFields:
    def test_empty_body_returns_empty_strings(self):
        r = parse_booking_body("", today=_TODAY)
        assert r["si_cutoff"] == ""
        assert r["cy_close"] == ""

    def test_body_with_only_si_no_cy(self):
        body = "SI cut off time: 09:00 MAY 15\nNo CY info."
        r = parse_booking_body(body, today=_TODAY)
        assert r["si_cutoff"].startswith("2026-05-15T09:00")
        assert r["cy_close"] == ""


# ===========================================================================
# Missing PO number
# ===========================================================================

class TestMissingPo:
    S = "NAFOODS BKG HJSC123456 // HPH-USLGB // 1X40HQ // ETD 10Jun - ETA 05Jul // NELSON // ONE"

    def test_po_empty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["po_number"] == ""

    def test_bkg_extracted(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["bkg_no"] == "HJSC123456"

    def test_container_hq(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "40HQ"


# ===========================================================================
# Missing vessel/voyage
# ===========================================================================

class TestMissingVessel:
    S = "SIRI BKG MSCU8877001 // HCM-LAX // 1X20DC // ETD 5Jun - ETA 28Jun // NELSON // MSC"

    def test_vessel_empty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["vessel"] == ""

    def test_voyage_empty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["voyage"] == ""

    def test_container_20dc(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "20DC"


# ===========================================================================
# 2X container
# ===========================================================================

class TestTwoContainers:
    S = "VINAFOOD BKG OOLU7788001 // HCM-TACOMA, WA // 2X40HC // ETD 3Jun - ETA 26Jun // NELSON // OOCL"

    def test_qty(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["qty"] == 2

    def test_container(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "40HC"


# ===========================================================================
# Reefer 40RF
# ===========================================================================

class TestReefer:
    S = "SEAFOOD BKG ONEY9988001 // HPH-USLAX // 1X40RF // ETD 20May - ETA 12Jun // NELSON // ONE"

    def test_container_rf(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["container"] == "40RF"

    def test_pol(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pol"] == "HPH"


# ===========================================================================
# Canada POD
# ===========================================================================

class TestCanadaPod:
    S = (
        "CANWOOD BKG CMAU5544001 // HPH-VANCOUVER, BC // 1X40HC "
        "// ETD 10May - ETA 31May // NELSON // CMA"
    )

    def test_pod(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["pod"] == "VANCOUVER"

    def test_final_dest(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["final_dest"] == "VANCOUVER, BC"

    def test_carrier_cma(self):
        r = parse_booking_subject(self.S, today=_TODAY)
        assert r["carrier"] == "CMA"


# ===========================================================================
# detect_booking_mail
# ===========================================================================

class TestDetectBookingMail:
    def test_direct_detected(self):
        s = "SORACHI BKG SGNG83555500 // HCM-TACOMA, WA // 1X40HC // ETD 1May"
        assert detect_booking_mail(s) is True

    def test_keep_space_not_detected(self):
        # Keep Space subject has no BKG number — should NOT trigger
        s = "[KEEP SPACE +SORACHI] | HCM-TACOMA, WA | 1X40HC | ONE | NELSON"
        assert detect_booking_mail(s) is False

    def test_random_subject_not_detected(self):
        assert detect_booking_mail("Re: Rate inquiry for October") is False

    def test_empty_not_detected(self):
        assert detect_booking_mail("") is False

    def test_partial_only_bkg_not_detected(self):
        # Has BKG number but no route pattern → False
        assert detect_booking_mail("BKG SGNG83555500 only") is False

    def test_partial_only_route_not_detected(self):
        # Has route but no BKG number → False
        assert detect_booking_mail("HCM-TACOMA, WA // 1X40HC // ETD 1May") is False


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_empty_subject(self):
        r = parse_booking_subject("", today=_TODAY)
        assert r["bkg_no"] == ""
        assert r["is_keep_space"] is False

    def test_missing_etd_eta(self):
        s = "TRANANH BKG HJSC987654 // HPH-USLGB // 1X40HQ // NELSON // ONE"
        r = parse_booking_subject(s, today=_TODAY)
        assert r["etd"] == ""
        assert r["eta"] == ""

    def test_pipe_delimiter_direct(self):
        # Direct booking using | delimiter (unusual but possible)
        s = "PANDA BKG COSU7766001 | HCM-LAX | 1X20DC | NELSON | COSCO"
        r = parse_booking_subject(s, today=_TODAY)
        assert r["bkg_no"] == "COSU7766001"
        assert r["carrier"] == "COSCO"

    def test_qty_9(self):
        s = "BIGCO BKG MSCU0012345 // HPH-USLGB // 9X40HC // ETD 1Jun // NELSON // MSC"
        r = parse_booking_subject(s, today=_TODAY)
        assert r["qty"] == 9
