"""
us_holidays.py — Lightweight US federal holiday checker
========================================================
Phase 2B — Smart Send Window

Wraps the `holidays` library for US federal holidays.
Falls back gracefully (returns False) if library not installed.

Usage:
    from email_engine.core.us_holidays import is_us_holiday
    from datetime import date
    is_us_holiday(date(2025, 7, 4))   # True — Independence Day
    is_us_holiday(date(2025, 7, 5))   # False
"""

from __future__ import annotations

import logging
from datetime import date

log = logging.getLogger(__name__)

try:
    from holidays import US as _US_Holidays
    _HOLIDAYS_AVAILABLE = True
except ImportError:
    _US_Holidays = None  # type: ignore
    _HOLIDAYS_AVAILABLE = False
    log.warning("holidays package not installed — US holiday skip disabled. pip install holidays")

# Cache per-year to avoid rebuilding on every call
_cache: dict[int, object] = {}


def _get_calendar(year: int):
    """Return cached US holiday calendar for the given year."""
    if not _HOLIDAYS_AVAILABLE:
        return set()
    if year not in _cache:
        _cache[year] = _US_Holidays(years=year)
    return _cache[year]


def is_us_holiday(dt: date) -> bool:
    """Return True if dt is a US federal holiday.

    Always returns False if the `holidays` package is not installed
    (degrades gracefully — sends may happen on holidays rather than crashing).
    """
    if not _HOLIDAYS_AVAILABLE:
        return False
    try:
        cal = _get_calendar(dt.year)
        return dt in cal
    except Exception as exc:
        log.warning("is_us_holiday error for %s: %s", dt, exc)
        return False


def holiday_name(dt: date) -> str | None:
    """Return the holiday name for dt, or None if not a holiday."""
    if not _HOLIDAYS_AVAILABLE:
        return None
    try:
        cal = _get_calendar(dt.year)
        return cal.get(dt)
    except Exception:
        return None
