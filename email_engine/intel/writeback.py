"""
writeback.py — Debounced write-back to cnee_master_v2.xlsx (Phase 02)
======================================================================
Per-event TIER / ACTION / counter updates accumulate in memory; we flush to
the OneDrive xlsx every 5 minutes OR when buffer >= 50 dirty CNEEs.

Design:
- Append updates via update_master(cnee_email, fields) — fast, non-blocking
- Background thread (start_background_flusher) wakes every flush_interval_s
- flush() also called automatically when dirty buffer hits flush_size
- Atomic writeback: pandas read -> patch DataFrame -> openpyxl write to temp
  -> os.replace
- File-lock guard: if Excel has the file open (we can detect by attempting
  exclusive open on a sentinel), retry once after 30s, otherwise keep buffer
  in memory for next interval
- Weekly snapshot: cnee_master_v2.YYYYMMDD.xlsx in same folder

Special field: EMAIL_QUALITY_SCORE_DELTA in fields applies a relative delta
to the existing column instead of an absolute set.

Public API:
    update_master(cnee_email, fields)   -> bool        # buffered
    flush()                              -> int         # force-write now
    start_background_flusher()           -> None        # daemon thread
    stop_background_flusher()            -> None
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — overridable via env / set_master_path()
# ---------------------------------------------------------------------------

DEFAULT_MASTER_PATH = os.environ.get(
    "INTEL_MASTER_V2_PATH",
    r"D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx",
)
EMAIL_COLUMN = "EMAIL"

FLUSH_INTERVAL_SECONDS = 300        # 5 minutes
FLUSH_BUFFER_SIZE = 50              # >= 50 dirty CNEEs triggers immediate flush
LOCK_RETRY_DELAY_SECONDS = 30
WEEKLY_BACKUP_WEEKDAY = 6           # Sunday (Mon=0..Sun=6)

# Internal state
_master_path: str = DEFAULT_MASTER_PATH
_buffer: dict[str, dict[str, Any]] = {}   # cnee_email -> merged fields
_buffer_lock = threading.Lock()
_flusher_thread: threading.Thread | None = None
_flusher_stop = threading.Event()
_last_backup_iso: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_master_path(path: str) -> None:
    """Override target xlsx path (used by tests)."""
    global _master_path
    _master_path = path


def update_master(cnee_email: str, fields: dict[str, Any]) -> bool:
    """Buffer an update for `cnee_email`. Triggers flush if buffer >= FLUSH_BUFFER_SIZE.
    Returns True if accepted into buffer. fields keys map to xlsx columns."""
    if not cnee_email:
        return False
    cnee = cnee_email.strip().lower()
    with _buffer_lock:
        existing = _buffer.get(cnee, {})
        # Sum quality score deltas instead of overwriting
        merged = _merge_fields(existing, fields)
        _buffer[cnee] = merged
        size = len(_buffer)
    if size >= FLUSH_BUFFER_SIZE:
        # spawn one-shot flush so caller stays non-blocking
        threading.Thread(target=_flush_until_drained,
                         name="intel-flush-burst", daemon=True).start()
    return True


def _flush_until_drained() -> None:
    """Flush in a loop until buffer is empty. Protects against a writer
    landing one more update while a burst flush is mid-write — the second
    pass picks it up immediately instead of waiting for the next interval."""
    for _ in range(5):
        n = flush()
        if n == 0:
            return
        with _buffer_lock:
            empty = len(_buffer) == 0
        if empty:
            return


def flush() -> int:
    """Force-write buffered updates to the xlsx. Returns rows touched.

    Returns 0 if buffer empty, file locked, or master file missing."""
    with _buffer_lock:
        snapshot = dict(_buffer)
        _buffer.clear()
    if not snapshot:
        return 0

    path = Path(_master_path)
    if not path.exists():
        logger.warning("master v2 not found at %s — re-buffering %d updates",
                       path, len(snapshot))
        _restore_buffer(snapshot)
        return 0

    if _is_locked(path):
        logger.info("master v2 locked, sleeping %ds and retrying once",
                    LOCK_RETRY_DELAY_SECONDS)
        time.sleep(LOCK_RETRY_DELAY_SECONDS)
        if _is_locked(path):
            logger.warning("master v2 still locked — re-buffering %d updates",
                           len(snapshot))
            _restore_buffer(snapshot)
            return 0

    try:
        touched = _apply_updates(path, snapshot)
    except Exception:
        logger.exception("flush failed — re-buffering %d updates",
                         len(snapshot))
        _restore_buffer(snapshot)
        return 0

    _maybe_weekly_backup(path)
    return touched


def start_background_flusher() -> None:
    """Launch daemon thread that calls flush() every FLUSH_INTERVAL_SECONDS."""
    global _flusher_thread
    if _flusher_thread and _flusher_thread.is_alive():
        return
    _flusher_stop.clear()
    _flusher_thread = threading.Thread(
        target=_flusher_loop, name="intel-flusher", daemon=True
    )
    _flusher_thread.start()


def stop_background_flusher() -> None:
    _flusher_stop.set()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _flusher_loop() -> None:
    while not _flusher_stop.wait(FLUSH_INTERVAL_SECONDS):
        try:
            flush()
        except Exception:
            logger.exception("background flush errored, continuing")


def _restore_buffer(snapshot: dict[str, dict[str, Any]]) -> None:
    """Put unflushed updates back so the next pass tries again."""
    with _buffer_lock:
        for k, v in snapshot.items():
            _buffer[k] = _merge_fields(_buffer.get(k, {}), v)


def _merge_fields(existing: dict[str, Any],
                  incoming: dict[str, Any]) -> dict[str, Any]:
    out = dict(existing)
    for k, v in incoming.items():
        if k == "EMAIL_QUALITY_SCORE_DELTA":
            out[k] = (out.get(k) or 0) + (v or 0)
        else:
            out[k] = v
    return out


def _is_locked(path: Path) -> bool:
    """Detect Excel file lock on Windows by checking the ~$ owner sentinel
    and by attempting an exclusive open. Best-effort, never raises."""
    sentinel = path.with_name("~$" + path.name)
    if sentinel.exists():
        return True
    try:
        with open(path, "rb+"):
            pass
    except OSError:
        return True
    return False


def _apply_updates(path: Path, updates: dict[str, dict[str, Any]]) -> int:
    """Read xlsx, patch matching rows, atomic write. Returns rows updated."""
    # Lazy import — pandas/openpyxl only needed at flush time
    import pandas as pd

    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    if EMAIL_COLUMN not in df.columns:
        raise RuntimeError(f"missing {EMAIL_COLUMN} column in {path.name}")

    # Build lower-case email index once
    email_series = df[EMAIL_COLUMN].astype(str).str.strip().str.lower()
    email_to_idx: dict[str, int] = {}
    for idx, em in enumerate(email_series):
        if em and em not in email_to_idx:
            email_to_idx[em] = idx

    touched = 0
    for cnee, fields in updates.items():
        idx = email_to_idx.get(cnee)
        if idx is None:
            logger.debug("writeback: %s not found in master v2", cnee)
            continue
        for col, val in fields.items():
            if col == "EMAIL_QUALITY_SCORE_DELTA":
                _apply_delta(df, idx, "EMAIL_QUALITY_SCORE", val)
                continue
            if col not in df.columns:
                logger.warning("writeback: column %s not in master v2 — skipping",
                               col)
                continue
            df.at[idx, col] = val
        touched += 1

    if not touched:
        return 0

    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_excel(tmp, index=False, engine="openpyxl")
    os.replace(tmp, path)
    logger.info("writeback flushed %d CNEEs to %s", touched, path.name)
    return touched


def _apply_delta(df, idx: int, col: str, delta: float) -> None:
    if col not in df.columns:
        return
    cur = df.at[idx, col]
    try:
        cur_n = float(cur) if cur is not None and str(cur) != "" else 0.0
    except (TypeError, ValueError):
        cur_n = 0.0
    df.at[idx, col] = cur_n + float(delta or 0)


def _maybe_weekly_backup(path: Path) -> None:
    """Snapshot the master file once per Sunday."""
    global _last_backup_iso
    today = datetime.utcnow().date()
    if today.weekday() != WEEKLY_BACKUP_WEEKDAY:
        return
    iso = today.isoformat()
    if _last_backup_iso == iso:
        return
    backup = path.with_name(
        f"{path.stem}.{today.strftime('%Y%m%d')}{path.suffix}"
    )
    try:
        shutil.copy2(path, backup)
        _last_backup_iso = iso
        logger.info("master v2 weekly backup -> %s", backup.name)
    except OSError:
        logger.exception("weekly backup failed")
