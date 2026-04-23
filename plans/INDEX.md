# Plans Index — Active + Pending

**Last updated:** 2026-04-23 (post-audit cleanup)
**Purpose:** Single source of truth for "what plans are still open?" — so AI and Nelson don't have to re-scan every session.

> Maintenance rule: khi một plan SHIP hoàn toàn → `git mv` vào `plans/archive/completed-YYYY-MM/` và xoá row khỏi bảng này.
> Khi start plan mới → thêm row.

## 🔨 PARTIAL — đã ship một phần, còn phase chưa làm

| Plan | Done | Remaining | Priority | Notes |
|------|------|-----------|----------|-------|
| [260422-1800-email-dashboard-v6-master](260422-1800-email-dashboard-v6-master/plan.md) | Phase 1 Data Migration · Phase 2.5 Safety Net (typo shield, cooldown 14d, hard limit 3) · **v6→v7 upgrade SHIPPED** (commit `e7375e9`) | Phase 2 Typo Shield full · Phase 3 Shipper Blacklist · Phase 4 Contacts UI · **Phase 5A/5B WhatsApp** · Phase 6 LinkedIn | Medium | v6 branding superseded by v7. Future phases (WhatsApp/LinkedIn) nên spawn plan mới nếu muốn làm. |
| [260420-1700-auto-cnee-milestone-notify](260420-1700-auto-cnee-milestone-notify/plan.md) | Phase 1 Schema · Phase 2 MVP · Phase 3 Tests (shipped 2026-04-20) | Phase 3 **SOAK** (1 tuần live monitor) — đã qua 3 ngày, còn 4 ngày | Low (soak auto) | Chờ hết soak → promote to DONE + archive. |
| [260418-shipment-brain](260418-shipment-brain/plan.md) | Phase 01 Customer Sort **LIVE** (59 rules, 269 emails/scan) · DuckDB extractor + vault_writer scaffolded | Phase 02 Extractor dual-write · Phase 03 Retrieval API · Phase 04 Fox Spirit skill | Medium | Infrastructure ready, cần Nelson ưu tiên. |

## ⏳ PENDING — chưa start, chờ Nelson approve

| Plan | Effort | Blocker | Open questions |
|------|--------|---------|----------------|
| [260415-price-watch-v2-requote-alert](260415-price-watch-v2-requote-alert/plan.md) | ~6h | None | UAT path ready. Nelson cần approve feature scope. |
| [260416-email-nelson-solo-platform](260416-email-nelson-solo-platform/plan.md) | 30-39h (9 phases) | v6 master đã có → OK start | Largest remaining. Có overlap với 260422-v6 plan → cần review trước khi start. |
| [260421-0000-rate-mix-calculator](260421-0000-rate-mix-calculator/plan.md) | 3h | CustomUI_v14.xml shared lock (CNEE Milestone merged OK) | 5 câu hỏi Nelson decide |
| [260421-0000-invoicelog-auto-scan](260421-0000-invoicelog-auto-scan/plan.md) | 4h | None — reuse 90% CNEE architecture | 5 câu hỏi Nelson decide |
| [260422-ribbon-pricing-toggle-buttons](260422-ribbon-pricing-toggle-buttons/plan.md) | 2h | Layout chưa chọn (Option A vs B) | 5 câu clarify |

## 📝 Next session prompt

- [NEXT_SESSION_PROMPT_ERP.md](NEXT_SESSION_PROMPT_ERP.md) — **STILL RELEVANT** (dated 2026-04-22).
  - PRIORITY TASK: Import Profit Reports 5/2025–3/2026 (2-3h)
  - 5 options outlined: Plan C Phase 1 debug · Rate Mix · InvoiceLog · Tech debt · Email Dashboard Sprint 2

## ✅ Recently archived (this session)

| Plan | Moved to | Why |
|------|----------|-----|
| 260422-2100-daily-rotation-engine | `archive/completed-2026-04/` | Status=completed, batch ROT_1776868843 verified 700/700 SENT. Memory confirms SHIPPED. |

## 📂 Archive folders

| Folder | Contents |
|--------|----------|
| `archive/completed-2026-04/` | 6 plans shipped April 2026 (contract-group-fix, full-tracking-system, tracking-auto-sync, refresh-all-fix, daily-rotation-engine, rule-engine-smart-consolidation) |
| `archive/email-v4-v5-superseded-by-v6/` | Legacy email dashboard iterations |
| `archive/email-sequence-ai-forecast/` | Older plan |
| `archive/completed-2026-04/` (root parent) | Mixed archive folder |
| `archive/260402-*` through `260414-*` | Historical plans (stand-alone archives) |

## 🤖 For AI

When Nelson asks "bây giờ làm gì tiếp?" hoặc "plan nào chưa làm?" → đọc file này trước. Top priorities (em đề xuất):
1. **InvoiceLog auto-scan** (4h, low risk, reuse architecture)
2. **Rate Mix calculator** (3h, unblocks ERP Pricing workflow)
3. **Ribbon toggle buttons** (2h, UX polish, nhỏ)
4. **Shipment Brain Phase 02-03** (mid effort, unlocks retrieval queries)
5. **Email Solo Platform 260416** (large, nên phân mảnh thành sprints)

Low priority / defer: **Email v6 future phases** (WhatsApp/LinkedIn) — speculative features, cần validate với Nelson trước.
