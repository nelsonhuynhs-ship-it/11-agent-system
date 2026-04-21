---
title: "InvoiceLog Auto-Populate from Accounting Emails"
description: "Scan internal accounting mails → update InvoiceLog STATUS (PENDING/PAID/OVERDUE) · Telegram alerts on overdue"
status: pending
priority: P2
effort: 4h
branch: main
tags: [erp, email-automation, invoicelog, accounting, reuse-cnee-milestone]
created: 2026-04-21
---

# Plan — InvoiceLog Auto-Populate from Accounting Emails

**Created:** 2026-04-21
**Related:** [260420-auto-cnee-milestone-notify](../260420-1700-auto-cnee-milestone-notify/plan.md) (reuse architecture + security hardening)
**Source of truth:** `docs/SYSTEM_STANDARDS.md`

## Goal

InvoiceLog sheet hiện empty (header only). 3 automation targets:

1. **Job WIN → VBA insert row** PENDING status (trigger: `OnAction_MarkQuoteWin` fires)
2. **Scanner detects payment mail** → update STATUS=PAID + PAID_DATE via JSON sidecar
3. **Scanner detects reminder mail** → update LAST_REMINDER_DATE
4. **Daily cron 08:05** → PENDING rows with DUE_DATE < today → STATUS=OVERDUE + Telegram alert

YAGNI cut: NO dashboard cell (future), NO PAID_AMOUNT reconciliation (future), NO auto email to customer.

## What We Reuse (90% borrowed from CNEE Milestone)

| CNEE Milestone asset | InvoiceLog reuse |
|---|---|
| `on_atd_detected()` hook pattern at `shipment_brain.py:585-591` | Add 2nd hook: `on_payment_event()` after existing hook |
| `PAYMENT_CONFIRMED` stage (already detected at line 179) | Already wired — just intercept |
| JSON sidecar `milestone_state.jsonl` pattern | New sidecar: `invoice_state.jsonl` |
| Security gates (auth-results, allowlist, kill switch, rate limit) | Copy verbatim — same BEC risk profile |
| `flush_telegram_summary()` buffer pattern | Use shared buffer OR local mirror |
| VBA Sync button (`Sync milestones`) | Add 2nd button: `Sync invoices` |
| Task Scheduler 08:00 (cnee eta-reminder) | New entry 08:05 (invoice overdue sweep) |

**Net new code:** ~120 LOC Python + ~40 LOC VBA (insert row on WIN).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Flow 1 — JOB WIN (synchronous, VBA-driven)             │
├─────────────────────────────────────────────────────────┤
│ User clicks "Mark WIN" button                           │
│   → OnAction_MarkQuoteWin (existing) promotes to AJ     │
│   → NEW: InvoiceLog_InsertOnWin appends PENDING row     │
│     with BKG_NO, CUSTOMER, DATE_ISSUED=today,           │
│     DUE_DATE=today+30d, STATUS=PENDING                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Flow 2 — Payment/Reminder mail (async, scanner)        │
├─────────────────────────────────────────────────────────┤
│ NelsonUnifiedScanner (30 min) → shipment_brain.py      │
│   scan_and_update() per-email loop:                     │
│     stages = detect_stages(full_text)                   │
│     ← PAYMENT_CONFIRMED already detected                │
│     ← NEW: PAYMENT_REMINDER stage added                 │
│                                                          │
│   After existing CNEE hook, NEW hook:                   │
│     if any(s in {"PAYMENT_CONFIRMED","PAYMENT_REMINDER"}│
│            for s in stages):                            │
│       invoice_tracker.on_payment_event(                 │
│         item, stages, ids, sender)                      │
│                                                          │
│ invoice_tracker.on_payment_event():                     │
│   • Kill switch + auth-results + allowlist              │
│     (ACCOUNTING_ALLOWLIST — separate from OPS)          │
│   • Extract Bkg from ids.BKG OR invoice_no regex        │
│   • Bulk detect (>5 identifiers → reject)               │
│   • For each identifier:                                │
│       type="PAID"  → append state (sets STATUS=PAID)    │
│       type="REMIND" → append state (sets LAST_REMINDER) │
│   • Write invoice_state.jsonl                           │
│   • Queue Telegram line                                 │
│                                                          │
│ End of scan → flush_telegram_summary() (shared w/ CNEE) │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Flow 3 — Overdue sweep (daily 08:05)                   │
├─────────────────────────────────────────────────────────┤
│ Task Scheduler → python -m email_engine.core            │
│                   .invoice_tracker overdue-sweep        │
│   • Load InvoiceLog via openpyxl read-only              │
│   • For each row where STATUS=PENDING and               │
│     DUE_DATE < today AND not already flagged:           │
│       → append OVERDUE state to sidecar                 │
│       → Telegram: "Overdue: {cust} ${amt} {days}d past" │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Flow 4 — Sync sidecar → xlsm (user-triggered)          │
├─────────────────────────────────────────────────────────┤
│ Nelson clicks VBA "Sync invoices" button OR             │
│ Workbook_Open auto-flushes:                             │
│   • Read invoice_state.jsonl line-by-line               │
│   • For each entry:                                     │
│     - Find InvoiceLog row by BKG_NO (or INVOICE_NUMBER) │
│     - Update STATUS + PAID_DATE + LAST_REMINDER_DATE    │
│   • Truncate processed lines from JSONL                 │
└─────────────────────────────────────────────────────────┘
```

## Phases

| # | File | Effort | Purpose |
|---|------|--------|---------|
| 01 | [Schema + sample data](phase-01-schema.md) | 30m | Define 11 cols on InvoiceLog sheet, pre-migration backup, column index constants |
| 02 | [Scanner hook + stage detection](phase-02-scanner-hook.md) | 2h | `invoice_tracker.py` + add PAYMENT_REMINDER stage + wire hook in shipment_brain.py |
| 03 | [VBA insert on WIN](phase-03-win-integration.md) | 30m | `InvoiceLog_InsertOnWin` sub + call from `OnAction_MarkQuoteWin` |
| 04 | [Daily overdue sweep](phase-04-overdue-daily.md) | 30m | CLI entry + Task Scheduler entry 08:05 + Telegram alert format |
| 05 | [Test + verify](phase-05-test-verify.md) | 30m | pytest unit tests + smoke test 3 scenarios |

**Total:** 4h realistic (reuses CNEE infra — if CNEE didn't exist, would be 10h).

## Files Touched

**New (3):**
- `email_engine/core/invoice_tracker.py` (~120 LOC — payment event handler + overdue sweep CLI)
- `email_engine/data/invoice_state.jsonl` (runtime sidecar)
- `tests/test_invoice_tracker.py` (~50 LOC)

**Modified (3):**
- `email_engine/core/shipment_brain.py` — add `PAYMENT_REMINDER` stage pattern (+1 line) + 5-line hook after existing CNEE hook
- `ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas` — `InvoiceLog_InsertOnWin` sub + call from `OnAction_MarkQuoteWin`; `OnAction_SyncInvoices` button callback
- Windows Task Scheduler — new entry 08:05 daily (`invoice_tracker overdue-sweep`)

**Unchanged (YAGNI):**
- `cnee_milestone.py` (separate module — don't entangle)
- Active Jobs schema
- CRM schema
- Dashboard cell on InvoiceLog (future phase)
- Email templates (we don't auto-send — only Telegram alert)

## Data Schema — InvoiceLog (11 cols)

| Col | Name | Type | Source | Notes |
|---|---|---|---|---|
| A | BKG_NO | text | VBA on WIN | Primary key — unique per invoice |
| B | CUSTOMER | text | VBA from AJ row | Copied from Active Jobs |
| C | INVOICE_NUMBER | text | Manual OR accounting mail | Secondary key — fallback if BKG absent in mail |
| D | AMOUNT | number | Manual after DN_SENT | USD — Nelson fills in |
| E | DATE_ISSUED | date | VBA on WIN | = today on WIN click |
| F | DUE_DATE | date | VBA on WIN | = DATE_ISSUED + 30d |
| G | STATUS | text | Scanner / cron | PENDING / PAID / OVERDUE |
| H | PAID_DATE | date | Scanner | Set when payment mail detected |
| I | PAID_AMOUNT | number | Manual reconcile (future) | NOT auto-populated in MVP |
| J | LAST_REMINDER_DATE | date | Scanner | Most recent reminder mail received |
| K | NOTES | text | Manual | Free-text |

Header row: **1** (no title chrome needed — simple log sheet).
Data starts row 2.

## Security Controls (baked in — reused from CNEE)

| Control | Value |
|---|---|
| Kill switch | `email_engine/data/INVOICE_TRACKER_DISABLED` (separate file — allows halting invoice flow without killing CNEE) |
| Sender allowlist | `ACCOUNTING_ALLOWLIST` — explicit SMTPs (e.g. `accounting@pudongprime.vn`, `finance@...`). TODO populate after first scan. |
| Auth-Results | Require SPF+DKIM+DMARC=pass (internal mail may fail — see Risks) |
| Rate limit | MAX_INVOICE_EVENTS_PER_RUN=10, PER_DAY=50 (higher than CNEE because batch payment mails more common) |
| Bulk detect | >5 BKG/Invoice identifiers in one mail → reject (likely statement of account) |
| JSON sidecar | `invoice_state.jsonl` — scanner NEVER writes xlsm directly |
| Match recency | Only update InvoiceLog rows where DATE_ISSUED > today-180d |

**NOT reused:** BEC placeholder sanitization (we don't compose outbound email — only Telegram). LOWER attack surface than CNEE.

## Data Flow

| Input | Transform | Output |
|---|---|---|
| Inbox mail from allowlist sender with "payment received" + Bkg | `detect_stages` → `PAYMENT_CONFIRMED` → `on_payment_event` extracts BKG | append `{type:"PAID", bkg:X, date:recv_date}` to invoice_state.jsonl |
| Inbox mail with "nhắc thanh toán" / "reminder" + Bkg | `detect_stages` → NEW `PAYMENT_REMINDER` → `on_payment_event` | append `{type:"REMIND", bkg:X, date:recv_date}` |
| Daily cron 08:05 | Load InvoiceLog openpyxl, find STATUS=PENDING + DUE_DATE<today | append `{type:"OVERDUE", bkg:X}` + Telegram alert |
| User WIN click | VBA `InvoiceLog_InsertOnWin` reads AJ row | Insert row to InvoiceLog with PENDING |
| User "Sync invoices" click | VBA reads sidecar, updates rows, truncates JSONL | InvoiceLog rows STATUS updated |

## Risks + Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Auth-Results absent on internal mail** (biggest risk — accounting team may be pure internal Exchange, no DKIM signing) | HIGH | Medium | Fallback: if Authentication-Results header absent AND sender in `ACCOUNTING_ALLOWLIST` explicit → ALLOW. Log explicitly. Different from CNEE (which receives external OPS mail, auth-results always present). |
| ACCOUNTING_ALLOWLIST miss → legit payment unflagged | Medium | High (missed collection) | Weekly Telegram digest of rejected PAYMENT_* mails → Nelson reviews and appends sender |
| Bkg_No collision across years (same Bkg reused) | Low | Medium | DATE_ISSUED>today-180d recency filter in sync |
| Double-insert on WIN (Nelson clicks twice) | Medium | Low | VBA: check `Application.WorksheetFunction.CountIf(InvoiceLog.BKG_NO, bkg)=0` before insert |
| Partial payment (AMOUNT≠PAID_AMOUNT) | High (real scenario) | Medium | MVP: mark PAID on any payment mail. v2: reconcile amounts. Add NOTES col flag for Nelson manual review. |
| Scanner writes to InvoiceLog while Nelson editing → xlsm corrupt | Critical | Critical | Already mitigated — sidecar pattern (same as CNEE). Scanner NEVER writes xlsm. |
| Overdue mails spam Telegram | Medium | Low | Deduplication: append `{type:"OVERDUE_ALERTED", bkg:X, date:today}` — don't re-alert same bkg in <7d |
| Invoice mail references HBL not Bkg | High | Medium | Fallback match by HBL → lookup Active Jobs → get Bkg. Same pattern as CNEE. |

## Backwards Compatibility

- InvoiceLog sheet currently empty (header only) → no existing data to migrate
- Adding cols to empty sheet = zero risk
- Pre-migration step: backup `ERP_Master_v14.xlsm` to `erp/backups/ERP_Master_v14_pre-invoicelog_20260421.xlsm` (copy, not rename)
- Rollback: delete sheet cols D-K (keep BKG_NO, CUSTOMER if any data accumulates before rollback)

## Test Matrix

| Layer | Test | Validation |
|---|---|---|
| Unit | `_detect_payment_type("đã nhận thanh toán")` | returns `"PAID"` |
| Unit | `_detect_payment_type("nhắc thanh toán đơn N123")` | returns `"REMIND"` |
| Unit | `_detect_payment_type("booking confirmation")` | returns `None` |
| Unit | Kill switch file exists → `on_payment_event()` returns False | Bypass |
| Unit | Bulk detect → 6 BKGs in text → reject | Rate limit |
| Integration | Fake mail with PAYMENT_CONFIRMED + Bkg X → scanner run → assert sidecar has `{type:"PAID",bkg:X}` | Full pipeline |
| Integration | Overdue sweep: InvoiceLog row with DUE_DATE=yesterday → assert Telegram queued | Cron path |
| VBA manual | Mark WIN → InvoiceLog row appended with STATUS=PENDING | Flow 1 |
| VBA manual | Click "Sync invoices" → row STATUS=PAID | Flow 4 |
| Soak | 1 week live → no xlsm corruption, sidecar grows then drains on sync | Prod |

## Rollback Plan

Per phase:

- **Phase 01:** Delete 10 non-BKG/CUSTOMER cols from InvoiceLog sheet; restore backup xlsm if data loss.
- **Phase 02:** Comment out hook block in `shipment_brain.py:~595` + git revert `invoice_tracker.py`. Sidecar JSONL becomes orphan (harmless — untruncated file).
- **Phase 03:** Remove `InvoiceLog_InsertOnWin` call from `OnAction_MarkQuoteWin`. Existing WIN rows stay in InvoiceLog (harmless).
- **Phase 04:** Disable Task Scheduler entry. Overdue rows stay PENDING (Nelson manual).
- **Phase 05:** N/A — tests only.

No phase cascades: phases 02+03+04 independent; all fail-open (scanner continues, WIN button still works).

## Success Criteria (measurable)

- [ ] Week 1: ≥3 WIN clicks produce InvoiceLog rows (Flow 1 works)
- [ ] Week 1: ≥1 payment mail detected and STATUS flipped to PAID after Sync click (Flow 2+4 works)
- [ ] Week 1: Overdue sweep fires Telegram alert ≥1 time (Flow 3 works)
- [ ] Week 1: Zero xlsm corruption (same as CNEE soak)
- [ ] Week 1: Zero false-positive PAID flips (manual audit)

## File Ownership (parallel phase safety)

- Phase 01 owns: `ERP_Master_v14.xlsm` InvoiceLog sheet schema
- Phase 02 owns: `email_engine/core/invoice_tracker.py`, `shipment_brain.py` hook block
- Phase 03 owns: `erp-v14-ribbon-callbacks.bas` (must merge after Phase 01 confirms col layout)
- Phase 04 owns: Task Scheduler entry + `invoice_tracker.py` CLI path
- Phase 05 owns: `tests/test_invoice_tracker.py`

**Dependency graph:** 01 → (02 ∥ 03 ∥ 04) → 05. Phases 02/03/04 can run parallel but all need 01's col layout locked.

## Out of Scope (explicit YAGNI)

- Dashboard cell "Total outstanding: $X" on InvoiceLog (future)
- PAID_AMOUNT auto-reconciliation vs AMOUNT (future v2)
- Auto-send reminder email to customer (POLICY: Nelson always reviews)
- OCR invoice PDF parsing
- Multi-currency support (currently USD only)
- Web UI for invoice status

## Open Questions (for Nelson)

1. **ACCOUNTING_ALLOWLIST seed:** which SMTPs? Accounting team email addresses?
2. **Payment by email vs bank statement:** do payment confirmation mails come from Pudong accounting OR directly from banks? (affects allowlist)
3. **Partial payment handling:** if customer pays 50% → flag as PAID or new status PARTIAL? (v1 defaults to PAID)
4. **Reminder frequency:** auto-suppress reminders if <7d since last? (proposed yes)
5. **DATE_ISSUED timing:** today on WIN, OR wait until DN_SENT stage fires? (proposed: today on WIN for simplicity; Nelson can edit cell if DN delayed)
