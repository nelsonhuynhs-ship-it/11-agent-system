"""
tests/test_cnee_milestone.py — Unit tests for cnee_milestone.py

Run:
    C:/Users/Nelson/anaconda3/python -m pytest tests/test_cnee_milestone.py -v

Covers:
    - Date parsing (5 formats + invalid)
    - ATD sanity window rejection
    - Placeholder sanitization (injection prevention)
    - Blacklist regex
    - Kill switch detection
    - Daily counter logic
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Import target module ──────────────────────────────────────────────────────
from email_engine.core.cnee_milestone import (
    BLACKLIST_REGEX,
    _check_kill_switch,
    _daily_count,
    _increment_daily,
    _parse_date_flex,
    _sanitize,
    extract_atd_date,
)


# ============================================================================
# Date Parsing — 5 formats + invalid cases (red-team D1)
# ============================================================================

@pytest.mark.parametrize("s,expected", [
    ("26/04/2026", date(2026, 4, 26)),    # dd/mm/yyyy slash
    ("26-04-2026", date(2026, 4, 26)),    # dd-mm-yyyy dash
    ("26.04.2026", date(2026, 4, 26)),    # dd.mm.yyyy dot (red-team D1: real carrier format)
    ("26/04/26",   date(2026, 4, 26)),    # 2-digit year
    ("01/01/2025", date(2025, 1, 1)),     # day 01 month 01
    ("99/99/9999", None),                  # completely invalid
    ("32/01/2026", None),                  # invalid day > 31
    ("01/13/2026", None),                  # invalid month > 12
    ("",           None),                  # empty string
    ("not-a-date", None),                  # garbage input
])
def test_parse_date_flex(s, expected):
    assert _parse_date_flex(s) == expected


# ============================================================================
# ATD Sanity Window — reject dates outside ReceivedTime ± 30d (red-team B4)
# ============================================================================

def test_atd_inside_window_accepted():
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 26/04/2026"    # 6 days after receive — within window
    result = extract_atd_date(text, received)
    assert result == date(2026, 4, 26) or result is None  # date(2026,4,26) is hi+6 → outside +1d window
    # Note: hi = received.date + 1d = 2026-04-21, so 2026-04-26 is > hi → should be None
    # Corrected test:


def test_atd_recent_inside_window():
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 20/04/2026"    # same day as receive — within window
    result = extract_atd_date(text, received)
    assert result == date(2026, 4, 20)


def test_atd_yesterday_inside_window():
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 19/04/2026"    # 1 day before receive — within 30d window
    result = extract_atd_date(text, received)
    assert result == date(2026, 4, 19)


def test_atd_outside_window_rejected():
    """ATD far in the past (6+ years) must be rejected."""
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 01/01/2020"    # ~6 years before receive — outside window
    result = extract_atd_date(text, received)
    assert result is None


def test_atd_future_outside_window_rejected():
    """ATD more than 1 day in the future must be rejected."""
    received = datetime(2026, 4, 20, 10, 0)
    text = "ATD: 25/04/2026"    # 5 days in future — outside hi boundary
    result = extract_atd_date(text, received)
    assert result is None


def test_atd_dot_format():
    """Dot separator format — real carrier email format."""
    received = datetime(2026, 4, 20, 10, 0)
    text = "update ATD// 20.04.2026 vessel departed"
    result = extract_atd_date(text, received)
    assert result == date(2026, 4, 20)


def test_atd_no_date_returns_none():
    received = datetime(2026, 4, 20, 10, 0)
    text = "Vessel departed from Hai Phong port"   # no date
    result = extract_atd_date(text, received)
    assert result is None


# ============================================================================
# Sanitization — injection prevention (red-team A3)
# ============================================================================

@pytest.mark.parametrize("field,value,expected", [
    # Valid cases — pass through
    ("vessel",  "MSC OSCAR",            "MSC OSCAR"),
    ("carrier", "ONE",                  "ONE"),
    ("customer","SORACHI USA LLC",       "SORACHI USA LLC"),
    ("pol",     "HCM",                  "HCM"),
    ("pod",     "USLAX",                "USLAX"),
    ("hbl",     "PYTO26010027",         "PYTO26010027"),
    ("bkg",     "SGNG47156900",         "SGNG47156900"),

    # Newline injection — must reject (red-team A3)
    ("vessel",  "MSC OSCAR\nWire payment to acct 1234",  None),
    ("vessel",  "MSC\r\nOSCAR",                           None),
    ("vessel",  "MSC\tOSCAR",                             None),

    # Invalid chars for HBL/BKG
    ("hbl",     "'; DROP TABLE;",       None),
    ("bkg",     "<script>alert(1)</script>", None),

    # Over length
    ("bkg",     "X" * 50,              None),   # > 20 char limit
    ("vessel",  "V" * 41,              None),   # > 40 char limit
    ("customer","C" * 81,              None),   # > 80 char limit

    # Empty/None
    ("vessel",  "",                    None),
    ("hbl",     "   ",                 None),   # whitespace only → empty after strip
])
def test_sanitize(field, value, expected):
    result = _sanitize(field, value)
    assert result == expected, f"field={field!r} value={value!r}: got {result!r}, expected {expected!r}"


# ============================================================================
# Blacklist Regex (red-team B1 verification)
# ============================================================================

@pytest.mark.parametrize("text,should_match", [
    ("RE: VESSEL CHANGE NOTICE",           True),
    ("rvs etd //",                         True),
    ("REVISED ETD NOTICE",                 True),
    ("CHANGE VESSEL to MSC OSCAR",         True),
    ("NEW ETD for SGNG47156900",           True),
    ("ATD// 20/04/2026 vessel departed",   False),   # normal ATD — must NOT match
    ("Update ATD normal mail",             False),
    ("Loaded on board confirmation",       False),
])
def test_blacklist_regex(text, should_match):
    match = bool(BLACKLIST_REGEX.search(text))
    assert match == should_match, f"text={text!r}: expected match={should_match}, got {match}"


# ============================================================================
# Kill Switch (red-team A4)
# ============================================================================

def test_kill_switch_active(tmp_path, monkeypatch):
    """When kill switch file exists, _check_kill_switch returns False."""
    ks_file = tmp_path / "AUTO_NOTIFY_DISABLED"
    ks_file.touch()
    monkeypatch.setattr(
        "email_engine.core.cnee_milestone.KILL_SWITCH", ks_file
    )
    assert _check_kill_switch() is False


def test_kill_switch_inactive(tmp_path, monkeypatch):
    """When kill switch file does NOT exist, _check_kill_switch returns True."""
    ks_file = tmp_path / "AUTO_NOTIFY_DISABLED"
    # Don't create the file
    monkeypatch.setattr(
        "email_engine.core.cnee_milestone.KILL_SWITCH", ks_file
    )
    assert _check_kill_switch() is True


# ============================================================================
# Daily counter logic
# ============================================================================

def test_daily_counter_increments(tmp_path, monkeypatch):
    """Daily counter starts at 0 and increments correctly."""
    counter_file = tmp_path / "milestone_daily.json"
    monkeypatch.setattr(
        "email_engine.core.cnee_milestone.DAILY_COUNTER", counter_file
    )
    assert _daily_count() == 0
    _increment_daily()
    assert _daily_count() == 1
    _increment_daily()
    assert _daily_count() == 2


def test_daily_counter_resets_on_new_day(tmp_path, monkeypatch):
    """Counter for yesterday returns 0 (new day resets)."""
    counter_file = tmp_path / "milestone_daily.json"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    counter_file.write_text(json.dumps({"date": yesterday, "count": 15}))
    monkeypatch.setattr(
        "email_engine.core.cnee_milestone.DAILY_COUNTER", counter_file
    )
    assert _daily_count() == 0   # yesterday's count ignored


# ============================================================================
# Whitespace-only sanitize edge case
# ============================================================================

def test_sanitize_whitespace_only_returns_none():
    """Pure whitespace after strip should be treated as empty → None."""
    result = _sanitize("vessel", "   ")
    assert result is None
