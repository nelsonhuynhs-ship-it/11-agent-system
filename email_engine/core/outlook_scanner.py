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


def run_si_48h_alert(config: dict, dry_run: bool = False) -> dict:
    """Run 48h SI cutoff alert — scans Active Jobs, Telegram if SI < 48h + Docs not done.

    Integrated as job #7 (instead of separate daily Task Scheduler entry) —
    leverages existing 30-min cadence + dedup per-day ensures no spam.
    """
    try:
        # File has hyphen ("si-48h-alert.py") — use importlib to load by path
        import importlib.util
        script_path = Path(_repo_root) / "scripts" / "si-48h-alert.py"
        spec = importlib.util.spec_from_file_location("si_48h_alert_module", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.run_alert(dry_run=dry_run)
    except Exception as e:
        log.error("[si_48h_alert] Error: %s\n%s", e, traceback.format_exc())
        return {"status": "error", "error": str(e)}


# Job name → runner function mapping
_JOB_RUNNERS = {
    "mentee_classification":  run_mentee_classification,
    "pricing_import":         run_pricing_import,
    "shipment_brain":         run_shipment_brain,
    "knowledge_ingest":       run_knowledge_ingest,
    "nelson_customer_sort":   run_nelson_customer_sort,
    "reply_processing":       run_reply_processing,   # job #6 — inbox reply/bounce handler
    "si_48h_alert":           run_si_48h_alert,       # job #7 — SI cutoff warning
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
# 4. TELEGRAM SUMMARY
# ==============================================================================

def send_telegram_summary(results: dict, rules: dict) -> bool:
    """Send combined scan summary to Nelson via Telegram."""
    if not rules.get("notifications", {}).get("telegram_enabled", False):
        return False
    if not rules.get("notifications", {}).get("summary_after_scan", False):
        return False

    # Read Telegram config from TelegramBot/.env
    try:
        env_file = PROJECT_ROOT.parent / "TelegramBot" / ".env"
        token, chat_id = None, None
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                elif line.startswith("ADMIN_CHAT_ID="):
                    chat_id = line.split("=", 1)[1].strip()

        if not token or not chat_id:
            log.warning("[Telegram] BOT_TOKEN or ADMIN_CHAT_ID not found")
            return False

    except Exception as e:
        log.warning("[Telegram] Config read error: %s", e)
        return False

    # Build summary message
    now_str = datetime.now().strftime("%H:%M %d/%m")
    lines = [f"📡 *Unified Scanner — {now_str}*", "━" * 28]

    for job_name, result in results.items():
        status = result.get("status", "?")
        elapsed = result.get("elapsed_seconds", 0)

        if status == "ok":
            icon = "✅"
        elif status == "dry_run":
            icon = "🔵"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"

        # Job-specific details
        label = job_name.replace("_", " ").title()
        detail = ""

        if job_name == "pricing_import" and status == "ok":
            rates = result.get("rates_imported", 0)
            net = result.get("net_new", 0)
            knowledge = result.get("knowledge_items", 0)
            if rates > 0:
                detail = f" | +{rates} rates (net {net})"
            elif knowledge > 0:
                detail = f" | {knowledge} knowledge items"
            else:
                detail = " | No new rates"

        elif job_name == "mentee_classification" and status == "ok":
            detail = " | Email routing done"

        elif job_name == "shipment_brain" and status == "ok":
            detail = " | Shipment tracking done"

        elif job_name == "knowledge_ingest" and status == "ok":
            new_e = result.get("new_emails", 0)
            total = result.get("total_emails", 0)
            custs = len(result.get("customers_updated", []))
            detail = f" | +{new_e} emails, {total} total, {custs} customers"

        elif job_name == "nelson_customer_sort" and status == "ok":
            direct = result.get("moved_direct", 0)
            fw     = result.get("moved_fw", 0)
            moved  = direct + fw
            if moved > 0:
                detail = f" | {moved} moved (DIRECT:{direct} FW:{fw})"
            else:
                detail = " | No emails to sort"

        elif job_name == "reply_processing" and status == "ok":
            scanned = result.get("scanned", 0)
            bounces = result.get("bounces", 0)
            replies = result.get("real_replies", 0)
            if scanned > 0:
                detail = f" | {scanned} scanned · {replies} replies · {bounces} bounces"
            else:
                detail = " | Inbox quiet"

        if status == "error":
            err = result.get("error", "unknown")[:60]
            detail = f" | ⚠️ {err}"

        lines.append(f"{icon} {label}{detail} ({elapsed:.0f}s)")

    # Total elapsed
    total = sum(r.get("elapsed_seconds", 0) for r in results.values())
    lines.append(f"\n⏱️ Total: {total:.0f}s")

    message = "\n".join(lines)

    # Send via Telegram API
    try:
        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            if ok:
                log.info("[Telegram] Summary sent ✅")
            return ok

    except Exception as e:
        log.warning("[Telegram] Send failed: %s", e)
        return False


# ==============================================================================
# 5. MAIN ORCHESTRATOR
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

    # Send Telegram summary (not in dry-run)
    if not args.dry_run:
        send_telegram_summary(results, rules)

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
