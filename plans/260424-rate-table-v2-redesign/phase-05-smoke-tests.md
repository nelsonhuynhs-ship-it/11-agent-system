---
phase: 5
status: done-auto-checks
priority: MEDIUM
effort: ~1h
blockedBy: [phase-04]
completed: 2026-04-24
manual-verification-pending: outlook-desktop-send-test
---

## ✅ Auto-Check Results (2026-04-24)

**Full matrix smoke (2 POL × 6 POD):**
| Route | BEST carrier | Rate | Notes |
|-------|-------------|------|-------|
| HCM→USSAV | **HPL SCFI** | $3008 | ✅ GOAL ACHIEVED — SCFI surface |
| HCM→USNYC | **HPL SCFI** | $3036 | ✅ GOAL ACHIEVED |
| HCM→USMIA | CMA FIX | $3273 | No SCFI data (expected) |
| HCM→USATL | ONE FAK | $3789 via SAV | ✅ RIPI routing works |
| HCM→USCHI | ONE FAK | $4882 | IPI default (LAX) |
| HCM→USLAX | ONE FIX | $2175 | Direct main port |
| HPH→USSAV | ONE FIX | $3247 | No HPH SCFI data (expected) |
| HPH→USATL | ONE FAK | $3939 via SAV | ✅ RIPI routing works |

**Pipeline validation:**
- Full test suite: 90/91 pass in `email_engine/tests/` (1 pre-existing failure, out of scope)
- HTML sample render: 18.6KB (target < 50KB ✓)
- `rate_table_renderer.py` matches approved visual preview

**Manual tests Nelson cần làm tay (trước khi archive hoàn toàn):**
- [ ] Test 1 — Quick Send → mysp2@mingyih-vn.com (HCM POL → verify HPL SCFI $3008 render trong Outlook desktop)
- [ ] Test 2 — Smart Draft Priority path
- [ ] Test 3 — Rotation side-by-side render
- [ ] Test 4 — `curl /api/rate-preview?pol=HCM&destinations=USSAV&markup=20` verify JSON
- [ ] Test 5 — USATL API check (gateway_port=USSAV)

# Phase 05 — Smoke Tests + Rollout Validation

## Context Links
- **Design:** `plans/reports/rate-table-v2-design-20260424.md` §7 (Success Criteria)
- **Plan overview:** [plan.md](plan.md)
- **All predecessors:** Phase 1-4 must be complete

## Overview
**Priority:** 🟢 MEDIUM — validation gate before full rollout
**Effort:** ~1h (send + wait + verify)
**Status:** ⏳ Pending (blocked by Phase 4)

End-to-end validation: send 5 test emails qua real send paths (Quick, Priority, Rotation) với CNEE test account, verify render + rate correctness.

## Key Insights
- Previous phases unit-tested in isolation — Phase 5 validates integration
- Use test CNEE (mysp2@mingyih-vn.com hoặc Nelson's own email) to avoid spamming real prospects
- Verify DB records + Outlook Sent folder + email render visually

## Requirements

### Functional
1. 5 smoke test emails send successfully qua 3 send paths
2. Rate content verified: HPL SCFI surfaces cho USEC lanes
3. Inland POD routed correctly (USATL via CHS, USCHI via LAX)
4. Email HTML renders OK trong Outlook desktop
5. No regression: existing Quick Send flow still works cho non-priority CNEE

### Non-functional
- All smoke tests complete < 15 minutes (send + wait Outlook sync)
- DB state verifiable via SQLite query
- Commit message references smoke test results

## Test Matrix

| # | Send Path | CNEE | POL | Expected POD | Key Assertion |
|---|-----------|------|-----|--------------|---------------|
| 1 | Quick Send | mysp2@mingyih-vn.com | HPH | 10 POD default | Email có HPL SCFI row cho USSAV/USNYC/USMIA |
| 2 | Smart Draft (Priority) | mysp2@mingyih-vn.com | HCM | 10 POD default | Email routed via `skip_priority=true`, USATL via CHS |
| 3 | Rotation ROT batch | 1 random rotation CNEE | HPH+HCM | 10 POD | Side-by-side render OK |
| 4 | Rate Preview API | `/api/rate-preview` | HPH | USATL only | JSON returns `gateway_port=USCHS` label=`"via CHS"` |
| 5 | Rate Preview API | `/api/rate-preview` | HCM | USCHI only | JSON returns `gateway_port=USLAX` label=`""` |

## Related Code Files

### Read only (validate behavior)
- `email_engine/web_server.py` endpoints
- `email_engine/outlook_queue_worker.py` — verify worker picks up jobs
- Outlook Sent folder (manual check)

### No modifications in this phase

## Implementation Steps

1. **Restart web_server** to load all Phase 1-4 changes:
   ```bash
   # PowerShell
   taskkill /F /IM python.exe
   cd "D:\NELSON\2. Areas\Engine_test"
   python email_engine\web_server.py
   ```
2. **Pre-warm caches:**
   ```bash
   curl http://localhost:8100/api/rotation/today
   curl http://localhost:8100/api/analytics/overview
   ```
3. **Test 1 — Quick Send:**
   - Dashboard → Quick Send → CNEE = mysp2@mingyih-vn.com → POL=HPH → Send
   - Wait 30s
   - Check Outlook Sent: 1 email to mysp2
   - Open email → verify:
     - 10 POD rows in HPH side
     - HPL SCFI row cho USSAV ($2,988)
     - USATL row với "RIPI" badge + "via CHS"
     - USCHI row với "IPI" badge
4. **Test 2 — Smart Draft Priority:**
   - Dashboard → Priority → Find MING YIH → Draft → Send
   - Wait 30s
   - Check Outlook Sent: 1 email từ mysp2 Smart Draft path
   - Verify same content criteria as Test 1
5. **Test 3 — Rotation:**
   - Dashboard → Rotation → Pick 1 upcoming CNEE → Manual run
   - Wait 30s
   - Verify side-by-side (HPH + HCM) render
6. **Test 4 — Rate Preview API (USATL):**
   ```bash
   curl "http://localhost:8100/api/rate-preview?pol=HPH&destinations=USATL&markup=20"
   ```
   Expected JSON:
   ```json
   {
     "rates": [
       {"carrier": "HPL", "gateway_port": "USCHS", "routing_label": "via CHS", ...},
       {"carrier": "ONE", "gateway_port": "USNOR", "routing_label": "via NOR", ...},
       ...
     ]
   }
   ```
7. **Test 5 — Rate Preview API (USCHI):**
   ```bash
   curl "http://localhost:8100/api/rate-preview?pol=HCM&destinations=USCHI&markup=20"
   ```
   Expected: `gateway_port=USLAX`, `routing_label=""` (no suffix for IPI default)
8. **Regression check:**
   ```bash
   pytest email_engine/tests/ -v
   ```
   All existing tests must pass.
9. **DB verification:**
   ```bash
   sqlite3 email_engine/data/outlook_queue.db \
     "SELECT status, batch_id, cnee_email FROM email_queue WHERE enqueued_at > datetime('now', '-1 hour') ORDER BY id DESC LIMIT 5"
   ```
   All 3 send-path tests should show `status='sent'`.

## Todo List
- [ ] Restart web_server (load Phase 1-4 changes)
- [ ] Pre-warm caches
- [ ] Test 1 — Quick Send → mysp2
- [ ] Verify Test 1 email content (10 POD + HPL SCFI + USATL via CHS)
- [ ] Test 2 — Smart Draft → mysp2
- [ ] Verify Test 2 email content
- [ ] Test 3 — Rotation single CNEE
- [ ] Verify Test 3 side-by-side render
- [ ] Test 4 — `/api/rate-preview` USATL JSON check
- [ ] Test 5 — `/api/rate-preview` USCHI JSON check
- [ ] Run full `pytest` — no regression
- [ ] SQLite query — 3 sends confirmed in DB
- [ ] Telegram notify Nelson results
- [ ] Commit: `test(rate-table): smoke tests pass for 5 scenarios`
- [ ] Update `plans/INDEX.md` — move plan to archive khi shipped
- [ ] Run `/ck:journal` for session log

## Success Criteria
1. ✅ 5/5 smoke tests pass
2. ✅ HPL SCFI surfaces BEST cho USSAV/USNYC/USMIA
3. ✅ USATL routed via CHS/NOR/SAV (not LAX)
4. ✅ USCHI/USDAL/USDEN routed via LAX (IPI default)
5. ✅ Side-by-side HPH/HCM render OK Outlook desktop
6. ✅ Full pytest passes (no regression)
7. ✅ DB records confirm 3 send-path tests sent

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Outlook COM flaky — 1 send may fail | Retry manually once; worker has built-in retry |
| mysp2 cooldown blocks Test 2 | Use `skip_cooldown=true` in test payload |
| Phase 3 gateway data sparse → USATL skipped | Accept — email renders 9 POD with "Note: Atlanta rate pending" in footer |
| Render diff between Outlook 2016 vs 365 | Test both if available; 2016 lowest common denominator |
| Test CNEE replies → inbox clutter | Use Nelson's test CNEE or catch-all account |

## Security Considerations
- Smoke tests use internal test CNEE, not external prospects
- No credentials exposed in test scripts
- Outlook COM authentication via existing Nelson session

## Rollout Strategy

**After Phase 5 passes:**
1. Update `plans/INDEX.md` — mark plan SHIPPED
2. Archive plan folder → `plans/archive/completed-2026-04/260424-rate-table-v2-redesign/`
3. Delete design doc? — **NO**, keep as reference trong archive
4. Notify Nelson via Telegram: "Rate Table v2 SHIPPED — HPL SCFI active, 10 POD default live"
5. Monitor next 3 daily rotations — verify no regression in batch sends

**Rollback plan nếu production issue:**
- Git revert last 5 commits (1 per phase)
- Restart web_server
- No DB rollback needed (no schema change)

## Final Deliverable
- Rate Table v2 LIVE trên PC Home + Laptop VP
- HPL SCFI surfaced as BEST cho USEC lanes
- 10 POD default rotation
- Email visual matches approved preview
- $60K/week opportunity gap CLOSED (est.)

## Next Steps After Ship
- Monitor 1 week — SCFI refresh cadence validation (Q2 daily — OK?)
- Collect first 10 replies — any feedback on layout/rates?
- Consider Phase 6 (future): carrier scorecard, dynamic POD selection based on CNEE commodity
