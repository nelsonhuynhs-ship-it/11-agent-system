"""CLI entry point for weekly market report generation.

Usage:
    python -m Pricing_Engine.market_report.cli --week current
    python -m Pricing_Engine.market_report.cli --week 2026-W15
    python -m Pricing_Engine.market_report.cli --prev 2026-W14 --next 2026-W15
"""
from __future__ import annotations

import argparse
import logging
import sys

from .paths import current_iso_week, next_iso_week
from .report_generator import generate_weekly_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate 4C weekly market report")
    parser.add_argument(
        "--week",
        default="current",
        help="Week to report on, e.g. '2026-W14' or 'current' (default)",
    )
    parser.add_argument(
        "--prev",
        help="Explicit previous-week override (skips --week)",
    )
    parser.add_argument(
        "--next",
        help="Explicit next-week override (skips --week)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.prev and args.next:
        prev_week = args.prev
        next_week = args.next
    else:
        if args.week == "current":
            prev_week = current_iso_week()
        else:
            prev_week = args.week
        next_week = next_iso_week(prev_week)

    print(f"Generating report: prev={prev_week} -> predict={next_week}")
    path = generate_weekly_report(prev_week, next_week)
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
