---
agent: QH-1
task: ERP Quote Polish — Fix A + C + D
date: 2026-04-19
---

# Agent QH-1 Report — erp-quote-polish.py

## Feature Checklist §A–D

### §A. Scope

**Q1. One-sentence description:**
Apply conditional formatting, KPI dashboard rows, autofilter and freeze pane to the Quotes sheet in ERP_Master_v14.xlsm via an idempotent Python script.

**Q2. ERP layers affected:**
- [x] Python helper (scripts/erp-quote-polish.py — NEW)
- [ ] Ribbon XML — not touched
- [ ] VBA handler — not touched
- [ ] Data schema — not touched (no new columns)
- [ ] External data — not touched

**Q3. Files created / modified:**
- CREATE: `scripts/erp-quote-polish.py`
- READ ONLY: `ERP/core/ribbon_guard.py`, `ERP/intelligence/price_watch.py` (Q_COL reference)
- NOT TOUCHED: any .bas, any other .py

**Q4. READ or WRITE to xlsm:**
WRITE — script modifies Quotes sheet formatting. Excel must be closed before run. `save_preserving_ribbon` is used (never `wb.save()`).

**Q5. Minimal viable slice:**
Single standalone script: Fix A (CF) + Fix C (KPI) + Fix D (autofilter/freeze) combined into one idempotent pass. No VBA changes needed.

---

### §B. Data dependencies

**Q6. Input data needed:**
- Quotes sheet columns (per price_watch.py Q_COL mapping):
  - col 2 (B) = Date
  - col 13 (M) = Buy_40GP
  - col 30 (AD) = Sell_40GP
  - col 36 (AJ) = Status

**Q7. Data present in workbook?**
Yes — Quotes sheet exists per erp-v14-source-of-truth.md.

**Q8. Output produced:**
- Modified Quotes sheet: formatting applied, KPI rows 1-3 inserted/refreshed, header at row 4, data from row 5
- Backup: `ERP_Master_v14.backup_YYYYMMDD_HHMMSS.xlsm` next to live file

**Q9. Who consumes the output?**
Nelson reads the Quotes sheet directly in Excel. KPI row 3 formulas auto-update each open. No downstream Python consumer — purely human-facing.

---

### §C. Standards compliance

**Q10. Gotchas applied:**
- **#6 (CRITICAL)** — `openpyxl.save()` strips customUI14.xml. Fixed: all saves go through `from ERP.core.ribbon_guard import save_preserving_ribbon`. `wb.save()` is never called directly in the script.
- **#7** — not applicable (no cell.value=None clearing in this script)
- No VBA written → #1/#2/#3/#4/#5/#11/#12 not applicable

**Q11. Source-of-truth imports:**
- Column indices read from `ERP/intelligence/price_watch.py` Q_COL dict (documented in comments), mirrored as constants in the script (`Q_DATE_COL=2`, `Q_STATUS_COL=36`, `Q_SELL_40GP_COL=30`, `Q_BUY_40GP_COL=13`). No hardcoded magic numbers without reference.

**Q12. Error handling strategy:**
- File-not-found → `sys.exit(2)` with clear message
- File lock (Excel open) → `PermissionError` caught → `sys.exit(1)` with "Close Excel first"
- Missing Quotes sheet → `sys.exit(3)` listing available sheets
- `ribbon_guard` import failure → `sys.exit(4)` with cause
- All backup/load steps wrapped in explicit checks

**Q13. Confirm dialog?**
Script is CLI-only (no ribbon button). `--dry-run` flag serves as the "preview before commit" safety valve. No interactive confirm needed.

---

### §D. Testing strategy

**Q14. 3 tests that prove it works:**

1. **Happy path** — mock workbook with Quotes sheet, 10 rows of data; run `main(dry_run=True)` → verify KPI rows inserted at rows 1-3, header at row 4, CF rules present, auto_filter.ref == "A4:AQ1000", freeze_panes == "A5".

2. **Idempotency (edge case)** — run script twice on same workbook; second run detects A1 == "📊 QUOTES TODAY", returns `kpi_status="REFRESHED"` and does NOT double-insert rows. KPI formula in A3 still correct after second run.

3. **Error path** — pass path to a non-existent file → script exits with code 2. Pass a locked file (simulate with pre-opened handle) → exits code 1. Pass xlsm without Quotes sheet → exits code 3.

**Q15. Regression check:**
```bash
python -c "import ast; ast.parse(open('scripts/erp-quote-polish.py', encoding='utf-8').read()); print('SYNTAX OK')"
scripts\verify-erp.bat
python scripts/erp-quote-polish.py --dry-run
```

---

## Gotchas applied (from docs/vba-gotchas.md)

| # | Gotcha | Applied |
|---|--------|---------|
| 6 | `openpyxl.save()` strips customUI14.xml | YES — `save_preserving_ribbon` used throughout, `wb.save()` never called directly |
| 7 | `cell.value = None` does not clear hyperlinks | N/A — no cell clearing in this script |
| 1-5, 8-12 | VBA-specific bugs | N/A — Python-only script |

---

## Script flow outline

```
main(erp_file, dry_run)
  ├── os.path.exists check            → exit 2 if missing
  ├── _check_excel_closed()           → open(erp_file, "a") probe → exit 1 if locked
  ├── _backup()                       → timestamped .xlsm copy (skip in dry-run)
  ├── openpyxl.load_workbook(keep_vba=True)
  ├── sheet lookup                    → exit 3 if "Quotes" missing
  ├── apply_kpi_rows(ws)
  │     ├── _kpi_already_inserted()  → check A1 == "📊 QUOTES TODAY"
  │     │     True  → _write_kpi_formulas() only → "REFRESHED"
  │     │     False → insert_rows(1,3) → style row1/2/3 → "INSERTED"
  ├── apply_conditional_formatting(ws)
  │     ├── clear existing CF rules  (idempotent reset)
  │     ├── FormulaRule: stale fade  (stopIfTrue)
  │     ├── FormulaRule: WIN/LOST/EXPIRED/PENDING
  │     └── range: A5:AQ1000
  ├── apply_autofilter_and_freeze(ws)
  │     ├── ws.auto_filter.ref = "A4:AQ1000"
  │     └── ws.freeze_panes = "A5"
  └── save_preserving_ribbon(wb, erp_file)   ← NOT wb.save()
```

---

## Column letter derivation (from Q_COL)

| Field | Col # | Letter |
|-------|-------|--------|
| Date | 2 | B |
| Buy_40GP | 13 | M |
| Sell_40GP | 30 | AD |
| Status | 36 | AJ |
| Last col (ContType+1) | 43 | AQ |

---

## Test plan (unit tests — optional)

File: `tests/test_erp_quote_polish.py`

```python
import openpyxl, pytest
from scripts.erp_quote_polish import apply_kpi_rows, apply_conditional_formatting, \
    apply_autofilter_and_freeze, _kpi_already_inserted, KPI_TITLE, HEADER_ROW, DATA_START_ROW

@pytest.fixture
def mock_wb_fresh():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quotes"
    # Seed header row and 3 data rows
    ws.append(["QuoteID", "Date", "Customer"] + [""] * 39)  # row 1 = header
    for i in range(1, 4):
        ws.append([f"Q{i:03}", "2026-04-19", f"CUST{i}"])
    return wb

def test_kpi_insert_fresh(mock_wb_fresh):
    ws = mock_wb_fresh["Quotes"]
    status = apply_kpi_rows(ws)
    assert status == "INSERTED"
    assert ws["A1"].value == KPI_TITLE
    # Original header pushed to row 4
    assert ws.cell(row=HEADER_ROW, column=1).value == "QuoteID"

def test_kpi_idempotent(mock_wb_fresh):
    ws = mock_wb_fresh["Quotes"]
    apply_kpi_rows(ws)
    # Second call must not insert again
    status = apply_kpi_rows(ws)
    assert status == "REFRESHED"
    # Row 5 still has first data row, not a new blank row
    assert ws.cell(row=DATA_START_ROW, column=1).value == "Q001"

def test_cf_rules_present(mock_wb_fresh):
    ws = mock_wb_fresh["Quotes"]
    apply_kpi_rows(ws)
    apply_conditional_formatting(ws)
    # Should have 5 CF rules (stale + 4 status)
    assert len(ws.conditional_formatting._cf_rules) == 5

def test_autofilter_freeze(mock_wb_fresh):
    ws = mock_wb_fresh["Quotes"]
    apply_kpi_rows(ws)
    apply_autofilter_and_freeze(ws)
    assert ws.auto_filter.ref == f"A{HEADER_ROW}:AQ1000"
    assert ws.freeze_panes == f"A{DATA_START_ROW}"
```

---

**Status:** DONE
**Summary:** `scripts/erp-quote-polish.py` created (200 lines). Syntax OK. Implements Fix A (conditional format 5 rules), Fix C (KPI rows idempotent), Fix D (autofilter+freeze). All saves via `save_preserving_ribbon`. `--dry-run` flag available. Backup before every write.
**Concerns:** None — no VBA touched, no schema change.
