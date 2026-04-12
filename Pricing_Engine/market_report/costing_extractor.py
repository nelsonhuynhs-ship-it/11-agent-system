"""Extract top costing items per lane from the master rate parquet.

For the given ISO week, query parquet filtering to recent effective rates,
group by lane (WC/EC/GULF), pick top-3 lowest per lane+carrier, compute
spread vs lane average.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import duckdb

from shared.paths import PARQUET_FILE

from .schemas import CostingItem

log = logging.getLogger(__name__)

# Port code / city → lane mapping (matches Nelson's report conventions).
# Keys are UPPER-cased; matching also strips non-alphanumeric for fuzzy hits.
LANE_MAP: dict[str, str] = {
    # WC — codes
    "LGB": "WC", "USLGB": "WC",
    "LAX": "WC", "USLAX": "WC",
    "OAK": "WC", "USOAK": "WC",
    "SEA": "WC", "USSEA": "WC",
    "TAC": "WC", "USTAC": "WC",
    "USWC": "WC", "WC": "WC",
    # WC — city-name variants seen in parquet
    "LAXLGB": "WC",
    "LONGBEACH": "WC", "LONGBEACHCA": "WC",
    "LOSANGELES": "WC", "LOSANGELESCA": "WC",
    "OAKLANDCA": "WC",
    "SEATTLEWA": "WC",
    "TACOMAWA": "WC",
    "VANCOUVERBC": "WC",  # Canadian WC
    # EC — codes
    "NYC": "EC", "USNYC": "EC",
    "BOS": "EC", "USBOS": "EC",
    "SAV": "EC", "USSAV": "EC",
    "CHS": "EC", "USCHS": "EC",
    "NWK": "EC", "USNWK": "EC",
    "NFK": "EC", "USNFK": "EC",
    "USEC": "EC", "EC": "EC",
    # EC — city-name variants
    "NEWYORKNY": "EC",
    "NEWYORK": "EC",
    "BOSTONMA": "EC",
    "SAVANNAHGA": "EC",
    "CHARLESTONSC": "EC",
    "NEWARKNJ": "EC",
    "NORFOLKVA": "EC",
    "TORONTOON": "EC",  # Canadian EC
    "MONTREALQC": "EC",
    # GULF — codes
    "HOU": "GULF", "USHOU": "GULF",
    "NOLA": "GULF", "USMSY": "GULF",
    "MSY": "GULF",
    "USGULF": "GULF", "GULF": "GULF",
    # GULF — city-name variants
    "HOUSTONTX": "GULF",
    "NEWORLEANSLA": "GULF",
    "MOBILEAL": "GULF",
}


def _iso_week_bounds(week: str) -> tuple[date, date]:
    """Return [monday, sunday] date range for a given ISO week string."""
    year_s, w_s = week.split("-W")
    year = int(year_s)
    w = int(w_s)
    monday = date.fromisocalendar(year, w, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _normalize_lane(pod: Optional[str]) -> Optional[str]:
    """Map POD code/city → WC/EC/GULF. Fuzzy-strips punctuation and US prefix."""
    if not pod:
        return None
    code = pod.strip().upper()
    # Exact hit
    if code in LANE_MAP:
        return LANE_MAP[code]
    # Strip non-alphanumeric (handles "LAX-LGB" → "LAXLGB", "NEW YORK, NY" → "NEWYORKNY")
    stripped = "".join(ch for ch in code if ch.isalnum())
    if stripped in LANE_MAP:
        return LANE_MAP[stripped]
    # Strip "US" prefix and retry
    if stripped.startswith("US") and len(stripped) > 2:
        short = stripped[2:]
        if short in LANE_MAP:
            return LANE_MAP[short]
    return None


def extract_costing(
    week: str,
    parquet_path: Optional[Path] = None,
    container_filter: str = "40HQ",
    top_n_per_lane: int = 3,
) -> list[CostingItem]:
    """Extract top costing rows from parquet for the given ISO week.

    Strategy:
      1. Filter parquet to rows with Eff within ±30 days of the week's Monday.
      2. Filter to 40HC (or provided container).
      3. Map POD → lane. Drop unmapped.
      4. For each (lane, carrier) pair, pick lowest price row.
      5. For each lane, return top N cheapest carriers.
      6. Compute spread vs lane_avg for each row.

    Returns empty list if parquet missing or query fails.
    """
    parquet_path = parquet_path or PARQUET_FILE
    if not parquet_path.exists():
        log.warning("Parquet not found: %s", parquet_path)
        return []

    monday, _ = _iso_week_bounds(week)
    window_start = monday - timedelta(days=30)
    window_end = monday + timedelta(days=14)

    query = f"""
        SELECT
            POD,
            Carrier,
            Rate_Type,
            Container_Type,
            Amount,
            Eff,
            Exp
        FROM read_parquet('{parquet_path.as_posix()}')
        WHERE Eff IS NOT NULL
          AND Eff >= TIMESTAMP '{window_start.isoformat()}'
          AND Eff <= TIMESTAMP '{window_end.isoformat()}'
          AND Container_Type = '{container_filter}'
          AND Amount IS NOT NULL
          AND Amount > 0
          AND Charge_Name IN ('Base Ocean Freight', 'Total Ocean Freight')
    """

    try:
        con = duckdb.connect()
        rows = con.execute(query).fetchall()
        con.close()
    except Exception as e:
        log.warning("DuckDB query failed for week %s: %s", week, e)
        return []

    # Group into (lane, carrier) → cheapest row
    best_per_lane_carrier: dict[tuple[str, str], tuple] = {}
    for row in rows:
        pod, carrier, rate_type, container, amount, eff, exp = row
        lane = _normalize_lane(pod)
        if lane is None or not carrier:
            continue
        key = (lane, carrier.strip().upper())
        if key not in best_per_lane_carrier or amount < best_per_lane_carrier[key][4]:
            best_per_lane_carrier[key] = row

    # Bucket by lane
    by_lane: dict[str, list[tuple]] = {"WC": [], "EC": [], "GULF": []}
    for (lane, _), row in best_per_lane_carrier.items():
        by_lane.setdefault(lane, []).append(row)

    items: list[CostingItem] = []
    for lane, lane_rows in by_lane.items():
        if not lane_rows:
            continue
        prices = [r[4] for r in lane_rows]
        lane_avg = sum(prices) / len(prices) if prices else 0.0
        lane_rows_sorted = sorted(lane_rows, key=lambda r: r[4])[:top_n_per_lane]
        for r in lane_rows_sorted:
            pod, carrier, rate_type, container, amount, eff, exp = r
            items.append(
                CostingItem(
                    lane=lane,  # type: ignore[arg-type]
                    carrier=carrier.strip().upper(),
                    rate_type=_normalize_rate_type(rate_type),
                    container=container or container_filter,
                    price=float(amount),
                    valid_from=_to_date(eff),
                    valid_to=_to_date(exp),
                    is_pudong_best=True,
                    spread_vs_lane_avg=float(amount) - lane_avg,
                    source_parquet_row=-1,
                )
            )
    return items


def _to_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    return None


def _normalize_rate_type(v) -> str:
    """Coerce raw Rate_Type to known literal, fallback to FIX."""
    if not v:
        return "FIX"
    s = str(v).strip().upper()
    for known in ("FIX", "FAK", "SCFI", "SPOT", "BULLET", "NAC"):
        if known in s:
            return known
    return "FIX"


def group_costing_by_lane(items: Iterable[CostingItem]) -> dict[str, list[CostingItem]]:
    """Bucket items into {'WC': [...], 'EC': [...], 'GULF': [...]}."""
    out: dict[str, list[CostingItem]] = {"WC": [], "EC": [], "GULF": []}
    for it in items:
        out.setdefault(it.lane, []).append(it)
    return out
