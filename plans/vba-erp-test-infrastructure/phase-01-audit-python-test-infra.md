---
phase: 1
title: "Audit Python Test Infra"
status: completed
priority: P1
effort: "1h"
dependencies: []
---

# Phase 1: Audit Python Test Infra

## Overview
Baseline: document exact state of test infrastructure, separate pytest-compatible tests from COM-only scripts.

## Requirements
- Functional: Identify all 7 files with `sys.exit`, separate COM scripts from pytest tests
- Non-functional: Preserve all test logic, no test deletion

## Architecture
N/A — audit only

## Related Code Files
| File | Issue |
|------|-------|
| `tests/test_duckdb_engine.py` | Has `def test_*` functions + `if __name__` custom runner |
| `tests/test_anomaly_detector.py` | Has `def test_*` functions + `for test in tests` loop |
| `tests/test_normalization.py` | Has `def test_*` functions + `for test in tests` loop |
| `tests/test_parquet_upgrader.py` | Has `def test_*` functions + `for test in tests` loop |
| `tests/test_rate_router.py` | Has `def test_*` functions + `for test in tests` loop |
| `tests/test_v13_ribbon.py` | COM-only script (no pytest functions), hardcoded wrong path |
| `tests/test_erp_e2e.py` | COM script with pytest functions, runs via `sys.exit(main())` |

## Implementation Steps

1. **Baseline pytest collection count** — run `pytest tests/ --collect-only -q 2>&1 | tail -3` record number
2. **Move COM scripts** to `scripts/com-e2e/`:
   - `tests/test_v13_ribbon.py` → `scripts/com-e2e/v13_ribbon_e2e.py`
   - `tests/test_erp_e2e.py` → `scripts/com-e2e/erp_e2e.py`
3. **Fix wrong path** in `scripts/com-e2e/v13_ribbon_e2e.py`: change `PricingSystem\Engine_test\` → `OneDrive\NelsonData\erp\`
4. **Re-run pytest collection** — confirm count unchanged (COM scripts had no pytest tests)
5. **Document findings** in `docs/test-infrastructure-audit.md`

## Success Criteria
- [ ] `pytest tests/ --collect-only -q` shows same count before and after moving COM scripts
- [ ] COM scripts still runnable: `python scripts/com-e2e/v13_ribbon_e2e.py`
- [ ] `docs/test-infrastructure-audit.md` lists all 7 problem files with fix strategy

## Risk Assessment
- **Risk**: Moving files breaks imports in other scripts
- **Mitigation**: Only move files confirmed as standalone COM scripts, no shared imports
