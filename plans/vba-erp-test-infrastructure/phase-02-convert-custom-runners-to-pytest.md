---
phase: 2
title: "Convert Custom Runners to pytest"
status: completed
priority: P1
effort: "3h"
dependencies: [1]
---

# Phase 2: Convert Custom Runners to pytest

## Overview
Convert 5 remaining test files from custom runner pattern (`for test in tests: test(); sys.exit(1)`) to proper pytest. All files already have `def test_*()` functions — custom runner code in `if __name__ == "__main__"` blocks must be removed.

## Requirements
- Functional: All `def test_*()` functions remain, custom runner code removed
- Non-functional: `pytest tests/` must collect and run all tests after conversion

## Architecture
Pattern: strip `if __name__ == "__main__":` block and `for test in tests:` loops from each file. Keep only `def test_*()` functions and `import pytest` (if present).

## Related Code Files
| File | Pattern to Remove |
|------|-------------------|
| `tests/test_duckdb_engine.py` | `if __name__ == "__main__":` block with `sys.exit(1)` |
| `tests/test_anomaly_detector.py` | `for test in tests:` loop + `sys.exit(1)` |
| `tests/test_normalization.py` | `for test in tests:` loop + `sys.exit(1)` |
| `tests/test_parquet_upgrader.py` | `for test in tests:` loop + `sys.exit(1)` |
| `tests/test_rate_router.py` | `for test in tests:` loop + `sys.exit(1)` |

## Implementation Steps

For each of the 5 files:

1. **Read the file** — identify start/end of custom runner code
2. **Remove** the `if __name__ == "__main__":` block and/or `for test in tests:` loop
3. **Keep** all `def test_*():` function definitions
4. **Keep** module-level imports, helper functions, fixtures
5. **Verify**: `pytest tests/test_<filename>.py --collect-only -q` shows test count > 0
6. **Run**: `pytest tests/test_<filename>.py -v --tb=short` all pass

**Example surgical edit** (test_normalization.py):
```
# REMOVE lines ~191-224:
# if __name__ == "__main__":
#     tests = [test_hpl_fak, test_hpl_fix_40, ...]
#     for test in tests:
#         try: test()
#         except: failed += 1
#     sys.exit(1)
```

## Success Criteria
- [ ] All 5 files pass `pytest tests/test_<name>.py -v` with 0 failures
- [ ] `pytest tests/ --collect-only -q` total count increases (previously invisible tests now collected)
- [ ] No `sys.exit()` calls remain in any `tests/test_*.py` file

## Risk Assessment
- **Risk**: Some `def test_*` functions may have side effects that the custom runner depended on (e.g., setup/teardown mixed into test body)
- **Mitigation**: Run full suite after each file conversion, check for new failures
- **Risk**: `sys.exit(1)` in `if __name__` block also exits pytest if somehow executed in pytest context (should not happen, but verify)
- **Mitigation**: Remove entirely — pytest handles exit codes automatically
