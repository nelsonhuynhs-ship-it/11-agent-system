Attribute VB_Name = "ERPv14Core"
Option Explicit

' ============================================================
'  ERP V14 — Module 1: Core Helpers + Auto-Expire + Rate Colors
'  NO SIDEBAR — Ribbon only (2 tabs: Pricing + Operations)
' ============================================================

' ============================================================
'  FindSheet — Safe sheet lookup by partial name
'  LOCKED FUNCTION — do NOT modify
' ============================================================
Public Function FindSheet(searchName As String) As Worksheet
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Sheets
        If InStr(LCase(ws.Name), LCase(searchName)) > 0 Then
            Set FindSheet = ws
            Exit Function
        End If
    Next ws
    Set FindSheet = Nothing
End Function

Public Function GetActivePricingSheet() As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ActiveSheet
    On Error GoTo 0

    If Not ws Is Nothing Then
        Select Case LCase(Trim(ws.Name))
            Case LCase("Pricing Dashboard"), LCase("Pricing Dry"), LCase("Pricing Reefer")
                Set GetActivePricingSheet = ws
                Exit Function
        End Select
    End If

    On Error Resume Next
    Set GetActivePricingSheet = ThisWorkbook.Sheets("Pricing Dry")
    If GetActivePricingSheet Is Nothing Then Set GetActivePricingSheet = ThisWorkbook.Sheets("Pricing Reefer")
    If GetActivePricingSheet Is Nothing Then Set GetActivePricingSheet = ThisWorkbook.Sheets("Pricing Dashboard")
    If GetActivePricingSheet Is Nothing Then Set GetActivePricingSheet = ThisWorkbook.Sheets(1)
    On Error GoTo 0
End Function

' ============================================================
'  HELPER FUNCTIONS
' ============================================================
Public Function SL(v As Variant) As Long
    On Error Resume Next
    If IsNumeric(v) Then SL = CLng(v) Else SL = 0
    On Error GoTo 0
End Function

Public Function SS(v As Variant) As String
    On Error Resume Next
    If IsEmpty(v) Or v = "" Then SS = "" Else SS = CStr(v)
    On Error GoTo 0
End Function

Public Function FmtPrice(v As Long) As String
    If v > 0 Then FmtPrice = "$" & Format(v, "#,##0") Else FmtPrice = ""
End Function

Public Function GetContainerPriceCol(contType As String) As Integer
    Select Case UCase(contType)
        Case "20GP":  GetContainerPriceCol = 10
        Case "40GP":  GetContainerPriceCol = 11
        Case "40HQ", "40HC": GetContainerPriceCol = 12
        Case "45HQ", "45HC": GetContainerPriceCol = 13
        Case "40NOR": GetContainerPriceCol = 14
        Case "20RF":  GetContainerPriceCol = 15
        Case "40RF":  GetContainerPriceCol = 16
        Case Else:    GetContainerPriceCol = 0
    End Select
End Function

' ============================================================
'  AUTO-EXPIRE — Mark quotes past Exp date as EXPIRED
' ============================================================
Public Sub AutoExpireOnOpen()
    On Error Resume Next
    Dim wsQ As Worksheet
    Set wsQ = FindSheet("Quotes")
    If wsQ Is Nothing Then Exit Sub

    Dim r As Long, lr As Long
    lr = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row
    If lr < 2 Then Exit Sub

    Dim expiredCount As Long: expiredCount = 0
    Dim today As Date: today = Date

    For r = 2 To lr
        Dim status As String: status = UCase(Trim(wsQ.Cells(r, 36).Value))
        If status = "PENDING" Or status = "" Then
            Dim expDate As Variant: expDate = wsQ.Cells(r, 10).Value
            If IsDate(expDate) Then
                If CDate(expDate) < today Then
                    wsQ.Cells(r, 36).Value = "EXPIRED"
                    wsQ.Cells(r, 38).Value = Now  ' StatusDate
                    expiredCount = expiredCount + 1
                End If
            End If
        End If
    Next r

    If expiredCount > 0 Then
        Debug.Print "[AutoExpire] " & expiredCount & " quotes expired on " & Format(Now, "yyyy-mm-dd hh:nn")
    End If
    On Error GoTo 0
End Sub

' ============================================================
'  RATE FRESHNESS COLORS — Color code based on Exp date age
'  Green = fresh (<7d), Yellow = aging (7-30d), Red = stale (>30d)
' ============================================================
Public Sub ApplyRateFreshnessColors()
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub

    Dim lr As Long
    lr = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lr < 2 Then Exit Sub

    Application.ScreenUpdating = False
    Dim today As Date: today = Date
    Dim r As Long

    For r = 2 To lr
        Dim expVal As Variant: expVal = ws.Cells(r, 7).Value  ' Col G = Exp
        If IsDate(expVal) Then
            Dim daysOld As Long: daysOld = DateDiff("d", CDate(expVal), today)
            Dim clr As Long
            If daysOld <= 0 Then
                clr = RGB(220, 252, 231)   ' Green — still valid
            ElseIf daysOld <= 30 Then
                clr = RGB(254, 249, 195)   ' Yellow — recently expired
            Else
                clr = RGB(254, 226, 226)   ' Red — stale
            End If
            ' Apply to price columns J-P
            Dim c As Integer
            For c = 10 To 16
                If ws.Cells(r, c).Value <> "" Then
                    ws.Cells(r, c).Interior.Color = clr
                End If
            Next c
        End If
    Next r

    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' ============================================================
'  REFRESH JOBS SUMMARY — KPI stub
' ============================================================
Public Sub RefreshJobsSummary()
    On Error Resume Next
    Dim wsJ As Worksheet
    Set wsJ = FindSheet("Active")
    If wsJ Is Nothing Then Exit Sub

    Dim lr As Long
    lr = wsJ.Cells(wsJ.Rows.Count, 1).End(xlUp).Row
    Dim jobCount As Long: jobCount = 0
    If lr >= 8 Then jobCount = lr - 7  ' Data starts row 8

    Debug.Print "[JobsSummary] " & jobCount & " active jobs as of " & Format(Now, "yyyy-mm-dd")
    On Error GoTo 0
End Sub

' ============================================================
'  QUICK SEARCH — Filter from Row 1 cells (A1-I1)
' ============================================================
Private Function GetPlaceholder(col As Integer) As String
    Select Case col
        Case 1: GetPlaceholder = "POL"
        Case 2: GetPlaceholder = "POD"
        Case 3: GetPlaceholder = "Place"
        Case 4: GetPlaceholder = "Carrier"
        Case 5: GetPlaceholder = "Commodity"
        Case 6: GetPlaceholder = "Eff"
        Case 7: GetPlaceholder = "Exp"
        Case 8: GetPlaceholder = "Note"
        Case 9: GetPlaceholder = "Source"
        Case Else: GetPlaceholder = ""
    End Select
End Function

Private Function IsPlaceholder(col As Integer, val As String) As Boolean
    IsPlaceholder = (UCase(Trim(val)) = UCase(GetPlaceholder(col)))
End Function

Public Sub ApplyQuickSearch()
    ' Fix 2 (2026-04-20): use UsedRange for lr + hard-reset AutoFilter before
    ' re-applying so no stale criteria survive across filter invocations.
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub

    Application.ScreenUpdating = False

    ' Fix 2a: UsedRange for lr to avoid truncation at first gap in col A
    Dim lr As Long
    lr = ws.UsedRange.Rows(ws.UsedRange.Rows.Count).Row
    If lr < 2 Then GoTo Done

    ' Read search values from Row 1 (cols 1-9, skip Exp col 7 — handled by preset)
    Dim searchVal(1 To 9) As String
    Dim hasSearch As Boolean: hasSearch = False
    Dim c As Integer
    Dim v As String
    For c = 1 To 9
        If c <> 7 Then   ' Col 7 (Exp) uses preset logic below — skip text read
            v = Trim(ws.Cells(1, c).Value)
            If v <> "" And Not IsPlaceholder(c, v) Then
                searchVal(c) = UCase(v)
                hasSearch = True
            Else
                searchVal(c) = ""
            End If
        End If
    Next c

    ' Fix 2b: Hard reset AutoFilter — clear every filter field, no stale criteria
    If ws.AutoFilterMode Then ws.AutoFilterMode = False
    ws.Rows("2:" & lr).Hidden = False

    ' Reapply AutoFilter on full data range A:P
    ws.Range("A1:P" & lr).AutoFilter

    ' Get Exp preset from ribbon module (default Active only if call fails)
    Dim expPreset As String: expPreset = ERPv14Ribbon.GetCurrentExpPreset()
    If Len(expPreset) = 0 Then expPreset = "Active only"

    ' Apply Exp date range filter (col 7) based on preset
    Dim todayStr As String: todayStr = Format(Date, "mm/dd/yyyy")
    Dim weekStr As String: weekStr = Format(Date + 7, "mm/dd/yyyy")
    Dim monthStr As String: monthStr = Format(Date + 30, "mm/dd/yyyy")
    Select Case expPreset
        Case "Active only"
            ws.Range("A1:P" & lr).AutoFilter Field:=7, Criteria1:=">=" & todayStr
            hasSearch = True
        Case "This week"
            ws.Range("A1:P" & lr).AutoFilter Field:=7, _
                Criteria1:=">=" & todayStr, Criteria2:="<=" & weekStr, Operator:=xlAnd
            hasSearch = True
        Case "This month"
            ws.Range("A1:P" & lr).AutoFilter Field:=7, _
                Criteria1:=">=" & todayStr, Criteria2:="<=" & monthStr, Operator:=xlAnd
            hasSearch = True
        Case "All (incl. expired)"
            ' No Exp filter — show all dates
    End Select

    ' Show all if no other search criteria
    If Not hasSearch Then GoTo UpdateStatus

    ' Apply text criteria for cols 1-6, 8-9 (col 7 Exp already handled above)
    Dim criteria As String
    For c = 1 To 9
        If c <> 7 And searchVal(c) <> "" Then
            criteria = "*" & Replace(searchVal(c), "~", "~~") & "*"
            ws.Range("A1:P" & lr).AutoFilter Field:=c, Criteria1:=criteria
        End If
    Next c

UpdateStatus:
    ' Bonus: write visible row count to Q1 for quick verification
    Dim visible As Long
    visible = Application.WorksheetFunction.Subtotal(103, ws.Range("A2:A" & lr))
    ws.Cells(1, 17).Value = visible & " of " & (lr - 1) & " rows"
    ws.Cells(1, 17).Font.Color = RGB(100, 100, 100)
    ws.Cells(1, 17).Font.Size = 8

Done:
    ws.Activate
    ActiveWindow.ScrollRow = 1
    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

Public Sub RestorePlaceholder(col As Integer)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    ws.Cells(1, col).Value = GetPlaceholder(col)
    ws.Cells(1, col).Font.Color = RGB(176, 176, 176)
    ws.Cells(1, col).Font.Italic = True
    On Error GoTo 0
End Sub

Public Sub HandleSearchChange(ByVal Target As Range)
    On Error Resume Next
    Dim c As Integer: c = Target.Column
    If Target.Row <> 1 Or c < 1 Or c > 9 Then Exit Sub

    Dim v As String: v = Trim(Target.Value)
    If v = "" Then
        Application.EnableEvents = False
        RestorePlaceholder c
        Application.EnableEvents = True
    Else
        If Not IsPlaceholder(c, v) Then
            Target.Font.Color = RGB(154, 52, 18)
            Target.Font.Italic = False
        End If
    End If
    ApplyQuickSearch
    On Error GoTo 0
End Sub

' ============================================================
'  P1 HELPERS — added 2026-04-11 (sheet activate + cascade)
' ============================================================

' Clear all 6 search placeholders on row 1 of a pricing sheet.
' Called when user switches between Pricing Dry / Pricing Reefer tabs
' so stale filter text from the previous sheet doesn't pollute the new one.
Public Sub ClearAllSearchPlaceholders(ws As Worksheet)
    On Error Resume Next
    Application.EnableEvents = False
    Dim c As Integer
    For c = 1 To 9
        RestorePlaceholder c
    Next c
    If ws.AutoFilterMode Then ws.AutoFilterMode = False
    Application.EnableEvents = True
    On Error GoTo 0
End Sub

' Return unique non-empty values from a column, visible rows only.
' Used by cascade-filter logic in OnChange_Search* callbacks: after a
' carrier is filtered, sibling combo dropdowns rebuild from this list
' so they only show values consistent with the filtered subset.
Public Function GetUniqueVisibleValues(col As Long) As Collection
    Dim c As New Collection
    Dim ws As Worksheet
    Set ws = GetActivePricingSheet()
    If ws Is Nothing Then
        Set GetUniqueVisibleValues = c
        Exit Function
    End If
    Dim r As Long, lastRow As Long, v As String
    On Error Resume Next
    lastRow = ws.Cells(ws.Rows.Count, col).End(xlUp).Row
    For r = 2 To lastRow
        If ws.Rows(r).Hidden = False Then
            v = SS(ws.Cells(r, col).Value)
            If Len(v) > 0 Then
                c.Add v, v
            End If
        End If
    Next r
    On Error GoTo 0
    Set GetUniqueVisibleValues = c
End Function

' ============================================================
'  LANE MAPPER — added 2026-04-11 (Phase 5)
' ============================================================
' Maps a POD string to a lane group for markup lookup.
' Mirrors the lane map used by forecast/market report.
' Returns "WC" / "EC" / "GULF" / "*" (default fallback).
Public Function GetLaneFromPOD(pod As String) As String
    Dim p As String: p = UCase(Trim(pod))
    If Len(p) = 0 Then GetLaneFromPOD = "*": Exit Function

    ' WC ports
    If InStr(p, "LAX") > 0 Or InStr(p, "LGB") > 0 Or InStr(p, "LONG BEACH") > 0 _
        Or InStr(p, "OAK") > 0 Or InStr(p, "OAKLAND") > 0 _
        Or InStr(p, "SEA") > 0 Or InStr(p, "TAC") > 0 Or InStr(p, "TACOMA") > 0 _
        Or InStr(p, "VANCOUVER") > 0 Or InStr(p, "PORTLAND") > 0 Then
        GetLaneFromPOD = "WC": Exit Function
    End If

    ' EC ports
    If InStr(p, "NYC") > 0 Or InStr(p, "NEW YORK") > 0 _
        Or InStr(p, "BOS") > 0 Or InStr(p, "BOSTON") > 0 _
        Or InStr(p, "SAV") > 0 Or InStr(p, "CHS") > 0 Or InStr(p, "CHARLESTON") > 0 _
        Or InStr(p, "BAL") > 0 Or InStr(p, "MIA") > 0 Or InStr(p, "MIAMI") > 0 _
        Or InStr(p, "NORFOLK") > 0 Or InStr(p, "JAX") > 0 Or InStr(p, "JACKSONVILLE") > 0 _
        Or InStr(p, "MONTREAL") > 0 Or InStr(p, "TORONTO") > 0 Or InStr(p, "HALIFAX") > 0 Then
        GetLaneFromPOD = "EC": Exit Function
    End If

    ' GULF ports
    If InStr(p, "HOU") > 0 Or InStr(p, "HOUSTON") > 0 _
        Or InStr(p, "NOLA") > 0 Or InStr(p, "NEW ORLEANS") > 0 _
        Or InStr(p, "MOBILE") > 0 Then
        GetLaneFromPOD = "GULF": Exit Function
    End If

    GetLaneFromPOD = "*"  ' fallback
End Function

' ============================================================
'  STUBS — Placeholder for QuoteJobWorkflow functions
'  Import QuoteJobWorkflow.bas + QuoteBuilder_ERP.bas later
'  to get full Quote/Win/Lost functionality
' ============================================================
' (These stubs are only used if the full modules are NOT imported)
