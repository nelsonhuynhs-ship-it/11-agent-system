"""
run_rotation_trigger.py — Daily Rotation Trigger Script
========================================================
Called by daily-rotation-trigger.bat at 08:00 Mon-Fri via Task Scheduler.
Builds daily plan + queues emails via Smart Send Window.
"""

import logging
import sys
from pathlib import Path

# Ensure project root on path
_PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            _PROJECT / "email_engine" / "logs" / "rotation.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("rotation_trigger")


def main() -> int:
    try:
        from email_engine.core.rotation_engine import build_daily_plan, queue_to_outlook_worker
    except ImportError as exc:
        log.error("Import failed: %s", exc)
        return 1

    try:
        plan = build_daily_plan()
    except FileNotFoundError as exc:
        log.error("Master file missing: %s", exc)
        return 1
    except Exception as exc:
        log.error("build_daily_plan failed: %s", exc)
        return 1

    if plan.get("skipped_reason"):
        log.info("Rotation skipped: %s", plan["skipped_reason"])
        return 0

    try:
        queued = queue_to_outlook_worker(plan)
        log.info(
            "ROTATION DONE: date=%s target=%d actual=%d queued=%d",
            plan.get("date"), plan.get("target_total"), plan.get("actual_total"), queued
        )
        return 0
    except Exception as exc:
        log.error("queue_to_outlook_worker failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
