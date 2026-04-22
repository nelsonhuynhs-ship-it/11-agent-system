# PM Report — 2026-04-22 Session ERP Full Tracking

**Session:** Continuation 2026-04-21 → 2026-04-22
**Scope:** ERP v14 upgrade — Contract#/Group Code + Full Tracking System + SI alert refactor

## 🎯 Shipped (3 plans · 6 commits)

| Plan | Status | Commit | Effort |
|------|--------|--------|--------|
| 260421-erp-contract-group-fix | ✅ completed | 291349b | 4h |
| 260421-erp-full-tracking-system | ✅ completed | Phase 1-5 batch + ab036ea + 8682e0b | 10h |
| 260421-refresh-all-fix | ✅ completed | customui_utils defensive fix | 1h |
| 260421-erp-tracking-auto-sync | 🔀 superseded | (absorbed into full-tracking) | - |

## 📊 Metrics

- **Tests delivered:** 98 pytest (55 booking_parser + 43 one_group_resolver) + 1 E2E suite
- **Parquet backfilled:** 1,589,215 ONE rows populated Group_Code (100%)
- **VBA LOC:** 5,790 → ~6,000 (+210)
- **Active Jobs cols:** 40 → 48
- **Sub-jobs UnifiedScanner:** 6 (merged si_48h into shipment_brain)
- **Agents orchestrated:** 8 sub-agents across 2 waves + 2 individual tasks

## 🐛 Bugs Caught & Fixed In-Session

1. **Col 41-44 collision** — SyncMilestones (CNEE Milestone 20/04) hardcoded cols 41+43, Phase 3 overwrote. Resolved: moved SyncMilestones to 46-48.
2. **VBA syntax error** — `_FindAJCol` leading underscore rejected by compiler. Renamed `FindAJColByHeader`.
3. **Scanner silent-fail 8 days** — root cause hardcoded `email_engine/data/` when config moved to OneDrive. Fixed via `shared.paths` integration.
4. **customUI rels strip** — openpyxl save drops customUI relationship causing ribbon 2-tab disappearance (3rd recurrence). Defensive fix: post-inject verification + force-patch fallback.

## 🏗 Architecture Decisions

1. **Merge si_48h_alert → shipment_brain** — same shipment-monitoring domain (event + time). Reduced jobs 7→6.
2. **Keep nelson_customer_sort separate** — different domain (routing vs detection). Gộp = over-engineer.
3. **Defer Email Pipeline refactor** — YAGNI. 3 jobs iterate Inbox redundantly ~10s/scan, but total < 3 min/day waste. Revisit when scan time becomes problematic.
4. **Bulletproof pattern for openpyxl+xlsm** — always re-inject customUI + verify + force-patch. New rule added to SYSTEM_STANDARDS.

## 📋 Pending (next session)

| Plan | Priority | Effort | Blocker |
|------|----------|--------|---------|
| 260421-0000-invoicelog-auto-scan | P2 | 4h | None — foundations shipped |
| 260421-0000-rate-mix-calculator | P2 | 3h | None — Booking Pool ribbon group unblocks shared-write |
| 260421-email-dashboard-deliverability-roadmap | P2 | 5h | Separate track (webapp) |

## 🎓 Nelson Insights (architecture review moments)

Nelson intervened 3 times with sharp architectural observations:
1. **"System đã có shipment_brain, sao thêm task riêng SI?"** → led to merge (correct call)
2. **"UnifiedScanner đã scan email rồi đâu cần task mới"** → validated integration pattern
3. **"3 job có gộp được?"** → triggered /ck:ask consultation, defined plugin-pattern option for future

Pattern: Nelson asks architectural "why" questions when he spots duplication. Next session, proactively validate design choices against his DRY/KISS instincts.

## 🚫 Unresolved

- **Tracking tooltip metadata empty cells** — current Active Jobs rows (pre-session) not populated with Pool metadata. New MarkWin Link mode will populate. Old rows need manual backfill OR accept as legacy.
- **Pricing_Engine/one_group_codes** ambiguous codes (Canada single vs consol) default to `990131` single. Nelson's real distribution: 5% consol. Acceptable but may tune later.
- **48h SI alert Vietnamese** — currently mixed English + Vietnamese in Telegram template. Nelson didn't request full Vietnamese translation.

## 📂 Artifacts

- Plan HTML review: `plans/260421-erp-full-tracking-system/visuals/plan-review.html`
- Session memory: `memory/project-erp-state-20260422.md`
- E2E test: `tests/test_erp_e2e.py`
