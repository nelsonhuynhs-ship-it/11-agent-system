"""Path resolver for Market Report 4C System.

Extends shared.paths without modifying it (main agent is editing that file).
All market-report data lives under OneDrive/pricing/market-reports/.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from shared.paths import PRICING_DATA

# Base directory for all market-report artifacts
MARKET_REPORTS_DIR = PRICING_DATA / "market-reports"

# Subdirectories
WEEKLY_DIR = MARKET_REPORTS_DIR / "weekly"
INPUTS_DIR = MARKET_REPORTS_DIR / "inputs"
TEMPLATES_DIR = MARKET_REPORTS_DIR / "templates"
STATE_DIR = MARKET_REPORTS_DIR / "state"

# Key files
BACKTEST_LOG = MARKET_REPORTS_DIR / "backtest-log.csv"
CATALYST_SOURCES_YAML = MARKET_REPORTS_DIR / "catalyst-sources.yaml"
CRAWLER_STATE = STATE_DIR / "crawler-state.json"

# Capacity input template
CAPACITY_TEMPLATE_XLSX = INPUTS_DIR / "capacity-template.xlsx"


def ensure_dirs() -> None:
    """Create all market-report directories if missing (idempotent)."""
    for d in (MARKET_REPORTS_DIR, WEEKLY_DIR, INPUTS_DIR, TEMPLATES_DIR, STATE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def week_dir(week: str) -> Path:
    """Get weekly subdirectory, e.g. `weekly/2026-W15/`. Auto-creates."""
    d = WEEKLY_DIR / week
    d.mkdir(parents=True, exist_ok=True)
    return d


def capacity_input_file(week: str) -> Path:
    """Team-filled capacity xlsx for a given week."""
    return INPUTS_DIR / f"capacity-{week}.xlsx"


def catalyst_seed_file(week: str) -> Path:
    """Manual yaml fallback for catalyst seeds when crawler is unavailable."""
    return INPUTS_DIR / f"catalysts-{week}.yaml"


def forecast_parquet(week: str) -> Path:
    """Stored forecast parquet for a given week (used by backtest)."""
    return week_dir(week) / f"{week}-forecast.parquet"


def report_docx(prev_week: str, next_week: str) -> Path:
    """Final DOCX artifact path."""
    return week_dir(prev_week) / f"report-{prev_week}-predict-{next_week}.docx"


def current_iso_week() -> str:
    """Return current ISO week as 'YYYY-WNN'."""
    today = date.today()
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def next_iso_week(week: str) -> str:
    """Given '2026-W15', return '2026-W16'. Handles year rollover roughly."""
    year_s, w_s = week.split("-W")
    year = int(year_s)
    w = int(w_s)
    if w >= 52:
        return f"{year + 1}-W01"
    return f"{year}-W{w + 1:02d}"


def prev_iso_week(week: str) -> str:
    """Given '2026-W15', return '2026-W14'. Rough year-rollover handling."""
    year_s, w_s = week.split("-W")
    year = int(year_s)
    w = int(w_s)
    if w <= 1:
        return f"{year - 1}-W52"
    return f"{year}-W{w - 1:02d}"
