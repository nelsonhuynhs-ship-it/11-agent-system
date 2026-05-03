"""
queue_worker_outlook.py — Background thread worker for Outlook COM queue.
Polls outlook_queue.db via queue_store.pop_one() and sends via Outlook COM.
Start via: python -m email_engine.queue_worker_outlook
Or import + call start_worker() from rotation_engine.py
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
import sys
from pathlib import Path

_repo = str(Path(__file__).parent.parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)

import pythoncom
import win32com.client

from email_engine.queue_store import pop_one, mark_sent, mark_failed, kill_switch_active

log = logging.getLogger(__name__)

WORKER_ID = f"outlook-worker-{uuid.uuid4().hex[:8]}"
INTERVAL_SEC = 5


class OutlookSender:
    """Thread-safe Outlook COM sender with single App instance."""

    def __init__(self):
        pythoncom.CoInitialize()
        self._app = None

    def _get_app(self):
        if self._app is None:
            self._app = win32com.client.Dispatch("Outlook.Application")
        return self._app

    def send(self, to: str, subject: str, html_body: str) -> bool:
        try:
            ol = self._get_app()
            m = ol.CreateItem(0)
            m.To = to
            m.Subject = subject
            m.HTMLBody = html_body
            m.Send()
            log.info("[%s] SENT %s", WORKER_ID, to)
            return True
        except Exception as e:
            log.error("[%s] SEND FAILED %s: %s", WORKER_ID, to, e)
            return False


def run_once(sender: OutlookSender) -> int:
    """Pop one job from queue and send. Returns 1 if sent, 0 if no job."""
    if kill_switch_active():
        log.warning("[%s] KILL_SWITCH active — sleeping %ds", WORKER_ID, INTERVAL_SEC)
        time.sleep(INTERVAL_SEC)
        return 0

    job = pop_one(WORKER_ID)
    if job is None:
        return 0

    email = job.get("cnee_email", "")
    subject = job.get("subject", "(no subject)")
    html_body = job.get("html_body", "")

    ok = sender.send(email, subject, html_body)
    if ok:
        mark_sent(job["id"])
    else:
        mark_failed(job["id"], "Outlook COM send failed")
    return 1


def worker_loop():
    """Main worker loop — run until interrupted."""
    sender = OutlookSender()
    log.info("[%s] Outlook queue worker started", WORKER_ID)
    while True:
        try:
            count = run_once(sender)
            if count == 0:
                time.sleep(INTERVAL_SEC)
        except Exception as e:
            log.error("[%s] Worker loop error: %s", WORKER_ID, e)
            time.sleep(INTERVAL_SEC)


_worker_thread: threading.Thread | None = None


def start_worker() -> None:
    """Start worker in background thread. Idempotent — safe to call multiple times."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(
            target=worker_loop,
            daemon=True,
            name="outlook-queue-worker",
        )
        _worker_thread.start()
        log.info("[%s] Outlook queue worker thread started", WORKER_ID)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=f"[%(asctime)s] %(levelname)-8s [{WORKER_ID}] %(message)s",
        datefmt="%H:%M:%S",
    )
    worker_loop()