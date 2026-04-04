# -*- coding: utf-8 -*-
"""
duckdb_engine.py — DuckDB-based Freight Rate Engine
=====================================================
High-performance rate queries via DuckDB (replaces Pandas read_parquet).
Designed for the Nelson Freight Intelligence Platform.

Usage:
    from db.duckdb_engine import FreightDB
    db = FreightDB("Pricing_Engine/data/Cleaned_Master_History.parquet")
    envelope = db.get_market_envelope("HCM", "LAX", "40HQ", days=30)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

__all__ = ["FreightDB"]


def _safe_days(days: int) -> int:
    """Validate days parameter — prevent SQL injection via int cast."""
    d = int(days)
    if d < 1:
        d = 1
    if d > 3650:
        d = 3650
    return d


class FreightDB:
    """
    DuckDB-backed freight rate database.

    All queries run against Parquet directly via DuckDB — no Pandas read_parquet().
    DuckDB pushes filters into the Parquet scan for minimal memory usage.

    Note: DuckDB does not support parameterized INTERVAL literals,
    so `days` is validated via _safe_days() and embedded directly.
    All string params use ? placeholders for safety.
    """

    def __init__(self, parquet_path: str | Path):
        self._path = Path(parquet_path)
        if not self._path.exists():
            log.warning("Parquet file not found: %s — FreightDB queries will return empty", self._path)
        self._parquet = self._path.as_posix()
        log.info("FreightDB initialized: %s (exists=%s)", self._parquet, self._path.exists())

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Create a fresh connection (thread-safe)."""
        return duckdb.connect()

    def _date_filter(self, days: int) -> str:
        """Build safe date filter clause."""
        d = _safe_days(days)
        return f"Eff >= CURRENT_DATE - INTERVAL '{d}' DAY"

    # ──────────────────────────────────────────────────────────────────────
    # 1. query_rates
    # ──────────────────────────────────────────────────────────────────────

    def query_rates(
        self,
        pol: Optional[str] = None,
        pod: Optional[str] = None,
        container_type: Optional[str] = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """
        Query active rates with filters. Returns a DataFrame.

        Filters on:
          - Eff >= (today - days)
          - Charge_Name = 'Total Ocean Freight'
          - Amount > 0
          - Optional: POL, POD (LIKE), Container_Type
        """
        conditions = [
            self._date_filter(days),
            "Charge_Name = 'Total Ocean Freight'",
            "Amount > 0",
        ]
        params: list = []

        if pol:
            conditions.append("UPPER(TRIM(POL)) = UPPER(?)")
            params.append(pol)
        if pod:
            conditions.append("UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'")
            params.append(pod)
        if container_type:
            conditions.append("UPPER(Container_Type) = UPPER(?)")
            params.append(container_type)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT POL, POD, Place, Carrier, Container_Type,
                   Amount, Eff, Exp, Rate_Type, Note, Commodity, Contract
            FROM read_parquet('{self._parquet}')
            WHERE {where}
            ORDER BY Amount ASC
        """

        con = self._connect()
        try:
            return con.execute(sql, params).fetchdf()
        finally:
            con.close()

    # ──────────────────────────────────────────────────────────────────────
    # 2. get_route_median
    # ──────────────────────────────────────────────────────────────────────

    def get_route_median(
        self,
        pol: str,
        pod: str,
        container_type: str = "40HQ",
        days: int = 30,
    ) -> float:
        """Return the median ocean freight amount for a route."""
        sql = f"""
            SELECT MEDIAN(Amount)
            FROM read_parquet('{self._parquet}')
            WHERE UPPER(TRIM(POL)) = UPPER(?)
              AND UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'
              AND UPPER(Container_Type) = UPPER(?)
              AND {self._date_filter(days)}
              AND Charge_Name = 'Total Ocean Freight'
              AND Amount > 0
        """
        con = self._connect()
        try:
            result = con.execute(sql, [pol, pod, container_type]).fetchone()
            return float(result[0]) if result and result[0] is not None else 0.0
        finally:
            con.close()

    # ──────────────────────────────────────────────────────────────────────
    # 3. get_market_envelope
    # ──────────────────────────────────────────────────────────────────────

    def get_market_envelope(
        self,
        pol: str,
        pod: str,
        container_type: str = "40HQ",
        days: int = 30,
    ) -> dict:
        """
        Market envelope: p2.5 / mean / p97.5 for a route.

        Returns:
            {
                "market_low": p2.5,
                "market_avg": mean,
                "market_high": p97.5,
                "data_points": N,
                "carriers": N,
                "median": median,
            }
        """
        sql = f"""
            SELECT
                PERCENTILE_CONT(0.025) WITHIN GROUP (ORDER BY Amount) AS p2_5,
                AVG(Amount) AS mean_amt,
                PERCENTILE_CONT(0.975) WITHIN GROUP (ORDER BY Amount) AS p97_5,
                MEDIAN(Amount) AS median_amt,
                COUNT(*) AS data_points,
                COUNT(DISTINCT Carrier) AS carrier_count
            FROM read_parquet('{self._parquet}')
            WHERE UPPER(TRIM(POL)) = UPPER(?)
              AND UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'
              AND UPPER(Container_Type) = UPPER(?)
              AND {self._date_filter(days)}
              AND Charge_Name = 'Total Ocean Freight'
              AND Amount > 0
        """
        con = self._connect()
        try:
            row = con.execute(sql, [pol, pod, container_type]).fetchone()
        finally:
            con.close()

        if not row or row[4] == 0:
            return {
                "market_low": 0, "market_avg": 0, "market_high": 0,
                "data_points": 0, "carriers": 0, "median": 0,
            }

        return {
            "market_low": round(float(row[0]), 0),
            "market_avg": round(float(row[1]), 0),
            "market_high": round(float(row[2]), 0),
            "median": round(float(row[3]), 0),
            "data_points": int(row[4]),
            "carriers": int(row[5]),
        }

    # ──────────────────────────────────────────────────────────────────────
    # 4. get_carrier_list
    # ──────────────────────────────────────────────────────────────────────

    def get_carrier_list(
        self,
        pol: Optional[str] = None,
        pod: Optional[str] = None,
    ) -> list[str]:
        """Return distinct carriers, optionally filtered by route."""
        conditions = [
            "Carrier IS NOT NULL",
            "Charge_Name = 'Total Ocean Freight'",
        ]
        params: list = []

        if pol:
            conditions.append("UPPER(TRIM(POL)) = UPPER(?)")
            params.append(pol)
        if pod:
            conditions.append("UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'")
            params.append(pod)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT DISTINCT Carrier
            FROM read_parquet('{self._parquet}')
            WHERE {where}
            ORDER BY Carrier
        """
        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
            return [r[0] for r in rows]
        finally:
            con.close()

    # ──────────────────────────────────────────────────────────────────────
    # 5. get_rate_stats
    # ──────────────────────────────────────────────────────────────────────

    def get_rate_stats(
        self,
        pol: str,
        pod: str,
        container_type: str = "40HQ",
        days: int = 30,
    ) -> dict:
        """
        Combined stats for API consumption.

        Returns envelope + additional stats (min, max, std_dev).
        """
        sql = f"""
            SELECT
                MIN(Amount) AS min_amt,
                MAX(Amount) AS max_amt,
                AVG(Amount) AS avg_amt,
                MEDIAN(Amount) AS median_amt,
                STDDEV(Amount) AS std_amt,
                PERCENTILE_CONT(0.025) WITHIN GROUP (ORDER BY Amount) AS p2_5,
                PERCENTILE_CONT(0.975) WITHIN GROUP (ORDER BY Amount) AS p97_5,
                COUNT(*) AS data_points,
                COUNT(DISTINCT Carrier) AS carrier_count,
                MIN(Eff) AS earliest_eff,
                MAX(Eff) AS latest_eff
            FROM read_parquet('{self._parquet}')
            WHERE UPPER(TRIM(POL)) = UPPER(?)
              AND UPPER(CAST(POD AS VARCHAR)) LIKE '%' || UPPER(?) || '%'
              AND UPPER(Container_Type) = UPPER(?)
              AND {self._date_filter(days)}
              AND Charge_Name = 'Total Ocean Freight'
              AND Amount > 0
        """
        con = self._connect()
        try:
            row = con.execute(sql, [pol, pod, container_type]).fetchone()
        finally:
            con.close()

        if not row or row[7] == 0:
            return {"error": "No data found", "data_points": 0}

        return {
            "min": round(float(row[0]), 0),
            "max": round(float(row[1]), 0),
            "avg": round(float(row[2]), 0),
            "median": round(float(row[3]), 0),
            "std_dev": round(float(row[4]), 2) if row[4] else 0,
            "market_low": round(float(row[5]), 0),
            "market_high": round(float(row[6]), 0),
            "data_points": int(row[7]),
            "carriers": int(row[8]),
            "earliest_date": str(row[9]),
            "latest_date": str(row[10]),
        }
