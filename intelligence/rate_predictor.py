# -*- coding: utf-8 -*-
"""
Rate Predictor v0.1 — Simple moving average baseline.
=====================================================
No external ML library. Uses Parquet + pandas for trend analysis.
Upgrade to linear regression or Gemini-assisted forecast later.

Source: Pricing_Engine/Backup_parquet/Cleaned_Master_History.parquet (9.87M rows)
Columns: POL, POD, Place, Carrier, Commodity, Contract, Eff, Exp, Note,
         Group Rate, Charge_Name, Container_Type, Amount, Source_File, Rate_Type

Usage:
    from intelligence.rate_predictor import RatePredictor
    predictor = RatePredictor()
    print(predictor.predict_next_week("HPH", "LAX", "40HQ"))
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Ensure repo root in sys.path for shared imports
_repo_root = str(Path(__file__).parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

log = logging.getLogger(__name__)

# Parquet data sources (OneDrive primary, old repo path as backup)
PARQUET_PATHS = [
    sp.PARQUET_FILE,
    sp.CODE_DIR / "Pricing_Engine" / "Backup_parquet" / "Cleaned_Master_History.parquet",
]


class RatePredictor:
    """Rate trend analysis using Parquet history — 4-week moving average."""

    def __init__(self):
        self._df = None

    def _load(self) -> pd.DataFrame:
        """Lazy-load Parquet data."""
        if self._df is not None:
            return self._df

        for path in PARQUET_PATHS:
            if path.exists():
                try:
                    self._df = pd.read_parquet(path)
                    log.info("[RatePredictor] Loaded %d rows from %s",
                             len(self._df), path.name)
                    return self._df
                except Exception as e:
                    log.warning("[RatePredictor] Failed to load %s: %s", path, e)

        log.error("[RatePredictor] No Parquet file found")
        return pd.DataFrame()

    def predict_next_week(self, pol: str, pod: str,
                          container: str = "40HQ",
                          days_history: int = 90) -> dict:
        """
        Simple approach: group rates by Eff date, compute 4-week moving average.
        Returns: {predicted_rate, confidence, trend, data_points}
        
        Args:
            pol: Port of Loading (e.g. "HPH", "HCM")
            pod: Port of Discharge or Place — matches both POD and Place columns
            container: Container type (e.g. "40HQ", "20GP")
            days_history: How many days back to look
        """
        df = self._load()
        if df.empty:
            return {"error": "no_data", "route": f"{pol}→{pod}/{container}"}

        # Filter by route — match POD or Place
        pol_upper = pol.upper()
        pod_upper = pod.upper()
        mask = (
            (df["POL"].str.upper().str.contains(pol_upper, na=False)) &
            (
                df["POD"].str.upper().str.contains(pod_upper, na=False) |
                df["Place"].str.upper().str.contains(pod_upper, na=False)
            ) &
            (df["Container_Type"].str.upper() == container.upper())
        )

        # Time filter using Eff date
        cutoff = (datetime.now() - timedelta(days=days_history)).strftime("%Y-%m-%d")
        if "Eff" in df.columns:
            mask &= df["Eff"].astype(str) >= cutoff

        filtered = df[mask].copy()

        if len(filtered) < 5:
            return {
                "error": "insufficient_data",
                "route": f"{pol}→{pod}/{container}",
                "min_required": 5,
                "found": len(filtered),
            }

        # Group by Eff date, take average Amount
        filtered["Eff_date"] = pd.to_datetime(filtered["Eff"], errors="coerce")
        filtered = filtered.dropna(subset=["Eff_date", "Amount"])
        filtered = filtered[filtered["Amount"] > 0]

        daily = (filtered.groupby(filtered["Eff_date"].dt.date)["Amount"]
                 .mean().sort_index())

        if len(daily) < 3:
            return {
                "error": "insufficient_date_groups",
                "route": f"{pol}→{pod}/{container}",
                "found": len(daily),
            }

        rates = daily.values.tolist()

        # Split into recent (last 4 weeks) vs older (4 weeks before)
        mid = len(rates) // 2
        recent = rates[mid:]
        older = rates[:mid]

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older) if older else avg_recent

        # Trend calculation
        trend_pct = ((avg_recent - avg_older) / avg_older * 100
                     if avg_older else 0)
        trend = ("rising" if trend_pct > 3
                 else "falling" if trend_pct < -3
                 else "stable")

        # Naive next-week forecast: recent avg + half the trend momentum
        predicted = avg_recent * (1 + (trend_pct / 200))

        # Confidence based on data density
        confidence = ("high" if len(daily) >= 20
                      else "medium" if len(daily) >= 8
                      else "low")

        # Top carriers in this route
        top_carriers = (filtered["Carrier"].value_counts().head(3)
                        .to_dict())

        return {
            "route": f"{pol}→{pod}/{container}",
            "predicted_rate": round(predicted, 0),
            "current_avg": round(avg_recent, 0),
            "trend": trend,
            "trend_pct": round(trend_pct, 1),
            "confidence": confidence,
            "data_points": len(daily),
            "date_range": f"{daily.index[0]}→{daily.index[-1]}",
            "top_carriers": top_carriers,
        }

    def top_routes_forecast(self) -> list[dict]:
        """Forecast Nelson's core routes."""
        ROUTES = [
            ("HPH", "LAX", "40HQ"),
            ("HPH", "LAX", "20GP"),
            ("HCM", "LAX", "40HQ"),
            ("HCM", "NYC", "40HQ"),
            ("HPH", "NYC", "40HQ"),
            ("HCM", "DENVER", "40HQ"),
            ("HCM", "CHICAGO", "40HQ"),
        ]
        results = []
        for pol, pod, cont in ROUTES:
            forecast = self.predict_next_week(pol, pod, cont)
            if "error" not in forecast:
                results.append(forecast)
            else:
                log.debug("[RatePredictor] Skip %s→%s: %s",
                          pol, pod, forecast.get("error"))
        return results

    def format_forecast_text(self, forecasts: list[dict] = None) -> str:
        """Format forecasts for Telegram/briefing output."""
        if forecasts is None:
            forecasts = self.top_routes_forecast()

        if not forecasts:
            return "📊 Rate Forecast: insufficient data for core routes"

        lines = ["📊 *Rate Forecast (next week):*"]
        for f in forecasts:
            arrow = "📈" if f["trend"] == "rising" else "📉" if f["trend"] == "falling" else "➡️"
            lines.append(
                f"  {arrow} {f['route']}: ${f['predicted_rate']:.0f} "
                f"({f['trend']} {f['trend_pct']:+.1f}%) "
                f"[{f['confidence']}]"
            )
        return "\n".join(lines)


# ── Standalone test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    predictor = RatePredictor()

    # Test single route
    result = predictor.predict_next_week("HPH", "LAX", "40HQ")
    print("\n=== HPH→LAX/40HQ ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Test all core routes
    print("\n=== Core Routes Forecast ===")
    print(predictor.format_forecast_text())
