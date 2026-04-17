# Phase 01 — Root-Cause Analysis & Baseline

**Priority:** P0 (blocks Phase 02)
**Status:** ⏳ PENDING
**Depends on:** nothing
**Est. tokens:** ~5k (audit only, no code change)

## Overview

Trước khi rewrite, phải hiểu script hiện tại đang làm gì trên data thật. Chạy `price_watch.py` với ERP hiện tại, capture output, đối chiếu với Quotes + Pricing Dry/Reefer sheet để xác định chính xác tại sao Nelson không thấy alert.

## Key Insights (assumed — phải verify)

1. Threshold $50 có thể filter hết alerts nếu Quotes sheet chưa có Buy rate column hoặc data thiếu
2. Matching (POL, POD, Place, Carrier, Cont) exact — nhiều quote sẽ miss vì carrier text mismatch
3. Có thể Quotes sheet đang empty hoặc rất ít row PENDING
4. Active Jobs col 35/36 trong code cũ là SAI — phải là 39/40 theo `active_jobs_cols.py`

## Requirements

### Functional
- [ ] Chạy `price_watch.py --threshold 0` (threshold 0 = show all matches) → capture text output
- [ ] Đếm số quote PENDING trong Quotes sheet
- [ ] Đếm số unique (POL, POD, Carrier, Cont) trong Pricing Dry/Reefer
- [ ] Đo bao nhiêu quote có carrier text match exact với Pricing, bao nhiêu match fuzzy, bao nhiêu miss
- [ ] List 10 carrier names thường xuất hiện trong Quotes vs Pricing → tạo seed alias map

### Non-Functional
- [ ] Script audit không được mutate ERP file (mở read-only hoặc copy)
- [ ] Report đặt tại `research/phase-01-baseline.md`

## Architecture

```
audit_price_watch.py (new helper — one-off)
  ├─ openpyxl read-only load ERP_Master_v14.xlsm
  ├─ scan Quotes: count PENDING, list carrier set, list (POL,POD) set
  ├─ scan Pricing Dry + Reefer: count rows, list carrier set
  ├─ cross-match: for each PENDING quote, try match against pricing
  │    - exact (POL,POD,Place,Carrier,Cont)
  │    - routine (POL,POD,Cont) any carrier
  │    - line (POL,POD,Carrier,Cont) any place
  └─ dump report → plans/260415-price-watch-v2-requote-alert/research/phase-01-baseline.md
```

## Related Code Files

**Read:**
- `ERP/intelligence/price_watch.py` (398 lines)
- `ERP/core/active_jobs_cols.py` (col 39/40)

**Create (one-off audit, not production):**
- `ERP/intelligence/audit_price_watch.py` (~120 lines)
- `plans/260415-price-watch-v2-requote-alert/research/phase-01-baseline.md`

**Do NOT modify:**
- ERP_Master_v14.xlsm (read-only)
- price_watch.py (Phase 02 rewrite)

## Implementation Steps

1. Write `audit_price_watch.py` — uses `openpyxl.load_workbook(..., read_only=True, data_only=True)`
2. Build 4 data structures:
   - `quotes_carriers: Counter[str]` — count carrier strings in Quotes PENDING
   - `pricing_carriers: Counter[str]` — count carrier strings in Pricing Dry + Reefer
   - `pending_quotes: list[dict]` — each quote with POL/POD/Carrier/Buy rates
   - `pricing_index: dict[(POL,POD,Place,Carrier,Cont), float]`
3. Cross-match loop: for each pending quote, check 3 lookup tiers → record hit/miss
4. Dump markdown report with:
   - Row counts
   - Top 10 carriers side-by-side (Quotes vs Pricing)
   - Hit rates per tier
   - 5 sample miss cases (debug hints)
5. Run script, paste output to `research/phase-01-baseline.md`

## Todo List

- [ ] Write `audit_price_watch.py`
- [ ] Run with ERP closed (`os.path.exists` + try open r+b check)
- [ ] Generate `research/phase-01-baseline.md`
- [ ] Review with Nelson: xác nhận 6 defect hypothesis đúng/sai
- [ ] Update Phase 02 scope dựa trên findings

## Success Criteria

- Report có data thật (không phải fake numbers)
- Đã xác định top 3 root causes chính xác (not theoretical)
- Nelson đồng ý với finding trước khi Phase 02 bắt đầu

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| ERP file đang mở trong Excel | Audit script check file lock, prompt Nelson đóng Excel |
| Quotes sheet chưa có đủ dữ liệu test | Seed 3-5 quote giả lập (edge cases) vào 1 row trống test |
| Carrier names quá messy → alias map bị nổ | Limit alias ở 10 carrier top, phần còn lại fallback substring match |

## Next Steps

→ Phase 02: rewrite `compute_alerts()` với Tier 1/2 + alias map dựa trên baseline finding
