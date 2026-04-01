"""
run_all.py — One-Click Email Pipeline
======================================
Modes:
  1. FULL  : clean bad emails -> scan bounce from Outlook -> classify replies -> send
  2. SCAN  : scan bounce + classify replies only (no send)
  3. SEND  : send only (must run scan first)

Usage:
  python run_all.py          -> interactive menu
  python run_all.py scan     -> non-interactive bounce scan
  python run_all.py classify -> classify replies only
"""

import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt = "%H:%M:%S",
    handlers= [logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent
PYTHON     = sys.executable


def run_step(label: str, script: str, extra_args: list[str] | None = None) -> bool:
    """Run a sub-script and return True if successful."""
    script_path = BASE_DIR / script
    if not script_path.exists():
        log.error("[SKIP] %s not found: %s", label, script)
        return False

    cmd = [PYTHON, str(script_path)] + (extra_args or [])
    log.info("")
    log.info("=" * 60)
    log.info("  STEP: %s", label)
    log.info("=" * 60)

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        log.error("[FAILED] %s exited with code %d", label, result.returncode)
        return False

    log.info("[DONE] %s", label)
    return True


def step_clean() -> bool:
    """Step 1: Remove hard-patterned bad emails from data.xlsx"""
    return run_step("Clean Data (pattern-based)", "ingest/clean_data.py")


def step_scan_bounce() -> bool:
    """Step 2: Scan Outlook for bounce/auto-reply, write-back to data.xlsx"""
    log.info("")
    log.info("=" * 60)
    log.info("  STEP: Scan Bounce & Auto-Reply from Outlook")
    log.info("=" * 60)
    log.info("  NOTE: read_email1.py is running with DRY_RUN flag.")
    log.info("  To enable actual write-back, set DRY_RUN=False in read_email1.py.")

    return run_step("Bounce Scanner", "core/read_email1.py")


def step_classify() -> bool:
    """Step 3: Classify reply tiers -> customer_final.xlsx"""
    return run_step("Reply Tier Classifier", "core/process_reply.py")


def step_send() -> bool:
    """Step 4: Interactive send (requires user input)"""
    return run_step("Send Email", "core/send_email.py")


def step_dashboard() -> bool:
    """Step 5: Generate email_master.xlsx dashboard"""
    return run_step("Dashboard Generator", "core/generate_dashboard.py")


def step_follow_up() -> bool:
    """Step 6: Run follow-up alert engine (auto, no user input needed)"""
    return run_step("Follow-up Alert Engine", "core/follow_up_engine.py")


def step_tier_send() -> bool:
    """Step 7: Semi-auto Tier Send (interactive tier selection)"""
    return run_step("Tier Send (semi-auto)", "core/send_email.py", extra_args=["--tier"])


def step_ingest() -> bool:
    """Step 8: Run combine_all.py to ingest new Panjiva files into master files."""
    return run_step("INGEST -- Process Panjiva files", "ingest/combine_all.py")


def step_sequence() -> bool:
    """Step 9: Run 3-email sequence engine (auto-advance all active sequences)."""
    return run_step("SEQUENCE -- Auto-advance email sequences",
                    "core/sequence_engine.py", extra_args=["--sequence", "--dry-run"])


def step_collect() -> bool:
    """Step 0: Process .msg files → SQLite (data pipeline)."""
    return run_step("COLLECT -- Process .msg files → SQLite", "core/data_collector.py")


def step_briefing() -> bool:
    """Step 10: Generate nelson_briefing.xlsx."""
    return run_step("BRIEFING -- Generate nelson_briefing.xlsx", "core/nelson_briefing.py")


def step_parquet() -> bool:
    """Step 11: Export SQLite tables to Parquet."""
    return run_step("PARQUET EXPORT -- SQLite -> Parquet",
                    "core/data_collector.py", extra_args=["parquet"])


def step_pst_import() -> bool:
    """Step 12: Import PST file into shipments.db."""
    print("\n  PST file: D:\\NELSON\\email_engine\\backup.pst")
    print("  Options:")
    print("    1. Quick import -- named folders only (CNEE, SHIPPER...) ~15 min")
    print("    2. Full import  -- all folders including Inbox ~45-90 min")
    print("    3. Dry run      -- preview counts only, no DB changes")
    choice = input("  Select (1/2/3): ").strip()
    since = input("  Import since date (default 2024-01-01): ").strip() or '2024-01-01'

    if choice == '1':
        return run_step('PST Import (folder-only)', 'core/pst_importer.py',
                        ['--folder-only', '--since', since])
    elif choice == '2':
        return run_step('PST Import (full)', 'core/pst_importer.py',
                        ['--since', since])
    elif choice == '3':
        return run_step('PST Import (dry-run)', 'core/pst_importer.py',
                        ['--dry-run', '--since', since])
    else:
        print("  Invalid choice.")
        return False


def step_auto_rate() -> bool:
    """Step 13: Auto Quote Send — generate per-customer rate tables from Parquet."""
    return run_step("AUTO QUOTE SEND", "core/send_email.py", extra_args=["--auto-rate"])


# =========================================================
# MENU
# =========================================================
def menu() -> str:
    print("\n" + "=" * 60)
    print("  EMAIL ENGINE — PIPELINE MENU")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    print("  0.  COLLECT       — Process .msg files → SQLite")
    print("  1.  SCAN ONLY     — Bounce scan + classify replies")
    print("  2.  CLASSIFY ONLY — Classify reply tiers (customer_final.xlsx)")
    print("  3.  SEND ONLY     — Send emails by CMD (requires scan done first)")
    print("  4.  FULL PIPELINE — Clean + Scan + Classify + Follow-up + Send")
    print("  5.  DASHBOARD     — Generate email_master.xlsx (no send)")
    print("  6.  TIER SEND     — Semi-auto send to REPLY_1/2/3 prospects")
    print("  7.  FOLLOW-UP     — Run follow-up alert engine only")
    print("  8.  INGEST        — Process new Panjiva files into master files")
    print("  9.  SEQUENCE      — Auto-advance email sequences (dry-run)")
    print("  10. BRIEFING      -- Generate nelson_briefing.xlsx")
    print("  11. PARQUET       -- Export SQLite -> Parquet")
    print("  12. PST IMPORT    -- Import backup.pst into DB")
    print("  13. AUTO QUOTE    -- Auto-generate rate email from Parquet (per customer route)")
    print()
    return input("  Select mode (0-13): ").strip()


def pipeline_scan():
    """Scan bounce + classify + follow-up alerts (safe, no send)"""
    ok = step_scan_bounce()
    if ok:
        step_classify()
        step_follow_up()   # auto-run follow-up after classify


def pipeline_classify():
    step_classify()


def pipeline_send():
    step_send()


def pipeline_full():
    log.info("Running FULL pipeline: clean -> scan -> classify -> follow-up -> send")
    # Step 1: Clean
    if not step_clean():
        if input("clean_data.py failed. Continue anyway? (Y/N): ").upper() != "Y":
            return

    # Step 2: Bounce scan
    if not step_scan_bounce():
        if input("Bounce scan failed. Continue anyway? (Y/N): ").upper() != "Y":
            return

    # Step 3: Classify
    step_classify()

    # Step 4: Follow-up alerts (automatic)
    step_follow_up()

    # Step 5: Send (interactive)
    print("\nSend mode:")
    print("  1. CMD SEND  (select by campaign)")
    print("  2. TIER SEND (send to REPLY_1/2/3 hot prospects)")
    print("  3. Skip send")
    send_choice = input("  Choice: ").strip()
    if send_choice == "1":
        step_send()
    elif send_choice == "2":
        step_tier_send()
    else:
        log.info("Send skipped.")


# =========================================================
# ENTRY POINT
# =========================================================
def main():
    # Allow non-interactive CLI mode
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "scan":
            pipeline_scan()
        elif arg == "classify":
            pipeline_classify()
        elif arg == "send":
            pipeline_send()
        elif arg == "full":
            pipeline_full()
        elif arg == "dashboard":
            step_dashboard()
        elif arg == "ingest":
            step_ingest()
        elif arg == "sequence":
            step_sequence()
        elif arg == "collect":
            step_collect()
        elif arg == "briefing":
            step_briefing()
        elif arg == "parquet":
            step_parquet()
        elif arg == "pst":
            step_pst_import()
        elif arg == "auto-rate":
            step_auto_rate()
        else:
            print(f"Unknown argument: {arg}. Use: scan | classify | send | full | dashboard | ingest | sequence | collect | briefing | parquet | pst | auto-rate")
        return

    # Interactive menu
    choice = menu()
    dispatch = {
        "0":  step_collect,
        "1":  pipeline_scan,
        "2":  pipeline_classify,
        "3":  pipeline_send,
        "4":  pipeline_full,
        "5":  step_dashboard,
        "6":  step_tier_send,
        "7":  step_follow_up,
        "8":  step_ingest,
        "9":  step_sequence,
        "10": step_briefing,
        "11": step_parquet,
        "12": step_pst_import,
        "13": step_auto_rate,
    }
    fn = dispatch.get(choice)
    if fn:
        fn()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
