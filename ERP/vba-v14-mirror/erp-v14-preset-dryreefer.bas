Attribute VB_Name = "ERPv14Preset"
Option Explicit

' ============================================================
'  ERP V14 — Module 3: DRY/REEFER Preset (2026-04-12 rewrite)
'  FIXED for 2-sheet layout (Pricing Dry + Pricing Reefer).
'
'  OLD bug: constants assumed single "Pricing Dashboard" sheet
'  with 7 container cols at 10-16. After split into Dry (cols
'  10-14) + Reefer (cols 10-11), clicking "REEFER Only" on the
'  Reefer sheet hid col 10 (which it thought was 20GP but is
'  actually 20RF) — making Nelson's RF prices invisible.
'
'  NEW behavior:
'   - DRY Only    → navigate to Pricing Dry + unhide its cols
'   - REEFER Only → navigate to Pricing Reefer + unhide its cols
'   - Show All    → unhide everything on BOTH pricing sheets
' ============================================================

Private Const DATA_START_ROW As Integer = 2

Private Function GetNamedPricingSheet(sheetName As String) As Worksheet
    On Error Resume Next
    Set GetNamedPricingSheet = ThisWorkbook.Sheets(sheetName)
    On Error GoTo 0
End Function

Private Sub EnsureVisiblePricingRows(ws As Worksheet)
    On Error Resume Next
    If ws.FilterMode Then ws.ShowAllData
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < DATA_START_ROW Then
        lastRow = ws.UsedRange.Rows(ws.UsedRange.Rows.Count).Row
    End If
    If lastRow >= DATA_START_ROW Then
        ws.Rows(DATA_START_ROW & ":" & lastRow).Hidden = False
    End If
    On Error GoTo 0
End Sub

' Unhide cols on a sheet up to `lastCol` inclusive.
Private Sub UnhideColumns(ws As Worksheet, firstCol As Integer, lastCol As Integer)
    On Error Resume Next
    Dim c As Integer
    For c = firstCol To lastCol
        ws.Columns(c).Hidden = False
    Next c
    On Error GoTo 0
End Sub

' ============================================================
'  DRY ONLY — navigate to Pricing Dry, show all its cols
'  (Dry sheet has 14 data cols: POL..40NOR, no RF cols)
' ============================================================
Public Sub OnAction_PresetDry(control As IRibbonControl)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = GetNamedPricingSheet("Pricing Dry")
    If ws Is Nothing Then Exit Sub

    Application.ScreenUpdating = False
    EnsureVisiblePricingRows ws
    UnhideColumns ws, 1, 16  ' generous upper bound — unhide extras too
    ws.Activate
    ActiveWindow.ScrollRow = 1
    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' ============================================================
'  REEFER ONLY — navigate to Pricing Reefer, show all its cols
'  (Reefer sheet has 11 data cols: POL..40RF)
' ============================================================
Public Sub OnAction_PresetReefer(control As IRibbonControl)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = GetNamedPricingSheet("Pricing Reefer")
    If ws Is Nothing Then Exit Sub

    Application.ScreenUpdating = False
    EnsureVisiblePricingRows ws
    UnhideColumns ws, 1, 16  ' generous upper bound
    ws.Activate
    ActiveWindow.ScrollRow = 1
    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' ============================================================
'  SHOW ALL — unhide everything on BOTH pricing sheets
' ============================================================
Public Sub OnAction_PresetShowAll(control As IRibbonControl)
    On Error Resume Next
    Application.ScreenUpdating = False
    Dim names As Variant
    names = Array("Pricing Dry", "Pricing Reefer")
    Dim i As Integer
    For i = LBound(names) To UBound(names)
        Dim ws As Worksheet: Set ws = GetNamedPricingSheet(CStr(names(i)))
        If Not ws Is Nothing Then
            EnsureVisiblePricingRows ws
            UnhideColumns ws, 1, 16
        End If
    Next i
    ' Activate Pricing Dry by default after Show All
    Dim wsDry As Worksheet: Set wsDry = GetNamedPricingSheet("Pricing Dry")
    If Not wsDry Is Nothing Then
        wsDry.Activate
        ActiveWindow.ScrollRow = 1
    End If
    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' ============================================================
'  RefreshActivePreset — called from Workbook_SheetActivate
'  After sheet switch, re-apply "show all cols" on active sheet
'  to undo any stale hidden state from legacy preset calls.
' ============================================================
Public Sub RefreshActivePreset()
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ActiveSheet
    If ws Is Nothing Then Exit Sub
    If InStr(1, ws.Name, "Pricing", vbTextCompare) > 0 Then
        UnhideColumns ws, 1, 16
    End If
    On Error GoTo 0
End Sub
