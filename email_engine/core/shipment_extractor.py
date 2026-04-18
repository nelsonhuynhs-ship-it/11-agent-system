# -*- coding: utf-8 -*-
"""
shipment_extractor.py — Shipment Brain Orchestrator  v1.0
==========================================================
Scans customer email folders, extracts shipment lifecycle events via
MiniMax LLM, and dual-writes to DuckDB + Markdown vault.

Folder convention (from Customer Sort output):
    DIRECT/{customer_id}/*.msg
    FW/{customer_id}/*.msg

Usage:
    python -m email_engine.core.shipment_extractor            # run all folders
    python -m email_engine.core.shipment_extractor --dry-run  # no writes
    python -m email_engine.core.shipment_extractor --folder FW/PANDA
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

# ─── stdlib-only imports first; heavy imports below after path setup ──────────
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from email_engine.core import llm_client
from email_engine.core import shipment_db
from email_engine.core import vault_writer

# ─── Logging ──────────────────────────────────────────────────────────────────
_LOG_FILE = _REPO_ROOT / "email_engine" / "logs" / "shipment_extractor.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("shipment_extractor")
log.setLevel(logging.INFO)

_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_fh = logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
_fh.setFormatter(_fmt)
log.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
log.addHandler(_sh)

# ─── Config ───────────────────────────────────────────────────────────────────
# Root folder where Customer Sort writes organised emails
_DEFAULT_SORTED_ROOT = _REPO_ROOT / "email_engine" / "sorted"

# Confidence threshold below which we still write but flag for review
CONFIDENCE_THRESHOLD = 0.7

# Batch commit size: write DB every N events
BATCH_SIZE = 10


def _sorted_root() -> Path:
    env = os.environ.get("SORTED_EMAIL_ROOT")
    if env:
        return Path(env)
    return _DEFAULT_SORTED_ROOT


def _msg_id_from_path(msg_path: Path) -> str:
    """
    Generate a stable dedup ID from file path + mtime.
    Used when Outlook entry_id is not available (plain .msg files).
    """
    stat = msg_path.stat() if msg_path.exists() else None
    mtime = str(stat.st_mtime) if stat else "0"
    raw = f"{msg_path.name}:{mtime}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _parse_msg_file(msg_path: Path) -> Optional[dict]:
    """
    Parse a .msg file into a simple dict with subject + body.

    Strategy (graceful degradation):
      1. Try extract-msg library (best, preserves encoding)
      2. Fall back to reading raw text lines from file
      3. Return None only if file is unreadable

    Returns dict with keys: subject, body, sender, date, filename
    """
    result: dict = {
        "subject": "",
        "body": "",
        "sender": "",
        "date": None,
        "filename": msg_path.name,
        "path": str(msg_path),
    }

    # Attempt 1: extract-msg
    try:
        import extract_msg  # type: ignore
        msg = extract_msg.openMsg(str(msg_path))
        result["subject"] = getattr(msg, "subject", "") or ""
        result["body"] = getattr(msg, "body", "") or ""
        result["sender"] = getattr(msg, "sender", "") or ""
        date_obj = getattr(msg, "date", None)
        result["date"] = date_obj.isoformat() if date_obj else None
        msg.close()
        return result
    except ImportError:
        log.debug("extract-msg not installed — falling back to raw read for %s", msg_path.name)
    except Exception as exc:
        log.debug("extract-msg failed for %s: %s", msg_path.name, exc)

    # Attempt 2: raw UTF-8 / latin-1 read (plain text .eml or .txt disguised as .msg)
    for enc in ("utf-8", "latin-1"):
        try:
            raw = msg_path.read_text(encoding=enc, errors="replace")
            # Naively grab subject from headers if present
            lines = raw.splitlines()
            for line in lines[:30]:
                if line.lower().startswith("subject:"):
                    result["subject"] = line[8:].strip()
                elif line.lower().startswith("from:"):
                    result["sender"] = line[5:].strip()
                elif line.lower().startswith("date:"):
                    result["date"] = line[5:].strip()
            result["body"] = raw
            return result
        except Exception:
            continue

    log.warning("Could not parse %s — skipping", msg_path)
    return None


def _build_email_text(parsed: dict) -> str:
    """Combine subject + body into a single string for LLM."""
    subject = parsed.get("subject", "")
    body = (parsed.get("body", "") or "")[:3500]  # cap body to save tokens
    return f"Subject: {subject}\n\n{body}"


def scan_customer_folders(
    sorted_root: Path | None = None,
    only_folder: Optional[str] = None,
) -> Iterator[tuple[str, Path]]:
    """
    Yield (customer_id, msg_path) for every .msg file under
    DIRECT/{customer_id}/ and FW/{customer_id}/ subfolders.

    Args:
        sorted_root:  root dir of sorted emails (defaults to _sorted_root())
        only_folder:  restrict to single sub-path e.g. "FW/PANDA"

    Yields:
        (customer_id, Path to .msg file)
    """
    root = sorted_root or _sorted_root()

    if not root.exists():
        log.warning("Sorted root does not exist: %s — nothing to scan", root)
        return

    prefixes = ["DIRECT", "FW"]

    for prefix in prefixes:
        prefix_dir = root / prefix
        if not prefix_dir.exists():
            continue

        for customer_dir in sorted(prefix_dir.iterdir()):
            if not customer_dir.is_dir():
                continue

            rel_path = f"{prefix}/{customer_dir.name}"
            if only_folder and only_folder != rel_path:
                continue

            customer_id = customer_dir.name

            for msg_file in sorted(customer_dir.glob("*.msg")):
                yield customer_id, msg_file


def process_msg(
    msg_path: Path,
    customer_id: str,
    dry_run: bool = False,
) -> Optional[dict]:
    """
    Core processing unit: parse one .msg file → LLM extract → dual-write.

    Args:
        msg_path:    absolute path to .msg file
        customer_id: folder name used as customer key
        dry_run:     if True, parse + LLM but skip all writes

    Returns:
        event_dict from LLM (or mock), or None if extraction failed / no event.
    """
    log.debug("Processing: %s / %s", customer_id, msg_path.name)

    # 1. Parse .msg
    parsed = _parse_msg_file(msg_path)
    if not parsed:
        return None

    email_text = _build_email_text(parsed)
    source_msg_id = _msg_id_from_path(msg_path)

    # 2. LLM extraction
    result = llm_client.extract(email_text)

    if result is None:
        log.warning("LLM extraction failed for %s — skipping", msg_path.name)
        return None

    shipment_ref = result.get("shipment_ref")
    if not shipment_ref:
        log.debug("No shipment event detected in %s", msg_path.name)
        return result  # {"shipment_ref": None} — valid no-event response

    event_type = result.get("event_type", "")
    confidence: float = float(result.get("confidence", 1.0))
    risk_flag: bool = bool(result.get("risk_flag", False))
    event_date_raw = result.get("event_date")

    event_date: Optional[datetime] = None
    if event_date_raw:
        try:
            from datetime import timezone
            event_date = datetime.fromisoformat(str(event_date_raw).replace("Z", "+00:00"))
        except ValueError:
            log.debug("Could not parse event_date '%s'", event_date_raw)

    if confidence < CONFIDENCE_THRESHOLD:
        log.info(
            "Low confidence (%.2f) for %s / %s — flagging risk",
            confidence, shipment_ref, event_type,
        )
        risk_flag = True

    if dry_run:
        log.info(
            "[DRY-RUN] Would write: %s | %s | %s | conf=%.2f | risk=%s",
            customer_id, shipment_ref, event_type, confidence, risk_flag,
        )
        return result

    # 3. DB write — upsert shipment header first
    try:
        shipment_db.upsert_shipment(
            shipment_id=shipment_ref,
            customer_id=customer_id,
        )
        inserted = shipment_db.insert_event(
            shipment_id=shipment_ref,
            event_type=event_type,
            event_date=event_date,
            source_msg_id=source_msg_id,
            source_path=str(msg_path),
            raw_excerpt=result.get("excerpt"),
            confidence=confidence,
            flagged_risk=risk_flag,
        )
        if not inserted:
            log.debug("DB: duplicate event skipped for %s / %s", shipment_ref, event_type)
    except Exception as exc:
        log.error("DB write failed for %s / %s: %s", shipment_ref, event_type, exc)

    # 4. Vault write
    try:
        vault_writer.append_event(
            customer_id=customer_id,
            shipment_ref=shipment_ref,
            event_dict=result,
            source_msg_id=source_msg_id,
            source_filename=msg_path.name,
        )
    except Exception as exc:
        log.error("Vault write failed for %s / %s: %s", shipment_ref, event_type, exc)

    return result


def run_extraction(
    only_folder: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Main extraction loop over all customer folders.

    Returns stats dict: {total, processed, events_found, errors}
    """
    llm_client.reset_token_counter()
    stats: dict[str, int] = {
        "total": 0, "processed": 0, "events_found": 0, "errors": 0
    }
    batch_count = 0

    log.info(
        "Starting shipment extraction (dry_run=%s, folder=%s)",
        dry_run, only_folder or "all",
    )

    for customer_id, msg_path in scan_customer_folders(only_folder=only_folder):
        stats["total"] += 1
        try:
            result = process_msg(msg_path, customer_id, dry_run=dry_run)
            stats["processed"] += 1
            if result and result.get("shipment_ref"):
                stats["events_found"] += 1
            batch_count += 1
            if batch_count >= BATCH_SIZE:
                log.info(
                    "Progress: %d processed, %d events found so far",
                    stats["processed"], stats["events_found"],
                )
                batch_count = 0
        except Exception as exc:
            stats["errors"] += 1
            log.error("Unhandled error processing %s: %s", msg_path, exc)

    usage = llm_client.get_token_usage()
    log.info(
        "Extraction complete — total=%d processed=%d events=%d errors=%d | "
        "LLM requests=%d tokens_in=%d tokens_out=%d",
        stats["total"], stats["processed"], stats["events_found"], stats["errors"],
        usage["requests"], usage["tokens_in"], usage["tokens_out"],
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shipment Brain Extractor — scan emails, extract lifecycle events"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse + LLM extract but skip all DB and vault writes",
    )
    parser.add_argument(
        "--folder", metavar="PREFIX/CUSTOMER",
        help="Restrict to single folder, e.g. FW/PANDA",
    )
    parser.add_argument(
        "--init-db", action="store_true",
        help="Initialise DB schema and exit",
    )
    args = parser.parse_args()

    if args.init_db:
        shipment_db.init_db()
        log.info("DB init complete.")
        return

    # Always ensure schema exists before running
    shipment_db.init_db()

    stats = run_extraction(only_folder=args.folder, dry_run=args.dry_run)
    print(
        f"\nDone: {stats['total']} files scanned | "
        f"{stats['events_found']} events found | "
        f"{stats['errors']} errors"
    )


if __name__ == "__main__":
    main()
