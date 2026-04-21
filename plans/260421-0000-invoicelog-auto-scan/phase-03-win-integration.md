# Phase 03 — VBA Insert Row on Job WIN + Sync Button

**Priority:** P2 · **Status:** pending · **Effort:** 30m · **Blocked by:** Phase 01

## Context Links

- [plan.md](plan.md)
- [erp-v14-ribbon-callbacks.bas:1739-2272](../../ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas) — `OnAction_MarkQuoteWin` (existing)
- `ERP/core/invoice_log_cols.py` (Phase 01 output — col constants)

## Goal

Two VBA subs:

1. **`InvoiceLog_InsertOnWin`** — called from `OnAction_MarkQuoteWin` after AJ row promotion. Appends PENDING row to InvoiceLog.
2. **`OnAction_SyncInvoices`** — ribbon button callback. Reads `invoice_state.jsonl`, applies STATUS/PAID_DATE/LAST_REMINDER_DATE updates to InvoiceLog rows, truncates processed entries.

## Key Insights

- `OnAction_MarkQuoteWin` ends at line 2272 (`ErrHandler: MsgBox ...`). Insert new call at line ~2267 just before "Exit Sub" on success path.
- Existing pattern uses `Application.WorksheetFunction.CountIf` — reuse for dedup.
- VBA JSON parsing: use lightweight parser (no external library). JSONL is line-delimited — `Split(content, vbLf)` then simple field extraction via `InStr`. No nested objects needed (flat records).
- File lock: use FSO `OpenAsTextStream` with lock hint; fall back to `Open For Input` if lock taken (means scanner currently writing — abort + retry).

## Requirements

**F1:** After AJ promotion on WIN, insert InvoiceLog row with:
- BKG_NO = AJ.BKG_NO
- CUSTOMER = AJ.CUSTOMER
- INVOICE_NUMBER = "" (Nelson fills manual OR scanner matches later)
- AMOUNT = 0 (Nelson fills when DN_SENT)
- DATE_ISSUED = Date (today)
- DUE_DATE = Date + 30
- STATUS = "PENDING"
- PAID_DATE = empty
- PAID_AMOUNT = 0
- LAST_REMINDER_DATE = empty
- NOTES = ""

**F2:** Idempotent — if BKG_NO already in InvoiceLog → skip silently (log message in Immediate window).

**F3:** Sync button reads JSONL, applies updates, truncates consumed lines.

**F4:** Sync button button on ERP ribbon tab "Operations" next to "Sync milestones" (CNEE button).

**NF1:** On error → MsgBox but don't break parent WIN flow.

## Related Code Files

**Modify:**
- `ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas`:
  - Add `Private Sub InvoiceLog_InsertOnWin(bkg As String, customer As String)` near line ~2280 (after WIN handler)
  - Add `Public Sub OnAction_SyncInvoices(control As IRibbonControl)` near existing "Sync milestones" handler
  - In `OnAction_MarkQuoteWin`, add call `InvoiceLog_InsertOnWin bkgNo, custName` just before the existing success MsgBox/Exit Sub
- `ERP/vba-v14-mirror/CustomUI_v14.xml`:
  - Add new `<button>` element under Operations tab for SyncInvoices

## Implementation Steps

1. **Read current `OnAction_MarkQuoteWin`** (full sub) to find exact variables holding BKG_NO + CUSTOMER after AJ row written.

2. **Write `InvoiceLog_InsertOnWin`:**
   ```vba
   Private Sub InvoiceLog_InsertOnWin(bkg As String, customer As String)
       On Error GoTo ErrHandler
       If Len(Trim$(bkg)) = 0 Then Exit Sub
       
       Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets("InvoiceLog")
       Dim lastRow As Long
       lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
       
       ' Dedup — check BKG not already present
       If lastRow >= 2 Then
           If Application.WorksheetFunction.CountIf( _
                  ws.Range(ws.Cells(2, 1), ws.Cells(lastRow, 1)), bkg) > 0 Then
               Debug.Print "InvoiceLog: BKG " & bkg & " already present, skip"
               Exit Sub
           End If
       End If
       
       Dim r As Long: r = lastRow + 1
       If lastRow = 1 Then r = 2  ' First data row
       
       ws.Cells(r, 1).Value = bkg           ' BKG_NO
       ws.Cells(r, 2).Value = customer      ' CUSTOMER
       ws.Cells(r, 3).Value = ""            ' INVOICE_NUMBER
       ws.Cells(r, 4).Value = 0             ' AMOUNT
       ws.Cells(r, 5).Value = Date          ' DATE_ISSUED
       ws.Cells(r, 6).Value = Date + 30     ' DUE_DATE
       ws.Cells(r, 7).Value = "PENDING"     ' STATUS
       ws.Cells(r, 8).Value = ""            ' PAID_DATE
       ws.Cells(r, 9).Value = 0             ' PAID_AMOUNT
       ws.Cells(r, 10).Value = ""           ' LAST_REMINDER_DATE
       ws.Cells(r, 11).Value = ""           ' NOTES
       
       Exit Sub
   ErrHandler:
       Debug.Print "InvoiceLog_InsertOnWin error: " & Err.Description
       ' Do NOT MsgBox — WIN flow must continue
   End Sub
   ```

3. **Modify `OnAction_MarkQuoteWin`** — add call just before success exit:
   ```vba
   ' Insert InvoiceLog PENDING row (fire-and-forget)
   Call InvoiceLog_InsertOnWin(bkgNoValue, customerValue)
   ```
   (Use ACTUAL variable names from existing sub — verify first.)

4. **Write `OnAction_SyncInvoices`:**
   ```vba
   Public Sub OnAction_SyncInvoices(control As IRibbonControl)
       On Error GoTo ErrHandler
       Application.ScreenUpdating = False
       
       Dim sidecarPath As String
       sidecarPath = ThisWorkbook.Path & "\..\Engine_test\email_engine\data\invoice_state.jsonl"
       ' OR use hardcoded path from SYSTEM_STANDARDS
       
       If Dir(sidecarPath) = "" Then
           MsgBox "No sidecar file found: " & sidecarPath, vbInformation
           GoTo Cleanup
       End If
       
       Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
       Dim txt As String
       With fso.OpenTextFile(sidecarPath, 1, False, -1)  ' ForReading, Unicode
           If Not .AtEndOfStream Then txt = .ReadAll
           .Close
       End With
       
       Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets("InvoiceLog")
       Dim lines() As String: lines = Split(txt, vbLf)
       Dim appliedCount As Long, skippedCount As Long
       Dim i As Long
       For i = 0 To UBound(lines)
           If Len(Trim$(lines(i))) > 0 Then
               If ApplyInvoiceStateEntry(ws, lines(i)) Then
                   appliedCount = appliedCount + 1
               Else
                   skippedCount = skippedCount + 1
               End If
           End If
       Next i
       
       ' Truncate sidecar (all lines processed OR skipped — both drain)
       With fso.OpenTextFile(sidecarPath, 2, True, -1)  ' ForWriting, truncate
           .Close
       End With
       
       MsgBox "Invoice sync: " & appliedCount & " applied, " & skippedCount & " skipped (not found)", _
              vbInformation
   Cleanup:
       Application.ScreenUpdating = True
       Exit Sub
   ErrHandler:
       Application.ScreenUpdating = True
       MsgBox "Sync error: " & Err.Description, vbCritical
   End Sub
   
   Private Function ApplyInvoiceStateEntry(ws As Worksheet, line As String) As Boolean
       ' Parse simple JSON fields: "type":"PAID", "bkg":"X", "date":"2026-04-21"
       Dim evType As String, bkg As String, eventDate As String
       evType = ExtractJsonField(line, "type")
       bkg = ExtractJsonField(line, "bkg")
       eventDate = ExtractJsonField(line, "date")
       
       If Len(bkg) = 0 Then ApplyInvoiceStateEntry = False: Exit Function
       
       ' Find row by BKG_NO (col 1)
       Dim lastRow As Long
       lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
       If lastRow < 2 Then ApplyInvoiceStateEntry = False: Exit Function
       
       Dim r As Long
       For r = 2 To lastRow
           If UCase$(Trim$(CStr(ws.Cells(r, 1).Value))) = UCase$(bkg) Then
               Select Case evType
                   Case "PAID"
                       ws.Cells(r, 7).Value = "PAID"                    ' STATUS
                       If Len(eventDate) > 0 Then _
                           ws.Cells(r, 8).Value = CDate(eventDate)       ' PAID_DATE
                   Case "REMIND"
                       If Len(eventDate) > 0 Then _
                           ws.Cells(r, 10).Value = CDate(eventDate)      ' LAST_REMINDER_DATE
                   Case "OVERDUE"
                       ws.Cells(r, 7).Value = "OVERDUE"
               End Select
               ApplyInvoiceStateEntry = True
               Exit Function
           End If
       Next r
       ApplyInvoiceStateEntry = False  ' Not found
   End Function
   
   Private Function ExtractJsonField(ln As String, fieldName As String) As String
       ' Simple extractor — looks for "field":"value"
       Dim needle As String: needle = """" & fieldName & """:"""
       Dim p As Long: p = InStr(1, ln, needle, vbTextCompare)
       If p = 0 Then ExtractJsonField = "": Exit Function
       p = p + Len(needle)
       Dim q As Long: q = InStr(p, ln, """")
       If q = 0 Then ExtractJsonField = "": Exit Function
       ExtractJsonField = Mid$(ln, p, q - p)
   End Function
   ```

5. **Add ribbon button** in `CustomUI_v14.xml` Operations tab:
   ```xml
   <button id="btnSyncInvoices" 
           label="Sync Invoices" 
           imageMso="FileSave" 
           size="large"
           onAction="OnAction_SyncInvoices" />
   ```

6. **Import updated .bas + .xml** into live ERP via `scripts/reload-vba-modules.py` (standard flow — see SYSTEM_STANDARDS §5).

7. **Test manually** — see Phase 05.

## Todo List

- [ ] Read full `OnAction_MarkQuoteWin` → identify BKG + CUSTOMER variable names
- [ ] Add `InvoiceLog_InsertOnWin` sub
- [ ] Add call in `OnAction_MarkQuoteWin` success path
- [ ] Add `OnAction_SyncInvoices` + helper functions
- [ ] Add ribbon button in CustomUI_v14.xml
- [ ] Reload VBA modules + ribbon
- [ ] Manual smoke test (Phase 05)

## Success Criteria

- [ ] Mark WIN on a test quote → new row appears in InvoiceLog with correct 11 cols
- [ ] Mark WIN on same quote twice → second click skipped (no duplicate row)
- [ ] Click "Sync Invoices" with empty sidecar → info message, no error
- [ ] With fixture JSONL `{"type":"PAID","bkg":"TESTBKG","date":"2026-04-21"}` → matching row STATUS→PAID, PAID_DATE=21/04/2026, sidecar truncated
- [ ] Ribbon button renders on Operations tab

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Sidecar path hardcoded to PC Home → breaks on Laptop VP | Use `ThisWorkbook.Path` relative OR environment var `%ENGINE_TEST_ROOT%` |
| VBA parser misreads escaped quotes in JSON NOTES | Use `ConvertFromString -AsHashtable` via PowerShell subprocess (fallback) OR restrict sidecar to flat fields (chosen — NOTES field not synced here) |
| `CDate` fails on ISO "2026-04-21" depending on locale | Write explicit `DateSerial(CInt(Left(d,4)), CInt(Mid(d,6,2)), CInt(Mid(d,9,2)))` helper |
| Scanner writes JSONL during Sync click → partial read | Scanner appends line-by-line atomically. Sync reads all. If new line written between read and truncate → data loss. **Mitigation:** rename sidecar first (`invoice_state.jsonl` → `invoice_state.processing`), process, delete. Rename is atomic on NTFS. |
| `CountIf` dedup case-sensitive behavior | Use `UCase$` for both sides |

## Security Considerations

- VBA has full xlsm write access — no sandboxing. Trust boundary: only reads sidecar file within project dir. User-controlled path must not accept arbitrary input.
- Sidecar rename-then-process prevents race with concurrent scanner write.

## Next Steps

- Phase 04 depends on sidecar format documented here
- Phase 05 manual test covers VBA paths
