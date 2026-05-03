---
phase: 0
title: "CI Regression Gate — VBA/Python Test Automation"
status: pending
priority: P1
effort: "4h"
dependencies: []
---

# Plan: CI Regression Gate

**Mục tiêu:** Mỗi PR tự động chạy pytest + COM E2E, FAIL nếu regression. Feature mới không được gây hỏng hệ thống.

## Problem Statement

- Hiện tại: pre-commit hook chỉ check `pytest --collect-only` và `sys.exit(1)` — không chạy tests thật
- VBA Rubberduck tests: developer-time only, không CI
- Không có automated gate khi PR được tạo → regression có thể merge vào main

## Architecture

```
PR opened → GitHub Actions trigger
  → pytest: run all tests (709 tests)
  → COM E2E smoke: run v14_ribbon_e2e.py (Excel COM)
  → VBA convention check: bas<Feature>.bas → TestModule_<Feature>.bas paired
  → PASS → allow merge
  → FAIL → block merge, report to PR
```

## 3 Phases

| # | Phase | Priority | Effort | Status |
|---|-------|---------|--------|--------|
| 1 | [GitHub Actions Workflow](phase-01-github-actions-workflow.md) | P1 | 2h | pending |
| 2 | [VBA Test Convention Checker](phase-02-vba-test-convention-checker.md) | P2 | 1h | pending |
| 3 | [PR Status Report Integration](phase-03-pr-status-report-integration.md) | P2 | 1h | pending |

## Key Rules

1. **pytest MUST pass 100%** — any failure blocks merge
2. **COM E2E smoke test** — run v14_ribbon_e2e.py on Windows runner
3. **VBA convention** — bas<Feature>.bas must have TestModule_<Feature>.bas
4. **No coverage requirement** (yet) — enforce presence, not depth

## Test Infrastructure Stack

| Test Type | Runner | Gate |
|-----------|--------|------|
| Python pytest (709 tests) | GitHub Actions `ubuntu-latest` | REQUIRED |
| COM E2E (v14_ribbon_e2e.py) | GitHub Actions `windows-latest` + Excel | REQUIRED |
| VBA Rubberduck | Developer-time only | N/A (manual) |