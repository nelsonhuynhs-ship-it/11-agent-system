---
phase: 0
title: "VBA ERP Test Infrastructure"
status: completed
priority: P1
effort: "12h"
dependencies: []
---

# Plan: VBA ERP Test Infrastructure

**Mục tiêu:** Mỗi feature mới (Python hoặc VBA) đều có E2E test coverage, không regression.

## Problem Statement
- 7 Python test files dùng `sys.exit(1)` custom runner → INVISIBLE to pytest
- 2 COM script nằm trong `tests/` → không phải pytest
- `erp-v14-ribbon-callbacks.bas` 1600 lines → mix UI + logic (cần tách)
- VBA có 0 unit tests (Rubberduck chưa dùng)

## 5 Phases

| # | Phase | Priority | Effort | Status |
|---|-------|---------|--------|--------|
| 1 | [Audit Python Test Infra](phase-01-audit-python-test-infra.md) | P1 | 1h | ✅ |
| 2 | [Convert Custom Runners to pytest](phase-02-convert-custom-runners-to-pytest.md) | P1 | 3h | ✅ |
| 3 | [Refactor VBA Ribbon Modules](phase-03-refactor-vba-ribbon-modules.md) | P1 | 4h | ✅ |
| 4 | [Add VBA Rubberduck Test Scaffold](phase-04-add-vba-rubberduck-test-scaffold.md) | P2 | 2h | ✅ |
| 5 | [E2E Coverage Gate](phase-05-e2e-coverage-gate.md) | P1 | 2h | ✅ |

## Architecture: Two-Track Testing

```
Python Feature
  → tests/integration/test_<feature>.py   ← CI gate (pytest)
  → scripts/com-e2e/                      ← COM smoke (manual)

VBA Feature
  → bas<Feature>.bas                      ← feature module
  → TestModule_<Feature>.bas              ← Rubberduck (developer-time)
```

## Key Rules
1. **Python**: `pytest tests/ --collect-only -q` phải pass (pre-commit hook)
2. **VBA**: feature module mới = Rubberduck test module bắt buộc
3. **Không `sys.exit(1)`** trong bất kỳ `tests/test_*.py` nào

## Test Infrastructure Root Cause
- 7 files: custom runner loop `for test in tests:` + `sys.exit(1)` → pytest không chạy
- Fix: xóa custom runner, giữ nguyên `def test_*()` functions
