Attribute VB_Name = "QuoteBuilder"
Option Explicit

' ============================================================
'  QUOTE BUILDER - ERP V13 Ribbon + Quick Search
'  Row 1 A-I = dual header/search (placeholder when empty)
'  Row 2+ = Data
' ============================================================

' ============================================================
'  MODULE-LEVEL STATE
' ============================================================
Private m_Carrier As String
Private m_POL As String
Private m_POD As String
Private m_Place As String
Private m_Customer As String
Private m_Eff As String
Private m_Exp As String
Private m_Note As String
Private m_Source As String
Private m_SourceRow As Long

' Buy prices
Private m_Buy20GP As Long
Private m_Buy40GP As Long
Private m_Buy40HC As Long
Private m_Buy45HC As Long
Private m_Buy40NOR As Long
Private m_Buy20RF As Long
Private m_Buy40RF As Long

' Margin
Private m_Mar20GP As Long
Private m_Mar40GP As Long
Private m_Mar40HC As Long
Private m_Mar45HC As Long
Private m_Mar40NOR As Long
Private m_Mar20RF As Long
Private m_Mar40RF As Long

' PUC
Private m_PUC20 As Long
Private m_PUC40 As Long
Private m_PUC40HC As Long

' SOC flag
Private m_IsSOC As Boolean

' Ribbon reference (set by onLoad callback)
Public ribbonUI As IRibbonUI

' ============================================================
'  CONSTANTS
' ============================================================
Private Const DATA_START_ROW As Integer = 2

' Active Jobs sheet layout
Private Const ACTIVEJOBS_HEADER_ROW As Long = 7
Private Const ACTIVEJOBS_DATA_START As Long = 8

' Active Jobs column positions — V13 slim layout (31 columns)
Private Const AJ_COL_CRMID          As Long = 1   ' A
Private Const AJ_COL_CUSTTYPE       As Long = 2   ' B
Private Const AJ_COL_ROUTING        As Long = 3   ' C
Private Const AJ_COL_BKG_NO         As Long = 4   ' D
Private Const AJ_COL_ETD            As Long = 5   ' E
Private Const AJ_COL_ETA            As Long = 6   ' F
Private Const AJ_COL_ATA            As Long = 7   ' G
Private Const AJ_COL_CARRIER        As Long = 8   ' H
Private Const AJ_COL_CONTRACT       As Long = 9   ' I
Private Const AJ_COL_CONTTYPE       As Long = 10  ' J
Private Const AJ_COL_QTY            As Long = 11  ' K
Private Const AJ_COL_SELL           As Long = 12  ' L
Private Const AJ_COL_BUY            As Long = 13  ' M
Private Const AJ_COL_PROFIT         As Long = 14  ' N
Private Const AJ_COL_MARGIN         As Long = 15  ' O
Private Const AJ_COL_STATUS         As Long = 16  ' P
Private Const AJ_COL_SI             As Long = 17  ' Q
Private Const AJ_COL_CYCUTOFF       As Long = 18  ' R
Private Const AJ_COL_DOOR           As Long = 19  ' S
Private Const AJ_COL_DOOR_ADDR      As Long = 20  ' T
Private Const AJ_COL_DOOR_STATUS    As Long = 21  ' U
Private Const AJ_COL_DELAY_CNT      As Long = 22  ' V
Private Const AJ_COL_DELAY_LOG      As Long = 23  ' W
Private Const AJ_COL_NOTES          As Long = 24  ' X
Private Const AJ_COL_CREATED        As Long = 25  ' Y
Private Const AJ_COL_UPDATED        As Long = 26  ' Z
Private Const AJ_COL_COST_BKD       As Long = 27  ' AA
Private Const AJ_COL_REQUEST_BKG    As Long = 28  ' AB
Private Const AJ_COL_FAST_JOB       As Long = 29  ' AC
Private Const AJ_COL_FAST_REF       As Long = 30  ' AD
Private Const AJ_COL_HBL            As Long = 31  ' AE

Private Const COL_POL       As Integer = 1
Private Const COL_POD       As Integer = 2
Private Const COL_PLACE     As Integer = 3
Private Const COL_CARRIER   As Integer = 4
Private Const COL_COMMODITY As Integer = 5
Private Const COL_EFF       As Integer = 6
Private Const COL_EXP       As Integer = 7
Private Const COL_NOTE      As Integer = 8
Private Const COL_SOURCE    As Integer = 9
Private Const COL_20GP      As Integer = 10
Private Const COL_40GP      As Integer = 11
Private Const COL_40HQ      As Integer = 12
Private Const COL_45HQ      As Integer = 13
Private Const COL_40NOR     As Integer = 14
Private Const COL_20RF      As Integer = 15
Private Const COL_40RF      As Integer = 16

' ============================================================
'  RIBBON LOAD CALLBACK
' ============================================================
Public Sub RibbonOnLoad(ribbon As IRibbonUI)
    Set ribbonUI = ribbon
End Sub

' Row 1 placeholder labels (shown when search is empty)
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

' ============================================================
'  HELPERS
' ============================================================
Private Function SL(v As Variant) As Long
    On Error Resume Next
    If IsNumeric(v) Then SL = CLng(v) Else SL = 0
    On Error GoTo 0
End Function

Private Function SS(v As Variant) As String
    On Error Resume Next
    If IsEmpty(v) Or v = "" Then SS = "" Else SS = CStr(v)
    On Error GoTo 0
End Function

Private Function FmtPrice(v As Long) As String
    If v > 0 Then FmtPrice = "$" & Format(v, "#,##0") Else FmtPrice = ""
End Function

' ============================================================
'  QUICK SEARCH — Filter from Row 1 cells (A1-I1)
'  Row 1 = dual purpose: placeholder label + search input
'  When cell has placeholder text or empty -> no filter
'  When cell has other text -> apply filter on that column
' ============================================================
Public Sub ApplyQuickSearch()
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(1)
    If ws Is Nothing Then Exit Sub
    
    Application.ScreenUpdating = False
    
    Dim lr As Long
    lr = ws.Cells(ws.Rows.Count, COL_POL).End(xlUp).Row
    If lr < DATA_START_ROW Then GoTo Done
    
    ' Read search values from Row 1 (ignore placeholders)
    Dim searchVal(1 To 9) As String
    Dim hasSearch As Boolean: hasSearch = False
    Dim c As Integer
    For c = 1 To 9
        Dim v As String: v = Trim(ws.Cells(1, c).Value)
        If v <> "" And Not IsPlaceholder(c, v) Then
            searchVal(c) = UCase(v)
            hasSearch = True
        Else
            searchVal(c) = ""
        End If
    Next c
    
    ' Show all if no search
    If Not hasSearch Then
        Dim rr As Long
        For rr = DATA_START_ROW To lr
            ws.Rows(rr).Hidden = False
        Next rr
        GoTo Done
    End If
    
    ' Apply filter — hide non-matching rows
    Dim r As Long
    For r = DATA_START_ROW To lr
        Dim show As Boolean: show = True
        
        For c = 1 To 9
            If searchVal(c) <> "" And show Then
                Dim cellVal As String
                cellVal = UCase(Trim(ws.Cells(r, c).Value))
                If InStr(1, cellVal, searchVal(c), vbTextCompare) = 0 Then
                    show = False
                End If
            End If
        Next c
        
        ws.Rows(r).Hidden = Not show
    Next r
    
Done:
    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' Restore placeholder label for a specific cell
Public Sub RestorePlaceholder(col As Integer)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(1)
    If ws Is Nothing Then Exit Sub
    
    ws.Cells(1, col).Value = GetPlaceholder(col)
    ws.Cells(1, col).Font.Color = RGB(176, 176, 176)
    ws.Cells(1, col).Font.Italic = True
    On Error GoTo 0
End Sub

' Called by Worksheet_Change — handles search cell changes
Public Sub HandleSearchChange(ByVal Target As Range)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = Target.Worksheet
    Dim c As Integer: c = Target.Column
    
    ' Only handle A1-I1
    If Target.Row <> 1 Or c < 1 Or c > 9 Then Exit Sub
    
    Dim v As String: v = Trim(Target.Value)
    
    ' If cell cleared -> restore placeholder
    If v = "" Then
        Application.EnableEvents = False
        RestorePlaceholder c
        Application.EnableEvents = True
    Else
        ' Make search text look active (dark font, not italic)
        If Not IsPlaceholder(c, v) Then
            Target.Font.Color = RGB(154, 52, 18)
            Target.Font.Italic = False
        End If
    End If
    
    ' Apply filter
    ApplyQuickSearch
    On Error GoTo 0
End Sub

' ============================================================
'  LOAD ROW TO RIBBON (called from Sheet1 SelectionChange)
' ============================================================
Public Sub LoadRowToRibbon(targetRow As Long)
    On Error Resume Next
    
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(1)
    If ws Is Nothing Then Exit Sub
    If targetRow < DATA_START_ROW Then Exit Sub
    If IsEmpty(ws.Cells(targetRow, COL_POL).Value) Then Exit Sub
    
    ' Read row data
    m_POL = SS(ws.Cells(targetRow, COL_POL).Value)
    m_POD = SS(ws.Cells(targetRow, COL_POD).Value)
    m_Place = SS(ws.Cells(targetRow, COL_PLACE).Value)
    m_Carrier = SS(ws.Cells(targetRow, COL_CARRIER).Value)
    m_Eff = SS(ws.Cells(targetRow, COL_EFF).Value)
    m_Exp = SS(ws.Cells(targetRow, COL_EXP).Value)
    m_Note = SS(ws.Cells(targetRow, COL_NOTE).Value)
    m_Source = SS(ws.Cells(targetRow, COL_SOURCE).Value)
    m_SourceRow = targetRow
    
    ' SOC detection
    m_IsSOC = (InStr(UCase(m_Note), "SOC") > 0) Or (InStr(UCase(m_Source), "SOC") > 0)
    
    ' Buy prices
    m_Buy20GP = SL(ws.Cells(targetRow, COL_20GP).Value)
    m_Buy40GP = SL(ws.Cells(targetRow, COL_40GP).Value)
    m_Buy40HC = SL(ws.Cells(targetRow, COL_40HQ).Value)
    m_Buy45HC = SL(ws.Cells(targetRow, COL_45HQ).Value)
    m_Buy40NOR = SL(ws.Cells(targetRow, COL_40NOR).Value)
    m_Buy20RF = SL(ws.Cells(targetRow, COL_20RF).Value)
    m_Buy40RF = SL(ws.Cells(targetRow, COL_40RF).Value)
    
    ' Load carrier markup
    LoadMarkupForCarrier m_Carrier
    
    ' PUC lookup (SOC only)
    If m_IsSOC Then
        LookupPUC m_Place
    Else
        m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    End If
    
    On Error GoTo 0
End Sub

' ============================================================
'  PUC LOOKUP
' ============================================================
Private Sub LookupPUC(placeName As String)
    m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    Dim wsPUC As Worksheet
    On Error Resume Next
    Set wsPUC = ThisWorkbook.Sheets("PUC_Lookup")
    On Error GoTo 0
    If wsPUC Is Nothing Then Exit Sub
    If placeName = "" Then Exit Sub
    
    Dim pn As String: pn = UCase(Trim(placeName))
    Dim pr As Long
    For pr = 2 To wsPUC.Cells(wsPUC.Rows.Count, 1).End(xlUp).Row
        If Len(wsPUC.Cells(pr, 1).Value) > 0 Then
            If InStr(pn, UCase(Left(wsPUC.Cells(pr, 1).Value, 5))) > 0 Then
                m_PUC20 = SL(wsPUC.Cells(pr, 2).Value)
                m_PUC40 = SL(wsPUC.Cells(pr, 3).Value)
                m_PUC40HC = SL(wsPUC.Cells(pr, 4).Value)
                Exit For
            End If
        End If
    Next pr
End Sub

' ============================================================
'  MARKUP STORE
' ============================================================
Private Sub LoadMarkupForCarrier(cn As String)
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0
    m_Mar45HC = 0: m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub
    
    Dim r As Long
    For r = 2 To wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            m_Mar20GP = SL(wsM.Cells(r, 2).Value)
            m_Mar40GP = SL(wsM.Cells(r, 3).Value)
            m_Mar40HC = SL(wsM.Cells(r, 4).Value)
            Exit Sub
        End If
    Next r
End Sub

Private Sub SaveMarkupForCarrier(cn As String)
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub
    Dim r As Long
    For r = 2 To wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            wsM.Cells(r, 2).Value = m_Mar20GP
            wsM.Cells(r, 3).Value = m_Mar40GP
            wsM.Cells(r, 4).Value = m_Mar40HC
            Exit Sub
        End If
    Next r
End Sub

' ============================================================
'  RIBBON CALLBACKS — Route Info
' ============================================================
Public Sub GetLabel_CarrierBadge(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Carrier <> "" Then
        If m_IsSOC Then label = m_Carrier & " [SOC]" Else label = m_Carrier & " [COC]"
    Else: label = "Carrier: --": End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_Route(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_POL <> "" Then label = m_POL & " > " & m_POD Else label = "Click a row to load"
    On Error GoTo 0
End Sub
Public Sub GetLabel_Voyage(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next: If m_Note <> "" Then label = "via " & m_Note Else label = "": On Error GoTo 0
End Sub
Public Sub GetLabel_Dates(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next: If m_Eff <> "" Then label = m_Eff & " - " & m_Exp Else label = "": On Error GoTo 0
End Sub

' ============================================================
'  RIBBON CALLBACKS — Buy Rate (read-only)
' ============================================================
Public Sub GetText_Buy20GP(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy20GP > 0 Then text = CStr(m_Buy20GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy40GP(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy40GP > 0 Then text = CStr(m_Buy40GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy40HC(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy40HC > 0 Then text = CStr(m_Buy40HC) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy45HC(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy45HC > 0 Then text = CStr(m_Buy45HC) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy40NOR(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy40NOR > 0 Then text = CStr(m_Buy40NOR) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy20RF(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy20RF > 0 Then text = CStr(m_Buy20RF) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Buy40RF(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Buy40RF > 0 Then text = CStr(m_Buy40RF) Else text = "": On Error GoTo 0
End Sub

' ============================================================
'  RIBBON CALLBACKS — Margin (getText + onChange)
' ============================================================
Public Sub GetText_Mar20(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar20GP <> 0 Then text = CStr(m_Mar20GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40GP(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40GP <> 0 Then text = CStr(m_Mar40GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40HC(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40HC <> 0 Then text = CStr(m_Mar40HC) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar45(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar45HC <> 0 Then text = CStr(m_Mar45HC) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40NOR(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40NOR <> 0 Then text = CStr(m_Mar40NOR) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar20RF(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar20RF <> 0 Then text = CStr(m_Mar20RF) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40RF(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40RF <> 0 Then text = CStr(m_Mar40RF) Else text = "": On Error GoTo 0
End Sub

Public Sub OnChange_Mar20(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar20GP = SL(text): SaveMarkupForCarrier m_Carrier: On Error GoTo 0
End Sub
Public Sub OnChange_Mar40GP(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40GP = SL(text): SaveMarkupForCarrier m_Carrier: On Error GoTo 0
End Sub
Public Sub OnChange_Mar40HC(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40HC = SL(text): SaveMarkupForCarrier m_Carrier: On Error GoTo 0
End Sub
Public Sub OnChange_Mar45(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar45HC = SL(text): On Error GoTo 0
End Sub
Public Sub OnChange_Mar40NOR(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40NOR = SL(text): On Error GoTo 0
End Sub
Public Sub OnChange_Mar20RF(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar20RF = SL(text): On Error GoTo 0
End Sub
Public Sub OnChange_Mar40RF(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40RF = SL(text): On Error GoTo 0
End Sub

Public Sub OnChange_Customer(control As IRibbonControl, text As String)
    On Error Resume Next: m_Customer = text: On Error GoTo 0
End Sub

' ============================================================
'  RIBBON CALLBACKS — PUC (SOC only)
' ============================================================
Public Sub GetLabel_PUC20(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_IsSOC And m_PUC20 > 0 Then
        label = "PUC 20: +$" & Format(m_PUC20, "#,##0")
    ElseIf m_IsSOC Then
        label = "PUC 20: --"
    Else
        label = ""
    End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_PUC40(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_IsSOC And m_PUC40 > 0 Then
        label = "PUC 40: +$" & Format(m_PUC40, "#,##0")
    ElseIf m_IsSOC Then
        label = "PUC 40: --"
    Else
        label = ""
    End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_PUC40HC(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_IsSOC And m_PUC40HC > 0 Then
        label = "PUC HC: +$" & Format(m_PUC40HC, "#,##0")
    ElseIf m_IsSOC Then
        label = "PUC HC: --"
    Else
        label = ""
    End If
    On Error GoTo 0
End Sub

' ============================================================
'  RIBBON CALLBACKS — Sell Rate (Buy + Margin + PUC)
' ============================================================
Public Sub GetLabel_Sell20(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy20GP > 0 Then label = "20GP = " & FmtPrice(m_Buy20GP + m_Mar20GP + m_PUC20) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40GP(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40GP > 0 And m_Buy40GP <> m_Buy40HC Then
        label = "40GP = " & FmtPrice(m_Buy40GP + m_Mar40GP + m_PUC40)
    ElseIf m_Buy40GP > 0 And m_Buy40GP = m_Buy40HC Then
        label = "40' = " & FmtPrice(m_Buy40GP + m_Mar40GP + m_PUC40)
    Else: label = "": End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40HC(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40HC > 0 And m_Buy40HC <> m_Buy40GP Then
        label = "40HC = " & FmtPrice(m_Buy40HC + m_Mar40HC + m_PUC40HC)
    Else: label = "": End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell45HC(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy45HC > 0 Then label = "45HC = " & FmtPrice(m_Buy45HC + m_Mar45HC) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40NOR(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40NOR > 0 Then label = "40NOR = " & FmtPrice(m_Buy40NOR + m_Mar40NOR) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell20RF(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy20RF > 0 Then label = "20RF = " & FmtPrice(m_Buy20RF + m_Mar20RF) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40RF(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40RF > 0 Then label = "40RF = " & FmtPrice(m_Buy40RF + m_Mar40RF) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Profit(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    Dim profit As Long
    profit = m_Mar20GP + m_Mar40GP + m_Mar40HC + m_Mar45HC + m_Mar40NOR + m_Mar20RF + m_Mar40RF
    If profit > 0 Then label = "Est. Profit: " & FmtPrice(profit) Else label = "Est. Profit: --"
    On Error GoTo 0
End Sub

' ============================================================
'  GENERATE QUOTE
' ============================================================
Public Sub GenerateQuote(control As IRibbonControl)
    On Error Resume Next
    If m_Customer = "" Then
        MsgBox "Please enter Customer name!", vbExclamation, "Quote Builder"
        Exit Sub
    End If
    If m_Carrier = "" Then
        MsgBox "Please click a data row first!", vbExclamation, "Quote Builder"
        Exit Sub
    End If
    
    Dim wsQ As Worksheet: Set wsQ = ThisWorkbook.Sheets("Quotes")
    If wsQ Is Nothing Then Exit Sub
    
    If IsEmpty(wsQ.Cells(1, 1).Value) Then
        Dim h As Variant
        h = Array("QuoteID", "Date", "Customer", "Carrier", "POL", "POD", "Place", "Via", "Eff", "Exp", "Source", _
                   "Buy_20GP", "Buy_40GP", "Buy_40HC", "Buy_45HC", "Buy_40NOR", "Buy_20RF", "Buy_40RF", _
                   "Mar_20GP", "Mar_40GP", "Mar_40HC", "Mar_45HC", "Mar_40NOR", "Mar_20RF", "Mar_40RF", _
                   "PUC_20", "PUC_40", "PUC_40HC", _
                   "Sell_20GP", "Sell_40GP", "Sell_40HC", "Sell_45HC", "Sell_40NOR", "Sell_20RF", "Sell_40RF", _
                   "Status", "Remark")
        Dim hi As Integer
        For hi = 0 To UBound(h): wsQ.Cells(1, hi + 1).Value = h(hi): Next hi
        wsQ.Range("A1:AK1").Font.Bold = True
    End If
    
    Dim qid As String
    qid = UCase(Format(Date, "DDMMM")) & "-" & Format(Int((999 - 100 + 1) * Rnd + 100), "000")
    Dim nr As Long: nr = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row + 1
    If nr < 2 Then nr = 2
    
    wsQ.Cells(nr, 1) = qid: wsQ.Cells(nr, 2) = Now
    wsQ.Cells(nr, 3) = m_Customer: wsQ.Cells(nr, 4) = m_Carrier
    wsQ.Cells(nr, 5) = m_POL: wsQ.Cells(nr, 6) = m_POD
    wsQ.Cells(nr, 7) = m_Place: wsQ.Cells(nr, 8) = m_Note
    wsQ.Cells(nr, 9) = m_Eff: wsQ.Cells(nr, 10) = m_Exp
    If m_IsSOC Then wsQ.Cells(nr, 11) = "SOC" Else wsQ.Cells(nr, 11) = "COC"
    
    If m_Buy20GP > 0 Then wsQ.Cells(nr, 12) = m_Buy20GP
    If m_Buy40GP > 0 Then wsQ.Cells(nr, 13) = m_Buy40GP
    If m_Buy40HC > 0 Then wsQ.Cells(nr, 14) = m_Buy40HC
    If m_Buy45HC > 0 Then wsQ.Cells(nr, 15) = m_Buy45HC
    If m_Buy40NOR > 0 Then wsQ.Cells(nr, 16) = m_Buy40NOR
    If m_Buy20RF > 0 Then wsQ.Cells(nr, 17) = m_Buy20RF
    If m_Buy40RF > 0 Then wsQ.Cells(nr, 18) = m_Buy40RF
    If m_Mar20GP <> 0 Then wsQ.Cells(nr, 19) = m_Mar20GP
    If m_Mar40GP <> 0 Then wsQ.Cells(nr, 20) = m_Mar40GP
    If m_Mar40HC <> 0 Then wsQ.Cells(nr, 21) = m_Mar40HC
    If m_Mar45HC <> 0 Then wsQ.Cells(nr, 22) = m_Mar45HC
    If m_Mar40NOR <> 0 Then wsQ.Cells(nr, 23) = m_Mar40NOR
    If m_Mar20RF <> 0 Then wsQ.Cells(nr, 24) = m_Mar20RF
    If m_Mar40RF <> 0 Then wsQ.Cells(nr, 25) = m_Mar40RF
    If m_PUC20 > 0 Then wsQ.Cells(nr, 26) = m_PUC20
    If m_PUC40 > 0 Then wsQ.Cells(nr, 27) = m_PUC40
    If m_PUC40HC > 0 Then wsQ.Cells(nr, 28) = m_PUC40HC
    If m_Buy20GP > 0 Then wsQ.Cells(nr, 29) = m_Buy20GP + m_Mar20GP + m_PUC20
    If m_Buy40GP > 0 Then wsQ.Cells(nr, 30) = m_Buy40GP + m_Mar40GP + m_PUC40
    If m_Buy40HC > 0 Then wsQ.Cells(nr, 31) = m_Buy40HC + m_Mar40HC + m_PUC40HC
    If m_Buy45HC > 0 Then wsQ.Cells(nr, 32) = m_Buy45HC + m_Mar45HC
    If m_Buy40NOR > 0 Then wsQ.Cells(nr, 33) = m_Buy40NOR + m_Mar40NOR
    If m_Buy20RF > 0 Then wsQ.Cells(nr, 34) = m_Buy20RF + m_Mar20RF
    If m_Buy40RF > 0 Then wsQ.Cells(nr, 35) = m_Buy40RF + m_Mar40RF
    wsQ.Cells(nr, 36) = "PENDING"
    
    Dim fc As Integer
    For fc = 12 To 35: wsQ.Cells(nr, fc).NumberFormat = "$#,##0": Next fc
    
    Dim routeStr As String: routeStr = m_POL & " > " & m_POD
    If m_Place <> "" And m_Place <> m_POD Then routeStr = m_POL & " > " & m_Place & " via " & m_POD
    
    MsgBox "Quote " & qid & " created!" & vbCrLf & _
           "Customer: " & m_Customer & vbCrLf & _
           "Route: " & routeStr & vbCrLf & _
           "Carrier: " & m_Carrier, vbInformation, "Quote Builder"
    On Error GoTo 0
End Sub


' ============================================================
'  MARK QUOTE WIN — V13 Ribbon Port
'  Trigger: Ribbon button btnWin
' ============================================================

Public Sub MarkQuoteWin(control As IRibbonControl)
    On Error GoTo ErrHandler
    
    Dim wsQ As Worksheet
    Dim wsJ As Worksheet
    Dim r As Long
    
    ' ── Step 1: Validate selection ──
    Set wsQ = Nothing
    On Error Resume Next
    Set wsQ = ThisWorkbook.Sheets("Quotes")
    On Error GoTo ErrHandler
    
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Please navigate to the Quotes sheet first!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    r = Selection.Row
    If r < 2 Then
        MsgBox "Select a quote data row (row 2+)!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    Dim quoteID As String
    quoteID = Trim(CStr(wsQ.Cells(r, 1).Value))
    If quoteID = "" Then
        MsgBox "No quote in this row!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    Dim currentStatus As String
    currentStatus = Trim(CStr(wsQ.Cells(r, 36).Value))
    
    If currentStatus = "WIN" Then
        MsgBox "Already marked as WIN!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    If InStr(currentStatus, "LOST") > 0 Or InStr(currentStatus, "EXPIRED") > 0 Then
        If MsgBox("Quote was " & currentStatus & ". Confirm WIN anyway?", _
                  vbYesNo + vbQuestion, "Mark WIN") = vbNo Then
            Exit Sub
        End If
    End If
    
    ' ── Step 2: Read quote data ──
    Dim customer As String: customer = CStr(wsQ.Cells(r, 3).Value)
    Dim carrier As String:  carrier = CStr(wsQ.Cells(r, 4).Value)
    Dim pol As String:      pol = CStr(wsQ.Cells(r, 5).Value)
    Dim pod As String:      pod = CStr(wsQ.Cells(r, 6).Value)
    Dim place As String:    place = CStr(wsQ.Cells(r, 7).Value)
    Dim eff As String:      eff = CStr(wsQ.Cells(r, 9).Value)
    Dim exp As String:      exp = CStr(wsQ.Cells(r, 10).Value)
    Dim source As String:   source = CStr(wsQ.Cells(r, 11).Value)
    
    ' ── Step 2b: Lookup CRM_ID from CRM sheet ──
    Dim crmID As String: crmID = ""
    Dim custType As String: custType = ""
    On Error Resume Next
    Dim wsCRM As Worksheet
    Set wsCRM = ThisWorkbook.Sheets("CRM")
    If Not wsCRM Is Nothing Then
        Dim cr As Long
        Dim searchCust As String: searchCust = UCase(Trim(customer))
        For cr = 2 To wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
            If UCase(Trim(CStr(wsCRM.Cells(cr, 2).Value))) = searchCust Then
                crmID = CStr(wsCRM.Cells(cr, 1).Value)
                custType = CStr(wsCRM.Cells(cr, 3).Value)
                Exit For
            End If
        Next cr
    End If
    On Error GoTo ErrHandler
    ' If CRM_ID not found, use customer name as fallback
    If crmID = "" Then crmID = customer
    
    ' ── Step 3: Ask container type ──
    Dim contType As String
    contType = UCase(Trim(InputBox( _
        "Container type booked?" & vbCrLf & _
        "Options: 20GP / 40GP / 40HC / 45HC / 40NOR / 20RF / 40RF", _
        "Mark WIN - " & quoteID, "40HC")))
    If contType = "" Then Exit Sub
    
    ' Map container type -> Buy and Sell column indices
    Dim buyCol As Integer, sellCol As Integer
    Select Case contType
        Case "20GP":  buyCol = 12: sellCol = 29
        Case "40GP":  buyCol = 13: sellCol = 30
        Case "40HC":  buyCol = 14: sellCol = 31
        Case "45HC":  buyCol = 15: sellCol = 32
        Case "40NOR": buyCol = 16: sellCol = 33
        Case "20RF":  buyCol = 17: sellCol = 34
        Case "40RF":  buyCol = 18: sellCol = 35
        Case Else
            MsgBox "Invalid container type: " & contType & vbCrLf & _
                   "Use: 20GP / 40GP / 40HC / 45HC / 40NOR / 20RF / 40RF", _
                   vbExclamation, "Mark WIN"
            Exit Sub
    End Select
    
    Dim buyRate As Double: buyRate = 0
    Dim sellRate As Double: sellRate = 0
    If IsNumeric(wsQ.Cells(r, buyCol).Value) Then buyRate = CDbl(wsQ.Cells(r, buyCol).Value)
    If IsNumeric(wsQ.Cells(r, sellCol).Value) Then sellRate = CDbl(wsQ.Cells(r, sellCol).Value)
    
    If sellRate = 0 Then
        MsgBox "No selling rate for " & contType & "!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    ' ── Step 4: Ask Qty ──
    Dim qtyInput As String
    qtyInput = InputBox("Quantity (containers)?", "Mark WIN - " & quoteID, "1")
    If qtyInput = "" Then Exit Sub
    Dim qty As Long: qty = CLng(qtyInput)
    If qty < 1 Then qty = 1
    
    ' ── Step 5: Find Active Jobs sheet ──
    Set wsJ = Nothing
    On Error Resume Next
    Set wsJ = ThisWorkbook.Sheets("Active Jobs")
    On Error GoTo ErrHandler
    
    If wsJ Is Nothing Then
        MsgBox "Active Jobs sheet not found!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    
    ' ── Step 6: Update Quotes sheet ──
    wsQ.Cells(r, 36).Value = "WIN"
    wsQ.Cells(r, 36).Interior.Color = RGB(0, 176, 80)
    wsQ.Cells(r, 36).Font.Color = RGB(255, 255, 255)
    wsQ.Cells(r, 36).Font.Bold = True
    wsQ.Cells(r, 38).Value = Now    ' StatusDate
    wsQ.Cells(r, 38).NumberFormat = "dd/mm/yyyy hh:mm"
    wsQ.Cells(r, 39).Value = qty    ' Qty
    wsQ.Cells(r, 42).Value = contType ' ContType
    
    ' ── Step 7: Write to Active Jobs (new 31-col layout) ──
    Dim nextJobRow As Long
    nextJobRow = wsJ.Cells(wsJ.Rows.Count, AJ_COL_CRMID).End(xlUp).Row + 1
    If nextJobRow < ACTIVEJOBS_DATA_START Then nextJobRow = ACTIVEJOBS_DATA_START
    
    Dim profit As Double: profit = (sellRate - buyRate) * qty
    Dim margin As Double: margin = 0
    If sellRate > 0 Then margin = (sellRate - buyRate) / sellRate
    
    ' A: CRM_ID
    wsJ.Cells(nextJobRow, AJ_COL_CRMID).Value = crmID
    ' B: Customer_Type
    wsJ.Cells(nextJobRow, AJ_COL_CUSTTYPE).Value = custType
    ' C: Routing
    If place <> "" And place <> pod Then
        wsJ.Cells(nextJobRow, AJ_COL_ROUTING).Value = pol & "-" & place & " VIA " & pod
    Else
        wsJ.Cells(nextJobRow, AJ_COL_ROUTING).Value = pol & "-" & pod
    End If
    ' H: Carrier
    wsJ.Cells(nextJobRow, AJ_COL_CARRIER).Value = carrier
    ' I: Contract_Type (SOC/COC)
    wsJ.Cells(nextJobRow, AJ_COL_CONTRACT).Value = source
    ' J: Container_Type
    wsJ.Cells(nextJobRow, AJ_COL_CONTTYPE).Value = contType
    ' K: Quantity
    wsJ.Cells(nextJobRow, AJ_COL_QTY).Value = qty
    ' L: Selling_Rate
    wsJ.Cells(nextJobRow, AJ_COL_SELL).Value = sellRate
    wsJ.Cells(nextJobRow, AJ_COL_SELL).NumberFormat = "$#,##0"
    ' M: Buying_Rate
    wsJ.Cells(nextJobRow, AJ_COL_BUY).Value = buyRate
    wsJ.Cells(nextJobRow, AJ_COL_BUY).NumberFormat = "$#,##0"
    ' N: Profit
    wsJ.Cells(nextJobRow, AJ_COL_PROFIT).Value = profit
    wsJ.Cells(nextJobRow, AJ_COL_PROFIT).NumberFormat = "$#,##0"
    If profit > 0 Then
        wsJ.Cells(nextJobRow, AJ_COL_PROFIT).Font.Color = RGB(0, 128, 0)
    ElseIf profit < 0 Then
        wsJ.Cells(nextJobRow, AJ_COL_PROFIT).Font.Color = RGB(192, 0, 0)
    End If
    ' O: Profit_Margin
    wsJ.Cells(nextJobRow, AJ_COL_MARGIN).Value = margin
    wsJ.Cells(nextJobRow, AJ_COL_MARGIN).NumberFormat = "0.0%"
    ' P: Status
    wsJ.Cells(nextJobRow, AJ_COL_STATUS).Value = "Booked"
    ' Y: Created_Date
    wsJ.Cells(nextJobRow, AJ_COL_CREATED).Value = Now
    wsJ.Cells(nextJobRow, AJ_COL_CREATED).NumberFormat = "dd/mm/yyyy hh:mm"
    ' Z: Last_Updated
    wsJ.Cells(nextJobRow, AJ_COL_UPDATED).Value = Now
    wsJ.Cells(nextJobRow, AJ_COL_UPDATED).NumberFormat = "dd/mm/yyyy hh:mm"
    
    ' ── Step 7b: Cost Breakdown — BasicCost_Lookup first, then fallback ──
    Dim sCostBreakdown As String: sCostBreakdown = ""
    Dim noteVal As String: noteVal = UCase(Trim(CStr(wsQ.Cells(r, 8).Value)))
    
    ' ── 7b.1: Try BasicCost_Lookup (Python-generated from Parquet) ──
    Dim sLookupKey As String
    sLookupKey = UCase(pol) & "|" & UCase(pod) & "|" & UCase(place) & "|" & UCase(carrier) & "|" & UCase(contType) & "|" & noteVal
    
    Dim wsBC As Worksheet
    On Error Resume Next
    Set wsBC = ThisWorkbook.Sheets("BasicCost_Lookup")
    On Error GoTo ErrHandler
    
    If Not wsBC Is Nothing Then
        Dim lastRowBC As Long
        lastRowBC = wsBC.Cells(wsBC.Rows.Count, 1).End(xlUp).Row
        Dim rBC As Long
        For rBC = 2 To lastRowBC
            If UCase(CStr(wsBC.Cells(rBC, 1).Value)) = sLookupKey Then
                sCostBreakdown = CStr(wsBC.Cells(rBC, 4).Value)
                Exit For
            End If
        Next rBC
    End If
    
    ' ── 7b.2: Fallback to CostBreakdown module if lookup missed ──
    If sCostBreakdown = "" Then
        On Error Resume Next
        Dim pucVal As Double: pucVal = 0
        Dim wsPUC As Worksheet
        Set wsPUC = ThisWorkbook.Sheets("PUC_Lookup")
        If Not wsPUC Is Nothing Then
            Dim pR As Long
            For pR = 2 To wsPUC.Cells(wsPUC.Rows.Count, 1).End(xlUp).Row
                If UCase(Trim(CStr(wsPUC.Cells(pR, 1).Value))) = UCase(Trim(place)) Then
                    Select Case contType
                        Case "20GP", "20RF": pucVal = Val(wsPUC.Cells(pR, 2).Value)
                        Case "40GP": pucVal = Val(wsPUC.Cells(pR, 3).Value)
                        Case "40HC": pucVal = Val(wsPUC.Cells(pR, 4).Value)
                        Case Else: pucVal = Val(wsPUC.Cells(pR, 3).Value)
                    End Select
                    Exit For
                End If
            Next pR
        End If
        On Error GoTo ErrHandler
        
        Dim whaVal As Double
        whaVal = CostBreakdown.GetWharfage(carrier, pod, contType)
        
        sCostBreakdown = CostBreakdown.BuildCostBreakdown( _
            carrier, source, contType, pol, pod, _
            "", "", _
            buyRate, 0, 39, pucVal, 0, 0, whaVal, 0, CInt(qty))
        
        ' Last resort fallback
        If sCostBreakdown = "" Then
            Dim mkupTotal As Double: mkupTotal = sellRate - buyRate
            sCostBreakdown = "COST: O/F $" & Format(buyRate, "#,##0")
            If mkupTotal > 0 Then sCostBreakdown = sCostBreakdown & " + MARKUP $" & Format(mkupTotal, "#,##0")
        End If
    End If
    
    ' AA: Cost_Breakdown
    wsJ.Cells(nextJobRow, AJ_COL_COST_BKD).Value = sCostBreakdown
    wsJ.Cells(nextJobRow, AJ_COL_COST_BKD).Font.Name = "Consolas"
    wsJ.Cells(nextJobRow, AJ_COL_COST_BKD).Font.Size = 9
    wsJ.Cells(nextJobRow, AJ_COL_COST_BKD).WrapText = True
    
    ' ── Step 8: Booking Email via BookingEmail module ──
    Dim emailContent As String
    emailContent = BookingEmail.BuildBookingEmail( _
        carrier, source, contType, pol, pod, place, _
        "", "", "Actual NAC", customer, CInt(qty), _
        0, "", "", "", "")
    
    Dim mailtoUrl As String
    mailtoUrl = BookingEmail.BuildMailtoLink(emailContent)
    
    ' AB: Request_BKG
    wsJ.Cells(nextJobRow, AJ_COL_REQUEST_BKG).Value = "Request BKG"
    wsJ.Hyperlinks.Add _
        Anchor:=wsJ.Cells(nextJobRow, AJ_COL_REQUEST_BKG), _
        Address:=mailtoUrl, _
        TextToDisplay:="Request BKG"
    wsJ.Cells(nextJobRow, AJ_COL_REQUEST_BKG).Font.Color = RGB(5, 99, 193)
    wsJ.Cells(nextJobRow, AJ_COL_REQUEST_BKG).Font.Bold = True
    wsJ.Cells(nextJobRow, AJ_COL_REQUEST_BKG).Font.Size = 10
    
    ' ── Step 9: Confirm ──
    MsgBox "Quote " & quoteID & " marked WIN!" & vbCrLf & vbCrLf & _
           "CRM_ID: " & crmID & vbCrLf & _
           "Container: " & contType & " | Qty: " & qty & vbCrLf & _
           "Sell: USD " & Format(sellRate, "#,##0") & " | Buy: USD " & Format(buyRate, "#,##0") & vbCrLf & _
           "Profit: USD " & Format(profit, "#,##0") & " (" & Format(margin * 100, "0.0") & "%)" & vbCrLf & _
           "Email link added!", vbInformation, "WIN Confirmed"
    Exit Sub
    
ErrHandler:
    MsgBox "Error in MarkQuoteWin: " & Err.Description, vbCritical, "Error"
End Sub


' ============================================================
'  MARK QUOTE LOST — V13 Ribbon Port
'  Trigger: Ribbon button btnLost
' ============================================================

Public Sub MarkQuoteLost(control As IRibbonControl)
    On Error GoTo ErrHandler
    
    Dim wsQ As Worksheet
    Set wsQ = Nothing
    On Error Resume Next
    Set wsQ = ThisWorkbook.Sheets("Quotes")
    On Error GoTo ErrHandler
    
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Mark LOST"
        Exit Sub
    End If
    
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Please navigate to the Quotes sheet first!", vbExclamation, "Mark LOST"
        Exit Sub
    End If
    
    Dim r As Long: r = Selection.Row
    If r < 2 Then
        MsgBox "Select a quote data row (row 2+)!", vbExclamation, "Mark LOST"
        Exit Sub
    End If
    
    Dim quoteID As String
    quoteID = Trim(CStr(wsQ.Cells(r, 1).Value))
    If quoteID = "" Then
        MsgBox "No quote in this row!", vbExclamation, "Mark LOST"
        Exit Sub
    End If
    
    Dim currentStatus As String
    currentStatus = Trim(CStr(wsQ.Cells(r, 36).Value))
    
    If currentStatus <> "PENDING" Then
        MsgBox "Only PENDING quotes can be marked LOST." & vbCrLf & _
               "Current status: " & currentStatus, vbExclamation, "Mark LOST"
        Exit Sub
    End If
    
    Dim reason As String
    reason = InputBox("Reason for LOST?", "Mark LOST - " & quoteID, "")
    If reason = "" Then Exit Sub
    
    wsQ.Cells(r, 36).Value = "LOST"
    wsQ.Cells(r, 36).Interior.Color = RGB(192, 0, 0)
    wsQ.Cells(r, 36).Font.Color = RGB(255, 255, 255)
    wsQ.Cells(r, 36).Font.Bold = True
    wsQ.Cells(r, 37).Value = reason  ' Remark
    wsQ.Cells(r, 38).Value = Now     ' StatusDate
    wsQ.Cells(r, 38).NumberFormat = "dd/mm/yyyy hh:mm"
    
    MsgBox "Quote " & quoteID & " marked LOST." & vbCrLf & _
           "Reason: " & reason, vbInformation, "LOST Confirmed"
    Exit Sub
    
ErrHandler:
    MsgBox "Error in MarkQuoteLost: " & Err.Description, vbCritical, "Error"
End Sub


' ============================================================
'  CHECK AUTO-EXPIRED — V13 Ribbon Port
'  Trigger: Workbook_Open + Ribbon button btnExpired
'  Logic: If Exp date (col 10) < Today AND Status = PENDING → EXPIRED
' ============================================================

Public Sub CheckAutoLost(control As IRibbonControl)
    Call CheckAutoExpired
End Sub

Public Sub CheckAutoExpired()
    On Error Resume Next
    
    Dim wsQ As Worksheet
    Set wsQ = ThisWorkbook.Sheets("Quotes")
    If wsQ Is Nothing Then Exit Sub
    
    Dim r As Long
    Dim lastRow As Long
    Dim expiredCount As Integer: expiredCount = 0
    
    lastRow = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then Exit Sub
    
    For r = 2 To lastRow
        If Trim(CStr(wsQ.Cells(r, 36).Value)) = "PENDING" Then
            ' Check Exp date (col 10)
            If IsDate(wsQ.Cells(r, 10).Value) Then
                If CDate(wsQ.Cells(r, 10).Value) < Date Then
                    wsQ.Cells(r, 36).Value = "EXPIRED"
                    wsQ.Cells(r, 36).Interior.Color = RGB(128, 128, 128)
                    wsQ.Cells(r, 36).Font.Color = RGB(255, 255, 255)
                    wsQ.Cells(r, 38).Value = Now
                    wsQ.Cells(r, 38).NumberFormat = "dd/mm/yyyy hh:mm"
                    expiredCount = expiredCount + 1
                End If
            End If
        End If
    Next r
    
    If expiredCount > 0 Then
        MsgBox expiredCount & " quote(s) auto-expired (past Exp date).", vbInformation, "Auto-Expire Check"
    End If
    ' Silent if nothing expired (no popup on startup)
End Sub
