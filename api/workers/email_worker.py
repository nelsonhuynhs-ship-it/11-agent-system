# -*- coding: utf-8 -*-
"""
email_worker.py — Scheduled Email Scan + Sync Worker
======================================================
Runs email scanning on a configurable schedule.
Phase 1: APScheduler in-process (current).
Phase 2+: Celery beat for distributed scheduling.

Integrates with:
- email_scanner.py (Outlook COM scan)
- email_event_engine.py (sync email → shipment state)
- event_bus.py (publishes email.scanned, email.synced events)
"""
import logging
import os
import sys
import threading
from datetime import datetime
from typing import Optional

log = logging.getLogger("nelson.workers.email")

# Ensure api dir is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_bus import bus, Event

# Configuration
SCAN_INTERVAL_MINUTES = int(os.environ.get("EMAIL_SCAN_INTERVAL", "15"))
ENABLED = os.environ.get("EMAIL_WORKER_ENABLED", "true").lower() == "true"


class EmailWorker:
    """
    Background worker that scans Outlook emails and syncs to shipment state.

    Schedule: Every SCAN_INTERVAL_MINUTES (default 15).
    Can also be triggered manually via API.
    """

    def __init__(self):
        self._scheduler = None
        self._last_run: Optional[datetime] = None
        self._last_result: dict = {}
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Start the scheduled email worker."""
        if not ENABLED:
            log.info("Email worker DISABLED (set EMAIL_WORKER_ENABLED=true to enable)")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                self.run_scan_and_sync,
                'interval',
                minutes=SCAN_INTERVAL_MINUTES,
                id='email_scan',
                name='Email Scan + Sync',
                max_instances=1,
                misfire_grace_time=120,
            )
            self._scheduler.start()
            log.info("Email worker started — scanning every %d minutes", SCAN_INTERVAL_MINUTES)
        except ImportError:
            log.warning("APScheduler not installed — email worker will not auto-scan. "
                        "Install with: pip install apscheduler")
        except Exception as e:
            log.error("Failed to start email worker: %s", e)

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            log.info("Email worker stopped")

    def run_scan_and_sync(self) -> dict:
        """Execute one scan+sync cycle."""
        if not self._lock.acquire(blocking=False):
            log.warning("Email worker already running, skipping")
            return {"skipped": True}

        try:
            self._running = True
            result = {"started_at": datetime.now().isoformat()}

            # Step 1: Scan Outlook
            scan_result = self._scan_emails()
            result["scan"] = scan_result

            # Step 2: Sync to shipment state
            if scan_result.get("ok"):
                sync_result = self._sync_shipments()
                result["sync"] = sync_result
            else:
                result["sync"] = {"skipped": True, "reason": "scan failed"}

            result["completed_at"] = datetime.now().isoformat()
            self._last_run = datetime.now()
            self._last_result = result
            return result

        except Exception as e:
            log.error("Email worker cycle failed: %s", e)
            return {"error": str(e)}
        finally:
            self._running = False
            self._lock.release()

    def _scan_emails(self) -> dict:
        """Run email scanner (Outlook COM)."""
        try:
            from email_scanner import run_scan
            result = run_scan(quick=True)

            bus.publish(Event(
                type="email.scanned",
                payload={
                    "ok": result.get("ok", False),
                    "count": result.get("total_processed", 0),
                    "new": result.get("new_entries", 0),
                },
                source="worker",
            ))
            return result

        except ImportError:
            log.warning("email_scanner not available")
            return {"ok": False, "error": "email_scanner not installed"}
        except Exception as e:
            log.error("Email scan failed: %s", e)
            return {"ok": False, "error": str(e)}

    def _sync_shipments(self) -> dict:
        """Sync email data to shipment state."""
        try:
            from email_event_engine import sync_email_dataset
            stats = sync_email_dataset()

            bus.publish(Event(
                type="email.synced",
                payload={
                    "matched": stats.get("matched", 0),
                    "new_shipments": stats.get("new_shipments", 0),
                    "stage_changes": stats.get("stage_changes", 0),
                },
                source="worker",
            ))
            return stats

        except ImportError:
            log.warning("email_event_engine not available")
            return {"ok": False, "error": "email_event_engine not installed"}
        except Exception as e:
            log.error("Email sync failed: %s", e)
            return {"ok": False, "error": str(e)}

    @property
    def status(self) -> dict:
        """Worker status for monitoring."""
        return {
            "enabled": ENABLED,
            "interval_minutes": SCAN_INTERVAL_MINUTES,
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_result": self._last_result,
            "scheduler_running": bool(self._scheduler and self._scheduler.running),
        }


# Singleton
email_worker = EmailWorker()
