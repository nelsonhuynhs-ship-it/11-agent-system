# -*- coding: utf-8 -*-
"""
anomaly_detector.py — Rate Anomaly Detection Engine
======================================================
Detects pricing anomalies by comparing quoted rates against route medians.
Uses Drewry-standard thresholds: warning >15%, critical >30%.

Bidirectional: flags BOTH overpriced and underpriced rates.
All data access via FreightDB (DuckDB) — no direct Parquet reads.

Consumers:
  - Telegram bot alerts (2.1.2)
  - Mentee monitoring (2.1.3)
  - WebApp dashboard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.duckdb_engine import FreightDB

log = logging.getLogger(__name__)

__all__ = ["AnomalyDetector", "AnomalyResult"]


@dataclass
class AnomalyResult:
    """Result of a single rate anomaly check."""
    is_anomaly: bool
    deviation_pct: float       # e.g. 35.2 (positive = above median, negative = below)
    route_median: float
    quoted_rate: float
    severity: str              # "normal" | "warning" | "critical"
    message: str               # Human-readable alert text
    carrier: str
    pol: str
    pod: str
    container_type: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Message Templates ────────────────────────────────────────────────────────
_MSG_NORMAL = (
    "✅ {carrier} {pol}→{pod}/{ct} ${rate:,.0f} — "
    "within normal range (median ${median:,.0f})"
)
_MSG_WARNING = (
    "⚠️ {carrier} {pol}→{pod}/{ct} ${rate:,.0f} — "
    "{dev:+.1f}% from median ${median:,.0f}"
)
_MSG_CRITICAL = (
    "🚨 {carrier} {pol}→{pod}/{ct} ${rate:,.0f} — "
    "{dev:+.1f}% from median ${median:,.0f} — REVIEW REQUIRED"
)
_MSG_NO_DATA = (
    "ℹ️ {carrier} {pol}→{pod}/{ct} ${rate:,.0f} — "
    "insufficient data for anomaly check"
)


class AnomalyDetector:
    """
    Rate anomaly detection using Drewry-standard thresholds.

    Compares quoted rates against 30-day route median across ALL carriers.
    Flags deviations in both directions (overpriced and underpriced).
    """

    THRESHOLD_WARNING = 0.15   # 15% deviation
    THRESHOLD_CRITICAL = 0.30  # 30% deviation

    def __init__(self, freight_db: FreightDB):
        self.db = freight_db

    def check_rate(
        self,
        carrier: str,
        pol: str,
        pod: str,
        container_type: str,
        quoted_rate: float,
        days: int = 30,
    ) -> AnomalyResult:
        """
        Check a single rate against the route median.

        Returns AnomalyResult with severity classification:
          - "normal": deviation < 15%
          - "warning": 15% ≤ deviation < 30%
          - "critical": deviation ≥ 30%

        Bidirectional: works for both above and below median.
        """
        # Edge case: invalid quoted_rate
        if quoted_rate <= 0:
            return AnomalyResult(
                is_anomaly=False, deviation_pct=0.0,
                route_median=0.0, quoted_rate=quoted_rate,
                severity="normal",
                message=_MSG_NO_DATA.format(
                    carrier=carrier, pol=pol, pod=pod,
                    ct=container_type, rate=quoted_rate,
                ),
                carrier=carrier, pol=pol, pod=pod,
                container_type=container_type,
            )

        # Get route median (ALL carriers on this route, last N days)
        route_median = self.db.get_route_median(
            pol=pol, pod=pod, container_type=container_type, days=days,
        )

        # Edge case: no data / zero median
        if route_median <= 0:
            return AnomalyResult(
                is_anomaly=False, deviation_pct=0.0,
                route_median=0.0, quoted_rate=quoted_rate,
                severity="normal",
                message=_MSG_NO_DATA.format(
                    carrier=carrier, pol=pol, pod=pod,
                    ct=container_type, rate=quoted_rate,
                ),
                carrier=carrier, pol=pol, pod=pod,
                container_type=container_type,
            )

        # Calculate deviation
        deviation_pct = ((quoted_rate - route_median) / route_median) * 100
        abs_deviation = abs(deviation_pct) / 100  # as fraction

        # Classify severity
        if abs_deviation >= self.THRESHOLD_CRITICAL:
            severity = "critical"
            is_anomaly = True
            msg = _MSG_CRITICAL.format(
                carrier=carrier, pol=pol, pod=pod,
                ct=container_type, rate=quoted_rate,
                dev=deviation_pct, median=route_median,
            )
        elif abs_deviation >= self.THRESHOLD_WARNING:
            severity = "warning"
            is_anomaly = True
            msg = _MSG_WARNING.format(
                carrier=carrier, pol=pol, pod=pod,
                ct=container_type, rate=quoted_rate,
                dev=deviation_pct, median=route_median,
            )
        else:
            severity = "normal"
            is_anomaly = False
            msg = _MSG_NORMAL.format(
                carrier=carrier, pol=pol, pod=pod,
                ct=container_type, rate=quoted_rate,
                median=route_median,
            )

        log.debug(
            "Anomaly check: %s %s→%s/%s $%.0f vs median $%.0f = %.1f%% [%s]",
            carrier, pol, pod, container_type,
            quoted_rate, route_median, deviation_pct, severity,
        )

        return AnomalyResult(
            is_anomaly=is_anomaly,
            deviation_pct=round(deviation_pct, 1),
            route_median=route_median,
            quoted_rate=quoted_rate,
            severity=severity,
            message=msg,
            carrier=carrier,
            pol=pol,
            pod=pod,
            container_type=container_type,
        )

    def check_batch(self, quotes: list[dict], days: int = 30) -> list[AnomalyResult]:
        """
        Check multiple quotes for anomalies.

        Each dict in quotes should have:
            carrier, pol, pod, container_type, quoted_rate

        Returns list of AnomalyResult in same order as input.
        """
        results = []
        for q in quotes:
            result = self.check_rate(
                carrier=q["carrier"],
                pol=q["pol"],
                pod=q["pod"],
                container_type=q.get("container_type", "40HQ"),
                quoted_rate=q["quoted_rate"],
                days=days,
            )
            results.append(result)
        return results

    def get_route_context(
        self,
        pol: str,
        pod: str,
        container_type: str = "40HQ",
        days: int = 30,
    ) -> dict:
        """
        Get full market context for a route.

        Returns:
            {
                "median": float,
                "envelope": {"market_low", "market_avg", "market_high", ...},
                "carrier_count": int,
                "data_points": int,
                "thresholds": {"warning_above", "warning_below", "critical_above", "critical_below"},
            }
        """
        median = self.db.get_route_median(pol, pod, container_type, days=days)
        envelope = self.db.get_market_envelope(pol, pod, container_type, days=days)

        thresholds = {}
        if median > 0:
            thresholds = {
                "warning_above": round(median * (1 + self.THRESHOLD_WARNING), 0),
                "warning_below": round(median * (1 - self.THRESHOLD_WARNING), 0),
                "critical_above": round(median * (1 + self.THRESHOLD_CRITICAL), 0),
                "critical_below": round(median * (1 - self.THRESHOLD_CRITICAL), 0),
            }

        return {
            "pol": pol,
            "pod": pod,
            "container_type": container_type,
            "days": days,
            "median": median,
            "envelope": envelope,
            "carrier_count": envelope.get("carriers", 0),
            "data_points": envelope.get("data_points", 0),
            "thresholds": thresholds,
        }
