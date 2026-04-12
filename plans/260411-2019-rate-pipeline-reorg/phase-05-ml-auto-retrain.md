# Phase 5 — ML forecast auto-retrain trigger

**Priority:** MEDIUM | **Status:** ✅ IMPLEMENTED 2026-04-11
**Effort:** 2h | **Files touched:** `Pricing_Engine/forecast_retrain/`, `rate_importer.py`, `scripts/check-retrain.bat`, `tests/unit/test_forecast_retrain.py`

## Goal

Decide automatically when the Nelson market forecaster (`forecast/run_forecast.py` 6-agent pipeline) should retrain, so the model stays fresh without manual prodding.

## Signal design (any OR trips retrain)

| Signal | Threshold | Rationale |
|---|---|---|
| **A. imports_since_train** | `>= 3` | 3 rate updates = meaningful market movement |
| **B. rows_delta** | `>= 500` rows | Volume-based — lots of small imports count |
| **C. days_since_train** | `>= 7` days | Weekly floor — never let model rot |
| **D. accuracy_error_pct** | `>= 20%` | Drift alarm — if backtest shows model is wrong, retrain immediately |

Thresholds are module constants in `Pricing_Engine/forecast_retrain/check_retrain.py` — tune in one place.

## Architecture

```
rate_importer.classify_and_import()
        ↓ (after parquet write)
forecast_retrain.bump_import_counter(rows_added, source)
        ↓
OneDrive/pricing/forecast/retrain_state.json
        ↑
scripts/check-retrain.bat  ← Task Scheduler 02:00 daily
        ↓
check_retrain.run_check()
        ├─ should_retrain(state) → (fire, reason)
        └─ if fire: subprocess.run(run_forecast.py) + mark_trained()
```

Decoupled: `rate_importer` only writes the state file. `check_retrain` reads + decides + spawns. Safe to run forecast runner concurrently from anywhere — it just resets the state when done.

## Files delivered

### `Pricing_Engine/forecast_retrain/__init__.py`
Re-exports public API: `RetrainState`, `load_state`, `save_state`, `bump_import_counter`, `should_retrain`, `run_check`.

### `Pricing_Engine/forecast_retrain/state.py`
Dataclasses + JSON I/O:
- `RetrainState` — root state (`last_trained_at`, `imports_since_train`, `data_deltas`, `last_accuracy`)
- `ImportDelta` — per-import row (`at`, `rows_added`, `source`)
- `AccuracySnapshot` — weekly error log (`week`, `avg_error_pct`, `checked_at`)
- `load_state()` — tolerant, returns default on missing/corrupt
- `save_state()` — atomic tmp + rename
- `bump_import_counter(rows_added, source)` — called from `rate_importer` after parquet write; trims history to last 50 deltas
- `mark_trained(parquet_rows)` — called after successful retrain; resets counter
- `record_accuracy(week, avg_error_pct)` — called by backtest job

State persists at `D:/OneDrive/NelsonData/pricing/forecast/retrain_state.json` so PC Home / Laptop VP / VPS share one view.

### `Pricing_Engine/forecast_retrain/check_retrain.py`
- `should_retrain(state) -> (bool, str)` — pure function, evaluates 4 signals, returns (fire, reason)
- `run_check(dry_run=False)` — loads state, evaluates, spawns `run_forecast.py` if needed, marks trained on success
- `main()` — argparse entry: `--dry-run`, `--force`
- Autodetects forecast runner at `D:/OneDrive/NelsonData/pricing/forecast/run_forecast.py`

### `Pricing_Engine/rate_importer.py` — hook
After successful `combined.to_parquet(...)`:
```python
try:
    from Pricing_Engine.forecast_retrain import bump_import_counter
    _types = {f.get("type", "") for f in files if f.get("type")}
    _source = next(iter(_types)) if len(_types) == 1 else "MIXED"
    bump_import_counter(
        rows_added=max(0, rates_after - rates_before),
        source=_source,
        parquet_rows_after=rates_after,
    )
except Exception as _e:
    log.warning("forecast_retrain bump failed (non-blocking): %s", _e)
```

Non-blocking — any failure in the retrain hook never blocks a successful rate import.

### `scripts/check-retrain.bat`
Task Scheduler wrapper:
```bat
check-retrain.bat            REM evaluate + spawn
check-retrain.bat --dry-run  REM evaluate only
check-retrain.bat --force    REM bypass signals
```
Scheduled: **Daily 02:00 Asia/Saigon** (after market close, before next business day).

### `tests/unit/test_forecast_retrain.py`
13 unit tests, all green:
- State: default, save/reload, corrupt file fallback
- Bump: increments, appends delta, trims to 50
- Mark: resets counters
- `should_retrain`: quiet state, each signal trips (A/B/C/D), never-trained edge case
- `run_check --dry-run`: fires without spawning

```
$ python -m pytest tests/unit/test_forecast_retrain.py -v
13 passed in 0.26s
```

## Task Scheduler setup (manual step — Nelson to run once)

```powershell
# Run in elevated PowerShell
schtasks /create /tn "Nelson\ForecastRetrainCheck" ^
  /tr "D:\NELSON\2. Areas\Engine_test\.claude\worktrees\dazzling-engelbart\scripts\check-retrain.bat" ^
  /sc daily /st 02:00 /rl limited /f
```

Or via Task Scheduler GUI:
- Trigger: Daily 02:00
- Action: `scripts\check-retrain.bat` from repo root
- Conditions: Wake computer to run, Start only if network available

## Success criteria (all ✅)

- [x] `retrain_state.json` persists across runs
- [x] `rate_importer` bumps counter on every successful import (non-blocking)
- [x] `check_retrain --dry-run` shows signal state + does NOT spawn
- [x] `should_retrain` unit-tested on all 4 signals + edge cases (13 tests)
- [x] CLI wrapper `scripts/check-retrain.bat` ready for Task Scheduler

## Non-goals

- ❌ LightGBM / Holt-Winters model improvements — scope creep, separate plan
- ❌ Accuracy backtester — use existing `agent3_backtest_judge.py` output, just record via `record_accuracy()`
- ❌ Notification to Telegram when retrain fires — add later if noisy

## Next

- Nelson runs Task Scheduler setup command above
- Monitor `retrain_state.json` first week to tune thresholds
- When Task A P2 (Python extraction from VBA) lands, use same state pattern for ERP formula retraining
