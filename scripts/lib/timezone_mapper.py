# -*- coding: utf-8 -*-
"""
scripts/lib/timezone_mapper.py — US State / CA Province → timezone string.
==========================================================================
Maps 2-letter state/province codes to IANA timezone identifiers.

Usage:
    from scripts.lib.timezone_mapper import state_to_timezone, TZ_MAP
    tz = state_to_timezone("CA")   # → "America/Los_Angeles"
    tz = state_to_timezone("ON")   # → "America/Toronto"
"""

from __future__ import annotations

# ── US States → IANA timezone ─────────────────────────────────────────────────
# Multi-timezone states use the most populated/commercial zone.
TZ_MAP: dict[str, str] = {
    # Eastern
    "CT": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",
    "GA": "America/New_York",
    "IN": "America/Indiana/Indianapolis",
    "KY": "America/Kentucky/Louisville",
    "MA": "America/New_York",
    "MD": "America/New_York",
    "ME": "America/New_York",
    "MI": "America/New_York",
    "NC": "America/New_York",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NY": "America/New_York",
    "OH": "America/New_York",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "VA": "America/New_York",
    "VT": "America/New_York",
    "WV": "America/New_York",
    "DC": "America/New_York",
    # Central
    "AL": "America/Chicago",
    "AR": "America/Chicago",
    "IA": "America/Chicago",
    "IL": "America/Chicago",
    "KS": "America/Chicago",
    "LA": "America/Chicago",
    "MN": "America/Chicago",
    "MO": "America/Chicago",
    "MS": "America/Chicago",
    "ND": "America/Chicago",
    "NE": "America/Chicago",
    "OK": "America/Chicago",
    "SD": "America/Chicago",
    "TN": "America/Chicago",
    "TX": "America/Chicago",
    "WI": "America/Chicago",
    # Mountain
    "AZ": "America/Phoenix",
    "CO": "America/Denver",
    "ID": "America/Denver",
    "MT": "America/Denver",
    "NM": "America/Denver",
    "UT": "America/Denver",
    "WY": "America/Denver",
    "NV": "America/Los_Angeles",  # Most commerce in Pacific zone
    # Pacific
    "CA": "America/Los_Angeles",
    "OR": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    # Non-contiguous
    "AK": "America/Anchorage",
    "HI": "Pacific/Honolulu",
    # Territories
    "PR": "America/Puerto_Rico",
    "GU": "Pacific/Guam",
    "VI": "America/Port_of_Spain",
    "AS": "Pacific/Pago_Pago",
    # Canadian provinces (common in freight)
    "AB": "America/Edmonton",
    "BC": "America/Vancouver",
    "MB": "America/Winnipeg",
    "NB": "America/Moncton",
    "NL": "America/St_Johns",
    "NS": "America/Halifax",
    "NT": "America/Yellowknife",
    "NU": "America/Rankin_Inlet",
    "ON": "America/Toronto",
    "PE": "America/Halifax",
    "QC": "America/Toronto",
    "SK": "America/Regina",
    "YT": "America/Whitehorse",
}

_VALID_STATES = set(TZ_MAP.keys())


def state_to_timezone(state_code: str) -> str:
    """Return IANA timezone for a 2-letter state/province code.

    Returns empty string if not found (never raises).
    """
    if not state_code:
        return ""
    return TZ_MAP.get(state_code.strip().upper(), "")


def is_valid_state(state_code: str) -> bool:
    """Return True if state_code is a known US state or CA province."""
    return (state_code or "").strip().upper() in _VALID_STATES
