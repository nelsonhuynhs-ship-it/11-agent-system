# Phase 01 — InvoiceLog Schema + Sample Data

**Priority:** P2 · **Status:** pending · **Effort:** 30m · **Blocks:** Phase 02, 03, 04

## Context Links

- [plan.md](plan.md) — overview
- [SYSTEM_STANDARDS §5](../../docs/SYSTEM_STANDARDS.md) — xlsm migration via win32com (not openpyxl — preserves VBA)
- ERP live file: `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm`

## Goal

Lock down InvoiceLog schema (11 cols) on live xlsm. Backup first. Emit Python col index constants for Phase 02 + VBA constants for Phase 03 to import.

## Current State

InvoiceLog sheet exists but empty (header only per `erp-v14-source-of-truth.md:38`). Unknown existing headers — MUST dump first, not assume.

## Schema (final)

| Col | Name | Width | Type | Notes |
|---|---|---|---|---|
| A (1) | BKG_NO | 16 | text | Primary key |
| B (2) | CUSTOMER | 24 | text | From AJ row |
| C (3) | INVOICE_NUMBER | 14 | text | Secondary key |
| D (4) | AMOUNT | 10 | number | USD, 0 decimals |
| E (5) | DATE_ISSUED | 11 | date | dd/mm/yyyy |
| F (6) | DUE_DATE | 11 | date | dd/mm/yyyy |
| G (7) | STATUS | 9 | text | PENDING/PAID/OVERDUE + Data Validation dropdown |
| H (8) | PAID_DATE | 11 | date | dd/mm/yyyy |
| I (9) | PAID_AMOUNT | 10 | number | USD (manual v2) |
| J (10) | LAST_REMINDER_DATE | 11 | date | dd/mm/yyyy |
| K (11) | NOTES | 40 | text | Free-form |

Header row: **1**. Data starts row **2**.

## Conditional Formatting (KISS, done during migration)

- STATUS=OVERDUE → red fill
- STATUS=PAID → green fill  
- STATUS=PENDING → no fill (default)
- DUE_DATE < today AND STATUS=PENDING → yellow fill (upcoming overdue visual cue)

## Related Code Files

**Create:**
- `ERP/core/invoice_log_cols.py` (source of truth — Python col index constants)
- `scripts/migrate_invoicelog_schema.py` (win32com migration — one-shot)

**Read:**
- `ERP/core/active_jobs_cols.py` (reference pattern)
- `docs/SYSTEM_STANDARDS.md` §5 (win32com rules)

## Implementation Steps

1. **Inspect current state:**
   ```bash
   python scripts/dump_erp_structure.py --sheet InvoiceLog
   ```
   Record current headers → add to this phase doc as "Before state".

2. **Backup xlsm:**
   ```powershell
   Copy-Item "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm" `
             "D:/OneDrive/NelsonData/erp/backups/ERP_Master_v14_pre-invoicelog_20260421.xlsm"
   ```

3. **Create `ERP/core/invoice_log_cols.py`:**
   ```python
   # Source of truth: InvoiceLog sheet columns
   HEADER_ROW = 1
   DATA_START_ROW = 2
   
   COL = {
       "BKG_NO": 1,
       "CUSTOMER": 2,
       "INVOICE_NUMBER": 3,
       "AMOUNT": 4,
       "DATE_ISSUED": 5,
       "DUE_DATE": 6,
       "STATUS": 7,
       "PAID_DATE": 8,
       "PAID_AMOUNT": 9,
       "LAST_REMINDER_DATE": 10,
       "NOTES": 11,
   }
   
   STATUS_VALUES = ("PENDING", "PAID", "OVERDUE")
   DUE_DAYS_DEFAULT = 30
   ```

4. **Write `scripts/migrate_invoicelog_schema.py`:**
   - Use `win32com.client.Dispatch("Excel.Application")` (NOT openpyxl — preserves VBA)
   - Open xlsm, set Visible=False
   - Write 11 headers row 1
   - Set column widths
   - Add Data Validation dropdown for STATUS col (PENDING,PAID,OVERDUE)
   - Add 3 Conditional Formatting rules
   - Freeze row 1
   - Save + Close + Quit app

5. **Run migration on live xlsm:** (Nelson manual trigger — NOT auto)
   ```bash
   python scripts/migrate_invoicelog_schema.py
   ```

6. **Verify:**
   - Open ERP manually, check InvoiceLog headers row 1 matches schema
   - Check VBA modules intact (Alt+F11 → list modules unchanged)
   - Check 1 existing module loads without error

## Todo List

- [ ] Dump current InvoiceLog state
- [ ] Backup xlsm to `backups/` folder
- [ ] Create `ERP/core/invoice_log_cols.py`
- [ ] Write `scripts/migrate_invoicelog_schema.py`
- [ ] Dry-run migration on xlsm COPY first
- [ ] Run migration on live xlsm
- [ ] Manual verify headers + VBA intact
- [ ] Commit `invoice_log_cols.py` + migration script

## Success Criteria

- [ ] InvoiceLog row 1 has 11 named headers matching schema
- [ ] STATUS col has dropdown Data Validation
- [ ] 3 Conditional Formatting rules applied
- [ ] All existing VBA modules load (open Alt+F11, no missing references)
- [ ] Backup file exists and opens cleanly

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Migration on live xlsm corrupts VBA | Run on COPY first; use win32com not openpyxl (preserves VBA per SYSTEM_STANDARDS §5) |
| Nelson has xlsm open during migration | Script checks `Application.Workbooks` and aborts if ERP open |
| Sheet "InvoiceLog" renamed | Script tries exact + fuzzy match; aborts on no match (no silent create) |

## Rollback

- Delete cols C-K (keep A-B; users likely entered manually)
- OR restore from `backups/ERP_Master_v14_pre-invoicelog_20260421.xlsm`

## Next Steps

Unblocks Phase 02 (needs `invoice_log_cols.py`), Phase 03 (needs col constants in VBA), Phase 04 (needs schema).
