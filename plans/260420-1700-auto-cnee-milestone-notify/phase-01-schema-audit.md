# Phase 01 — Schema Audit + Minimal Changes

**Effort:** 1h
**Priority:** HIGH (foundation + safety)
**Status:** pending

## Key Changes vs v1

- **First: AUDIT** actual Active Jobs + CRM headers (red-team B1: schema assumptions unverified)
- **Test on COPY** before production (red-team D2: rollback risk)
- **4 cols** (not 3) — boolean `NOTIFIED_ATD`, `NOTIFIED_ETA7` instead of substring `LAST_NOTIFIED` (red-team B5)
- **Drop Archive changes** (red-team C4: speculative)
- **Use win32com** preserving VBA/ribbon (per SYSTEM_STANDARDS §5)

## Steps

### 1. Audit current schema (15 min)

```bash
python scripts/_audit-erp-headers.py
```

Script output:
- Active Jobs actual header row + col names
- CRM sheet actual header row + col names
- Customer name samples from both sheets (check alignment)
- Save to `plans/reports/erp-headers-audit.csv`

**Stop + review** before proceeding. If customer names don't align between sheets → flag to Nelson, may need alias map.

### 2. Backup + test on COPY (15 min)

```bash
# Backup per SYSTEM_STANDARDS backup convention
cp "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm" \
   "D:/OneDrive/NelsonData/erp/ERP_Master_v14.backup_$(date +%Y%m%d_%H%M%S).xlsm"

# Create test copy
cp "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm" \
   "D:/OneDrive/NelsonData/erp/ERP_Master_v14.migration_test.xlsm"
```

Run migration script on `migration_test.xlsm` first. Open in Excel, verify:
- [ ] All 6 VBA modules present (Alt+F11)
- [ ] Ribbon buttons visible + clickable
- [ ] Data validation dropdowns on new cols work
- [ ] No "repair" dialog on open

### 3. Migration script (20 min)

`scripts/erp-add-milestone-cols.py`:

```python
# Use win32com (NOT openpyxl) to preserve VBA
import win32com.client
from pathlib import Path

ERP_PATH = r"D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"

def add_milestone_columns(test_mode=False):
    path = ERP_PATH if not test_mode else ERP_PATH.replace(".xlsm", ".migration_test.xlsm")

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    wb = excel.Workbooks.Open(path)
    try:
        # CRM sheet: add AUTO_NOTIFY
        crm = wb.Worksheets("CRM")
        add_col_if_missing(crm, "AUTO_NOTIFY", default="N",
                           validation_list=["Y", "N"])

        # Active Jobs: add 4 cols
        active = wb.Worksheets("Active Jobs")
        add_col_if_missing(active, "ATD_DATE", date_format=True)
        add_col_if_missing(active, "ETA_DATE", date_format=True)
        add_col_if_missing(active, "NOTIFIED_ATD", default="N",
                           validation_list=["Y", "N"])
        add_col_if_missing(active, "NOTIFIED_ETA7", default="N",
                           validation_list=["Y", "N"])

        wb.Save()  # Preserves VBA + ribbon natively with win32com
    finally:
        wb.Close()
        excel.Quit()

if __name__ == "__main__":
    import sys
    test_mode = "--test" in sys.argv
    add_milestone_columns(test_mode=test_mode)
```

### 4. Pre-rollback export (5 min)

Add `--rollback` flag that exports data FIRST:

```python
def rollback():
    # 1. Export current data to CSV (safety net)
    export_path = Path("plans/reports/erp-milestone-rollback-export.csv")
    # ... pandas read + save ...

    # 2. Then remove cols
    # ... remove cols ...
```

### 5. Verify + commit (5 min)

- [ ] Run `python scripts/validate-system.py` — pass
- [ ] Open ERP live → tick 1 customer CRM.AUTO_NOTIFY = "Y" → Save → reopen → still "Y"
- [ ] Git commit: `feat(erp): add milestone notify cols (CRM AUTO_NOTIFY + Active Jobs 4 cols)`

## Todo

- [ ] Write `scripts/_audit-erp-headers.py`
- [ ] Run audit, verify customer name alignment
- [ ] Backup xlsm (timestamped)
- [ ] Create migration_test copy
- [ ] Write `scripts/erp-add-milestone-cols.py` with `--test` + `--rollback` flags
- [ ] Run on COPY first — verify VBA + ribbon intact
- [ ] Run on production xlsm
- [ ] Export test: add value manually → save → reopen → value persists
- [ ] Update `docs/SYSTEM_STANDARDS.md` Active Jobs + CRM schema sections
- [ ] Commit

## Success Criteria

- [ ] Audit shows actual column names (Nelson verified alignment)
- [ ] Migration runs clean on COPY, VBA + ribbon intact
- [ ] Production migration zero-downtime
- [ ] Rollback path tested (CSV export → restore)

## Risks

| Risk | Mitigation |
|------|-----------|
| Customer names misalign between sheets | Audit first, build alias map if needed |
| VBA corruption | win32com (not openpyxl) + test on COPY |
| Column position breaks existing formulas | Insert at END, not inside existing range |

## Next Phase

Phase 02 uses these cols + imports the composer module.
