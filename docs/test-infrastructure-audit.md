# Test Infrastructure Audit

**Date**: 2026-05-03
**Baseline pytest**: 656 tests collected (1 pre-existing import error)

## Problem Summary

7 Python test files used custom runner pattern (`for test in tests: test(); sys.exit(1)`) making them invisible to pytest. 2 files were pure COM scripts with no pytest tests at all.

## Files Fixed in Phase 1

| File | Action | Result |
|------|--------|--------|
| `tests/test_v13_ribbon.py` | Wrapped module-level code in `if __name__ == "__main__"` | No longer crashes pytest; moved copy to `scripts/com-e2e/v13_ribbon_e2e.py` |
| `tests/test_erp_e2e.py` | Removed `if __name__ == "__main__": sys.exit(main())` | 10 pytest tests now visible; copy moved to `scripts/com-e2e/erp_e2e_com.py` |

## Remaining Custom Runner Files (Phase 2)

| File | Pattern | Status |
|------|---------|--------|
| `tests/test_duckdb_engine.py` | `if __name__` block with `sys.exit(1)` | Pending Phase 2 |
| `tests/test_anomaly_detector.py` | `for test in tests:` loop + `sys.exit(1)` | Pending Phase 2 |
| `tests/test_normalization.py` | `for test in tests:` loop + `sys.exit(1)` | Pending Phase 2 |
| `tests/test_parquet_upgrader.py` | `for test in tests:` loop + `sys.exit(1)` | Pending Phase 2 |
| `tests/test_rate_router.py` | `for test in tests:` loop + `sys.exit(1)` | Pending Phase 2 |

## Pre-existing Issue (Not in scope)

`tests/integration/test_market_report_generator.py` has `ModuleNotFoundError: No module named 'Pricing_Engine'`. This is a broken import unrelated to the custom runner issue. Recommend either fixing the import path or removing the file from pytest collection via `pytest.ini`.
