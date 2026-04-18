"""
outlook_queue_worker.py — FAST mode batch sender (Phase 01)
============================================================
ThreadPoolExecutor pulls jobs directly from local SQLite queue
(`queue_store`) and sends via Outlook COM. Each thread:
  - holds its own Outlook Dispatch (thread-local)
  - rate-limits at 60 sends/min/worker
  - respects KILL_SWITCH.flag (drains gracefully)
  - dry-run mode skips real Send (logs WOULD SEND)

Usage:
  python outlook_queue_worker.py --workers 3 --loop
  python outlook_queue_worker.py --workers 5 --loop --dry-run
  python outlook_queue_worker.py --workers 1            # one pass

Design notes:
  - Worker imports queue_store directly (no HTTP) for atomic SQLite ops.
  - --api flag kept for back-compat / future remote mode (no-op today).
  - Outlook security prompts: must be disabled in Trust Center once.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# Ensure root dir on sys.path so `email_engine` resolves as package
# even when this script is run from within email_engine/ folder (bat file does).
_THIS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _THIS_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

# Local import — atomic SQLite operations
from email_engine import queue_store

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_API = "http://localhost:8100"
DEFAULT_WORKERS = 3
RATE_LIMIT_PER_MIN = 60          # max sends per worker per rolling 60s
KILL_SWITCH_SLEEP = 30           # seconds when kill switch is active
EMPTY_QUEUE_SLEEP = 2            # seconds when no job available
LOG_EVERY_N = 10                 # progress log cadence per worker
STUCK_RESET_INTERVAL = 300       # seconds between periodic stuck-job sweeps
STUCK_AGE_MIN = 10               # reset jobs stuck in 'sending' longer than this

# Public base URL for open-tracking pixel. Must be reachable from recipient's
# mail client. Default localhost works when Nelson tests against his own inbox
# on the same machine. For production (email sent to real recipients), set:
#   export NELSON_TRACK_BASE_URL=http://14.225.207.145:8100  (VPS)
TRACK_BASE_URL = os.environ.get(
    "NELSON_TRACK_BASE_URL",
    "http://localhost:8100",
).rstrip("/")

_last_stuck_sweep = 0.0
_stuck_sweep_lock = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("worker")

# Per-thread Outlook dispatch (lazy) + rate-limit state
_thread_local = threading.local()
_shutdown = threading.Event()


# ---------------------------------------------------------------------------
# Outlook COM helpers (per-thread)
# ---------------------------------------------------------------------------

def _get_outlook():
    """Lazy per-thread Outlook Application. Returns None in dry-run mode
    or when win32com unavailable (lets tests import without Outlook)."""
    if getattr(_thread_local, "outlook", None) is not None:
        return _thread_local.outlook
    try:
        import pythoncom  # noqa: WPS433 — local import on purpose
        import win32com.client  # noqa: WPS433
        pythoncom.CoInitialize()
        _thread_local.outlook = win32com.client.Dispatch("Outlook.Application")
        return _thread_local.outlook
    except Exception as exc:  # pragma: no cover — Outlook optional in tests
        log.error("Cannot init Outlook on thread: %s", exc)
        _thread_local.outlook = None
        return None


_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png"
)
_LOGO_CID = "pudonglogo"  # must match <img src="cid:pudonglogo"> in signature


def _attach_inline_logo(mail) -> None:
    """Attach Pudong logo as inline CID attachment so <img src='cid:pudonglogo'>
    in the signature renders. Silently no-ops if file missing.

    Outlook COM trick:
      1. mail.Attachments.Add(path) attaches the file
      2. PR_ATTACH_CONTENT_ID (0x3712001F) = CID — sets inline reference
      3. PR_ATTACHMENT_HIDDEN (0x7FFE000B) = True hides it from recipient's
         attachment list (purely decorative)
    """
    if not os.path.exists(_LOGO_PATH):
        return
    try:
        att = mail.Attachments.Add(_LOGO_PATH)
        pa = att.PropertyAccessor
        # PR_ATTACH_CONTENT_ID
        pa.SetProperty(
            "http://schemas.microsoft.com/mapi/proptag/0x3712001F",
            _LOGO_CID,
        )
        # PR_ATTACHMENT_HIDDEN
        pa.SetProperty(
            "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B",
            True,
        )
    except Exception as exc:
        log.warning("inline logo attach failed: %s", exc)


def _inject_tracking_pixel(html_body: str, job_id: int) -> str:
    """Append invisible 1x1 open-tracking pixel right before </body> (or EOF).
    Pixel URL: {TRACK_BASE_URL}/t/o/{job_id}.gif — server records the open.
    No-op if html_body already contains the pixel (defensive against retries)."""
    if not html_body or not job_id:
        return html_body
    marker = f"/t/o/{job_id}.gif"
    if marker in html_body:
        return html_body
    pixel = (
        f'<img src="{TRACK_BASE_URL}/t/o/{job_id}.gif" '
        f'width="1" height="1" border="0" alt="" '
        f'style="display:block;width:1px;height:1px;border:0;">'
    )
    # Prefer to insert before </body> so it's part of the document flow
    low = html_body.lower()
    idx = low.rfind("</body>")
    if idx >= 0:
        return html_body[:idx] + pixel + html_body[idx:]
    return html_body + pixel


def _send_via_outlook(job: dict[str, Any]) -> tuple[bool, str | None]:
    """Send single job via Outlook COM. Returns (success, error).

    If job.html_body references 'cid:pudonglogo', the logo file at
    assets/logo.png is attached inline so Outlook / recipient's mail
    client renders the brand logo in the signature.
    """
    outlook = _get_outlook()
    if outlook is None:
        return False, "Outlook unavailable"
    try:
        mail = outlook.CreateItem(0)  # olMailItem
        mail.To = job["cnee_email"]
        mail.Subject = job["subject"]

        html_body = job["html_body"] or ""
        # Inject open-tracking pixel (adds /t/o/{id}.gif beacon at end).
        html_body = _inject_tracking_pixel(html_body, job.get("id") or 0)
        # Only attach logo if signature actually references it
        if "cid:pudonglogo" in html_body.lower():
            mail.HTMLBody = html_body
            _attach_inline_logo(mail)
        else:
            mail.HTMLBody = html_body

        cc = job.get("cc")
        if cc:
            mail.CC = cc if isinstance(cc, str) else ";".join(cc)
        mail.Send()
        return True, None
    except Exception as exc:
        return False, str(exc)[:500]


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def _rate_limit_wait():
    """Block thread if it has sent >= RATE_LIMIT_PER_MIN in last 60s."""
    if not hasattr(_thread_local, "send_times"):
        _thread_local.send_times = deque()
    now = time.time()
    while _thread_local.send_times and now - _thread_local.send_times[0] > 60:
        _thread_local.send_times.popleft()
    if len(_thread_local.send_times) >= RATE_LIMIT_PER_MIN:
        wait = 60 - (now - _thread_local.send_times[0])
        if wait > 0:
            log.info("[%s] rate limit, sleep %.1fs", threading.get_ident(), wait)
            time.sleep(wait)
    _thread_local.send_times.append(time.time())


# ---------------------------------------------------------------------------
# Worker thread main loop
# ---------------------------------------------------------------------------

def worker_loop(worker_id: str, dry_run: bool, loop: bool) -> int:
    """Main loop for one worker thread. Returns count of processed jobs."""
    processed = 0
    log.info("[%s] worker started (dry_run=%s, loop=%s)",
             worker_id, dry_run, loop)

    while not _shutdown.is_set():
        # 0. Periodic stuck-job sweep (Outlook crash recovery while worker lives)
        global _last_stuck_sweep
        now_mono = time.monotonic()
        if now_mono - _last_stuck_sweep > STUCK_RESET_INTERVAL:
            if _stuck_sweep_lock.acquire(blocking=False):
                try:
                    if now_mono - _last_stuck_sweep > STUCK_RESET_INTERVAL:
                        n = queue_store.reset_stuck(STUCK_AGE_MIN)
                        if n:
                            log.warning("[%s] periodic sweep reset %d stuck job(s)",
                                        worker_id, n)
                        _last_stuck_sweep = now_mono
                finally:
                    _stuck_sweep_lock.release()

        # 1. Kill switch check
        if queue_store.kill_switch_active():
            log.warning("[%s] KILL_SWITCH active — sleeping %ds",
                        worker_id, KILL_SWITCH_SLEEP)
            if _shutdown.wait(KILL_SWITCH_SLEEP):
                break
            continue

        # 2. Pop next job
        try:
            job = queue_store.pop_one(worker_id)
        except Exception as exc:
            log.exception("[%s] pop_one failed: %s", worker_id, exc)
            if _shutdown.wait(EMPTY_QUEUE_SLEEP):
                break
            continue

        if job is None:
            if not loop:
                log.info("[%s] queue empty, exiting (no --loop)", worker_id)
                break
            if _shutdown.wait(EMPTY_QUEUE_SLEEP):
                break
            continue

        # 3. Rate limit + send
        _rate_limit_wait()

        if dry_run:
            log.info("[%s] [DRY RUN] WOULD SEND to %s — %s",
                     worker_id, job["cnee_email"], job["subject"][:60])
            queue_store.mark_sent(job["id"])
            success = True
        else:
            success, error = _send_via_outlook(job)
            if success:
                queue_store.mark_sent(job["id"])
                log.info("[%s] SENT id=%s to=%s",
                         worker_id, job["id"], job["cnee_email"])
            else:
                queue_store.mark_failed(job["id"], error or "unknown")
                log.error("[%s] FAIL id=%s to=%s err=%s",
                          worker_id, job["id"], job["cnee_email"], error)

        processed += 1
        if processed % LOG_EVERY_N == 0:
            rate = len(getattr(_thread_local, "send_times", []))
            log.info("[%s] processed %d, rate ~%d/min",
                     worker_id, processed, rate)

    log.info("[%s] worker stopped, total processed=%d", worker_id, processed)
    return processed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _install_signal_handlers():
    def _handler(signum, _frame):
        log.warning("Signal %s — initiating graceful shutdown", signum)
        _shutdown.set()
    try:
        signal.signal(signal.SIGINT, _handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError):
        # Not main thread on Windows — skip
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Nelson FAST email worker")
    parser.add_argument("--api", default=DEFAULT_API,
                        help="API base URL (reserved; not used in v1 SQLite mode)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Number of worker threads (default {DEFAULT_WORKERS})")
    parser.add_argument("--loop", action="store_true",
                        help="Keep polling forever (default: drain & exit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip Outlook send; log WOULD SEND only")
    parser.add_argument("--db", default=None,
                        help="SQLite path override (default email_engine/data/outlook_queue.db)")
    args = parser.parse_args(argv)

    queue_store.init_db(args.db)
    log.info("worker booting: workers=%d loop=%s dry_run=%s db=%s",
             args.workers, args.loop, args.dry_run, args.db or "default")

    # Reset stuck rows from prior crashed runs (>10 min)
    n_reset = queue_store.reset_stuck(10)
    if n_reset:
        log.info("reset %d stuck job(s) from prior run", n_reset)

    _install_signal_handlers()

    with ThreadPoolExecutor(max_workers=args.workers,
                            thread_name_prefix="nelson-worker") as ex:
        futures = [
            ex.submit(worker_loop, f"W{i+1}", args.dry_run, args.loop)
            for i in range(args.workers)
        ]
        try:
            total = sum(f.result() for f in futures)
        except KeyboardInterrupt:
            log.warning("KeyboardInterrupt — shutting down")
            _shutdown.set()
            total = sum(f.result() for f in futures if f.done())

    log.info("DONE — total processed across all workers: %d", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
