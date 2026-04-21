# -*- coding: utf-8 -*-
"""
booking_parser.py — Parse Custeam booking email subjects and bodies.

Supports both delimiter styles (| and //) and both booking flows:
  - Direct:      "SORACHI BKG SGNG83555500 // HCM-TACOMA, WA // 1X40HC // ..."
  - Keep Space:  "[KEEP SPACE +SORACHI] | HCM-TACOMA, WA | 1X40HC | ONE | NELSON"

Public API:
    parse_booking_subject(subject)  -> dict
    parse_booking_body(body)        -> dict
    detect_booking_mail(subject)    -> bool

Only stdlib: re, datetime
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# BKG number: "BKG SGNG83555500" — 8–20 uppercase alphanumeric after "BKG "
_BKG_RE = re.compile(r'\bBKG\s+([A-Z0-9]{8,20})\b', re.IGNORECASE)

# Route segment: "HCM-TACOMA, WA" or "HPH-LAX"
# Group 1 = POL (3-4 uppercase), Group 2 = full POD string (e.g. "TACOMA, WA")
# Group 3 = first word of POD (e.g. "TACOMA"), Group 4 = state if any (e.g. "WA")
_ROUTE_RE = re.compile(
    r'\b([A-Z]{3,4})\s*-\s*([A-Z]{3,10}(?:,\s*[A-Z]{2})?)\b',
    re.IGNORECASE,
)

# Container + quantity: "1X40HC", "2X40RF", "9x20DC"
_CONTQTY_RE = re.compile(
    r'(\d+)\s*[Xx×]\s*((?:\d+)(?:HC|DC|GP|RF|HQ|NOR))',
    re.IGNORECASE,
)

# ETD / ETA pair: "ETD 1May - ETA 24May"  or solo "ETD 1May"
_ETD_ETA_RE = re.compile(
    r'ETD\s+(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    r'(?:\s*[-–]\s*ETA\s+(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))?',
    re.IGNORECASE,
)

# Standalone date: "24May" (used as ETA fallback)
_DATE_SOLO_RE = re.compile(
    r'\bETA\s+(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
    re.IGNORECASE,
)

# Vessel + voyage: "YM TOPMOST 024E"  — UPPERCASE words + digits + optional E/W/N/S
# Must contain at least 2 uppercase words before the voyage code
_VESSEL_RE = re.compile(
    r'\b((?:[A-Z][A-Z0-9]+\s+){1,4}[A-Z][A-Z0-9]*\s+\d{3,4}[EWNS]?)\b'
)

# PO number: "PO# LP-95"  or  "PO#LP-95"
_PO_RE = re.compile(r'PO#\s*([A-Z0-9][\w\-]+)', re.IGNORECASE)

# Keep Space marker:  "[KEEP SPACE +SORACHI]"  or  "[KEEP SPACE]"
_KEEP_SPACE_RE = re.compile(r'\[KEEP\s+SPACE(?:\s*\+([A-Z0-9\-]+))?\]', re.IGNORECASE)

# SI cutoff body: "S/I cut off time: 14:00 APR 21"
_SI_CUT_RE = re.compile(
    r'S/?I\s+cut\s*off\s+time[:\s]+(\d{1,2}:\d{2})\s+(\w{3})\s+(\d{1,2})',
    re.IGNORECASE,
)

# CY close body: "Deadline amendment: 11:00 APR 22"
_CY_CLOSE_RE = re.compile(
    r'(?:Deadline\s+amendment|CY\s+close?)[:\s]+(\d{1,2}:\d{2})\s+(\w{3})\s+(\d{1,2})',
    re.IGNORECASE,
)

# Detect booking mail: "BKG" + 8-20 alphanum chars  AND  route pattern (POL-POD)
_BKG_DETECT_RE = re.compile(r'\bBKG\s+[A-Z0-9]{8,20}\b', re.IGNORECASE)
_ROUTE_DETECT_RE = re.compile(r'\b[A-Z]{3,4}\s*-\s*[A-Z]{3,10}', re.IGNORECASE)

# Month name → number
_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,  'may': 5,  'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# Known carrier codes (used to identify which token is the carrier vs. sales)
_CARRIER_CODES = {
    'ONE', 'HPL', 'ZIM', 'MSC', 'CMA', 'COSCO', 'OOCL', 'EMC',
    'EVERGREEN', 'YANG MING', 'YM', 'WANHAI', 'WHL', 'PIL', 'KMTC',
    'MAERSK', 'HAPAG', 'YANGMING', 'TSL', 'SITC',
}

# Known sales codes (internal team names)
_SALES_CODES = {'NELSON', 'OTIS', 'JOHNNY', 'JENNIE', 'BLUE', 'LINA', 'JUN'}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_date(day: int, month_name: str, today: Optional[date] = None) -> str:
    """Resolve (day, month_name) to ISO date string.

    If the resolved date is already past today, assume next year.
    """
    if today is None:
        today = date.today()
    month = _MONTH_MAP.get(month_name.lower()[:3])
    if month is None:
        return ""
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return ""
    if d < today:
        try:
            d = date(year + 1, month, day)
        except ValueError:
            return ""
    return d.isoformat()


def _resolve_datetime(time_str: str, month_name: str, day: int,
                      today: Optional[date] = None) -> str:
    """Resolve time + month abbreviation + day to ISO datetime string."""
    if today is None:
        today = date.today()
    month = _MONTH_MAP.get(month_name.lower()[:3])
    if month is None:
        return ""
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return ""
    if d < today:
        try:
            d = date(year + 1, month, day)
        except ValueError:
            return ""
    # Combine date + time
    try:
        dt = datetime.fromisoformat(f"{d.isoformat()}T{time_str}")
        return dt.isoformat(timespec='minutes')
    except ValueError:
        return ""


def _split_tokens(subject: str) -> tuple[list[str], str]:
    """Split subject on // or | delimiter, returning (tokens, delimiter_type)."""
    if '//' in subject:
        raw = re.split(r'\s*//\s*', subject)
        delim = '//'
    else:
        raw = re.split(r'\s*\|\s*', subject)
        delim = '|'
    return [t.strip() for t in raw if t.strip()], delim


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_booking_mail(subject: str) -> bool:
    """Return True if subject looks like a Custeam booking confirmation email.

    Requires BOTH:
      - BKG pattern (BKG + 8-20 alphanum chars), AND
      - Route pattern (POL-POD)
    """
    if not subject:
        return False
    return bool(_BKG_DETECT_RE.search(subject) and _ROUTE_DETECT_RE.search(subject))


def parse_booking_subject(subject: str, today: Optional[date] = None) -> dict:
    """Parse Custeam booking subject line.

    Returns dict with all standard fields. Missing fields default to "".
    See module docstring for full field list.
    """
    result: dict = {
        'customer': '',
        'bkg_no': '',
        'pol': '',
        'pod': '',
        'final_dest': '',
        'container': '',
        'qty': 1,
        'etd': '',
        'eta': '',
        'sales': '',
        'carrier': '',
        'vessel': '',
        'voyage': '',
        'po_number': '',
        'is_keep_space': False,
        'raw_subject': subject,
    }

    if not subject:
        return result

    if today is None:
        today = date.today()

    # ── 1. Detect Keep Space ────────────────────────────────────────────────
    ks_match = _KEEP_SPACE_RE.search(subject)
    if ks_match:
        result['is_keep_space'] = True
        customer_name = ks_match.group(1) or ''
        result['customer'] = customer_name.upper() if customer_name else ''

    # ── 2. Extract BKG number ───────────────────────────────────────────────
    bkg_match = _BKG_RE.search(subject)
    if bkg_match:
        result['bkg_no'] = bkg_match.group(1).upper()
        # Customer = first WORD before "BKG" (for Direct flow)
        if not result['is_keep_space']:
            pre = subject[:bkg_match.start()].strip()
            # Take the last token of the pre-BKG portion as customer
            pre_tokens = pre.split()
            if pre_tokens and pre_tokens[-1].upper() not in ('', 'BKG'):
                result['customer'] = pre_tokens[-1].upper()

    # ── 3. Parse tokens for route, container, carrier, vessel, PO ──────────
    tokens, _ = _split_tokens(subject)

    # Remove Keep Space bracket from first token if present
    clean_tokens = []
    for t in tokens:
        if _KEEP_SPACE_RE.search(t):
            # Keep Space token — already extracted customer above
            continue
        clean_tokens.append(t)

    # Route — look in all tokens
    route_found = False
    for t in clean_tokens:
        rm = _ROUTE_RE.search(t)
        if rm:
            pol_raw = rm.group(1).upper()
            final_dest_raw = rm.group(2).upper()
            # POD = first word of final_dest (before comma)
            pod_raw = final_dest_raw.split(',')[0].strip()
            result['pol'] = pol_raw
            result['pod'] = pod_raw
            result['final_dest'] = final_dest_raw.replace(' ', '').replace(',', ', ').strip()
            # Clean up spacing: "TACOMA,WA" → "TACOMA, WA"
            result['final_dest'] = re.sub(r',\s*', ', ', final_dest_raw).strip()
            route_found = True
            break

    # Container + qty
    cq_match = _CONTQTY_RE.search(subject)
    if cq_match:
        result['qty'] = int(cq_match.group(1))
        result['container'] = cq_match.group(2).upper()

    # ETD / ETA dates
    etd_m = _ETD_ETA_RE.search(subject)
    if etd_m:
        result['etd'] = _resolve_date(int(etd_m.group(1)), etd_m.group(2), today)
        if etd_m.group(3):
            result['eta'] = _resolve_date(int(etd_m.group(3)), etd_m.group(4), today)
    # Fallback: standalone ETA
    if not result['eta']:
        eta_m = _DATE_SOLO_RE.search(subject)
        if eta_m:
            result['eta'] = _resolve_date(int(eta_m.group(1)), eta_m.group(2), today)

    # PO number
    po_m = _PO_RE.search(subject)
    if po_m:
        result['po_number'] = po_m.group(1).strip()

    # Vessel + voyage: find token containing uppercase words + digit voyage code
    for t in clean_tokens:
        v_match = _VESSEL_RE.search(t)
        if v_match:
            vessel_voyage = v_match.group(1).strip()
            # Split on last numeric sequence to separate vessel from voyage
            parts = re.split(r'\s+(?=\d{3,4}[EWNS]?\s*$)', vessel_voyage)
            if len(parts) == 2:
                result['vessel'] = parts[0].strip()
                result['voyage'] = parts[1].strip()
            else:
                # Try splitting on last whitespace before voyage code
                v_parts = vessel_voyage.rsplit(None, 1)
                if len(v_parts) == 2 and re.match(r'^\d{3,4}[EWNS]?$', v_parts[1]):
                    result['vessel'] = v_parts[0].strip()
                    result['voyage'] = v_parts[1].strip()
                else:
                    result['vessel'] = vessel_voyage
            break

    # Carrier and sales: scan clean tokens for known codes
    # After BKG token, the pattern typically is: ... // SALES // CARRIER // VESSEL
    for t in clean_tokens:
        upper_t = t.upper().strip()
        if upper_t in _CARRIER_CODES:
            result['carrier'] = upper_t
        elif upper_t in _SALES_CODES:
            result['sales'] = upper_t

    return result


def parse_booking_body(body: str, today: Optional[date] = None) -> dict:
    """Parse body text of Custeam booking mail for SI cutoff and CY close datetimes.

    Expected patterns:
      "S/I cut off time: 14:00 APR 21"
      "Deadline amendment: 11:00 APR 22"

    Returns:
        si_cutoff: ISO datetime string "2026-04-21T14:00" or ""
        cy_close:  ISO datetime string or ""
    """
    result = {'si_cutoff': '', 'cy_close': ''}

    if not body:
        return result

    if today is None:
        today = date.today()

    si_m = _SI_CUT_RE.search(body)
    if si_m:
        result['si_cutoff'] = _resolve_datetime(
            si_m.group(1), si_m.group(2), int(si_m.group(3)), today
        )

    cy_m = _CY_CLOSE_RE.search(body)
    if cy_m:
        result['cy_close'] = _resolve_datetime(
            cy_m.group(1), cy_m.group(2), int(cy_m.group(3)), today
        )

    return result
