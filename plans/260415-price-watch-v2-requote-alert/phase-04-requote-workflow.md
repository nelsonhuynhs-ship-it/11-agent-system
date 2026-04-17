# Phase 04 — Re-quote Workflow

**Priority:** P1 (Nelson's ROI moment)
**Status:** ⏳ PENDING
**Depends on:** Phase 03 visualization
**Est. tokens:** ~10k

## Overview

Nelson thấy alert trên Price_Watch sheet → bấm 1 nút "Re-quote This" → hệ thống:

1. Copy quote gốc sang row mới trong Quotes với QuoteID mới (`Q12345_RQ1`, `_RQ2`...)
2. Apply buy mới (từ Pricing hiện tại) + margin cũ → tính Sell mới
3. Mở Outlook draft email với subject + body pre-filled từ template
4. Highlight row mới để Nelson review trước khi gửi

Goal: từ lúc Nelson thấy alert → lúc email sẵn sàng gửi < 10 giây.

## Key Insights

1. **1-click = 1 row mới, không edit row cũ** — audit trail. Quote cũ giữ nguyên status PENDING (hoặc WIN), quote mới là `_RQ1` với Source="Re-quote from Qxxx".
2. **Buy mới + margin cũ = Sell mới** — không hỏi Nelson lại markup (đã commit lúc quote lần đầu). Có thể override trước khi gửi.
3. **Outlook draft** phải dùng COM (`CreateObject("Outlook.Application")`), không phải mailto (mailto giới hạn 2048 chars).
4. **Carrier có thể đổi** — nếu alert Tier 1 ROUTINE, new_carrier khác old_carrier → email subject note "chuyển sang [new_carrier]" để Nelson biết.
5. **Giá trị "tiền đã tiết kiệm"** — phải hiển thị nổi bật cho khách thấy giá trị: "Giá mới thấp hơn lần quote trước $300".

## Requirements

### Functional

1. **Trigger**: 2 entry points
   - **Inline button** trên Price_Watch sheet row (Phase 03 đã reserve col M)
   - **Ribbon button** mới `btnRequote` (Operations tab, group Quote) — active khi Price_Watch sheet đang selected

2. **Re-quote logic** (Python):
   ```python
   def requote(wb, original_qid: str, alert: Alert) -> str:
       q_ws = wb["Quotes"]
       orig_row = find_quote_row(q_ws, original_qid)
       new_qid = next_requote_id(q_ws, original_qid)  # Qxxx_RQ1, _RQ2
       new_row = q_ws.max_row + 1

       # Copy all cols from orig → new
       for c in range(1, 43):
           q_ws.cell(new_row, c, q_ws.cell(orig_row, c).value)

       # Override key fields
       q_ws.cell(new_row, Q_COL["QuoteID"], new_qid)
       q_ws.cell(new_row, Q_COL["Date"], datetime.now())
       q_ws.cell(new_row, Q_COL["Source"], f"Re-quote from {original_qid}")
       q_ws.cell(new_row, Q_COL["Status"], "")  # clear → becomes PENDING

       # Apply new carrier (if Tier 1) + new buy
       if alert.tier == "ROUTINE" and alert.carrier_new != alert.carrier_old:
           q_ws.cell(new_row, Q_COL["Carrier"], alert.carrier_new)
       buy_col = CONT_TO_BUY_COL[alert.cont_type]
       sell_col = buy_col.replace("Buy_", "Sell_")
       old_buy = q_ws.cell(orig_row, Q_COL[buy_col]).value or 0
       old_sell = q_ws.cell(orig_row, Q_COL[sell_col]).value or 0
       margin = old_sell - old_buy
       new_buy = alert.current_buy
       new_sell = new_buy + margin
       q_ws.cell(new_row, Q_COL[buy_col], new_buy)
       q_ws.cell(new_row, Q_COL[sell_col], new_sell)

       # Remark audit trail
       q_ws.cell(new_row, Q_COL["Remark"],
                 f"[RQ {datetime.now():%d%b %H:%M}] from {original_qid}: "
                 f"buy {old_buy:.0f}→{new_buy:.0f} (save ${old_buy-new_buy:.0f})")

       # Highlight row for Nelson review
       for c in range(1, 43):
           q_ws.cell(new_row, c).fill = PatternFill("solid", fgColor="D1FAE5")
       return new_qid
   ```

3. **Outlook draft** (VBA, after Python returns new_qid):
   ```vba
   Public Sub OpenRequoteEmail(newQid As String, custName As String, _
                                route As String, oldSell As Double, newSell As Double, _
                                carrierOld As String, carrierNew As String)
       On Error Resume Next
       Dim ol As Object: Set ol = CreateObject("Outlook.Application")
       Dim mi As Object: Set mi = ol.CreateItem(0)  ' olMailItem
       mi.Subject = "Updated quote " & route & " — save $" & Format(oldSell - newSell, "#,##0") & " USD/cont"
       mi.Body = "Dear " & custName & "," & vbCrLf & vbCrLf & _
                 "We've got a better rate on the " & route & " lane." & vbCrLf & _
                 IIf(carrierOld <> carrierNew, "We're shifting from " & carrierOld & " to " & carrierNew & " for this shipment." & vbCrLf, "") & _
                 "Updated sell: USD " & Format(newSell, "#,##0") & " (was USD " & Format(oldSell, "#,##0") & ", you save $" & Format(oldSell - newSell, "#,##0") & ")" & vbCrLf & vbCrLf & _
                 "Quote ref: " & newQid & vbCrLf & _
                 "Valid until " & Format(Date + 7, "dd mmm yyyy") & vbCrLf & vbCrLf & _
                 "Best regards," & vbCrLf & "Nelson Huynh · Nelson Freight"
       mi.Display  ' show to user — do NOT auto-send
   End Sub
   ```

4. **Inline button on Price_Watch row** — Col M value = `=HYPERLINK("#requote:Qxxx", "Re-quote")` + Workbook_SheetFollowHyperlink event handler:
   ```vba
   Private Sub Workbook_SheetFollowHyperlink(ByVal Sh As Object, ByVal Target As Hyperlink)
       If Sh.Name <> "Price_Watch" Then Exit Sub
       If Left(Target.SubAddress, 9) <> "requote:" Then Exit Sub
       Dim qid As String: qid = Mid(Target.SubAddress, 10)
       Call OnAction_Requote_Inline(qid)
   End Sub
   ```

5. **Ribbon button** (Operations tab, group Quote): `btnRequote` label "Re-quote", size=normal, screentip "Re-quote khi Price_Watch có alert"

### Non-Functional

- Total round-trip < 10s
- New quote row highlighted persistent (Nelson có thể xác nhận review sau)
- Email is **draft only**, never auto-send — Nelson review + send thủ công

## Architecture

```
Price_Watch sheet row M cell → HYPERLINK "requote:Qxxx"
    ↓
Workbook_SheetFollowHyperlink (ThisWorkbook VBA)
    ↓
OnAction_Requote_Inline(qid)  (erp-v14-jobs-automation.bas)
    ├─ close + call price_watch.py --requote Qxxx
    ├─ reopen workbook
    └─ OpenRequoteEmail(...)  — Outlook COM draft
```

## Related Code Files

**Modify:**
- `ERP/intelligence/price_watch.py` — add `requote(wb, qid, alert)` + CLI flag `--requote <qid>`
- `OneDrive/erp/erp-v14-jobs-automation.bas` — add `OnAction_Requote_Inline`, `OpenRequoteEmail`
- `OneDrive/erp/erp-v14-thisworkbook.txt` — add `Workbook_SheetFollowHyperlink` handler
- `OneDrive/erp/CustomUI_v14.xml` — add `btnRequote` to Operations tab, group Quote

**Create:**
- (none — extend existing)

## Implementation Steps

1. Python side:
   - `next_requote_id(ws, qid)` → scans Quotes col A for existing `Qxxx_RQ*`, returns next suffix
   - `find_quote_row(ws, qid)` → linear scan (small sheet)
   - Add CLI: `python price_watch.py --requote Q1234 --tier ROUTINE --cont 40HC`
     - Load workbook, compute alerts, find alert matching args, call requote(), save
2. VBA side:
   - `OnAction_Requote_Inline(qid)` calls EnsureFileClosedThenReopen + RunPythonHidden với CLI requote + ReopenWorkbook
   - After reopen, read new_qid từ log, call OpenRequoteEmail với Quote data fresh-read
3. Ribbon button:
   - Edit `CustomUI_v14.xml` add:
     ```xml
     <button id="btnRequote" label="Re-quote" size="normal"
             imageMso="ReplySendUpdate" onAction="OnAction_Requote_Menu"
             screentip="Re-quote từ Price_Watch alert đang selected"/>
     ```
   - `OnAction_Requote_Menu`: if ActiveSheet = "Price_Watch" → read QuoteID từ col C của ActiveCell.Row → call OnAction_Requote_Inline

## Todo List

- [ ] `next_requote_id` helper
- [ ] `requote(wb, qid, alert)` Python function
- [ ] CLI `--requote <qid> --tier <TIER> --cont <CONT>`
- [ ] `OnAction_Requote_Inline` VBA
- [ ] `OpenRequoteEmail` VBA (Outlook COM draft)
- [ ] `Workbook_SheetFollowHyperlink` event handler
- [ ] Ribbon `btnRequote` + `OnAction_Requote_Menu`
- [ ] Test: manual trigger → new Qxxx_RQ1 row → Outlook draft mở
- [ ] Test: carrier switch case (Tier 1 ROUTINE → new_carrier in email subject)

## Success Criteria

- Nelson click Re-quote hyperlink → Excel close/reopen trong 5-8s
- Quotes sheet có row mới `Qxxx_RQ1`, highlighted xanh nhẹ, Source="Re-quote from Qxxx"
- Outlook mở 1 draft email với đúng subject + body template + customer email address (nếu có trong CRM)
- Email KHÔNG auto-send, Nelson review rồi tự Send

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Outlook không chạy / bị block | Try Outlook COM first, fallback mailto với body truncated |
| Customer email address missing | Outlook draft mở với empty To field, Nelson paste |
| Duplicate _RQ1 nếu Nelson click 2 lần | `next_requote_id` scan existing suffix, pick max+1 |
| HYPERLINK SubAddress không trigger khi click (Excel quirk) | Fallback: ribbon button `btnRequote` đọc ActiveCell.Row làm selector |
| Customer name trong Quotes khác customer email trong cnee_master.xlsx | Best-effort match via CRM_ID, else Nelson paste email thủ công |

## Security Considerations

- Email chỉ Display, never Send — zero risk auto-spam
- Outlook COM cần Excel trust setting — verify Nelson's machine đã allow
- No external API calls

## Next Steps

→ Phase 05: auto-run Price Watch sau Refresh All + config sheet UX
