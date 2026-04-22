# Phase 1 Regression Test Report
**Date:** 2026-04-14
**Engineer:** Test Runner Agent
**Suite:** pytest | **Python:** 3.13.5 / Anaconda | **openpyxl:** 3.1.5

---

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 135 |
| Passed | 135 |
| Failed | 0 |
| Skipped | 0 |
| Duration | 623s (10m 23s) |
| Status | **PASS** |

---

## Test Files Added

| File | Tests | Module Covered |
|------|-------|----------------|
| `tests/conftest.py` | fixtures only | Shared: erp_copy, seeded_erp, sample_rules |
| `tests/test_ribbon_guard.py` | 5 | `ERP/core/ribbon_guard.py` |
| `tests/test_active_jobs_schema.py` | 8 | `ERP/core/active_jobs_schema.py` |
| `tests/test_monthly_report.py` | 26 | `ERP/intelligence/monthly_report.py` |
| `tests/test_price_watch.py` | 11 | `ERP/intelligence/price_watch.py` |
| `tests/test_email_builder.py` | 25 | `ERP/jobs/email_builder.py` |
| `tests/test_enrichment.py` | 13 | `ERP/jobs/enrichment.py` |
| `tests/test_shipment_tracker.py` | 21 | `ERP/jobs/shipment_tracker.py` |
| `tests/test_release_alerts.py` | 17 | `ERP/jobs/release_alerts.py` |

---

## Bugs Found and Fixed During Test Writing

### Bug 1: price_watch.py — CONT_TO_PRICE_COL key mismatch (test fixture bug, not module bug)
- **What:** `CONT_TO_BUY_COL` iterates using keys like `"40HC"` but `CONT_TO_PRICE_COL["40HC"]` resolves to `price_cont="40HQ"`. The pricing_latest dict key uses `"40HQ"`, not `"40HC"`.
- **Root cause:** Both `40HC` and `40HQ` map to the same `Buy_40HC` column and same `price_cont="40HQ"`. The module is correct — the initial test helper used the wrong key.
- **Fix applied:** Test helper `_make_pricing_dict` corrected to use `"40HQ"` as cont key.
- **Tests fixed:** 5 tests in `TestComputeAlertsDropRise` + `test_inland_pricing_matches_inland_quote`

### Bug 2: ribbon_guard.py — openpyxl 3.1+ behavior change (test expectation bug)
- **What:** `test_plain_save_strips_ribbon` expected openpyxl plain save to strip customUI14.xml. On openpyxl 3.1.5 (Python 3.13 environment), plain save PRESERVES the ribbon.
- **Root cause:** Historic bug was fixed in openpyxl 3.1+. Test was documenting old behavior.
- **Fix applied:** Test renamed `test_plain_save_ribbon_behavior_documented`, now verifies correct behavior per installed version. `save_preserving_ribbon()` remains necessary for older openpyxl or canonical XML content refresh.
- **No module change needed.**

---

## Coverage Notes by Module

### ribbon_guard.py (5 tests)
- Covers: plain-save behavior (versioned), save_preserving_ribbon injection, idempotent double-inject, graceful fallback on missing XML/util
- Gap: No test for `reinject_ribbon()` with valid xml_path but bad xlsm (corrupt file)

### active_jobs_schema.py (8 tests)
- Covers: all 6 headers added, col letter math, order verification, idempotency (2 runs), ribbon preservation, file-not-found, data-row preservation
- Gap: No test for concurrent write (permission error path)

### monthly_report.py (26 tests)
- Covers: parse_month 7 variants, extract_volume 8 scenarios, write_report structure (headers row 3/4, data row 5, TOTAL row, 24-col), filter_by_month 3 scenarios
- Gap: No test for multi-sheet workbook output or very large row sets

### price_watch.py (11 tests)
- Covers: DROP/RISE alert firing, threshold boundary (exact + below), route/customer population, no-buy-rate skip, place-matching regression (inland vs direct), load_latest_pricing, empty pricing sheet
- Gap: No test for stamp_quotes_sheet or write_price_watch_sheet formatting

### email_builder.py (25 tests)
- Covers: build_subject (4 scenarios), build_email_body (12 scenarios — reefer temp, DRY no-reefer, HPH no-MT, HCM MT, CMA payment_term, ONE no-extra, POL/POD, volume, greeting, closing, contract, reefer contract prefix), build_mailto_link (7 scenarios)
- Gap: No test for SOC subject flag

### enrichment.py (13 tests)
- Covers: parse_routing (5 variants), col 28 mailto population, hyperlink format validation, col 31 SERVICE fill, CY-DOOR/CY-CY logic, no-force skip, force overwrite, stats total, FileNotFoundError
- Gap: No test for PermissionError path

### shipment_tracker.py (21 tests)
- Covers: _is_set (6 variants), compute_stage all 7 stages (15 tests including highest-wins, stage7-beats-all, stage names), update_active_jobs integration (format, stage sum = total, dry-run no-write, FileNotFoundError)
- Gap: No test for very large workbooks (performance)

### release_alerts.py (17 tests)
- Covers: classify (8 unit tests — URGENT/WARN/INFO, boundary, countdown sign), _format_countdown (3 tests), scan_alerts integration (URGENT on 3h elapsed, no alert when confirmed, no alert outside ETA window, WARN at 50% deadline, no-email-sent skip, elapsed_hours accuracy)
- Gap: No test for write_alerts_sheet sheet formatting

---

## Notes for Follow-Up Agents (F4/F6/F7/F8/F9/F10)

- `seeded_erp` fixture in conftest seeds rows 8-14. F-agents adding new rows should start from row 15+.
- The `erp_copy` fixture uses `function` scope — each test gets a fresh copy. Tests run in ~10m total due to multiple ERP copies/saves per test.
- Performance improvement possible: collapse seeded_erp tests that only read into a single `scope="module"` copy (not done to keep tests independent).
- `test_ribbon_guard.py::test_plain_save_ribbon_behavior_documented` is the canary test — if it fails on a future openpyxl downgrade, ribbon stripping has returned.
