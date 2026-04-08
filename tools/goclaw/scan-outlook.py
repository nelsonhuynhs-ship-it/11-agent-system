# -*- coding: utf-8 -*-
"""
scan-outlook.py — GoClaw Tool: Run Outlook scanner jobs.

Usage:
    python scan-outlook.py                        # all enabled jobs
    python scan-outlook.py --job mentee           # single job
    python scan-outlook.py --job pricing --dry-run
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent  # tools/goclaw/ → tools/ → Engine_test/
SCANNER_SCRIPT = REPO_ROOT / "email_engine" / "core" / "outlook_scanner.py"
PYTHON = sys.executable

# Job name mapping (short → full)
JOB_MAP = {
    "mentee": "mentee_classification",
    "pricing": "pricing_import",
    "shipment": "shipment_brain",
    "knowledge": "knowledge_ingest",
    "all": None,  # run all
}


def run_scanner(job: str = "all", dry_run: bool = False) -> dict:
    """Run outlook_scanner.py with specified job."""
    if not SCANNER_SCRIPT.exists():
        return {"error": f"Scanner not found: {SCANNER_SCRIPT}"}

    cmd = [PYTHON, str(SCANNER_SCRIPT)]

    full_job = JOB_MAP.get(job, job)
    if full_job:
        cmd.extend(["--job", full_job])
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(REPO_ROOT), encoding="utf-8", errors="replace",
        )
        return {
            "job": job,
            "dry_run": dry_run,
            "exit_code": result.returncode,
            "success": result.returncode == 0,
            "stdout_lines": result.stdout.strip().split("\n")[-5:] if result.stdout else [],
            "errors": result.stderr.strip().split("\n")[-3:] if result.stderr else [],
        }
    except subprocess.TimeoutExpired:
        return {"error": "Scanner timed out after 600s", "job": job}
    except Exception as e:
        return {"error": str(e), "job": job}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run Outlook scanner")
    p.add_argument("--job", default="all",
                    choices=["all", "mentee", "pricing", "shipment", "knowledge"],
                    help="Scanner job to run")
    p.add_argument("--dry-run", action="store_true", help="Simulate without action")
    args = p.parse_args()

    result = run_scanner(args.job, args.dry_run)
    # Report result to Fox Spirit (GoClaw VPS) — fire-and-forget
    try:
        from goclaw_reporter import report_to_fox
        report_to_fox(f"scan-outlook:{args.job}", result)
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("success", False) or result.get("dry_run") else 1)
