# Phase 1 — Data Migration Foundation

**Status:** PENDING (start first)
**Effort:** 10h
**Cost:** $0
**Priority:** P0 — blocks all other phases

## Overview

Gom 7 file xlsx + 9 panjiva raw thành 1 master file 2-sheet, bảo vệ 5 cột priority, fill 95% cột rỗng, zero data loss.

## Key insights

- 22,230 rows hiện tại có `EMAIL_STATUS`/`SEND_COUNT`/`REPLY_STATUS` thật từ production → TUYỆT ĐỐI không overwrite
- 9 panjiva raw chứa Email 2/3, Phone 2/3, Shipper side, Place of Receipt, Carrier mà `panjiva_clean.py` v1 bỏ qua
- Split CNEE/SHIPPER = business rule của Nelson (Shipper VN đụng team, phải HOLD)

## Requirements

**Functional:**
- Output `contact_unified_v6.xlsx` 2 sheet CNEE + SHIPPER
- Schema 35 cột (xem plan.md)
- Primary key = EMAIL lowercase/trim per sheet
- Audit log CSV từng row action (NEW/UPDATE/SKIP) + cột đổi

**Non-functional:**
- Dry-run mode trước khi write thật
- Backup rotation 14 bản
- Rollback 1-click
- Validator phone E.164 format

## Architecture

```
Sources (7 files + 9 panjiva_raw)
   │
   ▼
[Step 1-4] Load + lock priority + re-extract panjiva
   │
   ▼
[Step 5-8] Merge CNEE side + SHIPPER side
   │
   ▼
[Step 9-11] Dedupe + blacklist + timezone map
   │
   ▼
[Step 12-14] Score + validate + save 2-sheet xlsx
```

## Files to create

- `scripts/panjiva_clean_v2.py` — extract 15 cols, split consignee↔shipper
- `scripts/migrate-to-unified-v6.py` — 14-step pipeline với --dry-run flag
- `scripts/lib/timezone_mapper.py` — STATE → US timezone
- `scripts/lib/audit_logger.py` — row-level change CSV writer

## Files to update

- Không overwrite — create new file, keep `cnee_master_v2_final.xlsx` as backup

## Implementation steps

1. Viết `timezone_mapper.py` + `audit_logger.py` utilities (1h)
2. Viết `panjiva_clean_v2.py` + unit test 1 file (2.5h)
3. Viết `migrate-to-unified-v6.py` skeleton 14 step (1h)
4. Implement step 1-5 (load + lock + re-extract + CNEE merge) (1.5h)
5. Implement step 6-11 (SHIPPER + supporting merges + dedupe) (1.5h)
6. Implement step 12-14 (score + validate + save) (1h)
7. Dry-run trên toàn bộ source, kiểm diff preview (0.5h)
8. Run thật, verify priority rows nguyên vẹn (1h)

## Todo checklist

- [x] `scripts/lib/timezone_mapper.py` created
- [x] `scripts/lib/audit_logger.py` created
- [x] `scripts/panjiva_clean_v2.py` extracts all 15 cols
- [x] Split logic CNEE vs SHIPPER correct
- [x] `scripts/migrate-to-unified-v6.py` 14 steps implemented
- [x] `--dry-run` flag works (tested: 22842 CNEE + 662 SHIPPER, no write)
- [x] 5-col LOCK verified (EMAIL_STATUS, SEND_COUNT, LAST_SENT_DATE, REPLY_STATUS, TIER=CUSTOMER/VIP)
- [x] Backup rotation 14 bản
- [x] Audit log CSV format pass
- [ ] `contact_unified_v6.xlsx` 2 sheets saved (pending real run by Nelson)
- [ ] Spot-check 20 random priority rows — no data lost
- [ ] POL/STATE/CARRIER fill rate >= 60%

## Success criteria

- 2-sheet file exists with ~30K total rows
- Priority rows (SEND_COUNT>0 OR REPLY_STATUS!=null OR TIER=CUSTOMER) untouched
- Audit log shows NEW/UPDATE/SKIP counts matching expected
- Dry-run output matches actual run output

## Risk assessment

| Risk | Mitigation |
|---|---|
| Overwrite priority data | 5-col LOCK + dry-run + audit log |
| Dedupe loses rows | Ưu tiên row SEND_COUNT>0 khi conflict |
| Panjiva re-extract ra wrong split | Test 1 file trước, check consignee/shipper count |
| Excel file lock by Nelson | Script detect + retry + message user close |

## Security considerations

- Backup rotation encrypted? → không cần, file nội bộ
- Audit log contain emails? → yes, local only, không commit git

## Next steps

Phase 2 (Typo Shield + Bounce Harvest) depends on this. After Phase 1 pass:
- Phase 2 can read from `contact_unified_v6.xlsx`
- Phase 3 Shipper Blacklist operates on SHIPPER sheet
- Phase 4 Contacts UI displays both sheets
