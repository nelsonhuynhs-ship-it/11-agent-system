# Email Dashboard v6 — Master Plan

**Status:** APPROVED — ready for Phase 1
**Created:** 2026-04-22
**Owner:** Nelson (approved all key decisions)
**Supersedes:** v4, v5 plans (archived at `plans/archive/email-v4-v5-superseded-by-v6/`)
**Visual:** `plans/visuals/email-dashboard-v6-plan.html`

---

## Mục tiêu v6

Biến email tool 1 kênh thành **multi-channel outreach platform**:
- Email (existing) — smart TZ, typo shield
- WhatsApp (Meta Cloud API direct) — $0 sandbox tuần 1 → $20/tháng production
- LinkedIn (Sales Nav + Expandi hybrid) — enrichment + safe automation

Với master data **2-sheet tách riêng CNEE/SHIPPER**, bảo vệ priority customer, harvest decision maker từ auto-reply.

---

## North Star metrics

| Metric | Hiện tại | Target v6 |
|---|---|---|
| Email open rate | 3.7% | 12-15% |
| WhatsApp conversation | 0 | 75-125/tháng (budget $20) |
| LinkedIn B2B conv | 0 | 10-15/tháng quality |
| Pool CNEE | 22,230 | 25-28K clean |
| Pool SHIPPER | 0 (trộn lộn) | 5-8K tách riêng, HOLD |
| POL/STATE/CARRIER fill | ~5% | 60-70% |
| Email typo silent sends | 345 | 0 |
| Data files rời rạc | 7 files | 1 master 2-sheet |

---

## Key decisions (Nelson approved 2026-04-22)

1. ✅ **Master file 2-sheet** — CNEE (gửi tự do) + SHIPPER (HOLD pending VN blacklist)
2. ✅ **WhatsApp Meta Cloud API DIRECT** — không qua BSP (Twilio/360dialog)
3. ✅ **Start SANDBOX FREE tuần 1** — test 5 số, $0 cost, upgrade sau
4. ✅ **Production budget cap $20/tháng** — hard stop, daily cap 20 tin
5. ✅ **LinkedIn hybrid** — Sales Nav + Expandi (không browser extension)
6. ✅ **Shipper Blacklist system** — 3-layer match tránh đụng team VN

---

## 6 Phase breakdown

| Phase | Thời gian | Chi phí | Status | File |
|---|---|---|---|---|
| 1. Data Migration Foundation | 10h | $0 | IN PROGRESS (scripts done, pending real write) | [phase-01](phases/phase-01-data-migration.md) |
| 2. Typo Shield + Bounce Harvest v2 | 6h | $0 | PENDING | [phase-02](phases/phase-02-typo-harvest.md) |
| 3. Shipper Blacklist System | 4h | $0 | PENDING | [phase-03](phases/phase-03-shipper-blacklist.md) |
| 4. Contacts Tab UI | 4h | $0 | PENDING | [phase-04](phases/phase-04-contacts-tab.md) |
| 5A. WhatsApp SANDBOX (free test) | 6h | $0 | PENDING | [phase-05a](phases/phase-05a-whatsapp-sandbox.md) |
| 5B. WhatsApp PRODUCTION | 4h | $20/mo cap | PENDING | [phase-05b](phases/phase-05b-whatsapp-production.md) |
| 6. LinkedIn Integration | 8h | $350/mo | DEFERRED | [phase-06](phases/phase-06-linkedin.md) |

**Total dev effort:** 42h (~2 tuần)
**Total monthly cost at full:** ~$370 (WA $20 + LI $350)

---

## Timeline (Nelson's week)

```
Tuần 1
  Day 1-2   Phase 1 Data Migration
  Day 3     Phase 2 Typo + Harvest (start)
  Day 4     Phase 2 finish + Phase 3 (start)
  Day 5     Phase 3 finish + Phase 4
  (parallel: Nelson apply Meta Business FREE)

Tuần 2
  Day 6     Phase 5A SANDBOX setup + template submit
  Day 7-12  SANDBOX test 1 tuần ($0)
  Day 13    Review → upgrade Phase 5B Production
  Day 14+   Phase 6 LinkedIn (deferred until WA stable)
```

---

## Files to create (scripts)

| File | Purpose |
|---|---|
| `scripts/panjiva_clean_v2.py` | Extract 15 cols, split CNEE/SHIPPER |
| `scripts/migrate-to-unified-v6.py` | 14-step migration with lock-priority |
| `email_engine/core/bounce_harvest_v2.py` | OOO + LEFT detector, harvest replacements |
| `email_engine/core/email_verifier.py` | Fix regex + typo fuzzy match (edit existing) |
| `email_engine/core/shipper_blacklist.py` | 3-layer match VN team overlap |
| `email_engine/core/wa_validator.py` | Meta contact check bulk |
| `email_engine/core/wa_sender.py` | Template send, sandbox/production modes |
| `email_engine/core/wa_budget_guard.py` | Hard cap $20 + daily 20 tin |
| `email_engine/api/routes/wa_router.py` | WhatsApp endpoints |
| `email_engine/api/routes/contacts_router.py` | Contacts tab CRUD |
| `email_engine/api/routes/shipper_blacklist_router.py` | Blacklist CRUD |

## Files to update (UI)

| File | Change |
|---|---|
| `plans/visuals/email-dashboard-v5.html` → `email-dashboard-v6.html` | Promote v6 to live |
| Tab 1 Quick Send | Add CNEE/SHIPPER radio + channel selector |
| Tab 3 Inbox | Add Harvest panel |
| New Tab 5 Contacts | 2-sheet browser + refresh/import/rollback |
| New Tab 6 WhatsApp | 4 panel + BUDGET GUARD widget |
| New Tab 7 LinkedIn | 3 panel (deferred) |
| Tab 8 Settings | WA config + Shipper Blacklist builder + Typo review |

---

## Data files — final state

**Master:** `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx`
- Sheet `CNEE` — ~25-28K rows, active
- Sheet `SHIPPER` — ~5-8K rows, HOLD status

**Support files:**
- `vn_team_overlap.xlsx` — 3-sheet blacklist (company/email/phone)
- `wa_templates.json` — approved Meta template cache
- `backups/contact_unified_v6.backup_YYYYMMDD_HHMM.xlsx` — 14 rotation
- `migration_audit.csv` — row-level change log

**Archived (v4/v5 legacy):**
- `cnee_master.xlsx`, `cnee_master_v2.xlsx` → `archive/`
- Keep `cnee_master_v2_final.xlsx` as rollback safety net during Phase 1

---

## Risk + mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Migration overwrites priority data | Mất lịch sử khách | 5-col LOCK + dry-run + audit log + backup rotation |
| Meta bans WA account | Mất kênh | Sandbox 7 ngày test trước, quality monitor, opt-out trong template |
| Shipper send đụng team VN | Trust issue | Default HOLD + 3-layer blacklist + Activate gate |
| LinkedIn automation ban | Mất account | Safe limits 20/ngày, không browser extension |
| Budget overrun | Chi phí mất kiểm soát | Hard cap $20 WA + daily cap + auto-pause 90% |

---

## Success criteria (end-of-sprint review)

- [ ] `contact_unified_v6.xlsx` 2 sheet exists, priority nguyên vẹn (audit log prove)
- [ ] Email open rate tăng >8% so với baseline 3.7%
- [ ] 0 email typo `.co`/`.cm` gửi im lặng (shield active)
- [ ] WhatsApp sandbox test 7 ngày pass, 5 test contact nhận template OK
- [ ] WhatsApp production BUDGET GUARD stop đúng tại $20
- [ ] Shipper sheet 100% flag HOLD đến khi blacklist ready
- [ ] Harvest 2-chiều bắt được replacement contact từ 3 file .msg mẫu

---

## Open questions (Nelson review tuần 1)

1. Schema 35 cột — có cần thêm cột gì đặc thù freight forwarding?
2. LinkedIn Phase 6 — làm luôn sau Phase 5 hay defer 1 tháng xem WA hiệu quả trước?
3. Timeline 2 tuần có quá gấp không — cần giãn Phase 5 chờ Meta approve?
