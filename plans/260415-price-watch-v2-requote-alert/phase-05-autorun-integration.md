# Phase 05 — Auto-run Integration

**Priority:** P1 (zero-friction)
**Status:** ⏳ PENDING
**Depends on:** Phase 02 + 03
**Est. tokens:** ~5k

## Overview

Nelson không nên phải nhớ bấm "Price Watch" mỗi ngày. Mỗi lần Refresh All (đã auto-update rates → mtime đổi → Last Refresh label update), Price Watch nên tự chạy và flash notification nếu có P1.

Nelson control on/off qua sheet `PW_Config!B7 = TRUE/FALSE`.

## Key Insights

1. **Piggyback trên Refresh All** là điểm chèn tốt nhất — vì đó là lúc pricing data mới nhất vừa được pull vào.
2. **Không auto-open Price_Watch tab** — Nelson có thể đang thao tác sheet khác, không nên bị kéo đi. Chỉ flash status bar.
3. **Async không cần** — scan 3500 pricing + 500 quotes chỉ ~2-3s, chạy sync OK.
4. **Chạy ẩn** — không mở Python console, không MsgBox (trừ khi có lỗi).

## Requirements

### Functional

1. **Hook vào `OnAction_RefreshAll`** (ribbon-callbacks.bas):
   - Sau khi Refresh All hoàn thành thành công (rc=0)
   - Đọc `PW_Config!B7` (autorun_on_refresh) — default TRUE nếu sheet chưa có
   - Nếu TRUE: chạy `price_watch.py` với `--silent` flag
   - Nếu FALSE: skip

2. **Python --silent mode:**
   - Không print ra stdout (trừ 1 dòng summary vào log file)
   - Không open Excel visual change (save_preserving_ribbon vẫn run)
   - Exit code 0 = success, 1 = error

3. **Status bar flash** (VBA):
   ```vba
   Dim p1 As Long, p2 As Long
   Call ReadPriceWatchSummary(logFile, p1, p2)  ' parse log
   If p1 > 0 Then
       Application.StatusBar = "⚡ Price Watch: " & p1 & " P1 alerts — mở tab Price_Watch"
       Application.OnTime Now + TimeValue("00:00:30"), "ClearStatusBar"
   ElseIf p2 > 0 Then
       Application.StatusBar = "Price Watch: " & p2 & " P2 monitoring alerts"
       Application.OnTime Now + TimeValue("00:00:15"), "ClearStatusBar"
   End If
   ```

4. **PW_Config sheet** (auto-create nếu chưa có):
   - Layout key-value format, readable
   - Row 1 banner merged A1:B1 "Price Watch Settings — edit col B only"
   - Rows 3-9 settings với comment/note mô tả

5. **Ribbon label "Last price watch"** trong group Rate Data (below Last Refresh):
   ```xml
   <labelControl id="lblLastPriceWatch" getLabel="GetLabel_LastPriceWatch"/>
   ```
   - Callback đọc mtime của `price_watch_log.txt` → "Last price watch: 15 Apr 18:00 (5 P1)"

### Non-Functional

- Auto-run add <5s vào Refresh All flow
- Fail silent nếu price_watch.py error → Refresh All vẫn success, chỉ skip alert
- Log rotate: keep last 10 runs trong `price_watch_log.txt` (no unbounded growth)

## Architecture

```
OnAction_RefreshAll (existing)
  ├─ [existing] Run refresh-v14.py
  ├─ [existing] reload sheets
  └─ [NEW] If PW_Config!B7 = TRUE:
         ├─ script = FindScript("ERP\intelligence\price_watch.py")
         ├─ rc = RunPythonHidden(script, "--silent", logFile)
         ├─ if rc=0: parse log → flash status bar
         └─ Invalidate ribbon (refresh Last Price Watch label)
```

## Related Code Files

**Modify:**
- `OneDrive/erp/erp-v14-ribbon-callbacks.bas` — extend `OnAction_RefreshAll`, add `GetLabel_LastPriceWatch`, `ClearStatusBar` helper
- `ERP/intelligence/price_watch.py` — add `--silent` flag (suppress prints + MsgBox-equivalent)
- `OneDrive/erp/CustomUI_v14.xml` — add `lblLastPriceWatch` in grpRateData

**Create:**
- (none)

## Implementation Steps

1. Python `--silent`:
   - Redirect stdout to log file only
   - Do NOT call any MsgBox (Python doesn't anyway, this is for VBA side)
2. VBA:
   - Add helper `ReadPriceWatchSummary(logFile, ByRef p1, ByRef p2)` — parse last 20 lines, regex `"alerts: \d+ \(DROP=(\d+)"` etc.
   - Extend `OnAction_RefreshAll` at end, after existing success block
   - Add `ClearStatusBar` subroutine: `Application.StatusBar = False`
   - Add `GetLabel_LastPriceWatch` — read mtime of `price_watch_log.txt` + parse last summary line
3. Ribbon XML: insert `lblLastPriceWatch` after `lblLastRefresh`
4. PW_Config sheet creator function (Python side, idempotent):
   ```python
   def ensure_pw_config(wb):
       if "PW_Config" in wb.sheetnames:
           return
       ws = wb.create_sheet("PW_Config")
       ws["A1"] = "Price Watch Settings — edit col B only"
       ws.merge_cells("A1:B1")
       settings = [
           ("threshold_routine", 100, "USD minimum delta for Tier 1 alert"),
           ("threshold_line", 50, "USD minimum delta for Tier 2 alert"),
           ("enabled_tier_1", True, "Scan different carriers same route"),
           ("enabled_tier_2", True, "Scan same carrier price drops"),
           ("ignore_expired", True, "Skip quotes past Exp date"),
           ("autorun_on_refresh", True, "Auto-run after Refresh All"),
       ]
       for i, (k, v, note) in enumerate(settings, start=3):
           ws.cell(i, 1, k)
           ws.cell(i, 2, v)
           ws.cell(i, 3, note)  # col C = doc (hidden-ish)
   ```

## Todo List

- [ ] Python `--silent` flag
- [ ] Python `ensure_pw_config(wb)`
- [ ] VBA extend `OnAction_RefreshAll` (autorun check)
- [ ] VBA `ReadPriceWatchSummary`
- [ ] VBA `GetLabel_LastPriceWatch`
- [ ] VBA `ClearStatusBar`
- [ ] Ribbon XML add `lblLastPriceWatch`
- [ ] Reimport VBA modules via reimport-erp-vba.py
- [ ] Test: Refresh All → Python autorun → status bar flash → label update

## Success Criteria

- Bấm Refresh All lúc 10:00 → 10:00:02 thấy "⚡ Price Watch: 2 P1 alerts — mở tab Price_Watch"
- Status bar tự clear sau 30s
- Label Last price watch trong ribbon update
- Disable `PW_Config!B7=FALSE` → Refresh All không trigger Price Watch (verified via log mtime unchanged)
- Lỗi Python không crash Refresh All flow

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Refresh All chậm thêm 3s | Measure; nếu >5s thì split thành 2 ribbon button (Refresh All + Refresh All w/ Price Watch) |
| PW_Config sheet bị Nelson xóa accidentally | Python auto-recreate on next run |
| Status bar conflict với Refresh All đang dùng | Refresh All clear StatusBar cuối cùng; Price Watch set sau khi Refresh done |
| Multi-user concurrent (2 Excel instances) | Use file lock check; skip autorun nếu lock detected |

## Next Steps

→ Phase 06: tests (pytest fixtures + verify-erp.bat gate)
