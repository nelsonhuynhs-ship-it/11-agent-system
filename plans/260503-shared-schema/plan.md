---
title: "Shared Schema — SOLE Data Contract for Multi-CLI Workspace"
description: "SHARED_SCHEMA.md là Single Source of Truth về data schema + business rules, dùng chung cho email_engine + ERP + pricing_engine trong 3 CLI độc lập"
status: pending
priority: P1
branch: "main"
tags: []
blockedBy: []
blocks: []
created: "2026-05-03T03:30:00.000Z"
createdBy: "ck:plan"
source: skill
---

# Shared Schema — SOLE Data Contract for Multi-CLI Workspace

## Overview

Tạo `docs/SHARED_SCHEMA.md` — Single Source of Truth về data schema + business rules — cho 3 Claude Code CLI độc lập (email_engine/ERP/pricing_engine). File này thay thế việc mỗi CLI phải tự khám phá schema từ code.

**Mục tiêu:** 3 CLI độc lập cùng hiểu 1 data contract, không cần copy schema sang nhiều chỗ.

## Phases

| Phase | Name | Priority | Effort | Description |
|-------|------|----------|--------|-------------|
| 1 | [phase-01-audit.md](./phase-01-audit.md) | P1 | 1h | Audit tất cả schema definitions hiện có trong docs + code |
| 2 | [phase-02-consolidate.md](./phase-02-consolidate.md) | P1 | 2h | Consolidate thành SHARED_SCHEMA.md duy nhất |
| 3 | [phase-03-coordination.md](./phase-03-coordination.md) | P2 | 1h | Tạo coordination file + batch launcher templates |

**Total estimated: ~4h**

## Dependencies

<!-- None — plan is self-contained -->

## Cross-Reference

- `email_engine/config/commodity_groups.yaml` — commodity group definitions (source of truth)
- `email_engine/core/rule_engine.py` — ARB_MAPPING + resolve_config()
- `docs/MASTER_V7_SCHEMA.md` — CNEE master schema (sẽ được tham chiếu trong SHARED_SCHEMA.md, không replace)
- `docs/ARB_ORIGIN_MAPPING.md` — ARB origin rules (sẽ được tham chiếu trong SHARED_SCHEMA.md, không replace)

## Verification

1. `cat docs/SHARED_SCHEMA.md` — file tồn tại, >100 lines
2. 3 CLI đều có thể đọc file này khi start
3. SHARED_SCHEMA.md không duplicate nội dung từ MASTER_V7_SCHEMA.md và ARB_ORIGIN_MAPPING.md — chỉ reference/link
4. Coordination file tồn tại tại `D:/OneDrive/NelsonData/coordination/active-sessions.md`
