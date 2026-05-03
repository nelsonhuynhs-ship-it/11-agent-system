---
phase: 2
title: "VBA Test Convention Checker"
status: pending
priority: P2
effort: "1h"
dependencies: [1]
---

# Phase 2: VBA Test Convention Checker

## Overview
Pre-commit hook kiểm tra mỗi `bas<Feature>.bas` file mới có `TestModule_<Feature>.bas` cùng tồn tại.

## Requirements
- Functional: Hook fail nếu thêm bas mới mà không có test module tương ứng
- Non-functional: Không delay commit nếu convention đã pass

## Architecture

```
pre-commit hook (Python script):
  1. git diff --name-only → lấy danh sách .bas files mới/thay đổi
  2. Filter files bắt đầu bằng "bas" (not TestModule_)
  3. Với mỗi bas file → check TestModule_<Name>.bas tồn tại
  4. FAIL nếu có bas file không có test module
```

## Related Code Files
- Create: `scripts/check-vba-convention.py` (pre-commit hook entry)
- Modify: `.pre-commit-config.yaml` (thêm VBA convention hook)

## Implementation Steps
1. Viết `scripts/check-vba-convention.py`
2. Thêm entry vào `.pre-commit-config.yaml`
3. Test: tạo bas file mà không có test → hook phải fail

## Success Criteria
- [ ] Hook pass khi bas + TestModule cùng tồn tại
- [ ] Hook fail khi bas file mới thiếu TestModule
- [ ] Không false positive cho existing files

## Risk Assessment
- **Risk**: Hook block legitimate refactor (đổi tên bas file)
- **Mitigation**: Chỉ check files trong `ERP/vba-v14-mirror/`, không check toàn repo