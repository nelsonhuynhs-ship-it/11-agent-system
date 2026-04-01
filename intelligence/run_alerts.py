# -*- coding: utf-8 -*-
"""
run_alerts.py — Standalone scheduled anomaly check
=====================================================
Backup trigger if rate_importer pipeline doesn't run.
Designed for: VPS cron (weekdays 08:00) or Windows Task Scheduler.

Usage:
    python -m intelligence.run_alerts
    # Or via cron: 0 8 * * 1-5 cd /home/nelson && python -m intelligence.run_alerts
"""

import sys
import os
import logging

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Running scheduled anomaly check...")
    try:
        from intelligence.alert_dispatcher import run_alert_cycle
        result = run_alert_cycle()
        logger.info("Result: %s", result)
    except Exception as e:
        logger.error("Alert cycle failed: %s", e, exc_info=True)
    logger.info("Done.")


if __name__ == "__main__":
    main()
