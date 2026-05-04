# Code Review Report — Nelson Freight ERP E2E System

**Date**: 2026-05-03
**Reviewer**: Code Reviewer Agent
**Files Reviewed**: 48 files (38 Python, 7 test, 3 VBA)

---

## Executive Summary

ERP system is a multi-tier Python/VBA/FastAPI stack with DuckDB and Excel COM integration. 41 Python modules across 4 top-level packages (ERP, api, email_engine, db). Active Jobs v4 (40-col layout) is the central data hub.

**Overall state**: MEDIUM RISK. Test infrastructure is broken by design — 7 test files use custom test runners that call `sys.exit(1)` to signal pass/fail, making them invisible to pytest. Integration tests depend on xlwings + live OneDrive ERP file. No isolated unit tests for core logic. However, the code itself is well-structured with good separation of concerns.

---

## Architecture Diagram

```
Nelson Freight ERP — Component Map
=====================================

[Excel VBA] ←──COM── [erp_api_bridge.py] ←──HTTP── [FastAPI :8100]
     ↑                    ↑                        ↑
[ERP_Master_v14.xlsm]  [ribbon_guard.py]    [15 routers]
     ↑                    ↑                   api/routers/*
[openpyxl reads]    [openpyxl saves]             ↑
                                           [DuckDB engine]
     ↑                                        db/duckdb_engine.py
[Active Jobs v4]                              ↑
40-col layout from                      [Parquet ~6.6M rows]
[active_jobs_cols.py]                   Cleaned_Master_History.parquet

[Python helpers] ←──────────────────────────────┐
ERP/core/               ERP/jobs/      ERP/intelligence/  ERP/quotes/
  active_jobs_cols.py     email_builder.py    price_watch.py   image_generator.py
  ribbon_guard.py         release_alerts.py   daily_sync.py    manager.py
  migrate_active_jobs_v4.py  enrichment.py    monthly_report.py
  seed_test_jobs.py        transit_time.py    weekly_report.py
                            fast_id.py        carrier_alias.py
                            reefer_plug.py     price_alerts.py
                            shipment_tracker.py  quote_matcher.py
                            carrier_performance.py profit_calculator.py

[email_engine/] ←───────────────────────────────┐
email_engine/core/        email_engine/intel/  email_engine/api/
  rotation_engine.py        memory.py           routes/rotation_router.py
  smart_send_window.py      tier_engine.py      routes/contacts_router.py
  sequence_engine.py        pattern_learner.py
  follow_up_engine.py       market_engine.py
  email_parser.py
  bounce_knowledge.py
  bounce_harvest_v2.py
```

---

## Test Infrastructure Assessment

### Critical Finding #1: 7 Test Files Use Custom Test Runners (NOT pytest)

Every test file that calls `sys.exit(1)` implements a **custom manual test runner loop** instead of using pytest. This makes them invisible to pytest's collection/execution system:

| File | Custom Runner Style | pytest compatible |
|------|---------------------|-------------------|
| `test_v13_ribbon.py` | Standalone COM script using `win32com` — no pytest at all | NO |
| `test_duckdb_engine.py:178` | Custom `for test in tests:` loop → `sys.exit(1)` on fail | NO |
| `test_normalization.py:224` | Same custom loop pattern | NO |
| `test_parquet_upgrader.py:173` | Same custom loop pattern | NO |
| `test_rate_router.py:227` | Same custom loop pattern | NO |
| `test_anomaly_detector.py:201` | Same custom loop pattern | NO |
| `test_erp_e2e.py:606` | `if __name__ == "__main__": sys.exit(main())` — standalone COM | NO |

**Impact**: `pytest tests/` does NOT run these tests. You must run them manually as scripts. The `test_v13_ribbon.py` also has hardcoded wrong path `D:\NELSON\2. Areas\PricingSystem\Engine_test\...` instead of `D:\OneDrive\NelsonData\erp\...`.

### Critical Finding #2: Path Mismatch — test_v13_ribbon.py vs test_erp_e2e.py

```python
# test_v13_ribbon.py:13 — WRONG PATH (PricingSystem, not OneDrive)
ERP_FILE = os.path.abspath(r"D:\NELSON\2. Areas\PricingSystem\Engine_test\ERP\data\ERP_V13_STAGING.xlsm")

# test_erp_e2e.py:36 — CORRECT PATH (OneDrive)
ERP_PATH = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
```

Both attempt to use live ERP files. The first uses a staging file that may not exist.

### Critical Finding #3: xlwings Dependency for Integration Tests

`conftest.py` defines `excel_app` and `erp_workbook` fixtures using xlwings + COM. These are **session-scoped** (one Excel instance for all tests). If xlwings is missing, pytest skips those tests with `pytest.skip("xlwings not installed")`.

```python
# conftest.py:156-157
try:
    import xlwings as xw
except ImportError:
    pytest.skip("xlwings not installed — skip COM integration tests")
```

Integration tests that use xlwings fixtures:
- `test_api_ribbon.py` (line 6: `test_rates()`)
- `integration/test_erp_quote_image.py` (line 50: `@pytest.mark.skip`)
- `integration/test_erp_lane_mapper.py`
- `integration/test_erp_quote_flow.py`
- `integration/test_active_jobs_v4_end_to_end.py` — MOST COMPLETE

### Critical Finding #4: QuoteImage Integration Test SKIPPED

```python
# integration/test_erp_quote_image.py:45-49
@pytest.mark.skip(
    reason="QuoteImage VBA feature under v4 COL rework — tracked in "
           "docs/known-legacy-failures.md. Re-enable after QuoteImage is "
           "ported to the 40-col layout and selection logic is validated."
)
def test_quote_image_multi_route(erp_workbook):
```

Active Jobs v4 (40-col layout) changed the column positions, so QuoteImage VBA macro is not validated against the new layout. This is a KNOWN GAP documented in `docs/known-legacy-failures.md`.

---

## Feature Inventory

### Feature 1: Active Jobs v4 (40-col layout)

**What it does**: Full reordering of Active Jobs sheet columns from v13 36-col to v4 40-col (19 visible + 21 hidden). Visual styling (frozen panes, conditional formatting, tracking dots).

**Files**:
- `ERP/core/active_jobs_cols.py` — SINGLE SOURCE OF TRUTH for col indices
- `ERP/core/migrate_active_jobs_v4.py` — migration script (idempotent)
- `ERP/core/active_jobs_schema.py` — schema definitions
- `ERP/core/seed_test_jobs.py` — test data seeder

**Dependencies**: `ribbon_guard.py` (saves preserve CustomUI)

**Risk**: All Python helpers MUST use `COL` dict from `active_jobs_cols.py` — hard-coded col indices anywhere will break.

---

### Feature 2: Ribbon Guard (CustomUI Preservation)

**What it does**: Prevents openpyxl.save() from stripping `customUI/customUI14.xml` from .xlsm files.

**Files**:
- `ERP/core/ribbon_guard.py` — `save_preserving_ribbon(wb, erp_file)`
- `ERP/core/customui_utils.py` — re-injects ribbon XML

**Dependency**: Hard-coded paths to `D:\OneDrive\NelsonData\erp\` fallback.

**Risk**: If CustomUI_v14.xml is deleted from OneDrive, ribbon is permanently lost on next save.

---

### Feature 3: Price Watch / Re-quote Alert

**What it does**: Monitors PENDING quotes vs latest buy rates. Fires alert when carrier price drops >= threshold (default $50). Stamps Active Jobs col 39-40.

**Files**:
- `ERP/intelligence/price_watch.py` — main logic
- `ERP/intelligence/carrier_alias.py` — carrier name normalization

**Dependencies**: `carrier_alias.py` (Phase 02), `ribbon_guard.py`, `COL` from `active_jobs_cols.py`

**Risk**: Telegram notify disabled (2026-04-26). If alert fires, no one receives it unless they check the Price_Watch sheet manually.

---

### Feature 4: ETA Release Alert

**What it does**: Watches for jobs where `RELEASE_EMAIL_SENT` (col 37) is set but `RELEASE_CONFIRMED` (col 38) is blank >= 2 hours. Urgency escalates if ETA within 3 days.

**Files**:
- `ERP/jobs/release_alerts.py` — main logic
- `ERP/jobs/email_builder.py` — mailto: link builder

**Dependencies**: `COL` (col 37, 38), `ribbon_guard.py`

**Risk**: Exit code non-zero if P1 URGENT alert present — VBA could poll this.

---

### Feature 5: Quote Image Generator

**What it does**: Generates PNG quote images with split header, rate table (buy/sell/trend), wharfage section, footer.

**Files**:
- `ERP/quotes/image_generator.py` — matplotlib-based PNG generator
- `ERP/quotes/manager.py` — quote lifecycle
- `ERP/quotes/crm_quote_manager.py` — CRM quote manager

**Dependencies**: `WHARFAGE_FILE`, `MASTER_PRICING_FILE`, `logo_pudong.png`

**Status**: **SKIPPED in integration tests** — VBA not yet ported to v4 COL layout. See `docs/known-legacy-failures.md`.

**Risk**: If quote data has different POL-PLACE combinations, VBA duplicate-Dim error occurs (fixed in P4 but untested).

---

### Feature 6: Smart Send Window

**What it does**: Calculates UTC send time for B2B email optimal window (Tue-Thu 9-11h local). Avoids US holidays, Monday before 10h, Friday after 15h, weekends.

**Files**:
- `email_engine/core/smart_send_window.py` — `plan_send_time(contact_row, now_utc)`
- `tests/test_smart_send_window.py` — 10 scenario unit tests

**Dependencies**: `zoneinfo` (Python 3.9+), `pytz` fallback

**Risk**: Falls back to EST for unknown timezones. VN team using Tokyo TZ → falls back to EST → wrong send time.

---

### Feature 7: Daily Rotation Engine

**What it does**: Builds daily send plan of 700 emails distributed across commodity quotas. Enforces 7-day cooldown, 3-send/30d hard limit, excluded-email list. Auto-redistributes surplus.

**Files**:
- `email_engine/core/rotation_engine.py` — `build_daily_plan()`
- `email_engine/core/rotation_helpers.py` — helpers
- `email_engine/api/routes/rotation_router.py` — FastAPI endpoints
- `tests/test_rotation_engine.py` — 4 scenario unit tests

**Dependencies**: `load_master_df()`, `load_quota_config()`, `load_excluded_emails()`, `PLANS_DIR`

**Risk**: If `cnee_master.xlsx` is locked by another process, rotation engine fails silently (returns empty plan).

---

### Feature 8: Fast ID Generator

**What it does**: Auto-generates `FAST_ID` from last job in Active Jobs, format `NF-2605-001`.

**Files**:
- `ERP/jobs/fast_id.py` — `generate_next_fast_id()`
- `tests/test_fast_id.py` — unit tests

**Dependencies**: Direct Excel openpyxl read of Active Jobs sheet

**Risk**: Race condition if two processes generate IDs simultaneously.

---

### Feature 9: Carrier Rules Builder

**What it does**: Generates carrier-specific JSON rules (weight limits, OWS charges) from GW_Raw Excel files. 11 carriers covered: COSCO, EMC, HMM, HPL, MSC, MSK, ONE, YML, ZIM.

**Files**:
- `ERP/carrier_rules/builder.py` — JSON generator
- `ERP/carrier_rules/*.json` — per-carrier rules (11 files)
- `ERP/carrier_rules/weight_rules/*.json` — weight tier rules
- `tests/test_carrier_rules.py` — loader + normalization tests

**Dependencies**: `GW_Raw` Excel files in `ERP/data/`

**Risk**: If carrier weight rules Excel is missing, builder crashes.

---

### Feature 10: Transit Time Calculator

**What it does**: Calculates transit days per lane (HPH→USLGB = ~14 days, HCM→USLGB = ~16 days).

**Files**:
- `ERP/jobs/transit_time.py` — `calculate_transit_days(pol, pod)`
- `tests/unit/test_transit_time.py` — unit tests

**Risk**: Hard-coded transit days — not updated from actual carrier data.

---

### Feature 11: Reefer Plug Alert

**What it does**: Checks if shipped reefer jobs have recorded plug-in times. Missing plug-in = demurrage risk.

**Files**:
- `ERP/jobs/reefer_plug.py` — `check_reefer_plugs()`
- `tests/test_reefer_plug.py` — unit tests

**Dependencies**: Active Jobs col 33+ (Created_Date)

**Risk**: Only alerts — no automatic action.

---

### Feature 12: CNEE Milestone Tracker

**What it does**: Tracks CNEE milestones from emails → Active Jobs.

**Files**:
- `tests/test_cnee_milestone.py` — unit tests

**Dependencies**: Email parser, Active Jobs writer

---

### Feature 13: Email Sequence Intelligence

**What it does**: Multi-step email sequences with cooldown, follow-up, bounce handling.

**Files**:
- `email_engine/core/sequence_engine.py`
- `email_engine/core/follow_up_engine.py`
- `email_engine/core/bounce_knowledge.py`
- `email_engine/core/bounce_harvest_v2.py`
- `email_engine/core/reply_detector.py`
- `email_engine/core/reply_analyzer.py`

**Dependencies**: `llm_client.py` (OpenAI/Gemini), `queue_store.py`

**Risk**: LLM client requires API key — if missing, sequence falls back to template-only.

---

### Feature 14: Market Intelligence

**What it does**: Price prediction, anomaly detection, pattern learning from rate history.

**Files**:
- `email_engine/intelligence/market_engine.py`
- `email_engine/intel/tier_engine.py`
- `email_engine/intel/pattern_learner.py`
- `email_engine/core/rate_predictor.py`
- `tests/test_anomaly_detector.py` — **custom runner, not pytest-compatible**

**Dependencies**: Parquet ~6.6M rows, DuckDB

**Risk**: `rate_predictor.py` has no unit tests. Anomaly detector uses custom runner → invisible to pytest.

---

### Feature 15: API Bridge (VBA → Python → FastAPI)

**What it does**: VBA calls Python CLI via Shell(), which calls Nelson API. Enables Excel → API → DuckDB → Parquet flow.

**Files**:
- `api/erp_api_bridge.py` — CLI entry point (`refresh`, `create_quote`, `check_status`)
- `api/routers/erp_router.py` — FastAPI router

**Dependencies**: `NELSON_API_URL`, `NELSON_API_KEY` env vars

**Risk**: Fallback to `urllib` if `httpx` missing. No retry logic. No auth token refresh.

---

## Conflict Matrix — Which Features Can Break Which

| Feature | Can Break | Mechanism |
|---------|-----------|-----------|
| Active Jobs v4 migration | QuoteImage VBA | VBA still uses old 36-col positions |
| Active Jobs v4 migration | Price Watch | Needs COL dict alignment |
| Smart Send Window TZ | Rotation Engine | Wrong TZ → email sent at wrong time |
| Carrier alias changes | Price Watch | Wrong normalization → missed alerts |
| Ribbon Guard failure | ALL features writing ERP | CustomUI disappears from Excel |
| xlwings update (Excel close) | All xlwings tests | COM session dies mid-test |
| Parquet file missing | DuckDB, Rate Router, Anomaly | Empty results, no error |
| cnee_master.xlsx locked | Rotation Engine | Silent failure → empty plan |

---

## Root Cause Analysis — "Test Pass but Code Wrong"

### Pattern 1: Custom Test Runner Tests Never Run in pytest

**Root cause**: 7 files use `for test in tests: test(); sys.exit(1) on fail` pattern. pytest doesn't collect/execute them as tests — it only sees them as modules. They must be run as standalone scripts.

**Why it passes**: You run `pytest` and see "all passed" because pytest never runs those files. When you run them manually `python test_duckdb_engine.py` you get real results.

**Fix**: Convert all custom runners to pytest fixtures. Add `--tb=no -q` to suppress noise. Add a pre-commit hook to run `pytest tests/ --collect-only` to verify all tests are collectible.

### Pattern 2: Integration Tests Depend on Live OneDrive File

**Root cause**: `conftest.py:MASTER_XLSM = "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"` — if Nelson is working on the file, tests overwrite it.

**Why**: `erp_copy` and `seeded_erp` fixtures copy the live file to `tmpdir`, mutate freely, then `tmp_path` cleans up. But if the live file is open in Excel (COM session), openpyxl fails with "file locked".

**Fix**: Use `LockFile` check before copy. Add `ERPCOPY_IS_SEEDED=1` env to skip seeding if already done.

### Pattern 3: QuoteImage VBA Not Ported to v4

**Root cause**: `integration/test_erp_quote_image.py` is SKIPPED because VBA uses old col layout. No CI catches if VBA breaks.

**Why**: VBA lives on OneDrive (not in repo). Can't validate without Excel COM.

**Fix**: Add a monthly VBA audit step. Track in `docs/known-legacy-failures.md`.

### Pattern 4: Price Watch Telegram Disabled

**Root cause**: `price_watch.py:46` sets `_telegram_send = None` — alerts go to sheet only.

**Impact**: If rate drops significantly, Nelson only sees it if they open ERP and check Price_Watch sheet.

**Fix**: Re-enable Telegram or add webhook to notify.

---

## Recommendations

### Priority 1 — Fix Test Infrastructure (CRITICAL)

1. **Convert all custom runners to pytest**:
   - Replace `for test in tests: try: test(); passed+=1` loop with pytest functions
   - Remove `sys.exit(1)` from any pytest test (it exits pytest itself)
   - Keep `if __name__ == "__main__": sys.exit(main())` only in pure COM standalone scripts, move them out of `tests/`

2. **Add test collection verification**:
   ```bash
   # Add to pre-commit
   pytest tests/ --collect-only -q
   ```
   Should show "44 tests collected" (or similar). If fewer, something is broken.

3. **Move standalone COM scripts** out of `tests/` to `scripts/com-e2e/`:
   - `test_v13_ribbon.py` → `scripts/com-e2e/v13_ribbon_e2e.py`
   - `test_erp_e2e.py` → `scripts/com-e2e/erp_e2e.py`

4. **Fix test_v13_ribbon.py hardcoded path**: Change from `PricingSystem\Engine_test\` to `OneDrive\NelsonData\erp\`.

### Priority 2 — QuoteImage VBA Port (HIGH)

1. Run `python ERP/core/migrate_active_jobs_v4.py --dry-run` to verify 40-col layout
2. Update VBA `OnAction_QuoteImage` to use new col indices (mirror `active_jobs_cols.py`)
3. Re-enable `test_erp_quote_image.py::test_quote_image_multi_route`

### Priority 3 — Add Missing Unit Tests (MEDIUM)

Files with zero test coverage:
- `ERP/jobs/shipment_tracker.py`
- `ERP/jobs/carrier_performance.py`
- `ERP/jobs/create_from_quote.py`
- `ERP/jobs/delay_tracker.py`
- `ERP/jobs/analyze_shipments.py`
- `ERP/intelligence/tracking_manager.py`
- `ERP/intelligence/sailing_schedule.py`
- `ERP/intelligence/spot_cache.py`
- `email_engine/core/auto_rate_builder.py`
- `email_engine/core/sequence_engine.py`

### Priority 4 — DuckDB Query Isolation (MEDIUM)

All DuckDB queries go through `db/duckdb_engine.py` — good. But `data_access.py` has direct Parquet reads. Consolidate all Parquet access through `FreightDB` class to prevent dual behavior.

### Priority 5 — API Bridge Resilience (LOW)

`erp_api_bridge.py` fallback to `urllib` works but has no retry. Add 3 retries with exponential backoff for network failures.

---

## Files Analyzed

### ERP Core (Python)
- `ERP/core/active_jobs_cols.py` — COL dict, 40 cols
- `ERP/core/ribbon_guard.py` — CustomUI preservation
- `ERP/core/migrate_active_jobs_v4.py` — v4 migration script
- `ERP/core/control.py` — master control menu
- `ERP/core/customui_utils.py` — ensure_customui
- `ERP/core/active_jobs_schema.py` — schema defs
- `ERP/core/seed_test_jobs.py` — test seeder

### ERP Jobs
- `ERP/jobs/email_builder.py` — mailto: builder
- `ERP/jobs/release_alerts.py` — ETA release alerts
- `ERP/jobs/enrichment.py` — data enrichment
- `ERP/jobs/transit_time.py` — transit calculator
- `ERP/jobs/fast_id.py` — Fast ID generator
- `ERP/jobs/reefer_plug.py` — reefer alerts

### ERP Intelligence
- `ERP/intelligence/price_watch.py` — re-quote alerts
- `ERP/intelligence/daily_sync.py` — daily sync
- `ERP/intelligence/carrier_alias.py` — alias normalization
- `ERP/intelligence/cost_addons.py` — cost addon calculator
- `ERP/intelligence/monthly_report.py` — monthly report
- `ERP/intelligence/weekly_report.py` — weekly report

### ERP Quotes
- `ERP/quotes/image_generator.py` — quote PNG generator
- `ERP/quotes/manager.py` — quote manager

### API Layer
- `api/erp_api_bridge.py` — VBA-Python bridge
- `api/routers/job_router.py` — job endpoints
- `api/data_access.py` — data access layer

### DuckDB
- `db/duckdb_engine.py` — DuckDB query engine

### Email Engine
- `email_engine/core/rotation_engine.py` — daily rotation
- `email_engine/core/smart_send_window.py` — send time planner
- `email_engine/api/routes/rotation_router.py` — rotation API

### Carrier Rules
- `ERP/carrier_rules/builder.py` — JSON builder

### Test Infrastructure
- `pytest.ini` — pytest config
- `tests/conftest.py` — fixtures
- `tests/test_v13_ribbon.py` — COM script (not pytest)
- `tests/test_erp_e2e.py` — COM script (not pytest)
- `tests/test_duckdb_engine.py` — custom runner
- `tests/test_normalization.py` — custom runner
- `tests/test_anomaly_detector.py` — custom runner
- `tests/test_rotation_engine.py` — proper pytest
- `tests/test_smart_send_window.py` — proper pytest
- `tests/integration/test_active_jobs_v4_end_to_end.py` — integration

### VBA Mirror
- `ERP/vba-v14-mirror/*.bas` — VBA source mirrors