"""state_parser.py — Parse US state (and CA province) from DESTINATION strings.

A2 — Send-time State Rules module.

Supports formats like:
  "Port Of Boston, Boston, Massachusetts"  → "MA"
  "Long Beach, CA"                         → "CA"
  "Newark, New Jersey, USA"                → "NJ"
  "Houston, TX 77002"                      → "TX"
  "Chicago, Illinois"                      → "IL"
  "Vancouver, BC, Canada"                  → "BC"

Returns USPS 2-letter code, or None if unparseable.
"""

import re
from typing import Optional

# ── US States — full name → 2-letter code ─────────────────────────────────────
_STATE_FULL: dict[str, str] = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    # Territories
    "PUERTO RICO": "PR",
    "GUAM": "GU",
    "VIRGIN ISLANDS": "VI",
    "AMERICAN SAMOA": "AS",
    "NORTHERN MARIANA ISLANDS": "MP",
}

# ── Canada provinces ───────────────────────────────────────────────────────────
_PROVINCE_FULL: dict[str, str] = {
    "BRITISH COLUMBIA": "BC",
    "ONTARIO": "ON",
    "QUEBEC": "QC",
    "ALBERTA": "AB",
    "NOVA SCOTIA": "NS",
    "MANITOBA": "MB",
    "SASKATCHEWAN": "SK",
    "NEW BRUNSWICK": "NB",
    "NEWFOUNDLAND AND LABRADOR": "NL",
    "NEWFOUNDLAND": "NL",
    "LABRADOR": "NL",
    "PRINCE EDWARD ISLAND": "PE",
    "NORTHWEST TERRITORIES": "NT",
    "YUKON": "YT",
    "NUNAVUT": "NU",
}

# Merged: full name → code (US + Canada)
_ALL_FULL: dict[str, str] = {**_STATE_FULL, **_PROVINCE_FULL}

# Valid 2-letter codes (US + DC + territories + CA provinces)
_VALID_CODES: set[str] = set(_STATE_FULL.values()) | set(_PROVINCE_FULL.values())

# City → state hint for disambiguation (top freight cities)
_CITY_STATE_HINT: dict[str, str] = {
    "LOS ANGELES": "CA",
    "LONG BEACH": "CA",
    "SAN FRANCISCO": "CA",
    "SAN DIEGO": "CA",
    "SACRAMENTO": "CA",
    "OAKLAND": "CA",
    "SEATTLE": "WA",
    "TACOMA": "WA",
    "PORTLAND": "OR",
    "PHOENIX": "AZ",
    "TUCSON": "AZ",
    "LAS VEGAS": "NV",
    "RENO": "NV",
    "SALT LAKE CITY": "UT",
    "DENVER": "CO",
    "ALBUQUERQUE": "NM",
    "BILLINGS": "MT",
    "BOISE": "ID",
    "CHEYENNE": "WY",
    "HOUSTON": "TX",
    "DALLAS": "TX",
    "FORT WORTH": "TX",
    "SAN ANTONIO": "TX",
    "AUSTIN": "TX",
    "EL PASO": "TX",
    "CHICAGO": "IL",
    "MINNEAPOLIS": "MN",
    "MILWAUKEE": "WI",
    "KANSAS CITY": "MO",
    "ST LOUIS": "MO",
    "SAINT LOUIS": "MO",
    "OMAHA": "NE",
    "SIOUX FALLS": "SD",
    "FARGO": "ND",
    "DES MOINES": "IA",
    "MEMPHIS": "TN",
    "NASHVILLE": "TN",
    "LOUISVILLE": "KY",
    "CINCINNATI": "OH",
    "CLEVELAND": "OH",
    "COLUMBUS": "OH",
    "DETROIT": "MI",
    "INDIANAPOLIS": "IN",
    "NEW YORK": "NY",
    "NEWARK": "NJ",
    "BROOKLYN": "NY",
    "BRONX": "NY",
    "QUEENS": "NY",
    "BUFFALO": "NY",
    "PHILADELPHIA": "PA",
    "PITTSBURGH": "PA",
    "BALTIMORE": "MD",
    "WASHINGTON": "DC",
    "BOSTON": "MA",
    "PROVIDENCE": "RI",
    "HARTFORD": "CT",
    "NEW HAVEN": "CT",
    "BRIDGEPORT": "CT",
    "ALBANY": "NY",
    "NEWARK": "NJ",
    "TRENTON": "NJ",
    "RICHMOND": "VA",
    "NORFOLK": "VA",
    "VIRGINIA BEACH": "VA",
    "CHARLESTON": "SC",
    "COLUMBIA": "SC",
    "CHARLOTTE": "NC",
    "RALEIGH": "NC",
    "WILMINGTON": "NC",
    "SAVANNAH": "GA",
    "ATLANTA": "GA",
    "JACKSONVILLE": "FL",
    "MIAMI": "FL",
    "TAMPA": "FL",
    "ORLANDO": "FL",
    "FORT LAUDERDALE": "FL",
    "PORT EVERGLADES": "FL",
    "MOBILE": "AL",
    "BIRMINGHAM": "AL",
    "NEW ORLEANS": "LA",
    "BATON ROUGE": "LA",
    "JACKSON": "MS",
    "LITTLE ROCK": "AR",
    "OKLAHOMA CITY": "OK",
    "TULSA": "OK",
    "WICHITA": "KS",
    "TOPEKA": "KS",
    "LINCOLN": "NE",
    "ANCHORAGE": "AK",
    "FAIRBANKS": "AK",
    "JUNEAU": "AK",
    "HONOLULU": "HI",
    "HILO": "HI",
    "CONCORD": "NH",
    "MANCHESTER": "NH",
    "PORTLAND ME": "ME",
    "BURLINGTON": "VT",
    "MONTPELIER": "VT",
    "DOVER": "DE",
    "WILMINGTON DE": "DE",
    "CHARLESTON WV": "WV",
    "MORGANTOWN": "WV",
    # Canada
    "VANCOUVER": "BC",
    "VICTORIA": "BC",
    "TORONTO": "ON",
    "OTTAWA": "ON",
    "MONTREAL": "QC",
    "CALGARY": "AB",
    "EDMONTON": "AB",
    "WINNIPEG": "MB",
    "HALIFAX": "NS",
    "PRINCE RUPERT": "BC",
    "SAINT JOHN": "NB",
}

# Regex: standalone 2-letter code (word boundary), optionally followed by zip
_CODE_RE = re.compile(
    r"(?<![A-Za-z])([A-Z]{2})(?:\s+\d{5}(?:-\d{4})?)?(?![A-Za-z])"
)

# "The Port of" / "Port of Entry" junk prefix stripper
_PORT_JUNK_RE = re.compile(r"^(?:the\s+)?port\s+of(?:\s+entry)?[,\s-]*", re.IGNORECASE)


def parse_state(destination: str) -> Optional[str]:
    """Parse a DESTINATION string → USPS 2-letter state/province code.

    Strategy (in priority order):
    1. Standalone 2-letter code in the last segment (e.g. "City, TX" or "City, TX 77002")
       — checked first so "Washington, DC" yields DC not WA.
    2. Full state/province name found as a whole-word substring
       (longer names tried first: "WEST VIRGINIA" before "VIRGINIA")
    3. City hint lookup
    4. Standalone 2-letter code anywhere in remaining segments (fallback)

    Returns None if no match.
    """
    if not destination or not isinstance(destination, str):
        return None

    # Strip 'The Port of …' prefix noise
    cleaned = _PORT_JUNK_RE.sub("", destination).strip()

    # Upper-cased version for matching
    up = cleaned.upper()

    # Split segments (comma / semicolon / slash)
    segments = [s.strip() for s in re.split(r"[,;/]", cleaned)]

    # ── 1. Last segment 2-letter code (highest precision) ───────────────────
    for seg in reversed(segments):
        seg_up = seg.strip().upper()
        # Strip trailing zip: "TX 77002" → "TX"
        seg_up_clean = re.sub(r"\s+\d{5}(?:-\d{4})?$", "", seg_up).strip()
        if seg_up_clean in _VALID_CODES:
            return seg_up_clean

    # ── 2. Full name match ───────────────────────────────────────────────────
    # Try longer names first: "WEST VIRGINIA" before "VIRGINIA"
    sorted_full = sorted(_ALL_FULL.keys(), key=len, reverse=True)
    for name in sorted_full:
        pattern = r"(?<![A-Z])" + re.escape(name) + r"(?![A-Z])"
        if re.search(pattern, up):
            return _ALL_FULL[name]

    # ── 3. City hint ─────────────────────────────────────────────────────────
    sorted_cities = sorted(_CITY_STATE_HINT.keys(), key=len, reverse=True)
    for city in sorted_cities:
        if city in up:
            return _CITY_STATE_HINT[city]

    # ── 4. Regex 2-letter code anywhere (fallback) ───────────────────────────
    for seg in reversed(segments):
        seg_up = seg.strip().upper()
        for m in _CODE_RE.finditer(seg_up):
            code = m.group(1)
            if code in _VALID_CODES:
                return code

    return None


def parse_state_bulk(destinations: list[str]) -> list[Optional[str]]:
    """Batch parse — same as parse_state but vectorised for DataFrames."""
    return [parse_state(d) for d in destinations]


# ── Unit tests (run with: python -m pytest email_engine/core/state_parser.py) ──

def _run_tests():
    """Quick self-test — not pytest, just for smoke check during dev."""
    cases = [
        ("Port Of Boston, Boston, Massachusetts", "MA"),
        ("Long Beach, CA", "CA"),
        ("Newark, New Jersey, USA", "NJ"),
        ("Houston, TX 77002", "TX"),
        ("Chicago, Illinois", "IL"),
        ("The Port of Los Angeles, Los Angeles, California", "CA"),
        ("New York/Newark Area, Newark, New Jersey", "NJ"),
        ("USCHI", None),          # port code, not parseable as state
        ("USLAX", None),          # same
        ("Savannah, GA 31401, USA", "GA"),
        ("Seattle, Washington", "WA"),
        ("Miami, Florida", "FL"),
        ("Norfolk, Virginia", "VA"),
        ("Baltimore, Maryland", "MD"),
        ("Philadelphia, Pennsylvania", "PA"),
        ("Vancouver, BC, Canada", "BC"),
        ("Toronto, Ontario, Canada", "ON"),
        ("Montreal, Quebec", "QC"),
        ("", None),
        (None, None),
        ("Dallas, Texas", "TX"),
        ("Tacoma, WA", "WA"),
        ("New Orleans, LA", "LA"),
        ("Denver, CO 80201", "CO"),
        ("Honolulu, Hawaii", "HI"),
        ("Anchorage, Alaska", "AK"),
        ("The Port of Entry - Long Beach, California", "CA"),
        ("Port of Miami, Florida", "FL"),
        ("West Virginia", "WV"),
        ("Washington, DC", "DC"),
    ]
    passed = failed = 0
    for dest, expected in cases:
        result = parse_state(dest)
        if result == expected:
            passed += 1
        else:
            print(f"  FAIL: parse_state({dest!r}) = {result!r}, expected {expected!r}")
            failed += 1
    print(f"\nstate_parser self-test: {passed}/{passed+failed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    _run_tests()
