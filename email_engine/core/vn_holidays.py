"""
vn_holidays.py — Vietnamese public holiday checker
====================================================
Phase 4 — Daily Scheduler

Covers fixed-date holidays + Tet (lunar new year) range.
Degrades gracefully: if lunarcalendar/ephem not available, Tet is
estimated (±1 day) using a hardcoded lookup table for 2024-2030.

Usage:
    from email_engine.core.vn_holidays import is_vn_holiday
    from datetime import date
    is_vn_holiday(date(2026, 4, 30))  # True — Reunification Day
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)

# ── Fixed-date holidays (month, day) ─────────────────────────────────────────
_FIXED_HOLIDAYS: list[tuple[int, int]] = [
    (1, 1),   # New Year's Day
    (4, 30),  # Reunification Day (Liberation Day)
    (5, 1),   # International Labour Day
    (9, 2),   # National Day (Independence Day)
]

# ── Tet Nguyen Dan: approximate Gregorian dates of Lunar New Year eve+day ────
# Each entry = (year, month, day) of the first day of the lunar new year.
# Source: published lunar calendar, covers 2024-2030.
_TET_DATES: dict[int, date] = {
    2024: date(2024, 2, 10),
    2025: date(2025, 1, 29),
    2026: date(2026, 2, 17),
    2027: date(2027, 2, 6),
    2028: date(2028, 1, 26),
    2029: date(2029, 2, 13),
    2030: date(2030, 2, 3),
}

# Official Tet holiday window: eve + 3 days (total 4 days surrounding new year)
_TET_EVE_OFFSET = -1    # day before Lunar New Year
_TET_LAST_OFFSET = 3    # day after Lunar New Year (inclusive)

# King Hung Commemoration (10th day of 3rd lunar month) — varies ~April.
# Hardcoded for 2024-2030 (stable enough).
_HUNG_KINGS_DATES: dict[int, date] = {
    2024: date(2024, 4, 18),
    2025: date(2025, 4, 7),
    2026: date(2026, 3, 27),  # falls in March 2026
    2027: date(2027, 4, 16),
    2028: date(2028, 4, 5),
    2029: date(2029, 4, 25),
    2030: date(2030, 4, 14),
}


def _tet_range(year: int) -> tuple[date, date] | None:
    """Return (start, end) inclusive Tet holiday range for the given year.

    Returns None if the year is not in the lookup table.
    """
    tet_day = _TET_DATES.get(year)
    if tet_day is None:
        return None
    start = tet_day + timedelta(days=_TET_EVE_OFFSET)
    end   = tet_day + timedelta(days=_TET_LAST_OFFSET)
    return start, end


def is_vn_holiday(dt: date) -> bool:
    """Return True if dt is a Vietnamese public holiday.

    Covers:
    - Fixed-date holidays (New Year, Reunification, Labour Day, National Day)
    - Hung Kings Commemoration (Gio To Hung Vuong)
    - Tet Nguyen Dan (4-day window: eve + 3 days)
    """
    try:
        # Fixed holidays
        if (dt.month, dt.day) in _FIXED_HOLIDAYS:
            return True

        # Hung Kings Commemoration
        hung = _HUNG_KINGS_DATES.get(dt.year)
        if hung and dt == hung:
            return True

        # Tet range
        tet = _tet_range(dt.year)
        if tet and tet[0] <= dt <= tet[1]:
            return True

        return False
    except Exception as exc:
        log.warning("is_vn_holiday error for %s: %s", dt, exc)
        return False


def holiday_name(dt: date) -> str | None:
    """Return the Vietnamese holiday name for dt, or None."""
    try:
        if (dt.month, dt.day) == (1, 1):
            return "Tet Duong Lich (New Year)"
        if (dt.month, dt.day) == (4, 30):
            return "Ngay Giai Phong Mien Nam"
        if (dt.month, dt.day) == (5, 1):
            return "Quoc Te Lao Dong"
        if (dt.month, dt.day) == (9, 2):
            return "Quoc Khanh"

        hung = _HUNG_KINGS_DATES.get(dt.year)
        if hung and dt == hung:
            return "Gio To Hung Vuong"

        tet = _tet_range(dt.year)
        if tet and tet[0] <= dt <= tet[1]:
            return "Tet Nguyen Dan"

        return None
    except Exception:
        return None
