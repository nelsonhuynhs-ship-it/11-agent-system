# -*- coding: utf-8 -*-
"""
market_engine.py — Per-lane market state analyzer.

Reads Parquet rate history (`Cleaned_Master_History.parquet`) via DuckDB,
classifies each (pol, destination) lane into one of:
    URGENT | COMPETITIVE | STABLE | DECLINING

Public API
----------
analyze_lane(pol: str, destination: str) -> dict
    Returns {state, delta_pct, current_rate_40hq, prev_rate_40hq, mean_90d,
             forecast_next_week, confidence, sample_size, updated_at}

State rules (per phase-03 spec)
    URGENT      : delta_pct >= +3% WoW AND sample_size >= 30 AND confidence >= 0.7
    DECLINING   : delta_pct <= -3% WoW
    COMPETITIVE : current_rate < mean_90d * 0.95
    STABLE      : default

Cache: 30 minutes per (pol, dest) via in-memory dict.
Fallback: STABLE with empty stats if Parquet missing or sample_size < 30.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("market_engine")

# ── Parquet path resolution (graceful fallback) ───────────────────────────────
try:
    from shared.paths import PARQUET_FILE as _PARQUET_FILE  # type: ignore
    PARQUET_FILE = Path(_PARQUET_FILE)
except Exception:
    _here = Path(__file__).resolve()
    # email_engine/intelligence/market_engine.py → repo root is 3 parents up
    PARQUET_FILE = _here.parents[2] / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"

# ── Cache (in-memory, 30 min TTL) ────────────────────────────────────────────
_CACHE_TTL_SEC = 30 * 60
_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_cache_lock = threading.Lock()

# Minimum rows to classify URGENT (below this → fallback STABLE)
_MIN_SAMPLE = 30


def _empty_result(
    pol: str,
    destination: str,
    reason: str = "no_data",
) -> dict:
    """Return a safe fallback STABLE dict when data is missing."""
    return {
        "state": "STABLE",
        "delta_pct": 0.0,
        "current_rate_40hq": None,
        "prev_rate_40hq": None,
        "mean_90d": None,
        "forecast_next_week": None,
        "confidence": 0.0,
        "sample_size": 0,
        "pol": pol.upper(),
        "destination": destination.upper(),
        "reason": reason,
        "updated_at": time.time(),
    }


def _run_duckdb_query(pol: str, destination: str) -> list[dict]:
    """
    Query Parquet via DuckDB for 40HQ TOTAL rates of (pol, destination) in last 90 days.

    Returns list of {date, amount} dicts sorted ascending by date.
    Returns [] if Parquet missing or query fails.
    """
    if not PARQUET_FILE.exists():
        log.warning("[market] Parquet not found at %s", PARQUET_FILE)
        return []

    try:
        import duckdb
    except ImportError:
        log.error("[market] DuckDB not installed")
        return []

    pq = str(PARQUET_FILE).replace("\\", "/")
    pol_u = pol.upper()
    dest_u = destination.upper()
    try:
        q = f"""
            SELECT
                CAST(Eff AS DATE) AS eff_date,
                CAST(Amount AS DOUBLE) AS amount
            FROM read_parquet('{pq}')
            WHERE UPPER(Charge_Name) LIKE '%TOTAL%'
              AND UPPER(Container_Type) IN ('40HQ','40HC','40HG')
              AND UPPER(POL) LIKE '%{pol_u}%'
              AND (UPPER(POD) LIKE '%{dest_u}%' OR UPPER(Place) LIKE '%{dest_u}%')
              AND Amount IS NOT NULL
              AND Amount > 0
              AND Eff >= CURRENT_DATE - INTERVAL '90 days'
            ORDER BY eff_date ASC
        """
        rows = duckdb.sql(q).df()
        return [
            {"date": r["eff_date"], "amount": float(r["amount"])}
            for _, r in rows.iterrows()
        ]
    except Exception as e:
        log.warning("[market] DuckDB query failed for %s/%s: %s", pol, destination, e)
        return []


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 == 1 else float((s[mid - 1] + s[mid]) / 2.0)


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return var ** 0.5


def _linear_forecast(weekly_medians: list[float]) -> float | None:
    """
    Simple linear regression over (x=week_index, y=median_rate) for last 4 weeks.
    Returns predicted value for next week, or None if <2 points.
    """
    pts = [(i, y) for i, y in enumerate(weekly_medians) if y is not None]
    if len(pts) < 2:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] ** 2 for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return float(slope * n + intercept)  # next week index = n


def _bucket_by_iso_week(rows: list[dict]) -> dict[tuple[int, int], list[float]]:
    """Group rate rows by (iso_year, iso_week) → list of amounts."""
    import datetime as _dt

    buckets: dict[tuple[int, int], list[float]] = {}
    for r in rows:
        d = r["date"]
        if d is None:
            continue
        if not isinstance(d, (_dt.date, _dt.datetime)):
            try:
                d = _dt.datetime.fromisoformat(str(d)).date()
            except Exception:
                continue
        if isinstance(d, _dt.datetime):
            d = d.date()
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        buckets.setdefault(key, []).append(r["amount"])
    return buckets


def _classify(
    delta_pct: float,
    current_rate: float | None,
    mean_90d: float | None,
    sample_size: int,
    confidence: float,
) -> str:
    """Apply state classification rules."""
    # URGENT requires sample + confidence threshold
    if (
        delta_pct >= 3.0
        and sample_size >= _MIN_SAMPLE
        and confidence >= 0.7
    ):
        return "URGENT"
    if delta_pct <= -3.0:
        return "DECLINING"
    if (
        current_rate is not None
        and mean_90d is not None
        and mean_90d > 0
        and current_rate < mean_90d * 0.95
    ):
        return "COMPETITIVE"
    return "STABLE"


def _analyze_from_rows(pol: str, destination: str, rows: list[dict]) -> dict:
    """Core analyzer — pure function on pre-fetched rate rows."""
    if not rows:
        return _empty_result(pol, destination, reason="empty_query")

    sample_size = len(rows)
    amounts = [r["amount"] for r in rows]

    # Buckets by ISO week
    buckets = _bucket_by_iso_week(rows)
    week_keys = sorted(buckets.keys())
    weekly_medians = [_median(buckets[k]) for k in week_keys]

    # Current = last week median ; prev = second-last week
    current_rate = weekly_medians[-1] if weekly_medians else None
    prev_rate = weekly_medians[-2] if len(weekly_medians) >= 2 else None

    delta_pct = 0.0
    if current_rate is not None and prev_rate is not None and prev_rate > 0:
        delta_pct = round((current_rate - prev_rate) / prev_rate * 100.0, 2)

    mean_90d = _mean(amounts)
    std_90d = _std(amounts)
    # Confidence = 1 - coefficient of variation, clipped to [0, 1]
    if mean_90d > 0:
        confidence = 1.0 - (std_90d / mean_90d)
        confidence = max(0.0, min(1.0, confidence))
    else:
        confidence = 0.0

    # Forecast next week = linear regression over last 4 weekly medians
    last4 = weekly_medians[-4:] if len(weekly_medians) >= 2 else weekly_medians
    forecast = _linear_forecast(last4) if len(last4) >= 2 else None

    # Small-sample fallback: if not enough rows, treat as STABLE
    if sample_size < _MIN_SAMPLE:
        state = "DECLINING" if delta_pct <= -3.0 else "STABLE"
    else:
        state = _classify(delta_pct, current_rate, mean_90d, sample_size, confidence)

    return {
        "state": state,
        "delta_pct": delta_pct,
        "current_rate_40hq": round(current_rate, 2) if current_rate is not None else None,
        "prev_rate_40hq": round(prev_rate, 2) if prev_rate is not None else None,
        "mean_90d": round(mean_90d, 2) if mean_90d else None,
        "forecast_next_week": round(forecast, 2) if forecast is not None else None,
        "confidence": round(confidence, 3),
        "sample_size": sample_size,
        "pol": pol.upper(),
        "destination": destination.upper(),
        "reason": "ok",
        "updated_at": time.time(),
    }


def analyze_lane(pol: str, destination: str) -> dict:
    """
    Analyze a single (pol, destination) lane.

    Returns a dict with keys: state, delta_pct, current_rate_40hq, prev_rate_40hq,
    mean_90d, forecast_next_week, confidence, sample_size.

    Cached 30 minutes per (pol, dest).
    On any failure → STABLE fallback (never raises).
    """
    if not pol or not destination:
        return _empty_result(pol or "", destination or "", reason="bad_args")

    key = (pol.strip().upper(), destination.strip().upper())
    now = time.time()

    # Cache lookup
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            ts, payload = hit
            if now - ts < _CACHE_TTL_SEC:
                return dict(payload)  # return copy

    # Testing hook: allow injecting synthetic rows via env or module attr
    rows = _fetch_rows(key[0], key[1])
    try:
        result = _analyze_from_rows(key[0], key[1], rows)
    except Exception as e:
        log.exception("[market] analyze failure: %s", e)
        result = _empty_result(key[0], key[1], reason=f"exception:{e}")

    with _cache_lock:
        _cache[key] = (now, result)
    return dict(result)


# ── Fetch indirection for testability ─────────────────────────────────────────

def _fetch_rows(pol: str, destination: str) -> list[dict]:
    """Indirection layer — tests monkeypatch this to inject synthetic data."""
    return _run_duckdb_query(pol, destination)


def clear_cache() -> None:
    """Clear in-memory cache — useful for tests / admin ops."""
    with _cache_lock:
        _cache.clear()
