# -*- coding: utf-8 -*-
from __future__ import annotations
import io, sys
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
outlook_scanner.py — Unified Outlook Scanner Orchestrator
=========================================================
One script runs 3 scan jobs, all controlled by scanner_rules.json.

Jobs:
  1. Mentee Classification  — Phân loại email Team Sunny (main.py)
  2. Pricing Import          — Scan Harry email → download → Parquet (rate_importer.py)
  3. Shipment Brain          — Track shipment lifecycle (shipment_brain.py)

Runs via Windows Task Scheduler every 30 minutes, 08:00-17:30.

Usage:
    python outlook_scanner.py              # run all enabled jobs
    python outlook_scanner.py --dry-run    # show what would run, no action
    python outlook_scanner.py --job mentee_classification   # run single job
"""


import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
RULES_FILE = SCRIPT_DIR / "scanner_rules.json"

_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

LOG_FILE       = sp.EMAIL_LOG_DIR / "outlook_scanner.log"
PRICING_ENGINE = sp.PRICING_CODE

# ── Logging ───────────────────────────────────────────────────────────────────
_fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")

_fh = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_fh, _sh])
log = logging.getLogger("outlook_scanner")


# ==============================================================================
# 1. LOAD RULES
# ==============================================================================

def load_rules(path: Path = RULES_FILE) -> dict:
    """Load scanner_rules.json."""
    if not path.exists():
        log.error("scanner_rules.json not found: %s", path)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# 2. TIME GUARD
# ==============================================================================

def within_schedule(schedule: dict) -> bool:
    """Check if current time is within the allowed schedule."""
    now = datetime.now().time()
    start = dtime(*map(int, schedule["start_time"].split(":")))
    end   = dtime(*map(int, schedule["end_time"].split(":")))
    if start <= now <= end:
        return True
    log.info("Outside schedule (%s – %s). Now: %s. Exiting.",
             schedule["start_time"], schedule["end_time"],
             now.strftime("%H:%M"))
    return False


# ==============================================================================
# 3. JOB RUNNERS
# ==============================================================================

def run_mentee_classification(config: dict, dry_run: bool = False) -> dict:
    """Run Team Sunny email classification (main.py)."""
    if dry_run:
        return {"status": "dry_run", "description": config["description"]}

    try:
        # Import main.py from same directory
        from main import main as mentee_main
        mentee_main()
        return {"status": "ok", "description": "Mentee classification completed"}
    except SystemExit:
        # main.py may call sys.exit() — that's OK
        return {"status": "ok", "note": "clean exit"}
    except Exception as e:
        log.error("[mentee] Error: %s", e)
        return {"status": "error", "error": str(e)}


def run_pricing_import(config: dict, dry_run: bool = False) -> dict:
    """Run Harry pricing email scan → download → import Parquet."""
    if dry_run:
        return {"status": "dry_run", "description": config["description"]}

    # Add Pricing_Engine to path so we can import rate_importer
    if str(PRICING_ENGINE) not in sys.path:
        sys.path.insert(0, str(PRICING_ENGINE))

    try:
        from rate_importer import run_full_import
        days = config.get("import_days", 1)
        result = run_full_import(days=days)

        # Extract key metrics for summary
        return {
            "status": "ok",
            "files_processed": result.get("files_processed", 0),
            "rates_imported": result.get("rates_imported", 0),
            "net_new": result.get("net_new", 0),
            "knowledge_items": result.get("knowledge_items", 0),
            "surcharge_alerts": result.get("surcharge_alerts", 0),
        }
    except Exception as e:
        log.error("[pricing] Error: %s\n%s", e, traceback.format_exc())
        return {"status": "error", "error": str(e)}


def run_shipment_brain(config: dict, dry_run: bool = False) -> dict:
    """Run Shipment Brain scan (shipment_brain.py)."""
    if dry_run:
        return {"status": "dry_run", "description": config["description"]}

    try:
        from shipment_brain import main as brain_main
        brain_main()
        return {"status": "ok", "description": "Shipment brain scan completed"}
    except SystemExit:
        return {"status": "ok", "note": "clean exit"}
    except Exception as e:
        log.error("[shipment_brain] Error: %s", e)
        return {"status": "error", "error": str(e)}


def run_knowledge_ingest(config: dict, dry_run: bool = False) -> dict:
    """Run Knowledge Ingest — email JSONs + .msg → per-customer Parquet."""
    if dry_run:
        return {"status": "dry_run", "description": config["description"]}

    try:
        from knowledge_ingest import run_knowledge_ingest as ingest_main
        result = ingest_main()
        return {
            "status": "ok",
            "new_emails": result.get("new_emails", 0),
            "total_emails": result.get("total_emails", 0),
            "customers_updated": result.get("customers_updated", []),
        }
    except Exception as e:
        log.error("[knowledge_ingest] Error: %s\n%s", e, traceback.format_exc())
        return {"status": "error", "error": str(e)}


def run_reply_processing(config: dict, dry_run: bool = False) -> dict:
    """Run inbox reply/bounce scanner — calls inbox_scanner.run_scan().

    This is job #6. Processes real replies, bounces, auto-replies from the
    Outlook Inbox so that handle_real_reply + handle_bounce actually execute
    every 30 min (the code existed but was never wired into the scheduler).
    """
    if dry_run:
        return {"status": "dry_run", "description": config["description"]}

    try:
        from email_engine.scanner.inbox_scanner import run_scan  # type: ignore
        result = run_scan()
        return {
            "status": "ok",
            "scanned":      result.get("scanned", 0),
            "bounces":      result.get("bounces", 0),
            "real_replies": result.get("real_replies", 0),
            "auto_replies": result.get("auto_replies", 0),
            "unsubs":       result.get("unsubs", 0),
            "errors":       result.get("errors", 0),
        }
    except Exception as e:
        log.error("[reply_processing] Error: %s\n%s", e, traceback.format_exc())
        return {"status": "error", "error": str(e)}


def run_nelson_customer_sort(config: dict, dry_run: bool = False) -> dict:
    """Run Nelson Customer Sort — move khách Nelson emails to DIRECT/FW folders."""
    if dry_run:
        # In dry-run mode we still call the sorter with dry_run=True so it
        # logs "Would move" lines without touching the mailbox.
        pass

    try:
        from nelson_customer_sort import run as sort_run
        result = sort_run(dry_run=dry_run)

        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error", "unknown")}

        return {
            "status": "dry_run" if dry_run else "ok",
            "moved_direct":  result.get("moved_direct", 0),
            "moved_fw":      result.get("moved_fw", 0),
            "skipped":       result.get("skipped", 0),
            "errors":        result.get("errors", 0),
            "total_scanned": result.get("total_scanned", 0),
        }
    except Exception as e:
        log.error("[nelson_customer_sort] Error: %s\n%s", e, traceback.format_exc())
        return {"status": "error", "error": str(e)}


# Job name → runner function mapping
# Note: si_48h_alert merged INTO shipment_brain (2026-04-22) per architecture review —
# same "shipment lifecycle monitoring" domain, just event-driven + time-driven concerns.
_JOB_RUNNERS = {
    "mentee_classification":  run_mentee_classification,
    "pricing_import":         run_pricing_import,
    "shipment_brain":         run_shipment_brain,       # includes SI 48h alert
    "knowledge_ingest":       run_knowledge_ingest,
    "nelson_customer_sort":   run_nelson_customer_sort,
    "reply_processing":       run_reply_processing,
}


def run_job(job_name: str, config: dict, dry_run: bool = False) -> dict:
    """Run a single scan job with timeout and error handling."""
    runner = _JOB_RUNNERS.get(job_name)
    if not runner:
        log.warning("Unknown job: %s", job_name)
        return {"status": "skipped", "reason": f"unknown job: {job_name}"}

    timeout = config.get("timeout_seconds", 120)
    log.info("-" * 50)
    log.info("JOB: %s (timeout: %ds)", job_name, timeout)
    log.info("-" * 50)

    start_time = time.time()
    try:
        result = runner(config, dry_run=dry_run)
    except Exception as e:
        result = {"status": "error", "error": str(e)}

    elapsed = time.time() - start_time
    result["elapsed_seconds"] = round(elapsed, 1)

    status_icon = "[OK]" if result.get("status") == "ok" else \
                  "[DRY]" if result.get("status") == "dry_run" else "[ERR]"
    log.info("%s %s completed in %.1fs", status_icon, job_name, elapsed)

    return result


# ==============================================================================
# 4. MAIN ORCHESTRATOR
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nelson Unified Outlook Scanner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run, no actual scanning")
    parser.add_argument("--job", type=str, default=None,
                        help="Run single job by name (e.g. pricing_import)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  NELSON UNIFIED SCANNER — %s",
             datetime.now().strftime("%Y-%m-%d %H:%M"))
    if args.dry_run:
        log.info("  MODE: DRY RUN (no changes)")
    log.info("=" * 60)

    # Load rules
    rules = load_rules()
    jobs  = rules.get("jobs", {})

    # Time guard (skip in dry-run mode)
    if not args.dry_run and not within_schedule(rules["schedule"]):
        return

    # Run jobs
    results = {}
    for job_name, job_config in jobs.items():
        # Filter by --job if specified
        if args.job and job_name != args.job:
            continue

        if not job_config.get("enabled", False):
            log.info("[SKIP] %s -- disabled in scanner_rules.json", job_name)
            results[job_name] = {"status": "skipped", "reason": "disabled"}
            continue

        result = run_job(job_name, job_config, dry_run=args.dry_run)
        results[job_name] = result

    # Summary log
    log.info("=" * 60)
    ok_count    = sum(1 for r in results.values() if r.get("status") == "ok")
    error_count = sum(1 for r in results.values() if r.get("status") == "error")
    log.info("DONE | OK: %d | Errors: %d | Total jobs: %d",
             ok_count, error_count, len(results))
    log.info("=" * 60)

    # Return for programmatic use
    return results


if __name__ == "__main__":
    _results = main()
    # Report to Fox Spirit (GoClaw VPS) — fire-and-forget
    try:
        import importlib.util, pathlib
        _rep = pathlib.Path(__file__).parent.parent.parent / "tools" / "goclaw" / "goclaw_reporter.py"
        _spec = importlib.util.spec_from_file_location("goclaw_reporter", _rep)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _summary = {k: v.get("status") for k, v in _results.items()} if isinstance(_results, dict) else {}
        _mod.report_to_fox("outlook-scanner", {"success": True, "jobs": _summary})
    except Exception:
        pass
