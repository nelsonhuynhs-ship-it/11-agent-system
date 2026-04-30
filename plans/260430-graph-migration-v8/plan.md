---
title: Email V8 — Graph API Migration (6 phase, rip COM khỏi 6 features)
slug: graph-migration-v8
date: 2026-04-30
owner: Nelson
status: draft
last_update: 2026-04-30 17:30
mode: --auto
related_decisions: D:/OneDrive/NelsonData/reports/2026-04-30/email-v7-feature-audit-decision.html
prereq: Sprint 1 graph-send-reliability (đã ship 04-29, default backend = "graph")
blockedBy: []
blocks: []
---

# Email V8 — Graph API Migration

## Context (1 dòng)

Sếp tick decision audit 04-30: **KEEP 17 features, DROP 5 dead code**. 6 features còn dependency COM → migrate sang Microsoft Graph API. Sprint 1 đã fix root cause Smart Send 700/day; phase này hoàn tất rip COM khỏi Tier 1+2 SEND/SCAN path.

## Goal Cụ thể

Sau khi xong:
- Reply/bounce real-time qua Graph webhook (không poll inbox)
- Smart Send Preview qua web Outlook URL (không Outlook desktop COM)
- Sent verify qua Graph messageId (không scan folder)
- Bounce KB feed từ DSN parse RFC 3464 (chuẩn, không subject regex)
- 0 file `import win32com` trong SEND/SCAN path (Tier 3 offline tools KEEP)
- viewInbox + Smart Send Preview hoạt động trở lại (đang chết từ 04/27)

## 6 Phase

| # | File | Effort MM | Depends |
|---|------|-----------|---------|
| 1 | [phase-01-graph-webhook-subscription.md](phase-01-graph-webhook-subscription.md) | 6-8h | — |
| 2 | [phase-02-smart-send-preview-graph.md](phase-02-smart-send-preview-graph.md) | 4h | — |
| 3 | [phase-03-bounce-kb-dsn-parser.md](phase-03-bounce-kb-dsn-parser.md) | 3h | phase-01 |
| 4 | [phase-04-sent-scan-graph.md](phase-04-sent-scan-graph.md) | 2h | — |
| 5 | [phase-05-cnee-draft-graph.md](phase-05-cnee-draft-graph.md) | 2h | — |
| 6 | [phase-06-sequence-engine-cleanup.md](phase-06-sequence-engine-cleanup.md) | 30 min | — |

**Tổng**: ~18-20h MM. Có thể dispatch song song phase 2, 4, 5, 6 (đều độc lập). Phase 3 phải chờ phase 1.

## Critical Path

```
Phase 1 (webhook) ──→ Phase 3 (DSN parser feed bounce KB)
Phase 2 (preview) ─┐
Phase 4 (sent verify) ─┼─→ Sprint hoàn tất
Phase 5 (cnee draft) ──┤
Phase 6 (cleanup) ─────┘
```

## Success Metrics

| Metric | Target | Measure |
|--------|--------|---------|
| Reply rate accuracy | UP từ 11.4% bias-low → ground truth | So sánh 7 ngày sau migrate vs trước |
| Smart Send Preview work | 100% (đang 0%) | Test 3 lần liên tiếp click Smart Send → preview hiện |
| Bounce capture | Real-time ≤ 5 phút | Send fake-bounce → check DB |
| `import win32com` SEND path | 0 file | `grep -rln "import win32com" email_engine/{api,senders,intelligence,scanner}` |
| Production stability | Smart Send 700/day không gián đoạn | Monitor 1 tuần |

## Out of Scope (KHÔNG migrate)

- Tier 3 offline tools (memory `sprint1_tier1_expanded`): `pst_importer.py`, `knowledge_ingest.py`, `read_email1.py` — Sếp dùng tay 1 lần, không production
- Reporting API tenant-level (cần admin perm) — Phase 7+ sau
- Read receipt tracking — feature mới, không migrate

## Dependencies / Constraints

- **Microsoft Graph token** đã work (Sprint 1 verified) — `email_engine/.cache/graph_token.bin`
- **Webhook endpoint HTTPS public** — Tailscale Funnel `https://laptop-no6f8ibp.tail82dc4e.ts.net/` work
- **Subscription lifecycle** — Graph webhook expire mỗi ~3 ngày, cần renew job
- **Pháp lý**: Suppression List (B8) GIỮ ép buộc — CAN-SPAM/CASL compliance

## Risks

| Risk | Mitigation |
|------|------------|
| Webhook subscription expire không renew → miss notifications | Cron job daily renew + alert nếu fail |
| Graph 429 throttling (30 msg/min limit) | Phase 1 inline rate limiter + retry-after handler |
| Tailscale Funnel down → webhook miss | Fallback poll `/me/messages?$filter=receivedDateTime gt LAST_CHECK` mỗi 1h |
| Migration fail giữa chừng | Mỗi phase atomic, có rollback step. Git tag trước mỗi cook |

## Rollback Strategy

- Git tag `v7-graph-fix-stable-20260429` đã có
- Mỗi phase tạo tag mới: `v8-phase-N-pass`
- Nếu phase fail → `git reset --hard v8-phase-(N-1)-pass`

## Next

Sếp confirm OK plan → cook phase 1 (webhook) trước. Phase 2/4/5/6 có thể song song sau khi phase 1 stable.
