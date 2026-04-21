# Phase 01 — Schema Setup

**Effort:** 1h
**Priority:** HIGH (foundation)
**Status:** pending
**Depends on:** none

## Overview

Thêm cột mới vào CRM sheet + Active Jobs sheet. Backfill default values.

## Files Modified

| File | Change |
|------|--------|
| `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` | Add cols |
| `scripts/erp-add-notify-columns.py` | NEW — migration script |
| `docs/SYSTEM_STANDARDS.md` | Update Active Jobs schema section |

## Schema Changes

### CRM sheet (add 1 col)

| Col Name | Type | Default | Notes |
|----------|------|---------|-------|
| `AUTO_NOTIFY` | Boolean (TRUE/FALSE) | FALSE | Nelson tick per customer |

### Active Jobs sheet (add 3 cols)

| Col Name | Type | Default | Notes |
|----------|------|---------|-------|
| `ATD` | Date | empty | Scanner auto-fill |
| `ETA` | Date | empty | Nelson manual nhập lúc booking |
| `LAST_NOTIFIED` | Text | empty | Format: `"ATD 2026-04-20 \| ETA-7 2026-04-25"` |

### Archive sheet

Same 3 cols as Active Jobs (để không miss khi migrate archive).

## Implementation Steps

1. Backup ERP_Master_v14.xlsm (timestamp backup theo convention)
2. Write `scripts/erp-add-notify-columns.py`:
   - Use `openpyxl` or `win32com` (per SYSTEM_STANDARDS §5 — use `save_preserving_ribbon`)
   - Insert cols at right position (after existing cols, before formula cols)
   - Apply header styling (match existing header format)
   - Add data validation for AUTO_NOTIFY (TRUE/FALSE dropdown)
   - Add date format for ATD/ETA cols
3. Run script with `--dry-run` first → verify col positions
4. Run live → verify ERP xlsm open correctly
5. Update `docs/SYSTEM_STANDARDS.md` section about Active Jobs schema

## Todo List

- [ ] Backup xlsm with timestamp
- [ ] Write migration script `scripts/erp-add-notify-columns.py`
- [ ] Test dry-run
- [ ] Apply migration live
- [ ] Verify xlsm opens + ribbon intact
- [ ] Update SYSTEM_STANDARDS.md
- [ ] Commit

## Success Criteria

- [ ] CRM sheet có col `AUTO_NOTIFY` với dropdown TRUE/FALSE
- [ ] Active Jobs có 3 col mới, header đẹp
- [ ] Archive sheet same
- [ ] Open xlsm không warning, ribbon intact
- [ ] Validation script `python scripts/validate-system.py` pass

## Risks

| Risk | Mitigation |
|------|-----------|
| xlsm ribbon bị corrupt | `save_preserving_ribbon` pattern per SYSTEM_STANDARDS §5 |
| Col position collision với future code | Place at END of existing cols |
| Type validation conflict | Use Excel data validation (dropdown), not formula |

## Next Phase

Phase 02 — Composer module reads these new cols.
