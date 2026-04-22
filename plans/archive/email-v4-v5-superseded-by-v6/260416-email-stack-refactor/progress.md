# Progress Log — Email Stack Refactor

## 2026-04-16

### Audit + Decision
- [x] Audit complete — findings.md written (4 flows identified)
- [x] Memory saved — `project-email-stack-audit.md`
- [x] Task plan draft — task_plan.md
- [x] Nelson Q&A: giải thích queue vs worker, API/endpoint, ví von freight
- [x] **Decision locked (Nelson 2026-04-16):**
  - Email: **LOCAL-ONLY** (kill VPS email)
  - Rate API VPS: **KEEP** (GoClaw bot Telegram cần query rate)
  - WebApp Next.js email page: kill

### Awaiting Approval
- [x] Phase A1 audit dependency ✅ DONE 2026-04-16
- [ ] Phase A2-A10 (VPS Cleanup) — chờ Nelson ok start
- [ ] Phase B (Local Stack Build)
- [ ] Phase C (Cleanup + Verify)
- [ ] Phase D (VPS Deploy)

## A1 Report Summary (2026-04-16)
- ⚠ Frontend: 3 pages + 2 lib files (api.ts, useApi.ts) depend email-rate → Nelson chọn XÓA cả 3 pages
- ⚠ Backend: 2 routers + queue_manager.py + template_engine.py + blacklist.py + migration SQL + test + deploy script
- ⚠ `api/pipeline/queue_manager.py` là auto-campaign scheduler nightly 8pm-6am → cần re-evaluate ở A2
- ✅ Local `email_engine/` không bị ảnh hưởng

## Linked Plan
- `plans/260416-email-intelligence-v1/` — Email Smart Templates (depends on Phase B of this plan)

## ⚠️ SUPERSEDED (2026-04-16 later)
This plan consolidated into: `plans/260416-email-nelson-solo-platform/`
Reason: Nelson reveal real intent (GoClaw integration + fast bulk + 30-min scanner). New plan is source of truth. Phases here mapped to new plan:
- A (VPS cleanup) → new Phase 07
- B (local queue) → new Phase 01
- C (verify) → absorbed into new Phase 01 testing

## Notes
- Không code gì cho đến khi Nelson duyệt Phase A1 (audit dependency)
- Sau audit A1, nếu thấy router email_rate bị depend bởi feature khác → propose workaround trước khi xóa
- Dashboard v4 Phase 3 đã ship (tối 15/04) — **giữ nguyên**, không rollback
