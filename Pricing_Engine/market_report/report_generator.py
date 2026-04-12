"""Orchestrator — loads all 4 streams and renders DOCX output."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .backtest_logger import log_backtest, read_recent_backtest
from .capacity_loader import load_capacity
from .catalyst_crawler import crawl_catalysts, rank_catalysts
from .costing_extractor import extract_costing, group_costing_by_lane
from .paths import ensure_dirs, prev_iso_week, report_docx
from .schemas import CostingItem, ForecastScenario
from .template.weekly_report_template import build_report

log = logging.getLogger(__name__)


def generate_weekly_report(
    prev_week: str,
    next_week: str,
    output_path: Optional[Path] = None,
    override_catalysts=None,
    override_costing=None,
) -> Path:
    """Full pipeline: load streams → build scenarios → render DOCX.

    Parameters:
        prev_week, next_week: ISO week strings like "2026-W14", "2026-W15"
        output_path: override file path (default derived from paths module)
        override_catalysts: optional pre-built list (used by tests)
        override_costing: optional pre-built list (used by tests)

    Returns path to written DOCX.
    """
    ensure_dirs()

    # 1. Costing — auto from parquet (or override for tests)
    costing = override_costing if override_costing is not None else extract_costing(prev_week)
    log.info("Costing: %d items loaded for %s", len(costing), prev_week)

    # 2. Capacity — from team-filled xlsx
    capacity = load_capacity(prev_week)
    log.info("Capacity: %d signals loaded for %s", len(capacity), prev_week)

    # 3. Catalysts — from yaml seed (or override)
    raw_catalysts = (
        override_catalysts
        if override_catalysts is not None
        else crawl_catalysts(prev_week)
    )
    catalysts = rank_catalysts(raw_catalysts)
    log.info("Catalysts: %d loaded for %s", len(catalysts), prev_week)

    # 4. Forecast — derive simple scenarios from costing (base = min price per lane)
    forecast = _build_baseline_scenarios(costing, next_week)
    log.info("Forecast: %d scenarios for %s", len(forecast), next_week)

    # 5. Backtest — compare previous-previous week if available
    backtest_rows = log_backtest(prev_iso_week(prev_week))
    if not backtest_rows:
        # Fallback: show any recent backtest rows
        backtest_rows = read_recent_backtest(n=3)

    # 6. Render
    output_path = output_path or report_docx(prev_week, next_week)
    build_report(
        prev_week=prev_week,
        next_week=next_week,
        costing=costing,
        capacity=capacity,
        catalysts=catalysts,
        forecast=forecast,
        backtest_rows=backtest_rows,
        output_path=output_path,
    )
    log.info("Report written: %s", output_path)
    return output_path


def _build_baseline_scenarios(
    costing: list[CostingItem],
    next_week: str,
    container: str = "40HQ",
) -> list[ForecastScenario]:
    """Simple scenario builder: base = lane min price, ±15% band.

    This is a placeholder until the real forecast engine is wired in.
    Keeps the pipeline demo-able end-to-end without depending on ML models.
    """
    by_lane = group_costing_by_lane(costing)
    scenarios: list[ForecastScenario] = []
    for lane, items in by_lane.items():
        if not items:
            continue
        prices = [i.price for i in items]
        base = min(prices)
        low = base * 0.85
        high = base * 1.15
        scenarios.append(
            ForecastScenario(
                lane=lane,  # type: ignore[arg-type]
                week=next_week,
                container=container,
                base_case=round(base, 2),
                low_case=round(low, 2),
                high_case=round(high, 2),
                confidence=0.5,
                rationale=f"Baseline from {len(items)} costing rows (±15% band).",
                model_version="baseline-v1",
            )
        )
    return scenarios
