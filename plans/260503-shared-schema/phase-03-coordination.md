---
phase: 3
title: "Create Coordination Infrastructure"
status: pending
priority: P2
effort: "1h"
dependencies: []
---

# Phase 3: Coordination Infrastructure

## Overview

Tạo coordination file + 3 batch launcher để 3 CLI độc lập có thể start nhanh và tránh conflict.

## Requirements
- Functional: Batch files launch 3 CLI độc lập, coordination file track ai đang làm gì
- Non-functional: Không cần code changes, chỉ tạo file text và batch

## Architecture

**Coordination File:** `D:/OneDrive/NelsonData/coordination/active-sessions.md`

```markdown
# Active CLI Sessions
Last updated: 2026-05-03

| CLI | Project | Status | Current Feature | Last Update | Branch |
|-----|---------|--------|----------------|-------------|--------|
| CLI-1 | EmailEngine | 🔄 | commodity grouping v2 | 11:30 | claude/cli-1-email |
| CLI-2 | ERPEngine | ⏳ | — | 11:25 | claude/cli-2-erp |
| CLI-3 | PricingEngine | ⏳ | — | — | claude/cli-3-pricing |

---

## Commit Log (2026-05-03)

| Time | CLI | Action | Files |
|------|-----|--------|-------|
| 11:28 | CLI-1 | commit | email_engine/core/rule_engine.py |
```

**Batch Launchers:** 3 `.bat` files trong `D:/NELSON/Batch/`

```bat
# start_email.bat
start "Claude-Email" cmd /k "cd /d D:\NELSON\Projects\EmailEngine && claude"
```

## Implementation Steps

1. Tạo `D:/OneDrive/NelsonData/coordination/active-sessions.md` (coordination file)
2. Tạo `D:/NELSON/Batch/start_email.bat`
3. Tạo `D:/NELSON/Batch/start_erp.bat`
4. Tạo `D:/NELSON/Batch/start_pricing.bat`
5. Test: chạy 1 batch → verify Claude CLI start đúng directory
6. Tạo `D:/OneDrive/NelsonData/coordination/commit-log.md` template

## Related Code Files
- Create: `D:/OneDrive/NelsonData/coordination/active-sessions.md`
- Create: `D:/OneDrive/NelsonData/coordination/commit-log.md`
- Create: `D:/NELSON/Batch/start_email.bat`
- Create: `D:/NELSON/Batch/start_erp.bat`
- Create: `D:/NELSON/Batch/start_pricing.bat`

## Success Criteria
- [ ] 3 batch files tồn tại trong `D:/NELSON/Batch/`
- [ ] Double-click batch → Claude CLI start ở đúng directory
- [ ] Coordination file mở bằng Notepad được, format markdown rõ ràng

## Risk Assessment
- Risk: 3 CLI cùng edit 1 file → conflict git
- Mitigation: Mỗi CLI checkout branch riêng, coordination file track ai đang làm gì

---

**Output:** 5 files created (1 coordination + 1 commit-log + 3 batch)
