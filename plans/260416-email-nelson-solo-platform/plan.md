# Plan — Email Nelson Solo Platform

**Created:** 2026-04-16
**North Star:** NHANH - CẠNH TRANH - YÊN TÂM (slogan Nelson Freight)
**Scope:** Nelson SOLO workflow. Không mentee. Local-only. GoClaw integrated.
**Replaces:** `260416-email-stack-refactor/` (A part) + `260416-email-intelligence-v1/` (consolidate)

## 🎯 Objective

Build 1 pipeline email thông minh hoàn chỉnh cho Nelson một mình:
1. **Tối** — Nelson bấm SEND 1 click → 1000 email bay ra nhanh nhất
2. **Đêm** — GoClaw tự handle khách hỏi giá + scan reply
3. **Sáng** — Nelson đọc summary + duyệt reply drafts

Khách cảm nhận: **"Nelson phản hồi cực nhanh, giá luôn cạnh tranh, và mình hiểu thị trường qua email của Nelson."**

## 📐 Pipeline Overview

```
┌──────────────────────────────────────────────────────────────┐
│ 🌆 NELSON TỐI — Bulk Send Fast                                │
│   Dashboard v4 → [SEND 1000] → Queue → Worker FAST MODE      │
│                                     (3-5 parallel threads)    │
│                                     → Outlook COM → Sent     │
│                                     → Intel log every send   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 🧠 INTEL MEMORY — Central DB                                  │
│   Per CNEE: #sent, #replied, last_topic, update_history      │
│   Per Event: {sent X at T, replied Y at T+N, sentiment}      │
│   Feed to: template engine + priority ranking                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 🔄 SCANNER LOOP — Every 30 min                                │
│   Scan Outlook Inbox (last 30 min)                           │
│   Classify: BOUNCE / AUTO-REPLY / REAL REPLY                 │
│   BOUNCE → update cnee_master EMAIL_STATUS                   │
│   AUTO-REPLY → log ignore                                     │
│   REAL REPLY → Telegram alert + GoClaw draft                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 🌙 GOCLAW NIGHT — Auto Response                               │
│   Scan HOT prospects + new inquiries                         │
│   Gen email reply using market intel                         │
│   Enqueue → worker sends                                      │
│   Log event to intel memory                                   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 🎨 SMART TEMPLATE ENGINE — Every email rendered               │
│   Input: CNEE profile + market state per lane + intel        │
│   Output: subject + body per-lane variation                   │
│   Config: email_rules.yaml (hot-reload)                       │
│   Tokens: {{first_name}}, {{delta}}, {{last_rate_quoted}}     │
└──────────────────────────────────────────────────────────────┘
```

## 🧩 Phase List

| # | Phase | Slogan Map | Effort |
|---|-------|-----------|--------|
| 01 | Fast Bulk Send (queue + parallel workers + kill switch + dry-run) | **NHANH** | 4-5h |
| 02 | Intel Memory System + 5D Tier Classification | foundation | 4-5h |
| 03 | Smart Template Engine + Default Routes config | **CẠNH TRANH + YÊN TÂM** | 5-6h |
| 04 | Reply Scanner + Auto-suppress + Bounce monitor | **NHANH** (reply) | 4-5h |
| 05 | GoClaw Night Auto (hook to queue) | **NHANH** (đêm) | 3-4h |
| 06 | Dashboard + Kill Switch + Tier Filter + Audit Log | UX + safety | 3-4h |
| 07 | VPS Cleanup (kill email routers) | tech debt | 1-2h |
| 08 | **Content Safety** (spam filter, domain blacklist, warm-up) | safety | 3-4h |
| 09 | **Health Monitor** (bounce rate, Telegram panic alert) | safety | 3-4h |

**Total:** 30-39h (4-5 days focused work)

**📎 Visual plan:** [`visuals/safety-tiers-defaults.html`](visuals/safety-tiers-defaults.html) — mở trong browser xem đầy đủ protection layers + tier system + default POD/POL

## 🚦 Dependencies

```
[07 VPS Cleanup] — can run parallel, low risk
         ↓
[01 Fast Bulk Send] ──→ [03 Smart Template] ──→ [06 Dashboard]
         ↓                      ↑
[02 Intel Memory] ──────────────┘
         ↓
[04 Reply Scanner] ──→ [05 GoClaw Night]
```

## 🎯 Acceptance (full pipeline)

- [ ] Nelson bấm SEND 1000 → 300-500 emails/phút throughput
- [ ] Mỗi email log intel: {cnee, template_id, market_state, timestamp, subject}
- [ ] Scanner mỗi 30 min phát hiện: 0 bounce, X auto-reply, Y real reply
- [ ] Real reply → Telegram alert trong <5 phút
- [ ] GoClaw gen reply draft → queue DRAFTS → Nelson review next morning
- [ ] Email body chứa: subject urgency, rate delta %, market forecast, CTA rõ
- [ ] Edit `email_rules.yaml` → email tiếp theo dùng template mới (không restart)
- [ ] Dashboard v4 hiển thị: Queue status, Intel panel per lane, Recent replies

## 📂 Files by Phase

- Phase 01: `email_engine/queue_store.py`, `web_server.py` (endpoints), `outlook_queue_worker.py` (parallel)
- Phase 02: `email_engine/intel/memory.py`, `intel/events.py`, SQLite schema
- Phase 03: `email_engine/intelligence/market_engine.py`, `template_selector.py`, `templates/email_rules.yaml`
- Phase 04: `email_engine/scanner/inbox_scanner.py`, classifier, Telegram hook
- Phase 05: GoClaw skill `intel-auto-reply/` + bridge to queue
- Phase 06: `plans/visuals/email-dashboard-v4.html` (add panels)
- Phase 07: Remove `api/routers/email_rate_router.py`, `email_queue_router.py`, webapp email pages

## 📚 References

- `memory/nelson-slogan-and-focus.md` — North Star (MUST obey)
- `memory/project-email-stack-audit.md` — current 4-flow problem
- `memory/project-email-outlook-com-constraint.md` — why local Windows
- `plans/260415-email-dashboard-v4-build/` — dashboard v4 wiring (shipped)

## 🚫 Explicitly OUT of scope

- Mentee workflows (approval, permission, leaderboard)
- Multi-language email
- Public WebApp email UI
- VPS email sending (GoClaw triggers via local queue, not VPS direct)
- A/B testing, follow-up sequences (can add later, not core)

## ⏭️ Next Action

Nelson duyệt plan.md → read phase-01 → approve start. Em KHÔNG code trước khi anh OK từng phase.
