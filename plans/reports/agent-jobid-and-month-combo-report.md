# Agent Report — JOBID-REMOVE + MONTH-COMBO

**Date:** 2026-04-20
**Agent:** JOBID-REMOVE + MONTH-COMBO

---

## Feature Checklist §A-D

### FIX 1 — Hide Job_ID

**A. Scope**
1. Hide Job_ID cols in Active Jobs (col C) + Archive (col A); stop auto-generating NF-MMDD-NNN IDs in import script. Primary key = Bkg_No.
2. Layers: Python helper (erp-import-shipments.py), new one-shot script, VBA (no change needed — already blank)
3. Files modified: `scripts/erp-import-shipments.py`; Created: `scripts/erp-hide-jobid-cols.py`
4. WRITE to xlsm (erp-hide-jobid-cols.py writes column_dimensions)
5. Minimal slice: hide cols + stop writing Job_ID in import script

**B. Data dependencies**
6. Active Jobs col C (Job_ID), Archive col A (Job_ID)
7. Data present — existing values preserved, only hidden flag changes
8. Output: hidden cols in xlsm; import no longer populates col 3/1
9. Downstream: Python scripts that read Job_ID via `COL["Job_ID"]` still work (value still there, just hidden)

**C. Standards**
10. Gotcha #6: erp-hide-jobid-cols.py uses `save_preserving_ribbon` — verified
11. `from active_jobs_cols import COL` — `COL["Job_ID"]=3` preserved, not deleted
12. try/except + argparse error handling in both scripts
13. Confirm dialog: N/A (one-shot script, not a ribbon button)

**D. Testing**
14. Tests: (1) dry-run prints "Would hide" without writing; (2) re-run after hide = idempotent (hidden=True again, no error); (3) import re-run → rec["Job_ID"] = None, col C stays blank
15. `python scripts/erp-hide-jobid-cols.py --dry-run` to preview

---

### FIX 2 — Month combo dropdown

**A. Scope**
1. Replace 3 Prev/Label/Next buttons with 1 comboBox showing "APR 2026 (26 jobs)" per month, filtered from actual data in Active Jobs + Archive.
2. Layers: Ribbon XML (CustomUI_v14.xml), VBA handler (erp-v14-jobs-automation.bas), Python (erp-import-shipments.py writes Archive MONTH col)
3. Files modified: `CustomUI_v14.xml`, `erp-v14-jobs-automation.bas`, `erp-import-shipments.py`, `erp-archive-add-month.py` (new)
4. READ (VBA scanning) + WRITE (filter via AutoFilter, no xlsm save needed for filtering)
5. Minimal slice: combo with real month list + AutoFilter on Active Jobs + Archive

**B. Data dependencies**
6. Active Jobs col 1 (MONTH), Archive col 15 (MONTH — new)
7. Archive MONTH col new — backfill via `scripts/erp-archive-add-month.py`
8. Output: AutoFilter applied to sheets; combo shows real counts
9. Downstream: VBA `OnChange_Month` → AutoFilter both sheets

**C. Standards**
10. Gotcha #1: No Chr() for Unicode — all ASCII label strings (APR, Tat ca). ChrW used only in ApplyTrackingDots (unchanged). OK.
    Gotcha #11: All 5 m_ vars at line 31-38, first Sub at line 40. VERIFIED.
    Gotcha #12: No leading underscore in new func names (RebuildMonthsList, MonthSortKey, MonthISOToDisplay, EnsureMonthsLoaded). VERIFIED by lint.
    Gotcha #6: erp-archive-add-month.py uses `save_preserving_ribbon`. VERIFIED.
11. Archive MONTH col added at end (col 15) — no column shifts, existing data intact
12. VBA: `On Error GoTo ErrBuild` in RebuildMonthsList; `On Error GoTo ErrChange` in OnChange_Month. Fallback to "Tat ca" if scan fails.
13. No confirm dialog needed — AutoFilter is non-destructive, no xlsm write

**D. Testing**
14. Tests:
    (1) Happy: open combo → shows months present in Active Jobs + Archive with correct counts
    (2) Edge: Archive has no MONTH col yet → EnsureMonthsLoaded fallback shows "Tat ca (N jobs)"
    (3) Error: sheet not found → ErrBuild fallback, no crash
15. Open ERP → Operations tab → Tháng group → dropdown visible with month options

---

## Gotchas Applied

| # | Gotcha | Applied |
|---|--------|---------|
| #1 | Chr → ChrW for Unicode | No new Unicode in month strings (ASCII only). ChrW already correct in existing ApplyTrackingDots. |
| #6 | save_preserving_ribbon | erp-hide-jobid-cols.py + erp-archive-add-month.py both use it. erp-import-shipments.py already used it. |
| #11 | Module vars at TOP | All 5 m_ vars declared before line 40 (first Sub). Verified by script. |
| #12 | No leading underscore | RebuildMonthsList, MonthSortKey, MonthISOToDisplay, EnsureMonthsLoaded — all clean. Verified by lint. |

---

## Line Diff Summary

### `scripts/erp-import-shipments.py`
- `ARCH_COL`: added `"MONTH": 15` entry
- `_ensure_archive_header`: header list + check includes MONTH col 15
- `write_active_jobs`: removed `_JobIDCounter` instantiation; sets `rec["Job_ID"] = None`
- `write_archive`: removed `_JobIDCounter`; signature `_write_archive_row(ws, row, rec)` (no job_id param)
- `_write_archive_row`: signature simplified; no longer writes Job_ID; adds MONTH write at col 15

### `scripts/erp-hide-jobid-cols.py` (NEW, ~110 lines)
- One-shot: hide Active Jobs col C + Archive col A; save_preserving_ribbon; idempotent

### `scripts/erp-archive-add-month.py` (NEW, ~120 lines)
- Backfill MONTH col 15 from Delivered_Date; derive "APR-26" format; idempotent; --overwrite flag

### `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml`
- Removed: `btnMonthPrev`, `btnMonthLabel`, `btnMonthNext`
- Added: `cmbMonth` comboBox with `getItemCount/getItemLabel/onChange/getText`

### `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas`
- Module top: added `m_Months()`, `m_MonthISO()`, `m_MonthCount`, `m_SelectedMonthLabel`; renamed `m_CurrentMonth` comment to DEPRECATED
- Added: `RebuildMonthsList`, `MonthSortKey`, `MonthISOToDisplay`, `EnsureMonthsLoaded`
- Added callbacks: `GetItemCount_Month`, `GetItemLabel_Month`, `GetText_Month`, `OnChange_Month`
- Old handlers: `OnAction_MonthPrev/Next/Reset`, `ShiftMonth`, `CurrentMonthISO`, `FormatMonthLabel`, `GetLabel_CurrentMonth` marked DEPRECATED (kept as stubs)

### `ERP/vba-v14-mirror/` (mirror updated)
- `erp-v14-jobs-automation.bas` — identical to OneDrive canonical
- `CustomUI_v14.xml` — identical to OneDrive canonical

---

## Known Concerns

1. **Archive MONTH derivation accuracy**: If some Archive rows have no Delivered_Date (null), MONTH will be blank — those rows won't appear in any month filter, only in "Tat ca". Acceptable per Nelson's requirement (Bkg_No is PK, Delivered_Date should be present on archived rows).

2. **cmbMonth combo first load**: VBA `RebuildMonthsList` runs lazily on first `GetItemCount_Month` call. If workbook opens with Operations tab visible, the combo will populate correctly. If combo never refreshes after new data import (without closing/reopening), Nelson may need to click away and back to force ribbon invalidate. Mitigation: add `ribbonUI.Invalidate` call in `RebuildMonthsList` if `ribbonUI` is accessible from JobsAutomation module (currently only accessible from ERPv14Ribbon module). Not blocking — workaround is ribbon tab switch or workbook reopen.

3. **Archive AutoFilter field number**: `Field:=15` assumes no hidden cols shift the filter field count. If Archive sheet has hidden cols before col 15, the field number may be off. In practice Archive has no hidden cols pre-2026-04-21 except Job_ID col A which is being hidden now — hidden cols count in AutoFilter Field numbering, so Field:=15 should be correct.

4. **_JobIDCounter class remains in erp-import-shipments.py**: Class is defined but no longer called. Can be removed in future cleanup. Left to avoid breaking any external code that might import it.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** FIX 1 (hide Job_ID) and FIX 2 (month combo) fully implemented. Python syntax verified. VBA gotchas #1/#6/#11/#12 all checked clean. Mirror files match canonical. Integration steps for Nelson: (1) close Excel, (2) run erp-hide-jobid-cols.py, (3) run erp-archive-add-month.py, (4) reimport VBA via reimport-erp-vba-modules.py, (5) VBE Debug.Compile, (6) open ERP → Operations → Tháng combo should show months with counts.
**Concerns:** ribbon combo lazy-load may need tab switch to refresh after data import (minor UX, not blocking); MONTH blank for Archive rows with no Delivered_Date (cosmetic, acceptable).
