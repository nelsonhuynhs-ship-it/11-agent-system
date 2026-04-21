# -*- coding: utf-8 -*-
"""
booking_pool_writer.py — Sidecar JSONL writer for Booking Pool (Phase 2).

Appends booking lifecycle events to a local JSONL sidecar file.
VBA "Sync Pool" button reads this file and flushes rows into the
Booking Pool Excel sheet.

Public API:
    append_booking_event(event_type, booking_data, mail_id, sender, received)

Event types:
    booking_received   — new booking mail parsed (Direct or Keep Space)
    keep_space_request — Keep Space mail (no BKG yet)
    si_update          — SI cutoff / CY close update
    release_to_customer— booking released from HOLDING to named customer
    si_request_48h     — OPS requesting SI 48h before cutoff

Dedup: same (event_type, bkg_no, mail_id) triplet within last 100 lines → skip.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent           # email_engine/core/
PROJECT_ROOT = BASE_DIR.parent                 # email_engine/
REPO_ROOT    = PROJECT_ROOT.parent             # Engine_test/

# Import schema constant (Pricing_Engine is a sibling of email_engine)
sys.path.insert(0, str(REPO_ROOT / "Pricing_Engine"))
try:
    from booking_pool_schema import POOL_SIDECAR_PATH
except ImportError:
    # Fallback — keeps module importable without Pricing_Engine on path
    POOL_SIDECAR_PATH = "email_engine/data/booking_pool_state.jsonl"

# Resolve absolute sidecar path
SIDECAR: Path = REPO_ROOT / POOL_SIDECAR_PATH

# ─── Logging ──────────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ─── Dedup window ─────────────────────────────────────────────────────────────
_DEDUP_WINDOW = 100   # lines to check for duplicate triplet

# ─── Valid event types ────────────────────────────────────────────────────────
_VALID_EVENTS = {
    "booking_received",
    "keep_space_request",
    "si_update",
    "release_to_customer",
    "si_request_48h",
}


# ==============================================================================
# Internal helpers
# ==============================================================================

def _load_recent_lines(n: int) -> list[dict]:
    """Read last *n* lines from sidecar JSONL. Returns list of parsed dicts."""
    if not SIDECAR.exists():
        return []
    lines: list[str] = []
    try:
        with SIDECAR.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        log.warning("booking_pool_writer: cannot read sidecar: %s", exc)
        return []

    recent: list[dict] = []
    for raw in lines[-n:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            recent.append(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return recent


def _is_duplicate(event_type: str, bkg_no: str, mail_id: str) -> bool:
    """Return True if this (event_type, bkg_no, mail_id) triplet already exists
    within the last _DEDUP_WINDOW lines of the sidecar."""
    if not mail_id:
        return False   # no mail_id → can't dedup, always allow
    recent = _load_recent_lines(_DEDUP_WINDOW)
    for rec in recent:
        if (
            rec.get("event") == event_type
            and rec.get("bkg") == bkg_no
            and rec.get("mail_id") == mail_id
        ):
            return True
    return False


def _format_received(received: Optional[datetime]) -> str:
    """Convert received datetime to ISO string, or empty string."""
    if received is None:
        return ""
    try:
        return received.isoformat(timespec="minutes")
    except Exception:
        return str(received)


def _build_record(
    event_type: str,
    booking_data: dict,
    mail_id: str,
    sender: str,
    received: Optional[datetime],
) -> dict:
    """Build the JSONL record for a given event type."""
    bkg = booking_data.get("bkg_no", "")
    received_str = _format_received(received)

    if event_type == "booking_received":
        return {
            "event":           event_type,
            "bkg":             bkg,
            "customer":        booking_data.get("customer", ""),
            "pol":             booking_data.get("pol", ""),
            "pod":             booking_data.get("pod", ""),
            "final_dest":      booking_data.get("final_dest", ""),
            "container":       booking_data.get("container", ""),
            "qty":             booking_data.get("qty", 1),
            "etd":             booking_data.get("etd", ""),
            "eta":             booking_data.get("eta", ""),
            "carrier":         booking_data.get("carrier", ""),
            "vessel":          booking_data.get("vessel", ""),
            "voyage":          booking_data.get("voyage", ""),
            "po_number":       booking_data.get("po_number", ""),
            "si_cutoff":       booking_data.get("si_cutoff", ""),
            "cy_close":        booking_data.get("cy_close", ""),
            "is_keep_space":   booking_data.get("is_keep_space", False),
            "mail_id":         mail_id,
            "sender":          sender,
            "received":        received_str,
            "synced_to_pool":  False,
        }

    if event_type == "keep_space_request":
        return {
            "event":           event_type,
            "bkg":             "",   # no BKG at this stage
            "customer":        booking_data.get("customer", ""),
            "pol":             booking_data.get("pol", ""),
            "pod":             booking_data.get("pod", ""),
            "container":       booking_data.get("container", ""),
            "qty":             booking_data.get("qty", 1),
            "carrier":         booking_data.get("carrier", ""),
            "is_keep_space":   True,
            "mail_id":         mail_id,
            "sender":          sender,
            "received":        received_str,
            "synced_to_pool":  False,
        }

    if event_type == "si_update":
        return {
            "event":     event_type,
            "bkg":       bkg,
            "si_cutoff": booking_data.get("si_cutoff", ""),
            "cy_close":  booking_data.get("cy_close", ""),
            "mail_id":   mail_id,
            "received":  received_str,
        }

    if event_type == "release_to_customer":
        return {
            "event":    event_type,
            "bkg":      bkg,
            "customer": booking_data.get("customer", ""),
            "mail_id":  mail_id,
            "received": received_str,
        }

    if event_type == "si_request_48h":
        return {
            "event":      event_type,
            "bkg":        bkg,
            "hours_left": booking_data.get("hours_left", ""),
            "mail_id":    mail_id,
            "received":   received_str,
        }

    # Fallback for unknown event types — include all booking_data fields
    record = {"event": event_type, "bkg": bkg, "mail_id": mail_id,
              "received": received_str}
    record.update(booking_data)
    return record


# ==============================================================================
# Public API
# ==============================================================================

def append_booking_event(
    event_type: str,
    booking_data: dict,
    mail_id: str,
    sender: str = "",
    received: Optional[datetime] = None,
) -> bool:
    """Append a booking lifecycle event to the sidecar JSONL.

    Returns True if the record was written, False if skipped (dedup).

    Parameters
    ----------
    event_type   : one of _VALID_EVENTS
    booking_data : parser output (parse_booking_subject / parse_booking_body)
                   or a partial update dict for si_update / release_to_customer
    mail_id      : Outlook EntryID — used for dedup and audit trail
    sender       : SMTP address of the sender
    received     : datetime when mail was received (for timestamp in record)
    """
    if event_type not in _VALID_EVENTS:
        log.warning("booking_pool_writer: unknown event_type '%s' — writing anyway", event_type)

    bkg_no = booking_data.get("bkg_no", "")

    # Dedup check
    if _is_duplicate(event_type, bkg_no, mail_id):
        log.debug(
            "booking_pool_writer: dedup skip — event=%s bkg=%s mail_id=%.16s",
            event_type, bkg_no, mail_id
        )
        return False

    # Build record
    record = _build_record(event_type, booking_data, mail_id, sender, received)

    # Ensure sidecar directory exists
    try:
        SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error("booking_pool_writer: cannot create sidecar dir: %s", exc)
        return False

    # Append to JSONL
    try:
        with SIDECAR.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.error("booking_pool_writer: write failed: %s", exc)
        return False

    log.info(
        "booking_pool_writer: wrote event=%s bkg=%s mail_id=%.16s",
        event_type, bkg_no, mail_id
    )
    return True
