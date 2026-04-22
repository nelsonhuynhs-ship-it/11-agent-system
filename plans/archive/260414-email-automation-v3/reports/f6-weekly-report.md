# F6 Weekly Report — Implementation Notes

**Feature:** Active Jobs v4 — Weekly Sales KPI Report Auto-Gen
**File:** `ERP/intelligence/weekly_report.py`
**Tests:** `tests/test_weekly_report.py` (10/10 pass)

---

## Previous File Disposition

The existing `weekly_report.py` was a 4C Market Analysis tool (Costing / Capacity / Challenge / Change) that read from `MasterFullPricing.xlsx` and printed a console market brief. It had no overlap with the sales KPI report requirement and was not used anywhere in the test suite. It was replaced entirely. If the 4C market report is needed in the future, it should be extracted to `ERP/intelligence/market_4c_report.py`.

---

## Sales Attribution Logic

**Problem:** Active Jobs v14 has no "Owner" or "Assigned Sales" column.

**Decision:** All jobs are attributed to Nelson (safe default). The `load_active_jobs_for_week()` function sets `"sales": "Nelson"` on every job row.

**Rationale:** Nelson is the primary NVOCC operator and currently manages the booking pipeline. Mentees do not yet have individual job ownership tracked in the ERP. When an Owner column is added to Active Jobs, the loader should be updated to read it at column N and map to sales names via `EMAIL_TO_SALES`.

**Email attribution:** The email_log.csv records `email` (recipient), not `sender`. The engine is run by Nelson, so all emails in the log are credited to Nelson. When the log gains a `sender_email` column, `load_emails_for_week()` auto-detects it and splits counts per sender.

---

## New vs Existing Customer Logic

- **CRM sheet** in `ERP_Master_v14.xlsm` is scanned for a "First Transaction Date" column (detected by header keyword search, not hardcoded column index — future-proof against column shifts).
- A customer (`CRM_ID`) is classified as **KH MOI (new)** if their `First Transaction Date` falls within the current ISO week (Monday 00:00 → Sunday 23:59:59).
- All other customers with jobs in the week are classified as **KH SDDV (existing)**.
- If the CRM sheet is missing or the column is not found, all customers default to the existing bucket. No crash, no silent error.

---

## TEU Volume Calculation

| Container | TEU Factor |
|-----------|-----------|
| 20GP / 20DC / 20RF | 1 |
| 40GP / 40DC / 40HC / 40HQ / 40RF / 45HC / 45HQ | 2 |
| Unknown types | 1 (safe default) |

Formula: `VOL = SUM(Quantity × TEU_factor)` per sales person.

---

## Hardcoded Columns (Manual Input by Nelson)

| Column | Value | Reason |
|--------|-------|--------|
| GAP KH | 0 | Nelson records in-person meetings manually |
| KH TIEM NANG | 0 | Pipeline tracking is manual |
| % HOAN THANH | empty string | Nelson calculates vs personal target |
| PLAN TUAN NAY | empty string | Next-week plan is entered manually |

---

## Assumptions

1. `Created_Date` (col 25, Active Jobs) is used as the job week filter — not ETD. Rationale: ETD can be weeks away; Created_Date reflects when the sale was booked.
2. ISO-8601 week numbering: weeks start Monday. Function `week_bounds()` derives Monday from the ISO week 1 anchor (Jan 4 is always in week 1).
3. Jobs with no `CRM_ID` are skipped (no customer to attribute).
4. The email log timestamp format `dd/mm/YYYY HH:MM` is the primary format; ISO variants are tried as fallbacks.

---

## CLI Output Path

Default: `D:\OneDrive\NelsonData\erp\weekly_reports\WEEKLY_{year}_W{week:02d}.xlsx`

The directory is created automatically if it does not exist.
