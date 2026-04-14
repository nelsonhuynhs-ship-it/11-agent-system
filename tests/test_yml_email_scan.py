# -*- coding: utf-8 -*-
"""
test_yml_email_scan.py — Unit tests for YML email parser (no COM required)
===========================================================================
Tests only the pure-Python parse_yml_event() function and related helpers.
The Outlook COM layer is NOT tested here.

Run:
    pytest tests/test_yml_email_scan.py -v
"""
from __future__ import annotations

import sys
import os

# Allow import from ERP/jobs without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Patch ribbon_guard import so tests work without openpyxl/OneDrive
import types
_rg = types.ModuleType("ribbon_guard")
_rg.save_preserving_ribbon = lambda wb, path, **kw: {"skipped": "test"}  # type: ignore
sys.modules["ribbon_guard"] = _rg

from ERP.jobs.yml_email_scan import parse_yml_event, _parse_date, _classify_event  # noqa: E402


# ── Test: gate-in event ────────────────────────────────────────────────────────

GATE_IN_EMAIL = """
Dear Customer,

We would like to inform you that your container has been gated in.

Container YMLU1234567 gated in at HCMC on 2026-04-10.

Booking Reference: YM-8834501
Please contact us if you have any questions.
"""


def test_parse_gate_in_event():
    events = parse_yml_event(GATE_IN_EMAIL)
    gate_events = [e for e in events if e["event_type"] == "GTIN"]
    assert gate_events, "Expected at least one GTIN event"
    ev = gate_events[0]
    assert ev["container"] == "YMLU1234567"
    assert ev["timestamp"] == "2026-04-10"
    assert "HCMC" in ev["location"] or ev["location"] != ""


# ── Test: vessel departure event ──────────────────────────────────────────────

VESSEL_DEPART_EMAIL = """
Tracking Update from Yang Ming Line

Container YMLU7654321 has been loaded on board.
Vessel YM WARRANTY departed Hai Phong on 2026-04-12.
ETA Los Angeles 2026-05-05.

Booking Ref: YM-8834501
"""


def test_parse_vessel_departure():
    events = parse_yml_event(VESSEL_DEPART_EMAIL)
    vd_events = [e for e in events if e["event_type"] == "VD"]
    assert vd_events, "Expected at least one VD (vessel departure) event"
    ev = vd_events[0]
    assert ev["timestamp"] == "2026-04-12"
    assert "YM WARRANTY" in ev["vessel"] or ev["vessel"] != ""


def test_parse_eta_info_extracted():
    events = parse_yml_event(VESSEL_DEPART_EMAIL)
    eta_events = [e for e in events if e["event_type"] == "ETA_INFO"]
    assert eta_events, "Expected ETA_INFO event from email"
    ev = eta_events[0]
    assert ev["timestamp"] == "2026-05-05"


# ── Test: vessel arrival event ────────────────────────────────────────────────

ARRIVAL_EMAIL = """
Yang Ming Tracking Notification

Your shipment has arrived at the destination port.
Container YMLU9999001 arrived at Los Angeles on 2026-05-06.

Please arrange for customs clearance.
Vessel: YM UNICORN
Booking: YM-9912345
"""


def test_parse_vessel_arrival():
    events = parse_yml_event(ARRIVAL_EMAIL)
    va_events = [e for e in events if e["event_type"] == "VA"]
    assert va_events, "Expected at least one VA (vessel arrival) event"
    ev = va_events[0]
    assert ev["container"] == "YMLU9999001"
    assert ev["timestamp"] == "2026-05-06"


# ── Test: multi-container email ───────────────────────────────────────────────

MULTI_CONTAINER_EMAIL = """
YML Tracking Update

Container YMLU1111111 gated in at HPH on 2026-04-08.
Container YMLU2222222 gated in at HPH on 2026-04-09.
Vessel YM WITNESS departed Hai Phong on 2026-04-15.
ETA Long Beach: 2026-05-12.
"""


def test_multi_container_multiple_events():
    events = parse_yml_event(MULTI_CONTAINER_EMAIL)
    assert len(events) >= 3, f"Expected 3+ events, got {len(events)}: {events}"
    gtin_events = [e for e in events if e["event_type"] == "GTIN"]
    assert len(gtin_events) >= 2, "Expected 2 gate-in events"
    containers_seen = {e["container"] for e in gtin_events}
    assert "YMLU1111111" in containers_seen
    assert "YMLU2222222" in containers_seen


# ── Test: empty / junk email returns nothing ──────────────────────────────────

def test_empty_body_returns_no_events():
    events = parse_yml_event("")
    assert events == []


def test_junk_body_returns_no_events():
    events = parse_yml_event("Hello, this is a newsletter. Please unsubscribe here.")
    assert events == []


# ── Test: date parsing helper ─────────────────────────────────────────────────

def test_parse_date_iso():
    assert _parse_date("Arrived on 2026-05-06 at LA") == "2026-05-06"


def test_parse_date_dmy():
    assert _parse_date("Departed 12/04/2026 from HPH") == "2026-04-12"


def test_parse_date_no_date():
    assert _parse_date("No dates here") is None


# ── Test: event classification helper ────────────────────────────────────────

def test_classify_gate_in():
    assert _classify_event("Container gated in at HCMC") == "GTIN"


def test_classify_vessel_departed():
    assert _classify_event("Vessel YM WARRANTY departed Hai Phong") == "VD"


def test_classify_vessel_arrived():
    assert _classify_event("Container arrived at destination port") == "VA"


def test_classify_unknown_returns_none():
    assert _classify_event("Please contact customer service.") is None
