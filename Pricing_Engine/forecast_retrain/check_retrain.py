"""Trigger logic for auto-retrain.

Evaluates 4 signals (any OR trips retrain):
    A. imports_since_train   >= N_IMPORTS_THRESHOLD   (default 3)
    B. rows_delta            >= N_ROWS_THRESHOLD      (default 500)
    C. days_since_train      >= N_DAYS_THRESHOLD      (default 7)
    D. last_accuracy_error   >= N_ACCURACY_THRESHOLD  (default 20.0 %)

Usage:
    # CLI — nightly cron 2am Asia/Saigon
    python -m Pricing_Engine.forecast_retrain.check_retrain

    # Library
    from Pricing_Engine.forecast_retrain import should_retrain, load_state
    fire, reason = should_retrain(load_state())
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

from .state import RetrainState, load_state, mark_trained

log = logging.getLogger("nelson.forecast_retrain.check")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ── Thresholds (tunable) ────────────────────────────────────────────────────
N_IMPORTS_THRESHOLD = 3        # (A) N imports since last train
N_ROWS_THRESHOLD = 500         # (B) rows added since last train
N_DAYS_THRESHOLD = 7           # (C) stale model floor
N_ACCURACY_THRESHOLD_PCT = 20.0  # (D) drift ceiling

# Path to forecast runner — repo-relative so it works on any machine.
FORECAST_RUNNER = (
    Path(__file__).resolve().parents[1]
    / "forecast"
    / "run_forecast.py"
)
# If the forecast/ lives on OneDrive (current setup), use that instead.
_ONEDRIVE_FORECAST = Path("D:/OneDrive/NelsonData/pricing/forecast/run_forecast.py")
if _ONEDRIVE_FORECAST.exists():
    FORECAST_RUNNER = _ONEDRIVE_FORECAST


def should_retrain(state: RetrainState) -> Tuple[bool, str]:
    """Return (fire, human-readable reason)."""
    reasons: list[str] = []

    # (A) imports
    if state.imports_since_train >= N_IMPORTS_THRESHOLD:
        reasons.append(
            f"imports_since_train={state.imports_since_train} >= {N_IMPORTS_THRESHOLD}"
        )

    # (B) rows
    rows_delta = sum(d.rows_added for d in state.data_deltas)
    if rows_delta >= N_ROWS_THRESHOLD:
        reasons.append(f"rows_delta={rows_delta} >= {N_ROWS_THRESHOLD}")

    # (C) days
    if state.last_trained_at:
        try:
            last = datetime.fromisoformat(state.last_trained_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - last).days
            if days >= N_DAYS_THRESHOLD:
                reasons.append(f"days_since_train={days} >= {N_DAYS_THRESHOLD}")
        except ValueError:
            reasons.append("last_trained_at unparseable — force retrain")
    else:
        reasons.append("never trained — force retrain")

    # (D) accuracy drift
    if state.last_accuracy and state.last_accuracy.avg_error_pct >= N_ACCURACY_THRESHOLD_PCT:
        reasons.append(
            f"accuracy_error={state.last_accuracy.avg_error_pct:.1f}% "
            f">= {N_ACCURACY_THRESHOLD_PCT}%"
        )

    if reasons:
        return True, " | ".join(reasons)
    return False, "all signals quiet"


def _current_parquet_rows() -> int:
    """Best-effort read of current parquet row count; 0 on failure."""
    try:
        from shared import paths as sp  # type: ignore
        import pyarrow.parquet as pq
        return int(pq.read_metadata(str(sp.PARQUET_FILE)).num_rows)
    except Exception as e:
        log.warning("could not read parquet row count: %s", e)
        return 0


def run_check(dry_run: bool = False) -> dict:
    """Nightly entry point. Returns a result dict (JSON-serializable)."""
    state = load_state()
    fire, reason = should_retrain(state)
    result = {
        "fire": fire,
        "reason": reason,
        "imports_since_train": state.imports_since_train,
        "rows_delta": sum(d.rows_added for d in state.data_deltas),
        "last_trained_at": state.last_trained_at,
        "dry_run": dry_run,
    }

    if not fire:
        log.info("no retrain needed: %s", reason)
        return result

    log.info("retrain TRIGGERED: %s", reason)

    if dry_run:
        result["action"] = "dry-run — skipping actual retrain"
        return result

    if not FORECAST_RUNNER.exists():
        log.error("forecast runner missing: %s", FORECAST_RUNNER)
        result["action"] = "skipped"
        result["error"] = f"runner missing: {FORECAST_RUNNER}"
        return result

    log.info("spawning: %s", FORECAST_RUNNER)
    try:
        rc = subprocess.run(
            [sys.executable, str(FORECAST_RUNNER)],
            cwd=str(FORECAST_RUNNER.parent),
            check=False,
            timeout=600,  # 10 min ceiling — existing runner is ~30s
        )
        if rc.returncode == 0:
            rows = _current_parquet_rows()
            mark_trained(parquet_rows=rows)
            result["action"] = "retrained"
            result["parquet_rows_at_train"] = rows
            log.info("retrain complete, state reset (rows=%d)", rows)
        else:
            result["action"] = "failed"
            result["exit_code"] = rc.returncode
            log.error("forecast runner exit code %d", rc.returncode)
    except subprocess.TimeoutExpired:
        result["action"] = "timeout"
        log.error("forecast runner exceeded 10min timeout")
    except Exception as e:
        result["action"] = "error"
        result["error"] = str(e)
        log.error("retrain spawn failed: %s", e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Check if forecast model should be retrained, spawn runner if so"
    )
    parser.add_argument("--dry-run", action="store_true", help="Evaluate signals, don't spawn")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass signal check, force a retrain",
    )
    args = parser.parse_args()

    if args.force:
        log.info("--force given, bypassing signal check")
        from .state import load_state as _ls
        state = _ls()
        # Monkey: flip one threshold for this run
        state.imports_since_train = max(state.imports_since_train, N_IMPORTS_THRESHOLD)

    result = run_check(dry_run=args.dry_run)
    import json as _json
    print(_json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not result.get("error") else 1)


if __name__ == "__main__":
    main()
