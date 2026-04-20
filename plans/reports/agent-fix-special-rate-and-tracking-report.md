# Agent Report: FIX → Special Rate + TRACKING Backfill
Date: 2026-04-20

## Deliverables

### FIX 1 — "FIX" → "Special Rate"

#### a. `D:/OneDrive/NelsonData/pricing/carrier_rules/_common.json`
Added two new sections at end of file:
- `source_shortcuts` — exact-match map: `FIX → "Special Rate"`, FAK/SCFI no-op
- `note_shortcuts_source` — substring replacements for Note col: `"FIXED RATE"`, `"Fixed Rate"`, `"FIX RATE"` → `"Special Rate"`

#### b. `Pricing_Engine/normalization/text_normalize.py`
Added `normalize_source(df)` public function:
- Reads `_SOURCE_SHORTCUTS` (FIX → Special Rate) and applies to `Source` column
- Applies `_NOTE_SHORTCUTS_SOURCE` to `Note` column (substring replace, idempotent)
- Falls back to `Rate_Type` col if `Source` not yet renamed
- Idempotent: "Special Rate" not in any source key, safe to re-run

#### c. `D:/OneDrive/NelsonData/erp/refresh-v14.py`
- Added `normalize_source as _tn_normalize_source` to import block
- Called `_tn_normalize_source(pivot)` after the `Rate_Type → Source` rename
- Prints count of "Special Rate" rows to refresh log

#### d. `erp-v14-ribbon-callbacks.bas` (OneDrive + mirror)
- Changed `contractLabel = "FIX"` → `contractLabel = "Special Rate"` at line 2107
- Mirror synced to `ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas`

### FIX 2 — TRACKING for migrated rows

#### e. `scripts/erp-import-shipments.py`
- Added `derive_tracking_stage(ata, etd_original, etd, status, bkg_no)` helper
- Added `_DOT_FULL` / `_DOT_EMPTY` unicode constants (U+25CF, U+25CB)
- Decision table (first match wins):
  - ATA not null → `ARRIVED` | `●●●●●●●○○○` (7/10)
  - ETD rescheduled OR Status=LOADED → `ATD` | `●●●●●●○○○○` (6/10)
  - Bkg_No present + Status=BOOKED/CONFIRMED → `BOOKED` | `●○○○○○○○○○` (1/10)
  - fallback → `PENDING` | `○○○○○○○○○○` (0/10)
- `read_shipments()` now calls `derive_tracking_stage()` inline and populates
  `TRACKING` and `TRACKING_STAGE` keys (previously both `None`)

#### f. `scripts/erp-fix-tracking-migrated.py` (NEW)
- One-shot backfill script for already-migrated rows
- Scans Active Jobs sheet: eligible = Bkg_No present AND TRACKING empty
- Uses ETD_Original proxy from Delay_Log ("Re-sched" text detection)
- Imports helpers from `erp-import-shipments.py` via importlib (DRY)
- `save_preserving_ribbon` (gotcha #6) — never `wb.save()`
- CLI: `python scripts/erp-fix-tracking-migrated.py [--dry-run] [--target PATH]`
- Idempotent: rows with TRACKING already filled are skipped

---

## Test Samples

### FIX 1 — normalize_source() before/after (verified with smoke test)

| Before Source | Before Note                  | After Source  | After Note                     |
|---------------|------------------------------|---------------|--------------------------------|
| `FIX`         | `FIXED RATE SOC DIRECT`      | `Special Rate`| `Special Rate SOC DIRECT`      |
| `FAK`         | `ZIM OWS INCL`               | `FAK`         | `ZIM OWS INCL` (unchanged)     |
| `SCFI`        | `FIX RATE TRANSIT`           | `SCFI`        | `Special Rate TRANSIT`         |

### FIX 2 — derive_tracking_stage() before/after (verified with 5-case smoke test)

| ATA      | ETD rescheduled | Status      | Bkg_No  | Stage    | Dots length |
|----------|-----------------|-------------|---------|----------|-------------|
| 2026-04-15 | -             | ARRIVED     | BKGABC  | ARRIVED  | 10          |
| -        | YES (3/1→4/1)   | BOOKED      | BKGXYZ  | ATD      | 10          |
| -        | -               | CONFIRMED   | BKGDEF  | BOOKED   | 10          |
| -        | -               | BOOKED      | BKGQQQ  | BOOKED   | 10          |
| -        | -               | PENDING     | (none)  | PENDING  | 10          |

All 5 cases: [OK]

---

## Gotchas Applied

- **#6 save_preserving_ribbon**: `erp-fix-tracking-migrated.py` uses `save_preserving_ribbon()` — never `wb.save()`
- **#1 ChrW for Unicode**: Python openpyxl writes raw unicode strings directly (no ChrW needed); dot chars written as `\u25cf` / `\u25cb`
- **#11 vars at top / #12 no underscore**: no VBA written (only the one-line contractLabel change); .bas change verified syntactically valid

---

## Integration Steps (for main agent to run)

1. Close Excel
2. `python D:/OneDrive/NelsonData/erp/refresh-v14.py` — verify "Source normalized: N Special Rate rows" in log + Pricing Dry sheet col 9 shows "Special Rate" for FIX rows
3. `python scripts/erp-fix-tracking-migrated.py --dry-run` — preview rows to fix
4. `python scripts/erp-fix-tracking-migrated.py` — apply backfill, check "Backfilled TRACKING for N row(s)"
5. Re-import VBA `.bas` if needed via `install_jobs_automation.py` — live compile check
6. Nelson Excel test: open ERP, check Active Jobs TRACKING dots + Source col in Pricing Dry

---

**Status:** DONE
**Summary:** FIX→Special Rate wired in 4 places (JSON config, text_normalize.py, refresh-v14.py, VBA ribbon). TRACKING auto-derive added to erp-import-shipments.py for future imports; one-shot backfill script ships for the 5 existing migrated rows.
