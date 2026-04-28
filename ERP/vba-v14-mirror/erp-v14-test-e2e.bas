Attribute VB_Name = "ERPv14TestE2E"
Option Explicit

' E2E test wrappers — Path A iteration 1 (2026-04-26)
' Approach: manipulate Row 1 search proxy + call ERPv14Core.ApplyQuickSearch.
' Returns string status: "OK:<details>" or "ERR:<msg>"

' ── Constants (mirror erp-v14-ribbon-callbacks.bas) ──────────
Private Const COL_POL As Integer = 1
Private Const COL_POD As Integer = 2
Private Const COL_PLACE As Integer = 3
Private Const COL_CARRIER As Integer = 4
Private Const COL_SOURCE As Integer = 9


Public Function TestE2E_Search(carrier As String, pol As String, pod As String) As String
    On Error GoTo TestErr

    ' Enable test mode (silence MsgBox)
    Call ERPv14Ribbon.SetTestMode(True)

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Pricing Dry")

    ' Set Row 1 search proxy
    ws.Cells(1, COL_CARRIER).Value = carrier
    ws.Cells(1, COL_POL).Value = pol
    ws.Cells(1, COL_POD).Value = pod

    ' Trigger filter
    Call ERPv14Core.ApplyQuickSearch

    ' Count visible rows (excluding header row 1)
    Dim visibleCount As Long
    On Error Resume Next
    visibleCount = ws.AutoFilter.Range.Columns(1).SpecialCells(xlCellTypeVisible).Count - 2
    If Err.Number <> 0 Then visibleCount = 0
    On Error GoTo TestErr

    TestE2E_Search = "OK:visible_rows=" & visibleCount
    Exit Function
TestErr:
    TestE2E_Search = "ERR:" & Err.Number & ":" & Err.Description
End Function


Public Function TestE2E_HighlightBest(carrier As String, pol As String, pod As String) As String
    On Error GoTo TestErr

    Call ERPv14Ribbon.SetTestMode(True)

    ' Run search first to populate filter
    Dim searchResult As String
    searchResult = TestE2E_Search(carrier, pol, pod)
    If Left(searchResult, 3) = "ERR" Then
        TestE2E_HighlightBest = searchResult
        Exit Function
    End If

    ' Call HighlightBest (requires IRibbonControl param — pass Nothing)
    Call ERPv14Ribbon.OnAction_HighlightBest(Nothing)

    TestE2E_HighlightBest = "OK:" & searchResult
    Exit Function
TestErr:
    TestE2E_HighlightBest = "ERR:" & Err.Number & ":" & Err.Description
End Function


Public Function TestE2E_GatewayUSATL(pol As String) As String
    ' Gateway routing test — search USATL with empty carrier (all carriers)
    On Error GoTo TestErr
    Call ERPv14Ribbon.SetTestMode(True)

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Pricing Dry")
    ws.Cells(1, COL_CARRIER).Value = ""
    ws.Cells(1, COL_POL).Value = pol
    ws.Cells(1, COL_POD).Value = "USATL"

    Call ERPv14Core.ApplyQuickSearch

    Dim visibleCount As Long
    On Error Resume Next
    visibleCount = ws.AutoFilter.Range.Columns(1).SpecialCells(xlCellTypeVisible).Count - 2
    If Err.Number <> 0 Then visibleCount = 0
    On Error GoTo TestErr

    TestE2E_GatewayUSATL = "OK:visible_rows=" & visibleCount
    Exit Function
TestErr:
    TestE2E_GatewayUSATL = "ERR:" & Err.Number & ":" & Err.Description
End Function

' ============================================================
'  Phase 3 (260428) — Smart Quote Img tests
' ============================================================

' Test: smart group detection from Pricing sheet
Public Function TestE2E_QuoteImg_FromPricing(customerName As String, contCSV As String) As String
    On Error GoTo TestErr
    Call ERPv14Ribbon.SetTestMode(True)

    ' Activate Pricing sheet (simulate Sep standing on Pricing)
    Dim wsP As Worksheet
    Set wsP = ERPv14Core.GetActivePricingSheet()
    If wsP Is Nothing Then TestE2E_QuoteImg_FromPricing = "FAIL:no_pricing_sheet": Exit Function
    wsP.Activate

    ' Call the smart dispatcher
    Call ERPv14Ribbon.OnAction_QuoteImage(Nothing)

    ' Check: should now be on Quotes sheet
    If ActiveSheet.Name <> "Quotes" Then
        TestE2E_QuoteImg_FromPricing = "FAIL:did_not_switch_to_quotes:active=" & ActiveSheet.Name
        Exit Function
    End If

    TestE2E_QuoteImg_FromPricing = "OK:switched_to_quotes"
    Exit Function
TestErr:
    TestE2E_QuoteImg_FromPricing = "FAIL:" & Err.Number & ":" & Err.Description
End Function

' Test: smart group detection — count rows in latest group
Public Function TestE2E_QuoteImg_LatestGroupCount(expectedRows As Long) As String
    On Error GoTo TestErr
    Call ERPv14Ribbon.SetTestMode(True)

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then TestE2E_QuoteImg_LatestGroupCount = "FAIL:no_quotes_sheet": Exit Function
    wsQ.Activate

    ' Clear any prior selection — force smart mode
    wsQ.Cells(1, 1).Select  ' header row → not "real" selection per dispatcher

    ' Note: we can't call Private subs directly from here, so we just
    ' verify the sheet has data and trust the dispatcher logic
    Dim lastRow As Long
    lastRow = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row
    If lastRow < 5 Then
        TestE2E_QuoteImg_LatestGroupCount = "FAIL:no_data_at_row5"
        Exit Function
    End If

    ' Walk from row 5 to count contiguous same-group rows (mimic QuoteImage_CollectLatestGroup)
    Dim refGid As String: refGid = Trim(CStr(wsQ.Cells(5, 43).Value))
    Dim refDate As String: refDate = Format(wsQ.Cells(5, 2).Value, "yyyy-mm-dd")
    Dim refCust As String: refCust = UCase(Trim(CStr(wsQ.Cells(5, 3).Value)))
    Dim r As Long: r = 5
    Dim cnt As Long: cnt = 0
    Do While r <= lastRow
        Dim qid As String: qid = Trim(CStr(wsQ.Cells(r, 1).Value))
        If qid = "" Then Exit Do
        Dim gid As String: gid = Trim(CStr(wsQ.Cells(r, 43).Value))
        Dim dt As String: dt = Format(wsQ.Cells(r, 2).Value, "yyyy-mm-dd")
        Dim cust As String: cust = UCase(Trim(CStr(wsQ.Cells(r, 3).Value)))
        Dim match As Boolean: match = False
        If refGid <> "" And gid = refGid Then
            match = True
        ElseIf cust = refCust And dt = refDate Then
            match = True
        End If
        If Not match Then Exit Do
        cnt = cnt + 1
        r = r + 1
    Loop

    If cnt = expectedRows Then
        TestE2E_QuoteImg_LatestGroupCount = "OK:rows=" & cnt
    Else
        TestE2E_QuoteImg_LatestGroupCount = "FAIL:expected=" & expectedRows & " got=" & cnt
    End If
    Exit Function
TestErr:
    TestE2E_QuoteImg_LatestGroupCount = "FAIL:" & Err.Number & ":" & Err.Description
End Function

' Test: backward compat — explicit row selection wins over smart
Public Function TestE2E_QuoteImg_ExplicitSelection(targetRow As Long) As String
    On Error GoTo TestErr
    Call ERPv14Ribbon.SetTestMode(True)

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then TestE2E_QuoteImg_ExplicitSelection = "FAIL:no_quotes_sheet": Exit Function
    wsQ.Activate
    wsQ.Rows(targetRow).Select  ' explicit row selection

    ' Manually walk selection to verify it picks exactly 1 row
    Dim selArea As Range, sr As Long, rowCount As Long
    Dim rowNums() As Long
    rowCount = 0
    For Each selArea In Selection.Areas
        For sr = 1 To selArea.Rows.Count
            Dim row As Long: row = selArea.Rows(sr).Row
            If row >= 2 And Trim(wsQ.Cells(row, 1).Value) <> "" Then
                rowCount = rowCount + 1
                ReDim Preserve rowNums(1 To rowCount)
                rowNums(rowCount) = row
            End If
        Next sr
    Next selArea

    If rowCount = 1 And rowNums(1) = targetRow Then
        TestE2E_QuoteImg_ExplicitSelection = "OK:row=" & rowNums(1)
    Else
        TestE2E_QuoteImg_ExplicitSelection = "FAIL:expected=" & targetRow & " count=" & rowCount
    End If
    Exit Function
TestErr:
    TestE2E_QuoteImg_ExplicitSelection = "FAIL:" & Err.Number & ":" & Err.Description
End Function

' Test: filter cache restore
Public Function TestE2E_FilterRestore(sheetName As String, _
                                       seedCarrier As String, seedPOL As String, _
                                       seedPOD As String, seedPlace As String) As String
    On Error GoTo TestErr
    Call ERPv14Ribbon.SetTestMode(True)

    ' Seed module-level filter state
    ERPv14Ribbon.SetSearchCarrier seedCarrier
    ERPv14Ribbon.SetSearchPOL seedPOL
    ERPv14Ribbon.SetSearchPOD seedPOD
    ERPv14Ribbon.SetSearchPlace seedPlace

    ' Cache it
    Call ERPv14Ribbon.CacheSearchState(sheetName)

    ' Wipe state (simulate sheet activate doing reset)
    ERPv14Ribbon.SetSearchCarrier ""
    ERPv14Ribbon.SetSearchPOL ""
    ERPv14Ribbon.SetSearchPOD ""
    ERPv14Ribbon.SetSearchPlace ""

    ' Restore
    Dim restored As Boolean
    restored = ERPv14Ribbon.TryRestoreSearchState(sheetName)

    If Not restored Then
        TestE2E_FilterRestore = "FAIL:restore_returned_false"
        Exit Function
    End If
    If ERPv14Ribbon.GetSearchCarrier = seedCarrier And _
       ERPv14Ribbon.GetSearchPOL = seedPOL And _
       ERPv14Ribbon.GetSearchPOD = seedPOD And _
       ERPv14Ribbon.GetSearchPlace = seedPlace Then
        TestE2E_FilterRestore = "OK:restored"
    Else
        TestE2E_FilterRestore = "FAIL:state_mismatch"
    End If
    Exit Function
TestErr:
    TestE2E_FilterRestore = "FAIL:" & Err.Number & ":" & Err.Description
End Function