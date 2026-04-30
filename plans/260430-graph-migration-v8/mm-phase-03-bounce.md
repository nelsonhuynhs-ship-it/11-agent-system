# Task: Phase 3 — Bounce KB DSN Parser RFC 3464

## Context
Plan: 260430-graph-migration-v8
Phase: 3
Invoked by: ck:workflow
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 3 theo spec: `plans/260430-graph-migration-v8/phase-03-bounce-kb-dsn-parser.md`

**Mục tiêu:** Replace COM-based bounce parsing trong bounce_handler.py bằng RFC 3464 DSN parser. Feed từ Phase 1 webhook.

## Files MODIFY
1. `email_engine/core/bounce_handler.py` — REWRITE:
   - Bỏ import win32com
   - Input: Graph message JSON (từ webhook)
   - Output: structured bounce record vào data/bounce_kb.db
   - Implement RFC 3464 multipart/report parsing
   - Auto-suppression: hard bounce → suppress ngay, soft bounce → counter

## Key Logic
- parse_dsn_from_graph_msg() — parse Graph NDR message
- _classify() — 5.x.x = hard, 4.x.x = soft
- handle_bounce() — hook vào webhook (từ Phase 1)
- Auto-suppression: hard → add suppression list immediately

## Success Criteria
- [ ] AC1: Parse 5 NDR thật → extract đúng email + status_code + action
- [ ] AC2: Hard bounce 5.1.1 → auto-suppress
- [ ] AC3: Soft bounce 4.x.x → counter +1, suppress sau 3 lần
- [ ] AC4: Fallback subject parse khi DSN không multipart/report
- [ ] AC5: 0 import win32com trong bounce_handler.py
- [ ] AC6: bounce_kb.db schema migrate: thêm action, status_code, bounce_class, source

## Constraints
- Do NOT touch: Phase 1 webhook_router.py (already done)
- Match existing code style
- Backup files before modify

## Report back
- List files modified
- Each AC pass/fail + evidence
