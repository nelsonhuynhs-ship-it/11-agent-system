---
phase: 3
title: "PR Status Report Integration"
status: pending
priority: P2
effort: "1h"
dependencies: [1]
---

# Phase 3: PR Status Report Integration

## Overview
GitHub Actions summary hiển thị test results rõ ràng trong PR conversation — pass/fail per job.

## Requirements
- Functional: PR checks hiển thị pytest + COM E2E status riêng
- Non-functional: Report phải đọc được trên mobile GitHub app

## Architecture

```
GitHub Actions jobs:
  pytest     → [✓] 709 tests passed (2m 14s)
  com-e2e    → [✓] v14_ribbon_e2e.py passed (3m 02s)
  vba-check  → [✓] All bas files have TestModule (0m 03s)
```

## Related Code Files
- Modify: `.github/workflows/ci-regression.yml` (thêm vba-check job)
- Create: `scripts/check-vba-convention.py` (từ Phase 2)

## Implementation Steps
1. Thêm `vba-check` job vào workflow
2. Config GitHub Actions annotations cho pytest failures
3. Test với actual PR

## Success Criteria
- [ ] pytest failure → hiển thị trực tiếp trên PR (not just logs)
- [ ] COM E2E failure → link đến runner logs
- [ ] All green → "Ready to merge" status

## Risk Assessment
- **Risk**: GitHub token permissions cần `checks: write`
- **Mitigation**: Workflow phải được admin approve lần đầu