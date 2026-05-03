# Plans Index — Active + Pending

**Last updated:** 2026-04-26 (cleanup: archived 6 completed plans, added 3 new plans 25/04)
**Purpose:** Single source of truth for "what plans are still open?" — so AI and Nelson don't have to re-scan every session.

> Maintenance rule: khi một plan SHIP hoàn toàn → `git mv` vào `plans/archive/completed-YYYY-MM/` và xoá row khỏi bảng này.
> Khi start plan mới → thêm row.

## ⏳ PENDING — chưa start, chờ Nelson approve

| Plan | Effort | Priority | Notes |
|------|--------|----------|-------|
| [260425-system-contract-discovery](260425-system-contract-discovery/plan.md) | ~18h | P1 / FOUNDATION | Auto-discover data contracts + DOMAIN_MODEL.md + validator pre-commit. Unblocks visual-tour. |
| [260425-customer-tier-margin](260425-customer-tier-margin/plan.md) | 10–13h | HIGH | VIP×0.7 / Regular×1.0 / New×1.3 multiplier in CRM. Anh approved Option A3. ERP pure. |
| [260425-visual-tour-domain-model](260425-visual-tour-domain-model/plan.md) | ~10h | HIGH | Visual onboarding + DOMAIN-ERP/DATA/EMAIL.md. Uses contract-discovery findings. |
| [260424-rate-table-v2-redesign](260424-rate-table-v2-redesign/plan.md) | ~10h | HIGH | Phase 1-4 SHIPPED 2026-04-24 (HPL SCFI surface, RIPI gateway, 10 POD). Phase 5 smoke tests pending. |
| [260416-email-nelson-solo-platform](260416-email-nelson-solo-platform/plan.md) | 30–39h (9 phases) | Low | Email-only, không phải ERP. Nên re-audit vs v7 master trước khi start. |

## 📝 Next session prompt

- [NEXT_SESSION_PROMPT_ERP.md](NEXT_SESSION_PROMPT_ERP.md) — dated 2026-04-22, có thể đã outdated sau 4 ngày.

## ✅ Recently archived (this cleanup 2026-04-26)

| Plan | Status | Why archived |
|------|--------|--------------|
| 260415-price-watch-v2-requote-alert | DISCARDED | Speculative, không Nelson approve. |
| 260418-shipment-brain | Phase 01 SHIPPED, P02-04 not pursued | Phase 01 Customer Sort live (59 rules). Phase 02-04 deferred — infrastructure đã đủ. |
| 260420-1700-auto-cnee-milestone-notify | SHIPPED + soak | Production live, soak passive observation. |
| 260421-0000-invoicelog-auto-scan | DISCARDED | Plan-only, không pursued. |
| 260421-0000-rate-mix-calculator | SHIPPED v1 (with known peer bug FIXED 22/04 commit 63d67c4) | Refresh-v14.py dedup fix recovered ports → Mix peer-finding now works for all carriers. |
| 260422-ribbon-pricing-toggle-buttons | DISCARDED | UX polish, không ưu tiên. |
| 260424-rate-table-v2-redesign Phase 06 | OBSOLETE — DELETED | Phase 06 (fix Rate Mix CMA/HPL/YML) was duplicate of fix already shipped commit 63d67c4. |

## 📂 Archive folders

| Folder | Contents |
|--------|----------|
| `archive/completed-2026-04/` | All 13 plans shipped or discarded April 2026 |
| `archive/email-v4-v5-superseded-by-v6/` | Legacy email dashboard iterations |
| `archive/email-sequence-ai-forecast/` | Older plan |
| `archive/260402-*` through `260414-*` | Historical plans |

## 🤖 For AI

When Nelson asks "bây giờ làm gì tiếp?" hoặc "plan nào chưa làm?" → đọc file này trước. Top priorities (em đề xuất):

1. **System Contract Discovery** (18h) — foundation, unblocks visual-tour + giúp tránh future drift bugs.
2. **Customer Tier Margin** (10-13h, HIGH) — ERP pure, ship nhanh, Anh đã approve A3.
3. **Visual Tour + DOMAIN_MODEL** (10h) — sau khi contract-discovery xong.
4. **Rate Table v2 Phase 5** (smoke tests, ~1h) — finish 260424.
5. **Email Solo Platform** (30h) — large, phân mảnh sprints, re-audit vs v7.

**Verify trước khi work:** Rate Mix ribbon hiện tại có work cho HPL/CMA/YML không? Commit 63d67c4 (22/04) đã fix `refresh-v14.py` dedup root cause. Test 1 quote thực tế trước khi assume bug còn.
