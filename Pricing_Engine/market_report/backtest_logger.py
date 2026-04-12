"""Backtest logger — compare prev week's forecast against actuals.

Appends a row per lane to `backtest-log.csv` with error_pct columns.

CSV schema:
  logged_at, prev_week, lane, container, forecast_base, actual_avg,
  error_abs, error_pct, model_version
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

from shared.paths import PARQUET_FILE

from .costing_extractor import LANE_MAP, _iso_week_bounds, _normalize_lane
from .paths import BACKTEST_LOG, ensure_dirs, forecast_parquet

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "logged_at", "prev_week", "lane", "container",
    "forecast_base", "actual_avg", "error_abs", "error_pct", "model_version",
]


def log_backtest(
    prev_week: str,
    parquet_path: Optional[Path] = None,
    container_filter: str = "40HQ",
) -> list[dict]:
    """Compare prev_week forecast parquet vs actual lane avgs. Append to CSV.

    Returns the list of rows appended (one per lane). Returns [] if the
    forecast parquet for prev_week is missing — backtest skipped.
    """
    ensure_dirs()
    parquet_path = parquet_path or PARQUET_FILE

    fcst_path = forecast_parquet(prev_week)
    if not fcst_path.exists():
        log.info("No forecast parquet for %s — skipping backtest", prev_week)
        return []

    # Load forecast base cases per lane
    try:
        con = duckdb.connect()
        fcst_rows = con.execute(
            f"SELECT lane, container, base_case, model_version "
            f"FROM read_parquet('{fcst_path.as_posix()}')"
        ).fetchall()
    except Exception as e:
        log.warning("Failed to read forecast parquet %s: %s", fcst_path, e)
        return []

    if not fcst_rows:
        con.close()
        return []

    # Compute actual lane averages from main parquet for prev_week range
    monday, sunday = _iso_week_bounds(prev_week)
    actual_avgs: dict[str, float] = {}
    if parquet_path.exists():
        try:
            actual_rows = con.execute(
                f"""
                SELECT POD, AVG(Amount) as avg_price
                FROM read_parquet('{parquet_path.as_posix()}')
                WHERE Eff >= TIMESTAMP '{monday.isoformat()}'
                  AND Eff <= TIMESTAMP '{sunday.isoformat()}'
                  AND Container_Type = '{container_filter}'
                  AND Amount IS NOT NULL AND Amount > 0
                GROUP BY POD
                """
            ).fetchall()
            # Bucket by lane
            lane_totals: dict[str, list[float]] = {}
            for pod, avg_p in actual_rows:
                lane = _normalize_lane(pod)
                if lane:
                    lane_totals.setdefault(lane, []).append(float(avg_p))
            for lane, vals in lane_totals.items():
                if vals:
                    actual_avgs[lane] = sum(vals) / len(vals)
        except Exception as e:
            log.warning("Failed to compute actuals from parquet: %s", e)
    con.close()

    now_iso = datetime.now().isoformat(timespec="seconds")
    appended: list[dict] = []
    for lane, container, base_case, model_version in fcst_rows:
        actual = actual_avgs.get(lane)
        if actual is None or not base_case:
            continue
        error_abs = actual - float(base_case)
        error_pct = (error_abs / float(base_case) * 100.0) if base_case else 0.0
        appended.append({
            "logged_at": now_iso,
            "prev_week": prev_week,
            "lane": lane,
            "container": container,
            "forecast_base": round(float(base_case), 2),
            "actual_avg": round(actual, 2),
            "error_abs": round(error_abs, 2),
            "error_pct": round(error_pct, 2),
            "model_version": model_version or "unknown",
        })

    if not appended:
        return []

    _append_csv(appended)
    return appended


def _append_csv(rows: list[dict]) -> None:
    """Append rows to backtest-log.csv, writing header if new."""
    BACKTEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not BACKTEST_LOG.exists()
    with BACKTEST_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def read_recent_backtest(n: int = 3) -> list[dict]:
    """Read last N rows from backtest log. Used by report section V."""
    if not BACKTEST_LOG.exists():
        return []
    with BACKTEST_LOG.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
    return all_rows[-n:] if all_rows else []
