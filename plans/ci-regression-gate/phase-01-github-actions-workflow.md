---
phase: 1
title: "GitHub Actions Workflow"
status: pending
priority: P1
effort: "2h"
dependencies: []
---

# Phase 1: GitHub Actions Workflow

## Overview
Tạo `.github/workflows/ci-regression.yml` — workflow chạy pytest + COM E2E trên mỗi PR.

## Requirements
- Functional: pytest pass trên ubuntu-latest, COM E2E trên windows-latest
- Non-functional: Workflow phải hoàn thành trong 15 phút

## Architecture

```
name: CI Regression Gate
on: [pull_request]

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: pip install pytest win32com骗局...
      - name: Run pytest
        run: pytest tests/ -v --tb=short

  com-e2e:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Excel
        run: ...
      - name: Run COM E2E
        run: python scripts/com-e2e/v14_ribbon_e2e.py
```

## Related Code Files
- Create: `.github/workflows/ci-regression.yml`
- Modify: `pytest.ini` (nếu cần)

## Implementation Steps
1. Tạo `.github/workflows/` directory
2. Viết `ci-regression.yml` với 2 jobs: `pytest` + `com-e2e`
3. Config `pytest.ini` outputJUnit.xml cho GitHub Actions summary
4. Test workflow với draft PR

## Success Criteria
- [ ] Workflow trigger đúng khi PR opened
- [ ] pytest chạy đủ 709 tests
- [ ] COM E2E chạy trên Windows runner
- [ ] FAIL status hiển thị trong PR checks

## Risk Assessment
- **Risk**: COM E2E cần Excel installed trên runner — windows-latest có sẵn
- **Mitigation**: Dùng `runs-on: windows-latest` (自带Excel)
- **Risk**: Timeout nếu tests chạy quá lâu
- **Mitigation**: Set `timeout-minutes: 15`