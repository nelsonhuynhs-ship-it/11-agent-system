# Phase 03 — Alert Visualization

**Priority:** P0 (Nelson cần thấy kết quả)
**Status:** ⏳ PENDING
**Depends on:** Phase 02 detection engine
**Est. tokens:** ~10k

## Overview

Nelson đã chỉ rõ: "anh muốn nó thật chuyên nghiệp". Visualization phải trả lời 3 câu hỏi Nelson mở ERP sáng thứ Hai:

1. **Có gì khẩn?** — dashboard nhìn 1 giây: 5 P1 / 3 P2 / 1 P3
2. **Chi tiết drop nào?** — table sortable với delta $ lớn trên đầu
3. **Hành động gì?** — nút Re-quote inline per row + MsgBox summary khi chạy xong

## Key Insights

1. **3 lớp visibility** (mạnh → yếu):
   - **Status bar flash** khi chạy xong: "⚡ Price Watch: 5 P1 alerts — xem tab Price_Watch"
   - **Price_Watch sheet** với summary card ở đầu + table ở giữa + instructions cuối
   - **Quotes sheet row highlight** (đỏ = P1, vàng = P2) + Remark column ghi tag `[PW 15Apr 18:00] Tier1 DROP ...`
   - **Active Jobs** col 39/40 stamp cho WIN quote (persistent memory sau restart)
2. **Summary cards** (3 ô 1x3) phải là Excel cell với formula `=COUNTIF(...)` để auto-update nếu Nelson filter manual.
3. **Priority color palette** — consistent với active-jobs-layout mockup:
   - P1 (DROP pending): `#FEE2E2` fill + `#B91C1C` text (red-100/700)
   - P2 (DROP won): `#FEF3C7` fill + `#B45309` text (amber-100/700)
   - P3 (RISE info): `#E0F2FE` fill + `#0369A1` text (sky-100/700)
4. **Tier column** bold: Tier 1 routine = 🎯 ROUTINE, Tier 2 line = 📍 LINE. (Emoji OK vì Nelson chuộng visual.)

## Requirements

### Functional

1. **Price_Watch sheet layout:**
   ```
   Row 1: Title bar — "PRICE WATCH — 15 Apr 2026 18:00" merged A1:L1
   Row 2: Blank
   Row 3: Summary cards
          A3:C3  [P1 PENDING DROP] 5 alerts  $4,500 saved potential
          D3:F3  [P2 WIN MONITOR]   3 alerts  $1,200 already lost
          G3:I3  [P3 RISE INFO]     1 alert   $200 cost creep
          J3:L3  [Last scan] 15 Apr 18:00 · Next auto-scan sau Refresh All
   Row 4: Blank
   Row 5: Legend — "🎯 ROUTINE = any carrier cheaper | 📍 LINE = same carrier dropped"
   Row 6: Blank
   Row 7: Headers — Priority | Tier | QuoteID | Date | Customer | POL→POD | Carrier Cũ | Cont | Quoted | Current | Δ | Action
   Row 8+: Data rows sorted by (priority ASC, |delta| DESC)
   ```

2. **Inline buttons** (Phase 04 implement) — col M per row: `Re-quote` shape-button
   - Phase 03 chỉ reserve col M header "Action" + dummy value `=HYPERLINK("#...", "Re-quote")` placeholder

3. **Quotes sheet stamp:**
   - Status cell fill: P1 = FILL_ALERT red, P2 = FILL_WARN amber
   - Remark prepend: `[PW 15Apr 18:00] T1:20GP:-$300 T2:40HC:-$150 | <existing>`
   - Clear previous `[PW ...]` tag before prepending (avoid stacking)

4. **Active Jobs stamp** (WIN quotes only):
   - Col 39 PRICE_WATCH_STATUS: `DROP` | `RISE` | `` (clear if no longer alerting)
   - Col 40 PRICE_WATCH_DELTA: signed integer (negative = drop = good)
   - Col 39 fill matches priority color

5. **Status bar flash on completion** (VBA side, Phase 05):
   - `Application.StatusBar = "⚡ Price Watch: " & p1Count & " P1 + " & p2Count & " P2 alerts — see Price_Watch tab"`
   - Auto-clear after 10s via `Application.OnTime`

### Non-Functional

- Render < 2s cho 100 alerts
- No merged cells in data rows (Ctrl+T convert to Excel Table)
- Freeze pane at row 8, col B (so Priority + Tier always visible on scroll)
- AutoFilter on row 7

## Architecture

```
price_watch.py (extend existing writers)
  │
  ├─ write_price_watch_sheet_v2(wb, alerts, cfg, scan_time)
  │    ├─ build title bar
  │    ├─ build summary cards (COUNTIF formulas pointing to data table)
  │    ├─ build legend row
  │    ├─ build headers + data rows
  │    ├─ apply priority fills + tier icons
  │    ├─ AutoFilter + freeze panes
  │    └─ convert A7:M(N) to Excel Table `tblPriceWatch`
  │
  ├─ stamp_quotes_sheet_v2(wb, alerts)  — clear prev [PW tag] → write new
  │
  └─ stamp_active_jobs_v2(wb, alerts)   — use AJ_COL["PRICE_WATCH_STATUS"] = 39
```

## Visual Deliverable

Trước khi code, tạo HTML mockup để Nelson duyệt layout:

- `visuals/price-watch-v2-mockup.html` — standalone HTML với fake data show 3 summary cards + 12 alert rows + Re-quote button per row
- Style giống `active-jobs-layout.html` (cùng palette + font Segoe UI)

## Related Code Files

**Modify:**
- `ERP/intelligence/price_watch.py` — replace `write_price_watch_sheet`, `stamp_quotes_sheet`, `stamp_active_jobs`

**Create:**
- `plans/260415-price-watch-v2-requote-alert/visuals/price-watch-v2-mockup.html`

## Implementation Steps

1. **Create HTML mockup first** — Nelson review → tweak layout → approve
2. Edit `price_watch.py`:
   - Add `from openpyxl.worksheet.table import Table, TableStyleInfo`
   - Write `write_price_watch_sheet_v2` — paste layout code + openpyxl styling
   - Write `stamp_quotes_sheet_v2` — regex `r"^\[PW [^\]]+\]"` to strip old tag
   - Fix `stamp_active_jobs` col index bug (35→39, 36→40)
3. Smoke test: run on ERP với fake 8-10 alerts → open Excel → verify visual match HTML mockup
4. Screenshot for UAT checklist

## Todo List

- [ ] Create HTML mockup `visuals/price-watch-v2-mockup.html`
- [ ] Nelson approve mockup
- [ ] Implement `write_price_watch_sheet_v2`
- [ ] Implement `stamp_quotes_sheet_v2` (strip old PW tag logic)
- [ ] Fix `stamp_active_jobs` col index
- [ ] Add Excel Table conversion
- [ ] Smoke test on real ERP
- [ ] Screenshot + paste vào UAT-ActiveJobs-v4-*.xlsx cell note

## Success Criteria

- HTML mockup được Nelson approve trước khi implement
- Price_Watch sheet hiện đầy đủ 3 card + legend + table có AutoFilter
- Quotes row highlighted đúng màu theo tier
- Active Jobs col 39/40 stamped cho WIN quote
- Mở Excel re-open → màu highlight vẫn còn (persistent, không bị strip)

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Excel Table conflict với merged cells | Row 1 + row 3 merged OK; table chỉ bao row 7+ trở xuống |
| Nelson không thích màu → phải redo | Mockup approve trước khi implement |
| AutoFilter clash với sort sẵn | Apply AutoFilter cuối cùng, sau khi data đã sorted |
| stamp_quotes regex strip sai (ăn cả Remark hợp lệ) | Regex chỉ match prefix `[PW DDMMM HH:MM]`, test với 3 edge cases |

## Next Steps

→ Phase 04: Re-quote workflow — button trên Price_Watch sheet tạo quote mới + draft email Outlook
