# Phase 06 — Tests & Verification

**Priority:** P1 (regression safety)
**Status:** ⏳ PENDING
**Depends on:** Phase 02-05
**Est. tokens:** ~6k

## Overview

Price Watch v2 thay đổi 3 module (price_watch.py, carrier_alias.py, jobs-automation.bas). Phải có pytest safety net + manual UAT trước ship.

## Key Insights

1. **Pytest fixtures dùng openpyxl.Workbook() in-memory** — không cần ERP file thật
2. **VBA compile test** — `verify-erp.bat` (R1-R9 lint + live compile) phải stay green
3. **UAT case** được thêm vào UAT-ActiveJobs-v4-YYYYMMDD.xlsx kế tiếp

## Requirements

### Functional — Pytest

Tạo `ERP/intelligence/tests/test_price_watch.py` với các nhóm test:

1. **test_normalize_carrier:**
   ```python
   assert normalize_carrier("Yang Ming") == "YML"
   assert normalize_carrier("ocean network express") == "ONE"
   assert normalize_carrier("MSC MEDITERRANEAN") == "MSC"
   assert normalize_carrier("RandomLine") == "RANDOMLINE"
   ```

2. **test_tier2_line_drop:**
   - Quote: MSC HPH-USLGB 40HC buy=2800
   - Pricing: MSC HPH-USLGB 40HC buy=2600 eff=today
   - Expected: 1 alert, tier=LINE, kind=DROP, delta=-200, priority=P1 (PENDING)

3. **test_tier1_routine_drop:**
   - Quote: MSC HPH-USLGB 40HC buy=2800
   - Pricing: CMA HPH-USLGB 40HC buy=2500
   - Expected: 1 alert, tier=ROUTINE, carrier_new=CMA, delta=-300, priority=P1

4. **test_tier1_and_tier2_both:**
   - Quote: MSC HPH-USLGB 40HC buy=2800
   - Pricing: MSC 2600, CMA 2500
   - Expected: 2 alerts, P1 ROUTINE (CMA) + P2 LINE (MSC)
   - Sort: ROUTINE first

5. **test_alias_match:**
   - Quote carrier="YML"
   - Pricing carrier="YANG MING"
   - Expected: match via alias → alert emitted

6. **test_win_quote_gets_p2:**
   - Quote status="WIN", buy=2800, pricing buy=2600
   - Expected: priority=P2 (WIN_DROP = monitoring)

7. **test_threshold_respected:**
   - Quote buy=2800, pricing buy=2780 (delta=20)
   - threshold_line=50
   - Expected: 0 alerts

8. **test_ignore_expired:**
   - Quote exp=2026-01-01 (past)
   - Expected: skipped entirely

9. **test_requote_new_row:**
   - Original Q1234, call requote()
   - Expected: new row with QuoteID="Q1234_RQ1", Status="", Source="Re-quote from Q1234"
   - Buy = alert.current_buy
   - Sell = old_sell - (old_buy - new_buy) [keep margin]

10. **test_requote_suffix_increments:**
    - Existing Q1234_RQ1, Q1234_RQ2 → next should be _RQ3

11. **test_pw_config_auto_create:**
    - Workbook không có PW_Config sheet → ensure_pw_config() tạo đủ 6 key-value
    - Re-run → idempotent, không duplicate

### Functional — VBA Compile Gate

- `verify-erp.bat` phải PASS (7/7 green) sau khi reimport với changes
- R1-R9 static lint check
- Live compile via `scripts\lint-erp-vba.py --live`

### Functional — Manual UAT

Thêm vào UAT checklist tiếp theo (tạo `UAT-PriceWatch-v2-20260416.xlsx` sau khi ship):

- **PW1:** Refresh All → status bar flash "Price Watch: X P1 alerts"
- **PW2:** Click tab Price_Watch → 3 summary cards + table sorted by priority
- **PW3:** Quote PENDING có carrier khác rẻ hơn → P1 ROUTINE alert hiện
- **PW4:** Quote PENDING cùng carrier hạ giá → P2 LINE alert
- **PW5:** Click Re-quote trên 1 row → Quotes có Qxxx_RQ1 + Outlook draft mở
- **PW6:** PW_Config!B7=FALSE → Refresh All không trigger Price Watch
- **PW7:** `verify-erp.bat` green

## Related Code Files

**Create:**
- `ERP/intelligence/tests/__init__.py` (empty)
- `ERP/intelligence/tests/test_price_watch.py` (~250 lines)
- `ERP/intelligence/tests/conftest.py` (fixture factories)

**Modify:**
- `scripts/build_uat_checklist.py` — optional add "PW" test section after R7

## Implementation Steps

1. Create tests folder structure
2. Write `conftest.py` with fixture factories:
   ```python
   @pytest.fixture
   def empty_wb():
       wb = Workbook()
       wb.remove(wb.active)
       return wb

   def seed_quote(ws, **kwargs):  # writes 1 row with Q_COL mapping

   def seed_pricing(ws, sheet_name, **kwargs):  # writes 1 row with P_COL mapping
   ```
3. Write 11 test cases (each <30 lines)
4. Run `python -m pytest ERP/intelligence/tests/test_price_watch.py -v` → all pass
5. Run `verify-erp.bat` → 7/7 green
6. Document test run in commit message

## Todo List

- [ ] Create `ERP/intelligence/tests/` folder
- [ ] Write `conftest.py` fixtures
- [ ] 11 pytest test cases
- [ ] `pytest` green (100%)
- [ ] `verify-erp.bat` green (7/7)
- [ ] Update `build_uat_checklist.py` with PW1-PW7 rows
- [ ] Generate UAT xlsx for Nelson
- [ ] Nelson runs UAT → mark all PASS

## Success Criteria

- `pytest ERP/intelligence/tests/test_price_watch.py -v` → 11/11 pass
- `verify-erp.bat` → 7/7 green
- UAT PW1-PW7 → all PASS
- Commit passes pre-commit hook (ruff + lint + compile)

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Pytest fixtures không match ERP real schema | Import Q_COL/P_COL từ price_watch.py để keep sync |
| Test flaky vì datetime/now() | Inject `scan_time` param, not datetime.now() |
| Openpyxl cross-version issue | Pin openpyxl==3.1.5 trong requirements-dev.txt |
| UAT case quá dài (7 items) → Nelson skip | Combine PW1-PW2 thành 1 test "auto-scan flow", PW3-PW4 thành 1 test "detection accuracy" |

## Next Steps

Sau Phase 06 green:
→ Commit + ship
→ Plan folder move to `plans/archive/260415-price-watch-v2-requote-alert/`
→ Update memory: `project_session_20260415.md` ghi nhận F1 Price Watch DONE
→ Next feature: F2 (Shipment Tracking Pipeline) hoặc theo Nelson priority
