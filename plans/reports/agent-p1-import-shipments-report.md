# Agent P1 — Import Shipments Report

**Date:** 2026-04-20
**Script:** `scripts/erp-import-shipments.py`
**Status:** DONE_WITH_CONCERNS

---

## Data Source Analysis

**File:** `C:/Users/Nelson/OneDrive/Desktop/Shipments.xlsx`
**Sheets processed:** 12 monthly (May 2025 → Apr 2026) — skip Sheet1/2/3

**Two schemas discovered (important):**

| Sheets | Col count | Col 1 | Col 8 | Col 18 | Col 26 |
|--------|-----------|-------|-------|--------|--------|
| May 2025 → Feb 2026 | 25 | `Customer` | `ATA` | `Carrier` | — |
| Mar 2026, Apr 2026 | 26 | `Stt` (serial) | `Carrier` | `ATA` | `Customer Type` |

Script uses **dynamic header detection** (`_detect_schema`) — reads header row 1 by name, not by position index. Safe for both schemas.

**Row counts (post-dedup):**

| Sheet | Non-empty rows | Skipped (no ID) | Has ID, no ETD |
|-------|---------------|-----------------|----------------|
| May–Dec 2025 | 130 | 0 | 0 |
| Jan–Feb 2026 | 24 | 1 | 0 |
| Mar 2026 | 20 | 4 | 1 |
| Apr 2026 | 26 | 20 | 2 |
| **TOTAL** | **200** | **25** | **3** |

Apr 2026 has 20 blank placeholder rows from Excel template — correctly skipped.

---

## Filter Rule Applied

```
ETD.month == Apr 2026  →  Active Jobs (5 rows)
ETD.month  < Apr 2026  →  Archive    (167 rows)
No ETD + has Bkg/HBL   →  SKIP + log warning (3 rows)
No Bkg AND no HBL       →  SKIP silently (25 rows)
```

Skipped rows with no ETD:
- `NELSON260325-01` (Mar 2026) — internal placeholder booking
- `NELSON260409-01` (Apr 2026) — same pattern
- `36564118` (Apr 2026) — Bkg No column contained Excel numeric date; Hbl No had multi-line text

---

## Dry-Run Counts

```
Active Jobs : +5 inserted (Bkg: SGNG47156900, SGNG47160400, ZIMUHCM80623198, 93217723, 6451184790)
Archive     : +167 inserted
```

---

## Schema Mapping (Active Jobs — 40 cols)

| Shipments field | → Active Jobs col | COL key | Notes |
|-----------------|-------------------|---------|-------|
| Customer | 4 | CRM_ID | direct |
| Customer Type | 25 | Customer_Type | new schema only (Mar+) |
| Routing | 20 | Routing | raw stored |
| Routing (parsed) | 5 | POL_POD | `derive_pol_pod()` → "HCM→HOUSTON" |
| Bkg No | 8 | Bkg_No | idempotency key |
| Hbl No | 9 | HBL_NO | |
| ETD | 13 | ETD | departure proxy |
| ETA | 21 | ETA | |
| ATA | 22 | ATA | |
| Container Type | 10 | Container_Type | |
| Quantity | 11 | Quantity | |
| Status | 14 | Status | mapped: Confirmed→BOOKED |
| Selling Rate | 16 | Selling_Rate | |
| Buying Rate | 17 | Buying_Rate | parsed from string e.g. "3571 + 75" via eval |
| Profit | 18 | Profit | |
| Si | 26 | SI_Received | |
| Cy | 27 | CY_Cutoff | |
| Carrier | 7 | Carrier | |
| Volume | 32 | Notes | appended as "Vol=X" |
| Hdl Fee Carrier | 32 | Notes | appended as "HdlFee=X" |
| Status_Calc | 32 | Notes | appended as "Calc=X" |
| Progress ETA | 32 | Notes | appended as "Progress=X" |
| ETD_Original | 31 | Delay_Log | "Re-sched from ETD_Orig YYYY-MM-DD" |
| Delay_Log | 31 | Delay_Log | merged with above |

**Auto-generated:**
- MONTH (col 1): `derive_month(ETD)` → "APR-26"
- Job_ID (col 3): "NF-MMDD-NNN" — sequential within run, avoids duplicates
- SERVICE (col 12): CY-DOOR if "VIA" in routing, else CY-CY
- Profit_Margin (col 24): Profit/Selling_Rate × 100
- Created_Date/Last_Updated (col 33/34): datetime.now()
- FAST_ID, Door_Address, TRACKING, Request_BKG: blank

---

## Archive Sheet Mapping (14 cols)

Existing Archive header at row 2 (row 1 = title "ARCHIVE — Completed / Cancelled Jobs"):

`Job_ID | FAST_ID | CUSTOMER | POL-POD | CARRIER | Bkg_No | HBL_NO | Container | Qty | SELL | COST | PROFIT | Delivered_Date | Closed_Reason`

Script auto-detects this structure, writes `_ensure_archive_header()` only if header absent.
`Delivered_Date` = ATA if available, else ETA. `Closed_Reason` = "Delivered".

---

## Known Edge Cases

1. **Buying Rate as expression** — "3571 + 75" parsed via restricted `eval()`. Safe (no builtins). Result = 3646.0.

2. **Bkg No = integer in Excel** — openpyxl returns int (e.g. `93217723`). `_parse_bkg_no()` converts to string for index matching.

3. **Job_ID counter** — uses `_JobIDCounter` scoped per record. For 5 active rows all with same ETD month, they will all get prefix "NF-0402-", "NF-0412-", etc. based on individual ETD date. If two records share same ETD date, counter increments correctly (NF-0402-001, NF-0402-002…).

4. **Console encoding** — `→` (U+2192) from `derive_pol_pod` causes UnicodeEncodeError on Windows cp1258 console. Fixed via encode-with-replace in `_log()`. Data written to Excel unaffected.

5. **Archive rows without Bkg_No** — May 2025 through some Feb 2026 rows have Bkg_No=None (booking not assigned yet). These still get written to Archive (HBL_NO is the alternate ID), but idempotency check on Bkg_No will INSERT on re-run since Bkg_No=None is not indexed. Nelson should assign Bkg_No in Shipments.xlsx to enable true idempotency for old rows.

6. **VITACOCO row** — Bkg No = `36564118` looks like an Excel numeric date (2000-01-01 + 36564118 days?) — likely a misformatted cell. Skipped correctly (ETD is None).

---

## Save Safety

Uses `save_preserving_ribbon(wb, target_path)` from `ERP.core.ribbon_guard`.
NEVER calls `wb.save()` directly. Gotcha #6 respected.
Backup created at `ERP_Master_v14.backup_YYYYMMDD_HHMMSS.xlsm` before any write.

---

## Concerns (DONE_WITH_CONCERNS)

1. **Archive idempotency for old rows** — rows without Bkg_No will duplicate on re-run. Acceptable for one-time historical import; Nelson should confirm.
2. **Job_ID counter resets per run** — if script is run twice, counter starts from 0 + max existing. Should be safe but Nelson must verify no NF- collision with manually entered Job_IDs.
3. **Bkg No = large integer** — 6 digit+ integers in Bkg No col (e.g. 6451184790, 93217723) are carrier booking numbers. Stored as string. Main agent should confirm this is correct treatment.
4. **Mar 2026 active vs archive boundary** — 4 rows in Mar 2026 have ETD in Mar → Archive. 1 has no ETD → skipped. Correct per filter rule.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Script created, syntax clean, dry-run verified. 5 Active rows + 167 Archive rows classified correctly. Key concerns: Archive idempotency for rows without Bkg_No; Job_ID counter restart behavior.
**Concerns/Blockers:** See concerns section above. No blockers — main agent can proceed to commit and Nelson live-test.
