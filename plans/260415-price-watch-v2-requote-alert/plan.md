# Plan — Price Watch v2: Re-quote Alert (F1 Active Jobs v4)

**Created:** 2026-04-15
**Priority:** P0 — Nelson: "Feat này sẽ có giá trị lớn nhất, muốn thật chuyên nghiệp"
**Status:** 🟡 PLANNING

## Goal

Nâng cấp Price Watch hiện tại thành một alert engine chuyên nghiệp: khi Nelson quote khách ngày X, hệ thống tự quét Pricing mỗi lần refresh và cảnh báo nếu:

- **Điều kiện 1 (primary) — cùng ROUTINE (POL-POD):** bất kỳ carrier nào ra giá rẻ hơn → Nelson có thể đổi carrier + re-quote
- **Điều kiện 2 (secondary) — cùng LINE (carrier):** chính carrier đó hạ giá → Nelson có thể giữ carrier nhưng re-quote giá tốt hơn

Khi phát hiện drop, hệ thống:
1. Highlight quote row (Quotes sheet) + sheet Active Jobs nếu đã WIN
2. List vào sheet **Price_Watch** có priority, delta, action suggestion
3. Cung cấp nút "Re-quote This" để Nelson 1-click tạo quote mới với giá rẻ + draft email khách

## Why current build fails Nelson's test

| # | Triệu chứng | Nguyên nhân |
|---|-------------|-------------|
| 1 | Không alert khi carrier khác rẻ hơn | Script chỉ match cùng carrier (thiếu điều kiện "routine") |
| 2 | "YML" quote không match "YANG MING" pricing | Key carrier exact-match, fuzzy fallback yếu |
| 3 | Nelson thấy MsgBox "complete" nhưng không có dòng alert | Threshold $50 + matching strict → filter hết ra 0 alert |
| 4 | Sheet Price_Watch trống | Khi 0 alert, chỉ 1 dòng text xám — trông như bug |
| 5 | Không re-quote được từ alert | Chưa có workflow từ alert → quote mới |
| 6 | Phải bấm tay mỗi lần | Không auto-trigger sau Refresh All |

## Phases

| # | File | Focus | Status |
|---|------|-------|--------|
| 01 | [phase-01-root-cause-analysis.md](phase-01-root-cause-analysis.md) | Audit script hiện tại, xác nhận 6 defect, đo baseline trên data thật | ⏳ |
| 02 | [phase-02-two-tier-detection-engine.md](phase-02-two-tier-detection-engine.md) | Rewrite `compute_alerts()` với 2 tier (ROUTINE + LINE); carrier alias map; configurable threshold per tier | ⏳ |
| 03 | [phase-03-alert-visualization.md](phase-03-alert-visualization.md) | Redesign Price_Watch sheet (summary cards + drill-down), inline highlight trên Quotes + Active Jobs, status bar flash khi có P1 | ⏳ |
| 04 | [phase-04-requote-workflow.md](phase-04-requote-workflow.md) | Ribbon button "Re-quote" trên Price_Watch sheet — 1 click copy quote gốc với buy mới + mở draft email Outlook | ⏳ |
| 05 | [phase-05-autorun-integration.md](phase-05-autorun-integration.md) | Auto-trigger Price Watch sau `OnAction_RefreshAll` (tùy chọn tắt bật); lưu settings vào sheet `PW_Config` | ⏳ |
| 06 | [phase-06-tests.md](phase-06-tests.md) | Pytest cases cho cả 2 tier + fixtures giả lập Pricing/Quotes; verify-erp.bat gate | ⏳ |

## Dependencies

- **Upstream:** `ERP/intelligence/price_watch.py` (đã có 398 lines — rewrite `compute_alerts` + add tier logic)
- **Data:** Pricing Dry (3496 rows), Pricing Reefer (76 rows), Quotes sheet, Active Jobs (col 39-40)
- **VBA:** `OnAction_PriceWatch` (jobs-automation.bas line 102) — giữ nguyên entry point
- **Schema:** `ERP/core/active_jobs_cols.py` — PRICE_WATCH_STATUS=39, PRICE_WATCH_DELTA=40

## Key Insights

1. **Nelson's mental model:** Route-first (Vietnam→USA đi đâu rẻ?), carrier là phương tiện. Nên **Tier 1 = ROUTINE** phải là default visible, Tier 2 = LINE chỉ là bổus.
2. **Carrier alias** bắt buộc — Nelson dùng "ONE", "YML", "WHL" trong quote nhưng Pricing có thể là "Ocean Network Express", "YANG MING", "WAN HAI" tùy source file.
3. **Threshold USD, không phải %** — freight rate biến động nhỏ về % nhưng $ lớn, Nelson thinking in dollars.
4. **P1 = PENDING quote còn treo** — highest impact, phải flash lên.
5. **P2 = WIN quote** — đã ký, giá thay đổi không cancel được nhưng cần biết để reprice lần sau.

## Success Criteria

- [ ] Test case: quote ngày 13 HPH-USLGB MSC $2800, pricing 15 Apr HPH-USLGB CMA $2500 → ra P1 alert Tier 1 ROUTINE (carrier khác)
- [ ] Test case: quote ngày 13 HPH-USLGB MSC $2800, pricing 15 Apr HPH-USLGB MSC $2600 → ra P1 alert Tier 2 LINE (same carrier)
- [ ] Test case: alias "YML" trong quote match "YANG MING" pricing
- [ ] Price_Watch sheet có: 3 summary cards (P1/P2/P3 count) + table sortable + nút "Re-quote" per row
- [ ] Nelson bấm "Re-quote" → quote mới xuất hiện trong Quotes + Outlook popup email draft với subject "Updated quote HPH-USLGB — USD saved 300"
- [ ] Auto-run sau Refresh All nếu `PW_Config!B1 = TRUE` (default ON)
- [ ] `pytest ERP/intelligence/tests/test_price_watch.py` 100% pass
- [ ] `verify-erp.bat` green (7/7 gate)
- [ ] Nelson UAT: mở ERP → Refresh All → thấy status bar "Price Watch: 3 P1 alerts" → click tab Price_Watch → Re-quote 1 row → email Outlook hiện ra

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Alias map miss một carrier → false negative | Test case coverage cho 8 carrier phổ biến (MSC/CMA/ONE/YML/MAERSK/HAPAG/WHL/COSCO) |
| Tier 1 (routine) noisy nếu carrier khác mà transit time khác nhiều | Chỉ alert nếu cùng POD region + transit time ± 10d |
| Auto-run sau Refresh All làm chậm | Target < 5s trên 3500 rows; run async if quá chậm |
| Re-quote tạo duplicate row | Key = (QuoteID + "_RQ1", "_RQ2"...) để audit trail |
| OneDrive race (giống Last Refresh) khi script viết Price_Watch | Dùng `save_preserving_ribbon` + retry 3x |

## Visual Mockup

HTML preview: `visuals/price-watch-v2-mockup.html` (Phase 03 deliverable — sẽ tạo sau khi Nelson approve plan)

## Next Steps

1. Nelson review plan + approve hoặc tweak priority/scope
2. Khởi động Phase 01 (baseline audit) — em sẽ chạy `price_watch.py` trên data thật, capture output, ghi báo cáo vào `research/phase-01-baseline.md`
3. Phase 02 implement detection engine — deliver `price_watch.py` v2
4. Phase 03-05 ship incrementally, mỗi phase 1 commit + verify-erp.bat
5. Phase 06 tests → UAT với Nelson
