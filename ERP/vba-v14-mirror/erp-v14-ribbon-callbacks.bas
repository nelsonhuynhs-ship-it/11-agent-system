Attribute VB_Name = "ERPv14Ribbon"
Option Explicit

' ============================================================
'  ERP V14 — Module 2: Ribbon Callbacks
'  2 Tabs: Pricing (daily) + Operations (reports/tools)
'  All callbacks match CustomUI_v14.xml
' ============================================================

' ============================================================
'  TEST HARNESS — added 2026-04-11 P2
' ============================================================
' When True, success/info MsgBox calls are silenced (logged via Debug.Print).
' Error MsgBox calls (vbExclamation/vbCritical) are NOT affected — they still fire.
' Set via ERPv14Ribbon.SetTestMode(True) from xlwings test harness.
'
' CRITICAL VBA rule: Public/Private variable declarations MUST come BEFORE
' any Sub/Function in the module. This Public declaration is fine here
' because it's still in the declarations section. The actual Sub/Function
' bodies (SetTestMode, SetCustomerForTest, MsgBoxOrSilent) live AFTER all
' module-level declarations — see "TEST HARNESS BODIES" section below.
Public g_TestMode As Boolean
Public g_LastError As String  ' Captures last error for test inspection

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

' Search comboBox text state (for getText callbacks + ClearSearch reset)
Private m_SearchCarrier As String
Private m_SearchPOL As String
Private m_SearchPOD As String
Private m_SearchPlace As String
Private m_SearchExp As String
Private m_SearchNote As String

' Ribbon reference
Public ribbonUI As IRibbonUI

' Bulk QuoteImage override state (used by OnAction_QuoteImageBulk to drive
' OnAction_QuoteImage without re-editing any Quotes sheet rows). When these
' are non-empty, OnAction_QuoteImage substitutes the customer name + output
' path instead of reading row 1's customer / opening _quote_live.html.
' Must be declared in the module-level section (R1: no decls after first Sub).
Private m_BulkCustomerName As String
Private m_BulkOutputPath As String

' Feature 6 — Last-quoted pill: caches formatted label string for lblLastQuoted.
' Updated whenever OnChange_Customer fires and finds an existing quote.
' Declared here (module-level) per gotcha #11: no declarations after first Sub.
Private m_LastQuotedLabel As String

' Exp preset filter constants (Fix 1 — 2026-04-20)
Private Const EXP_PRESET_ACTIVE As String = "Active only"
Private Const EXP_PRESET_WEEK As String = "This week"
Private Const EXP_PRESET_MONTH As String = "This month"
Private Const EXP_PRESET_ALL As String = "All (incl. expired)"
Private m_ExpPreset As String   ' current Exp dropdown selection

' Constants
Private Const DATA_START_ROW As Integer = 2
' Row where Quotes data begins (rows 1-3 = KPI dashboard, row 4 = header)
Private Const QUOTES_DATA_START As Long = 5
Private Const QUOTES_HEADER_ROW As Long = 4
Private Const COL_POL As Integer = 1
Private Const COL_POD As Integer = 2
Private Const COL_PLACE As Integer = 3
Private Const COL_CARRIER As Integer = 4
Private Const COL_COMMODITY As Integer = 5
Private Const COL_EFF As Integer = 6
Private Const COL_EXP As Integer = 7
Private Const COL_NOTE As Integer = 8
Private Const COL_SOURCE As Integer = 9
Private Const COL_20GP As Integer = 10
Private Const COL_40GP As Integer = 11
Private Const COL_40HQ As Integer = 12
Private Const COL_45HQ As Integer = 13
Private Const COL_40NOR As Integer = 14
Private Const COL_20RF As Integer = 15
Private Const COL_40RF As Integer = 16

' ============================================================
'  RIBBON LOAD
' ============================================================
' ComboBox item lists (built on load + after refresh)
Private m_Carriers() As String
Private m_CarrierCount As Long
Private m_POLs() As String
Private m_POLCount As Long
Private m_PODs() As String
Private m_PODCount As Long
Private m_Places() As String
Private m_PlaceCount As Long
Private m_Exps() As String
Private m_ExpCount As Long
Private m_Notes() As String
Private m_NoteCount As Long
Private m_Customers() As String
Private m_CustomerCount As Long

' ============================================================
'  TEST HARNESS BODIES — added 2026-04-11 P2
' ============================================================
' All test helper Sub/Function bodies live here, AFTER every module-level
' Public/Private declaration above. This is required by VBA: once any
' Sub/Function appears in a module, you cannot add more variable
' declarations after it.

Public Sub SetTestMode(enabled As Boolean)
    g_TestMode = enabled
End Sub

' Test-only setter — sets m_Customer without going through the
' IRibbonControl onChange callback path (which xlwings can't synthesize).
Public Sub SetCustomerForTest(s As String)
    m_Customer = s
End Sub

' Test wrapper for QuoteImage — returns "OK:N" or error details.
Public Function TestRunQuoteImage() As String
    g_LastError = ""
    On Error GoTo TestErr
    Call OnAction_QuoteImage(Nothing)
    ' Check g_LastError (set by QuoteImage's own ErrHandler)
    If g_LastError <> "" Then
        TestRunQuoteImage = g_LastError
        Exit Function
    End If
    ' Check if _QuoteImg exists and how many rows
    Dim tmpWs As Worksheet
    On Error Resume Next
    Set tmpWs = ThisWorkbook.Sheets("_QuoteImg")
    On Error GoTo TestErr
    If tmpWs Is Nothing Then
        TestRunQuoteImage = "OK_NO_SHEET"
    Else
        Dim lastRow As Long
        lastRow = tmpWs.Cells(tmpWs.Rows.Count, 1).End(xlUp).Row
        TestRunQuoteImage = "OK:" & lastRow
    End If
    Exit Function
TestErr:
    TestRunQuoteImage = "WRAPPER_ERR:" & Err.Number & ":" & Err.Description
End Function

' Wrapper: replaces MsgBox for success/info prompts when in test mode.
' Used by the 10 wrapped success MsgBox calls in OnAction_* below.
Private Function MsgBoxOrSilent(prompt As String, _
                                 Optional buttons As VbMsgBoxStyle = vbInformation, _
                                 Optional title As String = "ERP v14") As VbMsgBoxResult
    If g_TestMode Then
        Debug.Print "[silenced] " & title & ": " & prompt
        MsgBoxOrSilent = vbOK
        Exit Function
    End If
    MsgBoxOrSilent = MsgBox(prompt, buttons, title)
End Function

' P1 — Clear all module-level state when user switches sheets without
' selecting a row. Called from Workbook_SheetActivate (in ThisWorkbook).
Public Sub ClearRibbonState()
    m_POL = "": m_POD = "": m_Place = "": m_Carrier = ""
    m_Eff = "": m_Exp = "": m_Note = "": m_Source = ""
    m_Buy20GP = 0: m_Buy40GP = 0: m_Buy40HC = 0: m_Buy45HC = 0
    m_Buy40NOR = 0: m_Buy20RF = 0: m_Buy40RF = 0
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0: m_Mar45HC = 0
    m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    m_IsSOC = False: m_SourceRow = 0
    ' Note: m_Customer intentionally NOT cleared so user's typed customer
    ' survives a sheet switch (common workflow: type customer first, then
    ' browse pricing rows).
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
End Sub

' P1 — Refresh ribbon state from a sheet's active cell. Called from
' Workbook_SheetActivate so ribbon doesn't stay stale after tab switch.
Public Sub RefreshRibbonFromSheet(ws As Worksheet)
    On Error Resume Next
    If ws Is Nothing Then Exit Sub
    Dim r As Long: r = ws.Cells(1, 1).Worksheet.Application.ActiveCell.Row
    If r >= 2 Then
        LoadRowToRibbon r
    Else
        ClearRibbonState
    End If
    On Error GoTo 0
End Sub

' P1 — Rebuild combo lists from currently VISIBLE rows only.
' Called after a search combo filter is applied so sibling dropdowns
' (POL/POD/Place) cascade-filter to only the values consistent with
' the current filter (e.g., Carrier=ONE → POL list only shows ONE's POLs).
Public Sub RebuildVisibleComboLists()
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub

    ' Use helper from ERPv14Core to enumerate visible-only unique values
    Dim cCarrier As Collection: Set cCarrier = ERPv14Core.GetUniqueVisibleValues(COL_CARRIER)
    Dim cPOL As Collection: Set cPOL = ERPv14Core.GetUniqueVisibleValues(COL_POL)
    Dim cPOD As Collection: Set cPOD = ERPv14Core.GetUniqueVisibleValues(COL_POD)
    Dim cPlace As Collection: Set cPlace = ERPv14Core.GetUniqueVisibleValues(COL_PLACE)

    ' Refill the module-level arrays the GetItemCount/Label callbacks read from
    m_CarrierCount = cCarrier.Count
    If m_CarrierCount > 0 Then
        ReDim m_Carriers(0 To m_CarrierCount - 1)
        Dim i As Long: i = 0
        Dim v As Variant
        For Each v In cCarrier
            m_Carriers(i) = CStr(v): i = i + 1
        Next v
    End If

    m_POLCount = cPOL.Count
    If m_POLCount > 0 Then
        ReDim m_POLs(0 To m_POLCount - 1)
        i = 0
        For Each v In cPOL
            m_POLs(i) = CStr(v): i = i + 1
        Next v
    End If

    m_PODCount = cPOD.Count
    If m_PODCount > 0 Then
        ReDim m_PODs(0 To m_PODCount - 1)
        i = 0
        For Each v In cPOD
            m_PODs(i) = CStr(v): i = i + 1
        Next v
    End If

    m_PlaceCount = cPlace.Count
    If m_PlaceCount > 0 Then
        ReDim m_Places(0 To m_PlaceCount - 1)
        i = 0
        For Each v In cPlace
            m_Places(i) = CStr(v): i = i + 1
        Next v
    End If

    ' Force ribbon to re-fetch all 4 combo dropdowns
    If Not ribbonUI Is Nothing Then
        ribbonUI.InvalidateControl "cmbCarrier"
        ribbonUI.InvalidateControl "cmbPOL"
        ribbonUI.InvalidateControl "cmbPOD"
        ribbonUI.InvalidateControl "cmbPlace"
    End If
    On Error GoTo 0
End Sub

Private Function FormatShortDate(v As Variant) As String
    On Error Resume Next
    If IsDate(v) Then
        FormatShortDate = Format(CDate(v), "dd-mmm")
    Else
        FormatShortDate = Trim(CStr(v))
    End If
    On Error GoTo 0
End Function

Public Sub RibbonOnLoad(ribbon As IRibbonUI)
    Set ribbonUI = ribbon
    BuildComboLists
    ' Fix 1: default Exp preset to Active only on every workbook open
    m_ExpPreset = EXP_PRESET_ACTIVE
    m_SearchExp = EXP_PRESET_ACTIVE
    ERPv14Core.ApplyQuickSearch
End Sub

' Public invalidator — callable from other modules via Application.Run
Public Sub InvalidateRibbon()
    On Error Resume Next
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub

' Fix 1: Public getter so ERPv14Core.ApplyQuickSearch can read current Exp preset
Public Function GetCurrentExpPreset() As String
    If Len(m_ExpPreset) = 0 Then m_ExpPreset = EXP_PRESET_ACTIVE
    GetCurrentExpPreset = m_ExpPreset
End Function

' Public BuildComboLists alias (for modules that need to rebuild after data refresh)
Public Sub BuildComboListsPublic()
    BuildComboLists
End Sub

' Build unique value lists for comboBox dropdowns
Private Sub BuildComboLists()
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Dim lr As Long: lr = ws.Cells(ws.Rows.Count, COL_POL).End(xlUp).Row
    If lr < DATA_START_ROW Then Exit Sub

    ' Use Dictionary for unique values
    Dim dCarrier As Object: Set dCarrier = CreateObject("Scripting.Dictionary")
    Dim dPOL As Object: Set dPOL = CreateObject("Scripting.Dictionary")
    Dim dPOD As Object: Set dPOD = CreateObject("Scripting.Dictionary")
    Dim dPlace As Object: Set dPlace = CreateObject("Scripting.Dictionary")
    Dim dExp As Object: Set dExp = CreateObject("Scripting.Dictionary")
    Dim dNote As Object: Set dNote = CreateObject("Scripting.Dictionary")

    Dim r As Long, v As String
    For r = DATA_START_ROW To lr
        v = UCase(Trim(ws.Cells(r, COL_CARRIER).Value))
        If v <> "" And Not dCarrier.Exists(v) Then dCarrier.Add v, v
        v = UCase(Trim(ws.Cells(r, COL_POL).Value))
        If v <> "" And Not dPOL.Exists(v) Then dPOL.Add v, v
        v = UCase(Trim(ws.Cells(r, COL_POD).Value))
        If v <> "" And Not dPOD.Exists(v) Then dPOD.Add v, v
        v = Trim(ws.Cells(r, COL_PLACE).Value)
        If v <> "" And Not dPlace.Exists(v) Then dPlace.Add v, v
        If IsDate(ws.Cells(r, COL_EXP).Value) Then
            v = Format(ws.Cells(r, COL_EXP).Value, "dd-mmm")
            If v <> "" And Not dExp.Exists(v) Then dExp.Add v, v
        Else
            v = Trim(ws.Cells(r, COL_EXP).Value)
            If v <> "" And Not dExp.Exists(v) Then dExp.Add v, v
        End If
        v = Trim(ws.Cells(r, COL_NOTE).Value)
        If v <> "" And Not dNote.Exists(v) Then dNote.Add v, v
    Next r

    ' Convert to arrays
    m_CarrierCount = dCarrier.Count
    If m_CarrierCount > 0 Then m_Carriers = dCarrier.Keys
    m_POLCount = dPOL.Count
    If m_POLCount > 0 Then m_POLs = dPOL.Keys
    m_PODCount = dPOD.Count
    If m_PODCount > 0 Then m_PODs = dPOD.Keys
    m_PlaceCount = dPlace.Count
    If m_PlaceCount > 0 Then m_Places = dPlace.Keys
    m_ExpCount = dExp.Count
    If m_ExpCount > 0 Then m_Exps = dExp.Keys
    m_NoteCount = dNote.Count
    If m_NoteCount > 0 Then m_Notes = dNote.Keys

    ' Customer list from CRM sheet
    Dim wsCRM As Worksheet
    Set wsCRM = Nothing
    Set wsCRM = ERPv14Core.FindSheet("CRM")
    If Not wsCRM Is Nothing Then
        Dim dCust As Object: Set dCust = CreateObject("Scripting.Dictionary")
        Dim clr As Long: clr = wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
        For r = 2 To clr
            v = Trim(wsCRM.Cells(r, 2).Value)
            If v <> "" And Not dCust.Exists(v) Then dCust.Add v, v
        Next r
        m_CustomerCount = dCust.Count
        If m_CustomerCount > 0 Then m_Customers = dCust.Keys
    End If
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — Carrier
' ============================================================
Public Sub GetItemCount_Carrier(control As IRibbonControl, ByRef count As Variant)
    count = m_CarrierCount
End Sub
Public Sub GetItemLabel_Carrier(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_CarrierCount Then label = m_Carriers(index) Else label = ""
    On Error GoTo 0
End Sub
Public Sub OnChange_SearchCarrier(control As IRibbonControl, text As String)
    On Error Resume Next
    m_SearchCarrier = text
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Application.EnableEvents = False
    If Trim(text) = "" Then
        ERPv14Core.RestorePlaceholder COL_CARRIER
    Else
        ws.Cells(1, COL_CARRIER).Value = text
        ws.Cells(1, COL_CARRIER).Font.Color = RGB(154, 52, 18)
        ws.Cells(1, COL_CARRIER).Font.Italic = False
    End If
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch
    RebuildVisibleComboLists  ' P1 cascade
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — POL
' ============================================================
Public Sub GetItemCount_POL(control As IRibbonControl, ByRef count As Variant)
    count = m_POLCount
End Sub
Public Sub GetItemLabel_POL(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_POLCount Then label = m_POLs(index) Else label = ""
    On Error GoTo 0
End Sub
Public Sub OnChange_SearchPOL(control As IRibbonControl, text As String)
    On Error Resume Next
    m_SearchPOL = text
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Application.EnableEvents = False
    If Trim(text) = "" Then
        ERPv14Core.RestorePlaceholder COL_POL
    Else
        ws.Cells(1, COL_POL).Value = text
        ws.Cells(1, COL_POL).Font.Color = RGB(154, 52, 18)
        ws.Cells(1, COL_POL).Font.Italic = False
    End If
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch
    RebuildVisibleComboLists  ' P1 cascade
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — POD
' ============================================================
Public Sub GetItemCount_POD(control As IRibbonControl, ByRef count As Variant)
    count = m_PODCount
End Sub
Public Sub GetItemLabel_POD(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_PODCount Then label = m_PODs(index) Else label = ""
    On Error GoTo 0
End Sub
Public Sub OnChange_SearchPOD(control As IRibbonControl, text As String)
    On Error Resume Next
    m_SearchPOD = text
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Application.EnableEvents = False
    If Trim(text) = "" Then
        ERPv14Core.RestorePlaceholder COL_POD
    Else
        ws.Cells(1, COL_POD).Value = text
        ws.Cells(1, COL_POD).Font.Color = RGB(154, 52, 18)
        ws.Cells(1, COL_POD).Font.Italic = False
    End If
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch
    RebuildVisibleComboLists  ' P1 cascade
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — Place
' ============================================================
Public Sub GetItemCount_Place(control As IRibbonControl, ByRef count As Variant)
    count = m_PlaceCount
End Sub
Public Sub GetItemLabel_Place(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_PlaceCount Then label = m_Places(index) Else label = ""
    On Error GoTo 0
End Sub
Public Sub OnChange_SearchPlace(control As IRibbonControl, text As String)
    On Error Resume Next
    m_SearchPlace = text
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Application.EnableEvents = False
    If Trim(text) = "" Then
        ERPv14Core.RestorePlaceholder COL_PLACE
    Else
        ws.Cells(1, COL_PLACE).Value = text
        ws.Cells(1, COL_PLACE).Font.Color = RGB(154, 52, 18)
        ws.Cells(1, COL_PLACE).Font.Italic = False
    End If
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch
    RebuildVisibleComboLists  ' P1 cascade
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — Exp (Fix 1: 4-preset dropdown, 2026-04-20)
'  Returns 4 hard-coded preset labels — no dynamic date list needed.
' ============================================================
Public Sub GetItemCount_Exp(control As IRibbonControl, ByRef count As Variant)
    count = 4
End Sub
Public Sub GetItemLabel_Exp(control As IRibbonControl, index As Long, ByRef label As Variant)
    Select Case index
        Case 0: label = EXP_PRESET_ACTIVE
        Case 1: label = EXP_PRESET_WEEK
        Case 2: label = EXP_PRESET_MONTH
        Case 3: label = EXP_PRESET_ALL
        Case Else: label = ""
    End Select
End Sub
Public Sub OnChange_SearchExp(control As IRibbonControl, text As String)
    On Error Resume Next
    ' Store the preset selection (not raw text in col 7)
    Dim sel As String: sel = Trim(text)
    If sel = EXP_PRESET_ACTIVE Or sel = EXP_PRESET_WEEK Or _
       sel = EXP_PRESET_MONTH Or sel = EXP_PRESET_ALL Then
        m_ExpPreset = sel
    ElseIf sel = "" Then
        m_ExpPreset = EXP_PRESET_ACTIVE
    Else
        ' User typed freeform — treat as "Active only" to avoid confusion
        m_ExpPreset = EXP_PRESET_ACTIVE
    End If
    m_SearchExp = m_ExpPreset
    ' Clear col 7 row 1 so ApplyQuickSearch skips the text-match path for Exp
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If Not ws Is Nothing Then
        Application.EnableEvents = False
        ERPv14Core.RestorePlaceholder COL_EXP
        Application.EnableEvents = True
    End If
    ERPv14Core.ApplyQuickSearch
    On Error GoTo 0
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — Note
' ============================================================
Public Sub GetItemCount_Note(control As IRibbonControl, ByRef count As Variant)
    count = m_NoteCount
End Sub
Public Sub GetItemLabel_Note(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_NoteCount Then label = m_Notes(index) Else label = ""
    On Error GoTo 0
End Sub
Public Sub OnChange_SearchNote(control As IRibbonControl, text As String)
    On Error Resume Next
    m_SearchNote = text
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    Application.EnableEvents = False
    If Trim(text) = "" Then
        ERPv14Core.RestorePlaceholder COL_NOTE
    Else
        ws.Cells(1, COL_NOTE).Value = text
        ws.Cells(1, COL_NOTE).Font.Color = RGB(154, 52, 18)
        ws.Cells(1, COL_NOTE).Font.Italic = False
    End If
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch
    On Error GoTo 0
End Sub

' ============================================================
'  SEARCH COMBOBOX — getText callbacks (clear display on Invalidate)
' ============================================================
Public Sub GetText_SearchCarrier(control As IRibbonControl, ByRef text As Variant)
    text = m_SearchCarrier
End Sub
Public Sub GetText_SearchPOL(control As IRibbonControl, ByRef text As Variant)
    text = m_SearchPOL
End Sub
Public Sub GetText_SearchPOD(control As IRibbonControl, ByRef text As Variant)
    text = m_SearchPOD
End Sub
Public Sub GetText_SearchPlace(control As IRibbonControl, ByRef text As Variant)
    text = m_SearchPlace
End Sub
Public Sub GetText_SearchExp(control As IRibbonControl, ByRef text As Variant)
    ' Return current preset label so ribbon displays selection after Invalidate
    If Len(m_ExpPreset) = 0 Then m_ExpPreset = EXP_PRESET_ACTIVE
    text = m_ExpPreset
End Sub
Public Sub GetText_SearchNote(control As IRibbonControl, ByRef text As Variant)
    text = m_SearchNote
End Sub

' ============================================================
'  COMBOBOX CALLBACKS — Customer (from CRM)
' ============================================================
Public Sub GetItemCount_Customer(control As IRibbonControl, ByRef count As Variant)
    count = m_CustomerCount
End Sub
Public Sub GetItemLabel_Customer(control As IRibbonControl, index As Long, ByRef label As Variant)
    On Error Resume Next
    If index >= 0 And index < m_CustomerCount Then label = m_Customers(index) Else label = ""
    On Error GoTo 0
End Sub

' ============================================================
'  HIGHLIGHT BEST PRICE — Per carrier cheapest route
' ============================================================
Public Sub OnAction_HighlightBest(control As IRibbonControl)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub

    Dim lr As Long: lr = ws.Cells(ws.Rows.Count, COL_POL).End(xlUp).Row
    If lr < DATA_START_ROW Then Exit Sub

    Application.ScreenUpdating = False

    ' Detect active container column (first visible price col)
    Dim priceCol As Integer: priceCol = COL_20GP
    Dim pc As Integer
    For pc = COL_20GP To COL_40RF
        If Not ws.Columns(pc).Hidden Then
            priceCol = pc
            Exit For
        End If
    Next pc

    ' Clear previous highlights on price columns
    Dim r As Long
    For r = DATA_START_ROW To lr
        Dim c As Integer
        For c = COL_20GP To COL_40RF
            ws.Cells(r, c).Interior.ColorIndex = xlNone
        Next c
    Next r

    ' Build per-carrier min price using Dictionary
    ' Key = carrier, Value = min price for visible rows
    Dim dMin As Object: Set dMin = CreateObject("Scripting.Dictionary")
    Dim dMinRow As Object: Set dMinRow = CreateObject("Scripting.Dictionary")

    For r = DATA_START_ROW To lr
        If Not ws.Rows(r).Hidden Then
            Dim carrier As String: carrier = UCase(Trim(ws.Cells(r, COL_CARRIER).Value))
            Dim price As Double: price = 0
            If IsNumeric(ws.Cells(r, priceCol).Value) Then price = CDbl(ws.Cells(r, priceCol).Value)
            If price > 0 Then
                If Not dMin.Exists(carrier) Then
                    dMin.Add carrier, price
                    dMinRow.Add carrier, r
                ElseIf price < dMin(carrier) Then
                    dMin(carrier) = price
                    dMinRow(carrier) = r
                End If
            End If
        End If
    Next r

    ' Apply green highlight to cheapest row per carrier
    Dim keys As Variant: keys = dMinRow.Keys
    Dim i As Long
    For i = 0 To dMinRow.Count - 1
        Dim bestRow As Long: bestRow = dMinRow(keys(i))
        For c = COL_20GP To COL_40RF
            If Not ws.Columns(c).Hidden Then
                If ws.Cells(bestRow, c).Value <> "" Then
                    ws.Cells(bestRow, c).Interior.Color = RGB(220, 252, 231)  ' light green
                End If
            End If
        Next c
    Next i

    Application.ScreenUpdating = True
    On Error GoTo 0
End Sub

' ============================================================
'  LOAD ROW TO RIBBON (called from Sheet1 SelectionChange)
' ============================================================
Public Sub LoadRowToRibbon(targetRow As Long)
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    If targetRow < DATA_START_ROW Then Exit Sub
    If IsEmpty(ws.Cells(targetRow, COL_POL).Value) Then Exit Sub

    m_POL = ERPv14Core.SS(ws.Cells(targetRow, COL_POL).Value)
    m_POD = ERPv14Core.SS(ws.Cells(targetRow, COL_POD).Value)
    m_Place = ERPv14Core.SS(ws.Cells(targetRow, COL_PLACE).Value)
    m_Carrier = ERPv14Core.SS(ws.Cells(targetRow, COL_CARRIER).Value)
    m_Eff = FormatShortDate(ws.Cells(targetRow, COL_EFF).Value)
    m_Exp = FormatShortDate(ws.Cells(targetRow, COL_EXP).Value)
    m_Note = ERPv14Core.SS(ws.Cells(targetRow, COL_NOTE).Value)
    m_Source = ERPv14Core.SS(ws.Cells(targetRow, COL_SOURCE).Value)
    m_SourceRow = targetRow

    ' SOC detection
    m_IsSOC = (InStr(UCase(m_Note), "SOC") > 0) Or (InStr(UCase(m_Source), "SOC") > 0)

    ' Buy prices
    m_Buy20GP = 0: m_Buy40GP = 0: m_Buy40HC = 0: m_Buy45HC = 0: m_Buy40NOR = 0: m_Buy20RF = 0: m_Buy40RF = 0
    
    If InStr(1, ws.Name, "Reefer", vbTextCompare) > 0 Then
        ' Reefer sheet mapping: cols 10, 11
        m_Buy20RF = ERPv14Core.SL(ws.Cells(targetRow, 10).Value)
        m_Buy40RF = ERPv14Core.SL(ws.Cells(targetRow, 11).Value)
    Else
        ' Dry sheet mapping: cols 10 -> 14
        m_Buy20GP = ERPv14Core.SL(ws.Cells(targetRow, COL_20GP).Value)
        m_Buy40GP = ERPv14Core.SL(ws.Cells(targetRow, COL_40GP).Value)
        m_Buy40HC = ERPv14Core.SL(ws.Cells(targetRow, COL_40HQ).Value)
        m_Buy45HC = ERPv14Core.SL(ws.Cells(targetRow, COL_45HQ).Value)
        m_Buy40NOR = ERPv14Core.SL(ws.Cells(targetRow, COL_40NOR).Value)
    End If

    ' Load carrier markup
    LoadMarkupForCarrier m_Carrier

    ' PUC lookup (SOC only)
    If m_IsSOC Then
        LookupPUC m_Place
    Else
        m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    End If

    ' CRITICAL: Invalidate ribbon to refresh all GetLabel/GetText callbacks
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub

' ============================================================
'  MARKUP STORE — Load/Save
' ============================================================
Private Sub LoadMarkupForCarrier(cn As String)
    ' P5 — keyed by (Carrier, Lane). Falls back to "*" default row if no
    ' exact lane match. Lane is computed from m_POD via ERPv14Core.GetLaneFromPOD.
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0
    m_Mar45HC = 0: m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)
    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim foundExact As Long: foundExact = 0
    Dim foundDefault As Long: foundDefault = 0
    Dim r As Long
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            Dim rowLane As String
            rowLane = UCase(Trim(wsM.Cells(r, 2).Value))
            If rowLane = lane Then
                foundExact = r
                Exit For
            ElseIf rowLane = "*" Or Len(rowLane) = 0 Then
                foundDefault = r  ' keep scanning for exact lane match
            End If
        End If
    Next r

    Dim useRow As Long
    If foundExact > 0 Then
        useRow = foundExact
    ElseIf foundDefault > 0 Then
        useRow = foundDefault
    Else
        Exit Sub
    End If

    ' Columns shifted +1 because Lane was inserted at col 2
    m_Mar20GP = ERPv14Core.SL(wsM.Cells(useRow, 3).Value)
    m_Mar40GP = ERPv14Core.SL(wsM.Cells(useRow, 4).Value)
    m_Mar40HC = ERPv14Core.SL(wsM.Cells(useRow, 5).Value)
    m_Mar45HC = ERPv14Core.SL(wsM.Cells(useRow, 6).Value)
    m_Mar40NOR = ERPv14Core.SL(wsM.Cells(useRow, 7).Value)
    m_Mar20RF = ERPv14Core.SL(wsM.Cells(useRow, 8).Value)
    m_Mar40RF = ERPv14Core.SL(wsM.Cells(useRow, 9).Value)
End Sub

Private Sub SaveMarkupForCarrier(cn As String)
    ' P5 — keyed by (Carrier, Lane). Creates new row if no exact match.
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)
    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim r As Long, found As Long: found = 0
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) _
           And UCase(Trim(wsM.Cells(r, 2).Value)) = lane Then
            found = r
            Exit For
        End If
    Next r
    If found = 0 Then
        found = lastRow + 1
        wsM.Cells(found, 1).Value = cn
        wsM.Cells(found, 2).Value = lane
    End If

    ' Columns shifted +1 because Lane is at col 2
    wsM.Cells(found, 3).Value = m_Mar20GP
    wsM.Cells(found, 4).Value = m_Mar40GP
    wsM.Cells(found, 5).Value = m_Mar40HC
    wsM.Cells(found, 6).Value = m_Mar45HC
    wsM.Cells(found, 7).Value = m_Mar40NOR
    wsM.Cells(found, 8).Value = m_Mar20RF
    wsM.Cells(found, 9).Value = m_Mar40RF
End Sub

' ============================================================
'  PUC LOOKUP
' ============================================================
Private Sub LookupPUC(placeName As String)
    ' P3+P15 — Three-pass: alias expand → exact → fuzzy substring.
    ' Pass 0 handles code↔city mismatches: LAX/LGB → LOS ANGELES, NYC → NEW YORK, etc.
    m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    Dim wsPUC As Worksheet
    On Error Resume Next
    Set wsPUC = ThisWorkbook.Sheets("PUC_Lookup")
    On Error GoTo 0
    If wsPUC Is Nothing Or placeName = "" Then Exit Sub

    Dim target As String: target = UCase(Trim(placeName))

    ' Pass 0: alias expand — map port codes to PUC city names
    Dim alias As String: alias = ""
    If target = "LAX/LGB" Or target = "LAX-LGB" Or target = "LAX" Or target = "LGB" Or target = "LONG BEACH" Then alias = "LOS ANGELES"
    If target = "NYC" Or target = "NEWARK" Or target = "NEW YORK/NEW JERSEY" Then alias = "NEW YORK"
    If target = "SAV" Then alias = "SAVANNAH"
    If target = "CHS" Then alias = "CHARLESTON"
    If target = "HOU" Then alias = "HOUSTON"
    If target = "MIA" Then alias = "MIAMI"
    If target = "ORF" Or target = "NFK" Then alias = "NORFOLK"
    If target = "SEA" Then alias = "SEATTLE"
    If target = "MOB" Then alias = "MOBILE"
    If target = "MEM" Then alias = "MEMPHIS"
    If target = "ATL" Then alias = "ATLANTA"
    If target = "DAL" Or target = "DFW" Then alias = "DALLAS"
    If target = "CHI" Then alias = "CHICAGO"
    If target = "PDX" Then alias = "PORTLAND"
    If target = "TAC" Then alias = "TACOMA"
    If target = "OAK" Then alias = "OAKLAND"
    If target = "BOS" Then alias = "BOSTON"
    If target = "JAX" Then alias = "JACKSONVILLE"
    If alias <> "" Then target = alias
    Dim lastRow As Long: lastRow = wsPUC.Cells(wsPUC.Rows.Count, 1).End(xlUp).Row
    Dim pr As Long, rowPlace As String

    ' Pass 1: exact match
    For pr = 2 To lastRow
        rowPlace = UCase(Trim(wsPUC.Cells(pr, 1).Value))
        If Len(rowPlace) > 0 And rowPlace = target Then
            m_PUC20 = ERPv14Core.SL(wsPUC.Cells(pr, 2).Value)
            m_PUC40 = ERPv14Core.SL(wsPUC.Cells(pr, 3).Value)
            m_PUC40HC = ERPv14Core.SL(wsPUC.Cells(pr, 4).Value)
            Exit Sub
        End If
    Next pr

    ' Pass 2: bidirectional substring (handles "HO CHI MINH CITY" vs "HOCHIM")
    For pr = 2 To lastRow
        rowPlace = UCase(Trim(wsPUC.Cells(pr, 1).Value))
        If Len(rowPlace) >= 4 Then
            If InStr(target, rowPlace) > 0 Or InStr(rowPlace, target) > 0 Then
                m_PUC20 = ERPv14Core.SL(wsPUC.Cells(pr, 2).Value)
                m_PUC40 = ERPv14Core.SL(wsPUC.Cells(pr, 3).Value)
                m_PUC40HC = ERPv14Core.SL(wsPUC.Cells(pr, 4).Value)
                Debug.Print "[PUC fuzzy] " & placeName & " -> " & wsPUC.Cells(pr, 1).Value
                Exit Sub
            End If
        End If
    Next pr

    Debug.Print "[PUC] No match for: " & placeName
End Sub

' ============================================================
'  TAB 1: PRICING — Route Info Labels
' ============================================================
Public Sub GetLabel_Carrier(control As IRibbonControl, ByRef label As Variant)
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

Public Sub GetLabel_Dates(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Eff <> "" Then label = m_Eff & " - " & m_Exp Else label = ""
    On Error GoTo 0
End Sub

Public Sub GetLabel_Note(control As IRibbonControl, ByRef label As Variant)
    ' Note label removed from ribbon v15 layout (SOC info in carrier label + PUCInfo)
    ' Kept for backward compatibility — returns empty
    label = ""
End Sub

' ============================================================
'  TAB 1: PRICING — Buy Rate (read-only getText)
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
'  TAB 1: PRICING — Margin (getText + onChange)
' ============================================================
Public Sub GetText_Mar20GP(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar20GP <> 0 Then text = CStr(m_Mar20GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40GP(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40GP <> 0 Then text = CStr(m_Mar40GP) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar40HC(control As IRibbonControl, ByRef text As Variant)
    On Error Resume Next: If m_Mar40HC <> 0 Then text = CStr(m_Mar40HC) Else text = "": On Error GoTo 0
End Sub
Public Sub GetText_Mar45HC(control As IRibbonControl, ByRef text As Variant)
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

Public Sub OnChange_Mar20GP(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar20GP = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar40GP(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40GP = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar40HC(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40HC = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar45HC(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar45HC = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar40NOR(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40NOR = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar20RF(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar20RF = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub
Public Sub OnChange_Mar40RF(control As IRibbonControl, text As String)
    On Error Resume Next: m_Mar40RF = ERPv14Core.SL(text): SaveMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub

Public Sub OnChange_Customer(control As IRibbonControl, text As String)
    ' P3 — soft validation against CRM sheet. Status bar warns on typo,
    ' but does NOT block quote generation (Nelson can enter new customers).
    ' F6 — also refreshes m_LastQuotedLabel + invalidates lblLastQuoted.
    On Error Resume Next
    m_Customer = Trim(text)
    If Len(m_Customer) = 0 Then
        Application.StatusBar = False
        m_LastQuotedLabel = ""
        If Not ribbonUI Is Nothing Then ribbonUI.InvalidateControl "lblLastQuoted"
        Exit Sub
    End If

    Dim wsCRM As Worksheet
    Set wsCRM = ERPv14Core.FindSheet("CRM")
    If wsCRM Is Nothing Then
        Application.StatusBar = False
        GoTo RefreshLastQuoted
    End If

    Dim found As Boolean: found = False
    Dim lastRow As Long: lastRow = wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
    Dim r As Long
    For r = 2 To lastRow
        If UCase(Trim(wsCRM.Cells(r, 2).Value)) = UCase(m_Customer) Then
            found = True
            Exit For
        End If
    Next r

    If found Then
        Application.StatusBar = "Customer OK: " & m_Customer
    Else
        Application.StatusBar = "WARN: '" & m_Customer & "' not in CRM (typo? new customer?)"
    End If

RefreshLastQuoted:
    ' Feature 6 — scan Quotes sheet for most recent quote for this customer.
    ' Build label: "Last: 14APR-734 · HCM→LAX · $2,327 · PENDING"
    m_LastQuotedLabel = BuildLastQuotedLabel(m_Customer)
    If Not ribbonUI Is Nothing Then ribbonUI.InvalidateControl "lblLastQuoted"
    On Error GoTo 0
End Sub

' Feature 6 — Helper: scan Quotes sheet, find most recent row for customer,
' return formatted pill string. Returns "(no quotes yet)" when nothing found.
' Private because only called from OnChange_Customer + GetLabel_LastQuoted.
Private Function BuildLastQuotedLabel(custName As String) As String
    On Error Resume Next
    BuildLastQuotedLabel = "(no quotes yet)"
    If Len(Trim(custName)) = 0 Then Exit Function

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then Exit Function

    Dim lr As Long: lr = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row
    If lr < QUOTES_DATA_START Then Exit Function

    ' Scan all rows, find MAX Date (col 2) for matching customer (col 3).
    Dim bestRow As Long: bestRow = 0
    Dim bestDate As Date: bestDate = #1/1/2000#
    Dim qr As Long
    For qr = QUOTES_DATA_START To lr
        If UCase(Trim(CStr(wsQ.Cells(qr, 3).Value))) = UCase(Trim(custName)) Then
            If IsDate(wsQ.Cells(qr, 2).Value) Then
                Dim qDate As Date: qDate = CDate(wsQ.Cells(qr, 2).Value)
                If qDate > bestDate Then
                    bestDate = qDate
                    bestRow = qr
                End If
            End If
        End If
    Next qr

    If bestRow = 0 Then Exit Function

    Dim qid As String: qid = Trim(CStr(wsQ.Cells(bestRow, 1).Value))
    Dim qPOL As String: qPOL = Trim(CStr(wsQ.Cells(bestRow, 5).Value))
    Dim qPOD As String: qPOD = Trim(CStr(wsQ.Cells(bestRow, 6).Value))
    Dim qStatus As String: qStatus = Trim(CStr(wsQ.Cells(bestRow, 36).Value))

    ' Pick first non-zero sell price across the 7 container types
    Dim sellCols As Variant: sellCols = Array(29, 30, 31, 32, 33, 34, 35)
    Dim bestSell As Double: bestSell = 0
    Dim sc As Variant
    For Each sc In sellCols
        If IsNumeric(wsQ.Cells(bestRow, sc).Value) Then
            Dim sv As Double: sv = CDbl(wsQ.Cells(bestRow, sc).Value)
            If sv > 0 And bestSell = 0 Then bestSell = sv
        End If
    Next sc

    ' Format: "Last: 14APR-734 · HCM→LAX · $2,327 · PENDING"
    Dim priceStr As String
    If bestSell > 0 Then
        priceStr = " $" & Format(bestSell, "#,##0")
    Else
        priceStr = ""
    End If

    BuildLastQuotedLabel = "Last: " & qid & " " & ChrW(183) & " " & _
                           qPOL & ChrW(8594) & qPOD & " " & ChrW(183) & _
                           priceStr & " " & ChrW(183) & " " & qStatus
    On Error GoTo 0
End Function

' Feature 6 — Last Quoted pill label callback.
' Ribbon fetches this after InvalidateControl "lblLastQuoted" fires from OnChange_Customer.
' Returns m_LastQuotedLabel which was set by BuildLastQuotedLabel scan.
Public Sub GetLabel_LastQuoted(control As IRibbonControl, ByRef returnedVal As Variant)
    On Error Resume Next
    If Len(m_LastQuotedLabel) > 0 Then
        returnedVal = m_LastQuotedLabel
    Else
        returnedVal = ""
    End If
    On Error GoTo 0
End Sub

' P3 — Apply default margin button: re-load saved markup for current carrier
' so Nelson skips re-typing all 7 container margins for repeat quotes.
Public Sub OnAction_ApplyDefaultMargin(Optional control As IRibbonControl = Nothing)
    If Len(m_Carrier) = 0 Then
        MsgBox "Click a data row first to pick a carrier.", vbExclamation, "Apply Default"
        Exit Sub
    End If
    LoadMarkupForCarrier m_Carrier
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    Application.StatusBar = "Loaded default margin for " & m_Carrier
End Sub

' ============================================================
'  TAB 1: PRICING — PUC Labels (SOC only)
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

' Merged PUC info — single line for new ribbon layout
Public Sub GetLabel_PUCInfo(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_IsSOC And (m_PUC20 > 0 Or m_PUC40 > 0) Then
        label = "PUC: $" & Format(m_PUC20, "#,##0") & " / $" & Format(m_PUC40, "#,##0")
        If m_PUC40HC > 0 And m_PUC40HC <> m_PUC40 Then
            label = label & " / HC $" & Format(m_PUC40HC, "#,##0")
        End If
    ElseIf m_IsSOC Then
        label = "PUC: --"
    Else
        label = ""
    End If
    On Error GoTo 0
End Sub

' ============================================================
'  TAB 1: PRICING — Sell Rate Labels (Buy + Margin + PUC)
' ============================================================
Public Sub GetLabel_Sell20GP(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy20GP > 0 Then label = "20GP = " & ERPv14Core.FmtPrice(m_Buy20GP + m_Mar20GP + m_PUC20) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40GP(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40GP > 0 And m_Buy40GP <> m_Buy40HC Then
        label = "40GP = " & ERPv14Core.FmtPrice(m_Buy40GP + m_Mar40GP + m_PUC40)
    ElseIf m_Buy40GP > 0 Then
        label = "40' = " & ERPv14Core.FmtPrice(m_Buy40GP + m_Mar40GP + m_PUC40)
    Else: label = "": End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40HC(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40HC > 0 And m_Buy40HC <> m_Buy40GP Then
        label = "40HC = " & ERPv14Core.FmtPrice(m_Buy40HC + m_Mar40HC + m_PUC40HC)
    Else: label = "": End If
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell45HC(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy45HC > 0 Then label = "45HC = " & ERPv14Core.FmtPrice(m_Buy45HC + m_Mar45HC) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40NOR(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40NOR > 0 Then label = "40NOR = " & ERPv14Core.FmtPrice(m_Buy40NOR + m_Mar40NOR) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell20RF(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy20RF > 0 Then label = "20RF = " & ERPv14Core.FmtPrice(m_Buy20RF + m_Mar20RF) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Sell40RF(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    If m_Buy40RF > 0 Then label = "40RF = " & ERPv14Core.FmtPrice(m_Buy40RF + m_Mar40RF) Else label = ""
    On Error GoTo 0
End Sub
Public Sub GetLabel_Profit(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    Dim profit As Long
    profit = m_Mar20GP + m_Mar40GP + m_Mar40HC + m_Mar45HC + m_Mar40NOR + m_Mar20RF + m_Mar40RF
    If profit > 0 Then label = "Profit: " & ERPv14Core.FmtPrice(profit) Else label = "Profit: --"
    On Error GoTo 0
End Sub

' ============================================================
'  TAB 1: PRICING — Generate Quote (ribbon button)
' ============================================================
Public Sub OnAction_GenerateQuote(Optional control As IRibbonControl = Nothing)
    On Error Resume Next
    If m_Customer = "" Then
        MsgBox "Please enter Customer name!", vbExclamation, "Quote Builder v14"
        Exit Sub
    End If
    If m_Carrier = "" Then
        MsgBox "Please click a data row first!", vbExclamation, "Quote Builder v14"
        Exit Sub
    End If

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Quote Builder v14"
        Exit Sub
    End If

    ' Ensure headers exist at QUOTES_HEADER_ROW (row 4 — below KPI rows 1-3)
    If IsEmpty(wsQ.Cells(QUOTES_HEADER_ROW, 1).Value) Then
        Dim h As Variant
        h = Array("QuoteID", "Date", "Customer", "Carrier", "POL", "POD", _
                  "Place", "Via", "Eff", "Exp", "Source", _
                  "Buy_20GP", "Buy_40GP", "Buy_40HC", "Buy_45HC", "Buy_40NOR", "Buy_20RF", "Buy_40RF", _
                  "Mar_20GP", "Mar_40GP", "Mar_40HC", "Mar_45HC", "Mar_40NOR", "Mar_20RF", "Mar_40RF", _
                  "PUC_20", "PUC_40", "PUC_40HC", _
                  "Sell_20GP", "Sell_40GP", "Sell_40HC", "Sell_45HC", "Sell_40NOR", "Sell_20RF", "Sell_40RF", _
                  "Status", "Remark", "StatusDate")
        Dim hi As Integer
        For hi = 0 To UBound(h): wsQ.Cells(QUOTES_HEADER_ROW, hi + 1).Value = h(hi): Next hi
        wsQ.Range("A" & QUOTES_HEADER_ROW & ":AL" & QUOTES_HEADER_ROW).Font.Bold = True
    End If

    ' Feature 2 — Container picker: build default CSV from available buy rates,
    ' then ask Nelson to edit. Only columns in the CSV will be filled.
    Dim defaultCont As String: defaultCont = ""
    If m_Buy20GP > 0 Then defaultCont = defaultCont & "20GP,"
    If m_Buy40GP > 0 Then defaultCont = defaultCont & "40GP,"
    If m_Buy40HC > 0 Then defaultCont = defaultCont & "40HC,"
    If m_Buy45HC > 0 Then defaultCont = defaultCont & "45HC,"
    If m_Buy40NOR > 0 Then defaultCont = defaultCont & "40NOR,"
    If m_Buy20RF > 0 Then defaultCont = defaultCont & "20RF,"
    If m_Buy40RF > 0 Then defaultCont = defaultCont & "40RF,"
    ' Trim trailing comma
    If Len(defaultCont) > 0 Then defaultCont = Left(defaultCont, Len(defaultCont) - 1)
    If Len(defaultCont) = 0 Then defaultCont = "20GP,40GP,40HC"

    Dim contInput As String
    contInput = Trim(InputBox("Container types for this quote?" & vbCrLf & _
        "(Edit CSV — only listed types will be included)", _
        "Container Picker", defaultCont))
    If contInput = "" Then Exit Sub  ' user cancelled

    ' Parse selected container types into a lookup dictionary
    Dim dContSel As Object: Set dContSel = CreateObject("Scripting.Dictionary")
    Dim contParts() As String: contParts = Split(UCase(contInput), ",")
    Dim cp As Variant
    For Each cp In contParts
        Dim cpStr As String: cpStr = Trim(CStr(cp))
        If Len(cpStr) > 0 And Not dContSel.Exists(cpStr) Then dContSel.Add cpStr, cpStr
    Next cp

    ' Mask buy/margin/sell based on selection (only write if type selected)
    Dim sel20GP As Boolean: sel20GP = dContSel.Exists("20GP")
    Dim sel40GP As Boolean: sel40GP = dContSel.Exists("40GP")
    Dim sel40HC As Boolean: sel40HC = dContSel.Exists("40HC")
    Dim sel45HC As Boolean: sel45HC = dContSel.Exists("45HC")
    Dim sel40NOR As Boolean: sel40NOR = dContSel.Exists("40NOR")
    Dim sel20RF As Boolean: sel20RF = dContSel.Exists("20RF")
    Dim sel40RF As Boolean: sel40RF = dContSel.Exists("40RF")

    ' Generate Quote ID + QuoteGroupID
    Dim qid As String
    qid = UCase(Format(Date, "DDMMM")) & "-" & Format(Int((999 - 100 + 1) * Rnd + 100), "000")

    ' Insert a blank row at QUOTES_DATA_START (row 5), pushing all existing data down.
    ' This keeps newest quotes at the top so Nelson never has to scroll down.
    wsQ.Rows(QUOTES_DATA_START).Insert Shift:=xlDown, CopyOrigin:=xlFormatFromLeftOrAbove
    Dim nr As Long: nr = QUOTES_DATA_START

    ' QuoteGroupID: same group while same customer in same session
    ' Stored in col 43 (AQ). After insert-at-top the previous quote now lives at
    ' row QUOTES_DATA_START + 1 (it was just shifted down by one).
    Dim qgid As String: qgid = ""
    Dim prevCheckRow As Long: prevCheckRow = QUOTES_DATA_START + 1
    If Not IsEmpty(wsQ.Cells(prevCheckRow, 1).Value) Then
        Dim prevCust As String: prevCust = UCase(Trim(wsQ.Cells(prevCheckRow, 3).Value))
        Dim prevDate As String: prevDate = Format(wsQ.Cells(prevCheckRow, 2).Value, "DDMMM")
        Dim prevGid As String: prevGid = Trim(wsQ.Cells(prevCheckRow, 43).Value)
        If prevCust = UCase(Trim(m_Customer)) And prevDate = UCase(Format(Date, "DDMMM")) And prevGid <> "" Then
            qgid = prevGid  ' reuse same group
        End If
    End If
    If qgid = "" Then
        qgid = "QG-" & UCase(Format(Date, "DDMMM")) & "-" & Format(Int((99 - 10 + 1) * Rnd + 10), "00")
    End If

    ' Write quote row
    wsQ.Cells(nr, 1) = qid: wsQ.Cells(nr, 2) = Now
    wsQ.Cells(nr, 3) = m_Customer: wsQ.Cells(nr, 4) = m_Carrier
    wsQ.Cells(nr, 5) = m_POL: wsQ.Cells(nr, 6) = m_POD
    wsQ.Cells(nr, 7) = m_Place: wsQ.Cells(nr, 8) = m_Note
    wsQ.Cells(nr, 9) = m_Eff: wsQ.Cells(nr, 10) = m_Exp
    If m_IsSOC Then wsQ.Cells(nr, 11) = "SOC" Else wsQ.Cells(nr, 11) = "COC"

    ' Buy prices — only for selected container types (Feature 2)
    If sel20GP And m_Buy20GP > 0 Then wsQ.Cells(nr, 12) = m_Buy20GP
    If sel40GP And m_Buy40GP > 0 Then wsQ.Cells(nr, 13) = m_Buy40GP
    If sel40HC And m_Buy40HC > 0 Then wsQ.Cells(nr, 14) = m_Buy40HC
    If sel45HC And m_Buy45HC > 0 Then wsQ.Cells(nr, 15) = m_Buy45HC
    If sel40NOR And m_Buy40NOR > 0 Then wsQ.Cells(nr, 16) = m_Buy40NOR
    If sel20RF And m_Buy20RF > 0 Then wsQ.Cells(nr, 17) = m_Buy20RF
    If sel40RF And m_Buy40RF > 0 Then wsQ.Cells(nr, 18) = m_Buy40RF
    ' Margins — only for selected types
    If sel20GP And m_Mar20GP <> 0 Then wsQ.Cells(nr, 19) = m_Mar20GP
    If sel40GP And m_Mar40GP <> 0 Then wsQ.Cells(nr, 20) = m_Mar40GP
    If sel40HC And m_Mar40HC <> 0 Then wsQ.Cells(nr, 21) = m_Mar40HC
    If sel45HC And m_Mar45HC <> 0 Then wsQ.Cells(nr, 22) = m_Mar45HC
    If sel40NOR And m_Mar40NOR <> 0 Then wsQ.Cells(nr, 23) = m_Mar40NOR
    If sel20RF And m_Mar20RF <> 0 Then wsQ.Cells(nr, 24) = m_Mar20RF
    If sel40RF And m_Mar40RF <> 0 Then wsQ.Cells(nr, 25) = m_Mar40RF
    ' PUC — only for selected types
    If sel20GP And m_PUC20 > 0 Then wsQ.Cells(nr, 26) = m_PUC20
    If sel40GP And m_PUC40 > 0 Then wsQ.Cells(nr, 27) = m_PUC40
    If sel40HC And m_PUC40HC > 0 Then wsQ.Cells(nr, 28) = m_PUC40HC
    ' Sell = Buy + Margin + PUC — only for selected types
    If sel20GP And m_Buy20GP > 0 Then wsQ.Cells(nr, 29) = m_Buy20GP + m_Mar20GP + m_PUC20
    If sel40GP And m_Buy40GP > 0 Then wsQ.Cells(nr, 30) = m_Buy40GP + m_Mar40GP + m_PUC40
    If sel40HC And m_Buy40HC > 0 Then wsQ.Cells(nr, 31) = m_Buy40HC + m_Mar40HC + m_PUC40HC
    If sel45HC And m_Buy45HC > 0 Then wsQ.Cells(nr, 32) = m_Buy45HC + m_Mar45HC
    If sel40NOR And m_Buy40NOR > 0 Then wsQ.Cells(nr, 33) = m_Buy40NOR + m_Mar40NOR
    If sel20RF And m_Buy20RF > 0 Then wsQ.Cells(nr, 34) = m_Buy20RF + m_Mar20RF
    If sel40RF And m_Buy40RF > 0 Then wsQ.Cells(nr, 35) = m_Buy40RF + m_Mar40RF
    wsQ.Cells(nr, 36) = "PENDING"
    wsQ.Cells(nr, 42) = UCase(contInput)  ' ContType col 42 — pipe-joined CSV of selected types
    wsQ.Cells(nr, 43) = qgid  ' QuoteGroupID in col AQ

    ' Format price columns
    Dim fc As Integer
    For fc = 12 To 35: wsQ.Cells(nr, fc).NumberFormat = "$#,##0": Next fc

    Dim routeStr As String: routeStr = m_POL & " > " & m_POD
    If m_Place <> "" And m_Place <> m_POD Then routeStr = m_POL & " > " & m_Place & " via " & m_POD

    Call MsgBoxOrSilent("Quote " & qid & " created! [" & qgid & "]" & vbCrLf & _
           "Customer: " & m_Customer & vbCrLf & _
           "Route: " & routeStr & vbCrLf & _
           "Carrier: " & m_Carrier & vbCrLf & vbCrLf & _
           "Tip: Quote cung customer + cung ngay se nhom chung GroupID." & vbCrLf & _
           "Chon nhieu rows > Quote Image de tao hinh gui khach.", _
           vbInformation, "Quote Builder v14")
    On Error GoTo 0
End Sub

' ============================================================
'  TAB 1: PRICING — Generate Quote BATCH (multi-row selection)
'  Added 2026-04-16: let Nelson select N pricing rows + shared
'  markup + customer name, then write N quote rows with one click.
'  Use case: dau thang co gia moi -> bao gia 10-15 lanes cho cung
'  mot customer trong 1 lan click thay vi phai click tung dong.
' ============================================================
Public Sub OnAction_GenerateQuoteBatch(Optional control As IRibbonControl = Nothing)
    On Error GoTo EH

    If m_Customer = "" Then
        Call MsgBoxOrSilent("Please enter Customer name first!", vbExclamation, "Quote Batch")
        Exit Sub
    End If

    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then
        Call MsgBoxOrSilent("Open Pricing Dry or Pricing Reefer sheet first!", vbExclamation, "Quote Batch")
        Exit Sub
    End If
    If ActiveSheet.Name <> ws.Name Then
        Call MsgBoxOrSilent("Select rows on Pricing Dry / Pricing Reefer sheet!", vbExclamation, "Quote Batch")
        Exit Sub
    End If

    Dim isReefer As Boolean
    isReefer = (InStr(1, ws.Name, "Reefer", vbTextCompare) > 0)

    ' Collect unique selected rows (row >= 2, POL non-empty)
    Dim rowNums() As Long, rowCount As Long: rowCount = 0
    Dim selArea As Range, ri As Long, sr As Long, chk As Long, isDup As Boolean
    For Each selArea In Selection.Areas
        For ri = 1 To selArea.Rows.Count
            sr = selArea.Rows(ri).Row
            If sr >= DATA_START_ROW And Not IsEmpty(ws.Cells(sr, COL_POL).Value) Then
                isDup = False
                If rowCount > 0 Then
                    For chk = 1 To rowCount
                        If rowNums(chk) = sr Then isDup = True: Exit For
                    Next chk
                End If
                If Not isDup Then
                    rowCount = rowCount + 1
                    ReDim Preserve rowNums(1 To rowCount)
                    rowNums(rowCount) = sr
                End If
            End If
        Next ri
    Next selArea

    If rowCount = 0 Then
        Call MsgBoxOrSilent("Select data rows first (row 2+)!", vbExclamation, "Quote Batch")
        Exit Sub
    End If

    ' Single row -> delegate to the normal single-quote flow for parity
    If rowCount = 1 Then
        LoadRowToRibbon rowNums(1)
        Call OnAction_GenerateQuote(control)
        Exit Sub
    End If

    ' Confirm — with row preview so user can double-check the actual selection.
    ' 2026-04-15: added after Nelson reported Shift+Click range was counted as
    ' N rows when he thought he picked only 3. Preview lists first 5 rows so
    ' the row count is visually obvious before he confirms.
    Dim markupSummary As String
    If isReefer Then
        markupSummary = "20RF=" & m_Mar20RF & " | 40RF=" & m_Mar40RF
    Else
        markupSummary = "20GP=" & m_Mar20GP & " | 40HC=" & m_Mar40HC
    End If

    Dim previewLines As String, previewN As Long, pi As Long
    previewN = rowCount
    If previewN > 5 Then previewN = 5
    previewLines = "Preview:" & vbCrLf
    For pi = 1 To previewN
        previewLines = previewLines & "  Row " & rowNums(pi) & ": " & _
            ERPv14Core.SS(ws.Cells(rowNums(pi), COL_POL).Value) & "-" & _
            ERPv14Core.SS(ws.Cells(rowNums(pi), COL_POD).Value) & " " & _
            ERPv14Core.SS(ws.Cells(rowNums(pi), COL_CARRIER).Value) & vbCrLf
    Next pi
    If rowCount > 5 Then
        previewLines = previewLines & "  ... and " & (rowCount - 5) & " more rows"
    End If

    Dim confirmMsg As String
    confirmMsg = "Generate " & rowCount & " quotes for '" & m_Customer & "'?" & vbCrLf & _
                 "Shared markup: " & markupSummary & vbCrLf & vbCrLf & previewLines
    If rowCount > 10 Then
        confirmMsg = confirmMsg & vbCrLf & vbCrLf & _
                     "WARNING: " & rowCount & " rows is a lot. Did you Shift+Click a range?" & vbCrLf & _
                     "Use Ctrl+Click to pick individual rows only."
    End If
    If MsgBox(confirmMsg, vbYesNo + vbQuestion, "Quote Batch") = vbNo Then Exit Sub

    Dim wsQ As Worksheet: Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        Call MsgBoxOrSilent("Quotes sheet not found!", vbExclamation, "Quote Batch")
        Exit Sub
    End If
    EnsureQuotesHeaders wsQ

    ' ONE QuoteGroupID for whole batch
    Dim qgid As String
    qgid = "QG-" & UCase(Format(Date, "DDMMM")) & "-" & Format(Int((99 - 10 + 1) * Rnd + 10), "00")

    ' Insert rowCount blank rows at QUOTES_DATA_START in one operation (faster,
    ' less flicker than inserting one row per quote).  After this block, rows
    ' QUOTES_DATA_START .. QUOTES_DATA_START+rowCount-1 are blank and ready to
    ' receive the batch data; existing data has been shifted down by rowCount.
    wsQ.Rows(QUOTES_DATA_START & ":" & QUOTES_DATA_START + rowCount - 1).Insert _
        Shift:=xlDown, CopyOrigin:=xlFormatFromLeftOrAbove
    Dim nr As Long: nr = QUOTES_DATA_START

    Dim writtenCount As Long: writtenCount = 0
    Dim skippedNoRate As Long: skippedNoRate = 0
    Dim i As Long, r As Long

    Application.ScreenUpdating = False

    For i = 1 To rowCount
        r = rowNums(i)

        Dim rPOL As String, rPOD As String, rPlace As String, rCarrier As String
        Dim rEff As String, rExp As String, rNote As String, rSource As String
        rPOL = ERPv14Core.SS(ws.Cells(r, COL_POL).Value)
        rPOD = ERPv14Core.SS(ws.Cells(r, COL_POD).Value)
        rPlace = ERPv14Core.SS(ws.Cells(r, COL_PLACE).Value)
        rCarrier = ERPv14Core.SS(ws.Cells(r, COL_CARRIER).Value)
        rEff = FormatShortDate(ws.Cells(r, COL_EFF).Value)
        rExp = FormatShortDate(ws.Cells(r, COL_EXP).Value)
        rNote = ERPv14Core.SS(ws.Cells(r, COL_NOTE).Value)
        rSource = ERPv14Core.SS(ws.Cells(r, COL_SOURCE).Value)

        Dim rIsSOC As Boolean
        rIsSOC = (InStr(UCase(rNote), "SOC") > 0) Or (InStr(UCase(rSource), "SOC") > 0)

        ' Buy rates — sheet-type aware
        Dim rBuy20GP As Long, rBuy40GP As Long, rBuy40HC As Long, rBuy45HC As Long
        Dim rBuy40NOR As Long, rBuy20RF As Long, rBuy40RF As Long
        rBuy20GP = 0: rBuy40GP = 0: rBuy40HC = 0: rBuy45HC = 0
        rBuy40NOR = 0: rBuy20RF = 0: rBuy40RF = 0
        If isReefer Then
            rBuy20RF = ERPv14Core.SL(ws.Cells(r, 10).Value)
            rBuy40RF = ERPv14Core.SL(ws.Cells(r, 11).Value)
        Else
            rBuy20GP = ERPv14Core.SL(ws.Cells(r, COL_20GP).Value)
            rBuy40GP = ERPv14Core.SL(ws.Cells(r, COL_40GP).Value)
            rBuy40HC = ERPv14Core.SL(ws.Cells(r, COL_40HQ).Value)
            rBuy45HC = ERPv14Core.SL(ws.Cells(r, COL_45HQ).Value)
            rBuy40NOR = ERPv14Core.SL(ws.Cells(r, COL_40NOR).Value)
        End If

        Dim sumBuy As Long
        sumBuy = rBuy20GP + rBuy40GP + rBuy40HC + rBuy45HC + rBuy40NOR + rBuy20RF + rBuy40RF
        If sumBuy = 0 Then
            skippedNoRate = skippedNoRate + 1
            GoTo ContinueRow
        End If

        ' PUC per-row (SOC only) — ByRef output so we don't touch module state
        Dim rPUC20 As Long, rPUC40 As Long, rPUC40HC As Long
        rPUC20 = 0: rPUC40 = 0: rPUC40HC = 0
        If rIsSOC Then LookupPUCForPlace rPlace, rPUC20, rPUC40, rPUC40HC

        ' Generate per-row quote id
        Dim qid As String
        qid = UCase(Format(Date, "DDMMM")) & "-" & Format(Int((999 - 100 + 1) * Rnd + 100), "000")

        wsQ.Cells(nr, 1) = qid: wsQ.Cells(nr, 2) = Now
        wsQ.Cells(nr, 3) = m_Customer: wsQ.Cells(nr, 4) = rCarrier
        wsQ.Cells(nr, 5) = rPOL: wsQ.Cells(nr, 6) = rPOD
        wsQ.Cells(nr, 7) = rPlace: wsQ.Cells(nr, 8) = rNote
        wsQ.Cells(nr, 9) = rEff: wsQ.Cells(nr, 10) = rExp
        If rIsSOC Then wsQ.Cells(nr, 11) = "SOC" Else wsQ.Cells(nr, 11) = "COC"

        If rBuy20GP > 0 Then wsQ.Cells(nr, 12) = rBuy20GP
        If rBuy40GP > 0 Then wsQ.Cells(nr, 13) = rBuy40GP
        If rBuy40HC > 0 Then wsQ.Cells(nr, 14) = rBuy40HC
        If rBuy45HC > 0 Then wsQ.Cells(nr, 15) = rBuy45HC
        If rBuy40NOR > 0 Then wsQ.Cells(nr, 16) = rBuy40NOR
        If rBuy20RF > 0 Then wsQ.Cells(nr, 17) = rBuy20RF
        If rBuy40RF > 0 Then wsQ.Cells(nr, 18) = rBuy40RF

        If m_Mar20GP <> 0 Then wsQ.Cells(nr, 19) = m_Mar20GP
        If m_Mar40GP <> 0 Then wsQ.Cells(nr, 20) = m_Mar40GP
        If m_Mar40HC <> 0 Then wsQ.Cells(nr, 21) = m_Mar40HC
        If m_Mar45HC <> 0 Then wsQ.Cells(nr, 22) = m_Mar45HC
        If m_Mar40NOR <> 0 Then wsQ.Cells(nr, 23) = m_Mar40NOR
        If m_Mar20RF <> 0 Then wsQ.Cells(nr, 24) = m_Mar20RF
        If m_Mar40RF <> 0 Then wsQ.Cells(nr, 25) = m_Mar40RF

        If rPUC20 > 0 Then wsQ.Cells(nr, 26) = rPUC20
        If rPUC40 > 0 Then wsQ.Cells(nr, 27) = rPUC40
        If rPUC40HC > 0 Then wsQ.Cells(nr, 28) = rPUC40HC

        If rBuy20GP > 0 Then wsQ.Cells(nr, 29) = rBuy20GP + m_Mar20GP + rPUC20
        If rBuy40GP > 0 Then wsQ.Cells(nr, 30) = rBuy40GP + m_Mar40GP + rPUC40
        If rBuy40HC > 0 Then wsQ.Cells(nr, 31) = rBuy40HC + m_Mar40HC + rPUC40HC
        If rBuy45HC > 0 Then wsQ.Cells(nr, 32) = rBuy45HC + m_Mar45HC
        If rBuy40NOR > 0 Then wsQ.Cells(nr, 33) = rBuy40NOR + m_Mar40NOR
        If rBuy20RF > 0 Then wsQ.Cells(nr, 34) = rBuy20RF + m_Mar20RF
        If rBuy40RF > 0 Then wsQ.Cells(nr, 35) = rBuy40RF + m_Mar40RF
        wsQ.Cells(nr, 36) = "PENDING"
        wsQ.Cells(nr, 43) = qgid

        Dim fc As Integer
        For fc = 12 To 35: wsQ.Cells(nr, fc).NumberFormat = "$#,##0": Next fc

        writtenCount = writtenCount + 1
        nr = nr + 1
ContinueRow:
    Next i

    ' Remove blank rows that were pre-inserted but not used (skipped rows).
    ' nr now points to the first unused inserted row; rows from nr to
    ' QUOTES_DATA_START + rowCount - 1 are blank and must be deleted.
    Dim unusedStart As Long: unusedStart = nr
    Dim unusedEnd As Long: unusedEnd = QUOTES_DATA_START + rowCount - 1
    If unusedStart <= unusedEnd Then
        wsQ.Rows(unusedStart & ":" & unusedEnd).Delete Shift:=xlUp
    End If

    Application.ScreenUpdating = True

    Dim msg As String
    msg = "Batch complete!" & vbCrLf & vbCrLf & _
          "Customer: " & m_Customer & vbCrLf & _
          "Quotes written: " & writtenCount & " / " & rowCount & vbCrLf & _
          "Group: " & qgid
    If skippedNoRate > 0 Then
        msg = msg & vbCrLf & "Skipped (no rate): " & skippedNoRate
    End If
    msg = msg & vbCrLf & vbCrLf & _
          "Next: go to Quotes sheet, select these rows, click Quote Image."

    Call MsgBoxOrSilent(msg, vbInformation, "Quote Batch")
    Exit Sub

EH:
    Application.ScreenUpdating = True
    g_LastError = "OnAction_GenerateQuoteBatch #" & Err.Number & ": " & Err.Description
    MsgBox g_LastError, vbExclamation, "Quote Batch"
End Sub

' Shared helper — used by both single and batch Generate Quote flows.
Private Sub EnsureQuotesHeaders(wsQ As Worksheet)
    ' Headers live at QUOTES_HEADER_ROW (row 4) — KPI occupies rows 1-3.
    If Not IsEmpty(wsQ.Cells(QUOTES_HEADER_ROW, 1).Value) Then Exit Sub
    Dim h As Variant
    h = Array("QuoteID", "Date", "Customer", "Carrier", "POL", "POD", _
              "Place", "Via", "Eff", "Exp", "Source", _
              "Buy_20GP", "Buy_40GP", "Buy_40HC", "Buy_45HC", "Buy_40NOR", "Buy_20RF", "Buy_40RF", _
              "Mar_20GP", "Mar_40GP", "Mar_40HC", "Mar_45HC", "Mar_40NOR", "Mar_20RF", "Mar_40RF", _
              "PUC_20", "PUC_40", "PUC_40HC", _
              "Sell_20GP", "Sell_40GP", "Sell_40HC", "Sell_45HC", "Sell_40NOR", "Sell_20RF", "Sell_40RF", _
              "Status", "Remark", "StatusDate")
    Dim hi As Integer
    For hi = 0 To UBound(h): wsQ.Cells(QUOTES_HEADER_ROW, hi + 1).Value = h(hi): Next hi
    wsQ.Range("A" & QUOTES_HEADER_ROW & ":AL" & QUOTES_HEADER_ROW).Font.Bold = True
End Sub

' PUC lookup that outputs via ByRef params without mutating m_PUC* state.
' Mirrors LookupPUC (Pass 0 alias -> Pass 1 exact -> Pass 2 fuzzy) so batch
' flow gets the same numbers Nelson sees in single-quote mode.
Private Sub LookupPUCForPlace(placeName As String, ByRef out20 As Long, ByRef out40 As Long, ByRef out40HC As Long)
    out20 = 0: out40 = 0: out40HC = 0
    Dim wsPUC As Worksheet
    On Error Resume Next
    Set wsPUC = ThisWorkbook.Sheets("PUC_Lookup")
    On Error GoTo 0
    If wsPUC Is Nothing Or placeName = "" Then Exit Sub

    Dim target As String: target = UCase(Trim(placeName))

    ' Pass 0: alias expand — mirror LookupPUC port-code map
    Dim aliasVal As String: aliasVal = ""
    If target = "LAX/LGB" Or target = "LAX-LGB" Or target = "LAX" Or target = "LGB" Or target = "LONG BEACH" Then aliasVal = "LOS ANGELES"
    If target = "NYC" Or target = "NEWARK" Or target = "NEW YORK/NEW JERSEY" Then aliasVal = "NEW YORK"
    If target = "SAV" Then aliasVal = "SAVANNAH"
    If target = "CHS" Then aliasVal = "CHARLESTON"
    If target = "HOU" Then aliasVal = "HOUSTON"
    If target = "MIA" Then aliasVal = "MIAMI"
    If target = "ORF" Or target = "NFK" Then aliasVal = "NORFOLK"
    If target = "SEA" Then aliasVal = "SEATTLE"
    If target = "MOB" Then aliasVal = "MOBILE"
    If target = "MEM" Then aliasVal = "MEMPHIS"
    If target = "ATL" Then aliasVal = "ATLANTA"
    If target = "DAL" Or target = "DFW" Then aliasVal = "DALLAS"
    If target = "CHI" Then aliasVal = "CHICAGO"
    If target = "PDX" Then aliasVal = "PORTLAND"
    If target = "TAC" Then aliasVal = "TACOMA"
    If target = "OAK" Then aliasVal = "OAKLAND"
    If target = "BOS" Then aliasVal = "BOSTON"
    If target = "JAX" Then aliasVal = "JACKSONVILLE"
    If aliasVal <> "" Then target = aliasVal

    Dim lastRow As Long: lastRow = wsPUC.Cells(wsPUC.Rows.Count, 1).End(xlUp).Row
    Dim pr As Long, rowPlace As String

    ' Pass 1: exact
    For pr = 2 To lastRow
        rowPlace = UCase(Trim(wsPUC.Cells(pr, 1).Value))
        If Len(rowPlace) > 0 And rowPlace = target Then
            out20 = ERPv14Core.SL(wsPUC.Cells(pr, 2).Value)
            out40 = ERPv14Core.SL(wsPUC.Cells(pr, 3).Value)
            out40HC = ERPv14Core.SL(wsPUC.Cells(pr, 4).Value)
            Exit Sub
        End If
    Next pr

    ' Pass 2: fuzzy substring
    For pr = 2 To lastRow
        rowPlace = UCase(Trim(wsPUC.Cells(pr, 1).Value))
        If Len(rowPlace) >= 4 Then
            If InStr(target, rowPlace) > 0 Or InStr(rowPlace, target) > 0 Then
                out20 = ERPv14Core.SL(wsPUC.Cells(pr, 2).Value)
                out40 = ERPv14Core.SL(wsPUC.Cells(pr, 3).Value)
                out40HC = ERPv14Core.SL(wsPUC.Cells(pr, 4).Value)
                Exit Sub
            End If
        End If
    Next pr
End Sub

' ============================================================
'  TAB 2: OPERATIONS — Quote Status buttons (stubs)
'  Full implementation: import QuoteJobWorkflow.bas later
' ============================================================
Public Sub OnAction_MarkQuoteWin(control As IRibbonControl)
    On Error GoTo ErrHandler

    ' Active Jobs v4 layout (2026-04-14 migration to match HTML mockup)
    ' Source of truth: ERP/core/active_jobs_cols.py — keep in sync!
    Const AJ_DATA_START As Long = 8
    Const AJ_MONTH As Long = 1
    Const AJ_FAST_ID As Long = 2
    Const AJ_JOB_ID As Long = 3
    Const AJ_CRMID As Long = 4           ' CUSTOMER
    Const AJ_POL_POD As Long = 5
    Const AJ_DOOR_ADDRESS As Long = 6    ' FINAL DEST
    Const AJ_CARRIER As Long = 7
    Const AJ_BKG_NO As Long = 8
    Const AJ_HBL_NO As Long = 9
    Const AJ_CONTTYPE As Long = 10       ' CONT
    Const AJ_QTY As Long = 11
    Const AJ_SERVICE As Long = 12
    Const AJ_ETD As Long = 13
    Const AJ_STATUS As Long = 14
    Const AJ_TRACKING As Long = 15
    Const AJ_SELL As Long = 16
    Const AJ_BUY As Long = 17
    Const AJ_PROFIT As Long = 18
    Const AJ_EMAIL As Long = 19          ' Request_BKG mailto

    ' Hidden cols (T..AN)
    Const AJ_ROUTING As Long = 20
    Const AJ_ETA As Long = 21
    Const AJ_ATA As Long = 22
    Const AJ_CONTRACT As Long = 23
    Const AJ_MARGIN As Long = 24
    Const AJ_CUSTTYPE As Long = 25
    Const AJ_SI As Long = 26
    Const AJ_CY_CUT As Long = 27
    Const AJ_DOOR_DEL As Long = 28
    Const AJ_DOOR_ST As Long = 29
    Const AJ_DELAY_CNT As Long = 30
    Const AJ_DELAY_LOG As Long = 31
    Const AJ_NOTES As Long = 32
    Const AJ_CREATED As Long = 33
    Const AJ_UPDATED As Long = 34
    Const AJ_COST_BKD As Long = 35
    Const AJ_TRACKING_RAW As Long = 36   ' "5/7 ATD" text — source for AJ_TRACKING dots

    ' Phase 3 — Booking Pool hidden cols (extend-active-jobs-schema.py added these)
    Const AJ_SI_CUTOFF_COL As Long = 41
    Const AJ_CY_CLOSE_COL As Long = 42
    Const AJ_VESSEL_VOYAGE_COL As Long = 43
    Const AJ_PO_NUMBER_COL As Long = 44
    Const AJ_FLOW_TYPE_COL As Long = 45

    ' Step 1: Validate — must be on Quotes sheet
    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Mark WIN"
        Exit Sub
    End If
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Navigate to Quotes sheet first!", vbExclamation, "Mark WIN"
        Exit Sub
    End If

    Dim r As Long: r = Selection.Row
    If r < 2 Then
        MsgBox "Select a quote row (row 2+)!", vbExclamation, "Mark WIN"
        Exit Sub
    End If

    Dim quoteID As String: quoteID = Trim(CStr(wsQ.Cells(r, 1).Value))
    If quoteID = "" Then
        MsgBox "No quote in this row!", vbExclamation, "Mark WIN"
        Exit Sub
    End If

    Dim curStatus As String: curStatus = UCase(Trim(CStr(wsQ.Cells(r, 36).Value)))
    ' Allow multiple WIN on same quote (e.g., 2 shipments x 2x40HC)
    If curStatus = "WIN" Then
        If MsgBox("Quote already has WIN. Create another shipment/job?", _
                  vbYesNo + vbQuestion, "Mark WIN - Additional") = vbNo Then Exit Sub
    End If
    If InStr(curStatus, "LOST") > 0 Or InStr(curStatus, "EXPIRED") > 0 Then
        If MsgBox("Quote was " & curStatus & ". Confirm WIN anyway?", _
                  vbYesNo + vbQuestion, "Mark WIN") = vbNo Then Exit Sub
    End If

    ' Step 2: Auto-detect container from selected CELL column
    '   Buy_20GP=12, Buy_40GP=13, Buy_40HC=14, Buy_45HC=15,
    '   Buy_40NOR=16, Buy_20RF=17, Buy_40RF=18
    '   Sell_20GP=29, Sell_40GP=30, Sell_40HC=31, Sell_45HC=32,
    '   Sell_40NOR=33, Sell_20RF=34, Sell_40RF=35
    Dim selCol As Long: selCol = Selection.Column
    Dim contType As String: contType = ""
    Dim buyCol As Integer, sellCol As Integer

    Select Case selCol
        Case 12, 29: contType = "20GP":  buyCol = 12: sellCol = 29
        Case 13, 30: contType = "40GP":  buyCol = 13: sellCol = 30
        Case 14, 31: contType = "40HC":  buyCol = 14: sellCol = 31
        Case 15, 32: contType = "45HC":  buyCol = 15: sellCol = 32
        Case 16, 33: contType = "40NOR": buyCol = 16: sellCol = 33
        Case 17, 34: contType = "20RF":  buyCol = 17: sellCol = 34
        Case 18, 35: contType = "40RF":  buyCol = 18: sellCol = 35
        Case Else
            ' Fallback: ask user if not on a price column
            contType = UCase(Trim(InputBox( _
                "Click a price cell to auto-detect, or type:" & vbCrLf & _
                "20GP / 40GP / 40HC / 45HC / 40NOR / 20RF / 40RF", _
                "Mark WIN - " & quoteID, "40HC")))
            If contType = "" Then Exit Sub
            Select Case contType
                Case "20GP":  buyCol = 12: sellCol = 29
                Case "40GP":  buyCol = 13: sellCol = 30
                Case "40HC":  buyCol = 14: sellCol = 31
                Case "45HC":  buyCol = 15: sellCol = 32
                Case "40NOR": buyCol = 16: sellCol = 33
                Case "20RF":  buyCol = 17: sellCol = 34
                Case "40RF":  buyCol = 18: sellCol = 35
                Case Else
                    MsgBox "Invalid: " & contType, vbExclamation, "Mark WIN"
                    Exit Sub
            End Select
    End Select

    ' Step 3: Read quote data
    Dim customer As String: customer = CStr(wsQ.Cells(r, 3).Value)
    Dim carrier As String:  carrier = CStr(wsQ.Cells(r, 4).Value)
    Dim pol As String:      pol = CStr(wsQ.Cells(r, 5).Value)
    Dim pod As String:      pod = CStr(wsQ.Cells(r, 6).Value)
    Dim place As String:    place = CStr(wsQ.Cells(r, 7).Value)
    Dim source As String:   source = CStr(wsQ.Cells(r, 11).Value)

    ' Step 3c: Read Contract / Group Rate / Group Code from Pricing hidden cols
    ' Phase 4 — hidden cols 15 (Contract), 16 (Group Rate), 17 (Group Code / ONE only)
    ' written by refresh-v14.py after Phase 3. m_SourceRow is set when user clicks
    ' the Pricing Dry/Reefer row via LoadRowToRibbon.
    Dim contractNo As String: contractNo = ""
    Dim groupRate As String:  groupRate = ""
    Dim groupCode As String:  groupCode = ""
    If m_SourceRow > 0 Then
        Dim wsPricing As Worksheet
        On Error Resume Next
        Set wsPricing = ERPv14Core.GetActivePricingSheet()
        On Error GoTo ErrHandler
        If Not wsPricing Is Nothing Then
            contractNo = Trim(CStr(wsPricing.Cells(m_SourceRow, 15).Value))  ' Contract
            groupRate  = Trim(CStr(wsPricing.Cells(m_SourceRow, 16).Value))  ' Group Rate
            groupCode  = Trim(CStr(wsPricing.Cells(m_SourceRow, 17).Value))  ' Group Code (ONE only)
        End If
    End If

    Dim buyRate As Double: buyRate = 0
    Dim sellRate As Double: sellRate = 0
    If IsNumeric(wsQ.Cells(r, buyCol).Value) Then buyRate = CDbl(wsQ.Cells(r, buyCol).Value)
    If IsNumeric(wsQ.Cells(r, sellCol).Value) Then sellRate = CDbl(wsQ.Cells(r, sellCol).Value)
    If sellRate = 0 Then
        MsgBox "No selling rate for " & contType & "!", vbExclamation, "Mark WIN"
        Exit Sub
    End If

    ' Step 3b: Lookup CRM → resolve customer input to canonical NAME
    ' 2026-04-21 FIX (Nelson): Active Jobs CUSTOMER col was displaying CODE
    ' (e.g. "CS001296") instead of NAME (e.g. "PANDA HCM"). Fix: always
    ' resolve to col 2 (NAME). Match by EITHER col 1 (CODE) or col 2 (NAME)
    ' so users can type either — canonical output is always the NAME.
    Dim crmID As String: crmID = customer        ' default: keep original input
    Dim custType As String: custType = ""
    On Error Resume Next
    Dim wsCRM As Worksheet
    Set wsCRM = ERPv14Core.FindSheet("CRM")
    If Not wsCRM Is Nothing Then
        Dim cr As Long
        Dim uCust As String: uCust = UCase(Trim(customer))
        Dim lastCrmRow As Long
        lastCrmRow = wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
        For cr = 2 To lastCrmRow
            Dim crmCode As String: crmCode = UCase(Trim(CStr(wsCRM.Cells(cr, 1).Value)))
            Dim crmNm As String:   crmNm = UCase(Trim(CStr(wsCRM.Cells(cr, 2).Value)))
            If crmCode = uCust Or crmNm = uCust Then
                ' Always return canonical NAME (col 2), never the code
                crmID = CStr(wsCRM.Cells(cr, 2).Value)
                custType = CStr(wsCRM.Cells(cr, 3).Value)
                Exit For
            End If
        Next cr
    End If
    On Error GoTo ErrHandler
    ' crmID now holds NAME (e.g. "PANDA HCM") — kept variable name for
    ' backward compat with downstream error/log lines 2168, 2260.

    ' Step 4: Ask Qty
    Dim qtyInput As String
    qtyInput = InputBox("Quantity (containers)?" & vbCrLf & _
        "Container: " & contType & vbCrLf & _
        "Sell: $" & Format(sellRate, "#,##0") & " | Buy: $" & Format(buyRate, "#,##0"), _
        "Mark WIN - " & quoteID & " [" & contType & "]", "1")
    If qtyInput = "" Then Exit Sub
    Dim qty As Long: qty = CLng(qtyInput)
    If qty < 1 Then qty = 1

    ' Step 4b: TEU calculation (20'=1 TEU, 40'/45'=2 TEU per box)
    Dim teuPerBox As Long
    If Left(contType, 2) = "20" Then
        teuPerBox = 1
    Else
        teuPerBox = 2
    End If
    Dim totalTEU As Long: totalTEU = qty * teuPerBox

    ' Step 5: Find Active Jobs sheet
    Dim wsJ As Worksheet
    Set wsJ = ERPv14Core.FindSheet("Active")
    If wsJ Is Nothing Then
        MsgBox "Active Jobs sheet not found!", vbExclamation, "Mark WIN"
        Exit Sub
    End If

    ' Step 6: Update Quotes sheet
    wsQ.Cells(r, 36).Value = "WIN"
    wsQ.Cells(r, 36).Interior.Color = RGB(0, 176, 80)
    wsQ.Cells(r, 36).Font.Color = RGB(255, 255, 255)
    wsQ.Cells(r, 36).Font.Bold = True
    wsQ.Cells(r, 38).Value = Now
    wsQ.Cells(r, 39).Value = qty
    wsQ.Cells(r, 40).Value = totalTEU   ' Volume = TEU
    wsQ.Cells(r, 42).Value = contType

    ' ── Phase 3: Booking Pool Link mode ──────────────────────────
    ' Ask Nelson: link from existing HOLDING booking in Pool,
    ' or create new DIRECT flow job (no pool).
    Dim useFromPool As VbMsgBoxResult
    useFromPool = MsgBox("Link tu Booking Pool co san?" & ChrW(10) & ChrW(10) & _
                        "  Yes    = chon tu Pool HOLDING" & ChrW(10) & _
                        "  No     = tao moi (flow DIRECT)" & ChrW(10) & _
                        "  Cancel = huy toan bo", _
                        vbYesNoCancel + vbQuestion, "MarkQuoteWin — Booking Source")

    If useFromPool = vbCancel Then
        ' Undo Quote WIN mark — restore to previous status
        wsQ.Cells(r, 36).Value = curStatus
        wsQ.Cells(r, 36).Interior.ColorIndex = xlNone
        wsQ.Cells(r, 36).Font.Color = 0
        wsQ.Cells(r, 36).Font.Bold = False
        wsQ.Cells(r, 38).Value = ""
        wsQ.Cells(r, 39).Value = ""
        wsQ.Cells(r, 40).Value = ""
        wsQ.Cells(r, 42).Value = ""
        Exit Sub
    End If

    ' Pool link variables (populated if vbYes)
    Dim poolRow As Long:    poolRow = 0
    Dim poolBkg As String
    Dim poolSICutOff As String
    Dim poolCYClose As String
    Dim poolVesselVoyage As String
    Dim poolPO As String
    Dim poolFlowType As String

    If useFromPool = vbYes Then
        Dim wsPool As Worksheet
        On Error Resume Next
        Set wsPool = ThisWorkbook.Sheets("Booking Pool")
        On Error GoTo ErrHandler
        If wsPool Is Nothing Then
            MsgBox "Sheet 'Booking Pool' not found!" & ChrW(10) & "Fallback: using DIRECT flow.", _
                   vbExclamation, "MarkQuoteWin"
            poolFlowType = "DIRECT"
        Else
            Dim searchBkg As String
            searchBkg = Trim(InputBox("Nhap BKG# can link (HOLDING trong Pool):" & ChrW(10) & _
                                      "Vi du: SGNG83555500", _
                                      "Link Pool — " & quoteID))
            If searchBkg = "" Then
                MsgBox "BKG# blank — fallback to DIRECT flow.", vbInformation, "MarkQuoteWin"
                poolFlowType = "DIRECT"
            Else
                Dim pr As Long
                Dim poolLastRow As Long: poolLastRow = wsPool.UsedRange.Rows.Count
                For pr = 2 To poolLastRow
                    Dim prBkg As String: prBkg = Trim(CStr(wsPool.Cells(pr, 1).Value))
                    Dim prStat As String: prStat = UCase(Trim(CStr(wsPool.Cells(pr, 16).Value)))
                    If UCase(prBkg) = UCase(searchBkg) And prStat = "HOLDING" Then
                        poolRow = pr
                        Exit For
                    End If
                Next pr

                If poolRow = 0 Then
                    MsgBox "Khong tim thay BKG '" & searchBkg & "' voi Status=HOLDING." & ChrW(10) & _
                           "Fallback: using DIRECT flow.", _
                           vbExclamation, "MarkQuoteWin — Pool Not Found"
                    poolFlowType = "DIRECT"
                Else
                    ' Read all pool fields
                    poolBkg = CStr(wsPool.Cells(poolRow, 1).Value)
                    poolSICutOff = CStr(wsPool.Cells(poolRow, 11).Value)
                    poolCYClose = CStr(wsPool.Cells(poolRow, 12).Value)
                    Dim pVessel As String: pVessel = Trim(CStr(wsPool.Cells(poolRow, 13).Value))
                    Dim pVoyage As String: pVoyage = Trim(CStr(wsPool.Cells(poolRow, 14).Value))
                    poolVesselVoyage = Trim(pVessel & " " & pVoyage)
                    poolPO = CStr(wsPool.Cells(poolRow, 15).Value)
                    poolFlowType = "KEEP_SPACE"
                End If
            End If
        End If
    Else
        poolFlowType = "DIRECT"
    End If
    ' ── End Phase 3 Booking Pool Link mode ───────────────────────

    ' Step 7: Write to Active Jobs
    Dim nr As Long
    nr = wsJ.Cells(wsJ.Rows.Count, AJ_CRMID).End(xlUp).Row + 1
    If nr < AJ_DATA_START Then nr = AJ_DATA_START

    Dim profit As Double: profit = (sellRate - buyRate) * qty
    Dim margin As Double: margin = 0
    If sellRate > 0 Then margin = (sellRate - buyRate) / sellRate

    ' Visible cols (v4 mockup layout A-S)
    ' Force MONTH as text to avoid Excel auto-parsing "APR-26" as date
    wsJ.Cells(nr, AJ_MONTH).NumberFormat = "@"
    wsJ.Cells(nr, AJ_MONTH).Value = UCase(Format(Now, "mmm-yy"))    ' APR-26
    wsJ.Cells(nr, AJ_MONTH).HorizontalAlignment = xlCenter
    ' FAST_ID + Job_ID left blank for Nelson to fill
    wsJ.Cells(nr, AJ_CRMID).Value = crmID                            ' CUSTOMER (col 4)
    ' POL-POD: use ChrW() for Unicode arrow — Chr() only handles 0-255
    wsJ.Cells(nr, AJ_POL_POD).Value = pol & ChrW(8594) & pod         ' "HPH→USLGB"
    wsJ.Cells(nr, AJ_POL_POD).HorizontalAlignment = xlCenter
    wsJ.Cells(nr, AJ_DOOR_ADDRESS).Value = place                     ' FINAL DEST
    wsJ.Cells(nr, AJ_CARRIER).Value = carrier
    wsJ.Cells(nr, AJ_CONTTYPE).Value = contType
    wsJ.Cells(nr, AJ_QTY).Value = qty
    wsJ.Cells(nr, AJ_QTY).HorizontalAlignment = xlCenter
    wsJ.Cells(nr, AJ_ETD).Value = Now                                ' placeholder — Nelson updates
    wsJ.Cells(nr, AJ_ETD).NumberFormat = "dd/mm"
    wsJ.Cells(nr, AJ_STATUS).Value = "Booked"
    ' Tracking dots (mockup colors) — call public helper from JobsAutomation
    Call ERPv14JobsAutomation.ApplyTrackingDots(wsJ.Cells(nr, AJ_TRACKING), 1, False)
    wsJ.Cells(nr, AJ_SELL).Value = sellRate
    wsJ.Cells(nr, AJ_SELL).NumberFormat = "#,##0"
    wsJ.Cells(nr, AJ_BUY).Value = buyRate
    wsJ.Cells(nr, AJ_BUY).NumberFormat = "#,##0"
    wsJ.Cells(nr, AJ_PROFIT).Value = profit
    wsJ.Cells(nr, AJ_PROFIT).NumberFormat = "#,##0"
    wsJ.Cells(nr, AJ_PROFIT).Font.Bold = True
    If profit > 0 Then
        wsJ.Cells(nr, AJ_PROFIT).Font.Color = RGB(0, 128, 74)
    ElseIf profit < 0 Then
        wsJ.Cells(nr, AJ_PROFIT).Font.Color = RGB(192, 0, 0)
    End If

    ' Hidden cols (T..AN — preserved data)
    wsJ.Cells(nr, AJ_CUSTTYPE).Value = custType
    If place <> "" And place <> pod Then
        wsJ.Cells(nr, AJ_ROUTING).Value = pol & "-" & place & " VIA " & pod
    Else
        wsJ.Cells(nr, AJ_ROUTING).Value = pol & "-" & pod
    End If
    ' Phase 4: store real contract number instead of source (rate type).
    ' contractNo is read from Pricing hidden col 15 via m_SourceRow.
    ' Fall back to source if contractNo is empty (e.g. old Pricing rows without hidden cols).
    wsJ.Cells(nr, AJ_CONTRACT).Value = IIf(contractNo <> "", contractNo, source)
    wsJ.Cells(nr, AJ_MARGIN).Value = margin
    wsJ.Cells(nr, AJ_MARGIN).NumberFormat = "0.0%"
    wsJ.Cells(nr, AJ_TRACKING_RAW).Value = "1/7 BKG"                 ' raw for shipment_tracker

    ' v4 — auto-fill SERVICE col 31. Default CY-CY; upgrade to CY-DOOR if quote
    ' remark col 8 (Note) or place col 7 hints at inland delivery.
    Dim serviceMode As String: serviceMode = "CY-CY"
    Dim wsqPlace As String: wsqPlace = UCase(CStr(wsQ.Cells(r, 7).Value))
    Dim wsqRemark As String: wsqRemark = UCase(CStr(wsQ.Cells(r, 8).Value))
    If InStr(wsqPlace, "DOOR") > 0 Or InStr(wsqRemark, "DOOR") > 0 _
       Or InStr(wsqRemark, "INLAND") > 0 Then
        serviceMode = "CY-DOOR"
    End If
    wsJ.Cells(nr, AJ_SERVICE).Value = serviceMode
    wsJ.Cells(nr, AJ_SERVICE).HorizontalAlignment = xlCenter

    ' P3 2026-04-12 — shortened from "dd/mm/yyyy hh:mm" to "dd/mm hh:mm"
    ' per Nelson's request (more compact in Active Jobs row view).
    wsJ.Cells(nr, AJ_CREATED).Value = Now
    wsJ.Cells(nr, AJ_CREATED).NumberFormat = "dd/mm hh:mm"
    wsJ.Cells(nr, AJ_UPDATED).Value = Now
    wsJ.Cells(nr, AJ_UPDATED).NumberFormat = "dd/mm hh:mm"

    ' Phase 3 — Write Pool metadata to 5 hidden cols (41-45)
    ' Flow_Type always written; SI/CY/Vessel/PO only when pool linked.
    wsJ.Cells(nr, AJ_FLOW_TYPE_COL).Value = poolFlowType

    If poolRow > 0 Then
        ' Pool-linked job: copy booking metadata from Booking Pool
        wsJ.Cells(nr, AJ_SI_CUTOFF_COL).Value = poolSICutOff
        wsJ.Cells(nr, AJ_CY_CLOSE_COL).Value = poolCYClose
        wsJ.Cells(nr, AJ_VESSEL_VOYAGE_COL).Value = poolVesselVoyage
        wsJ.Cells(nr, AJ_PO_NUMBER_COL).Value = poolPO

        ' Back-fill BKG_No col (col 8) with the pool's confirmed BKG
        If poolBkg <> "" Then wsJ.Cells(nr, AJ_BKG_NO).Value = poolBkg

        ' Update Pool row: HOLDING → ASSIGNED, record link back to AJ row
        On Error Resume Next
        wsPool.Cells(poolRow, 16).Value = "ASSIGNED"
        wsPool.Cells(poolRow, 17).Value = nr   ' Link_AJ_Row
        ' Clear yellow highlight, apply green for ASSIGNED
        wsPool.Rows(poolRow).Interior.ColorIndex = xlNone
        wsPool.Cells(poolRow, 16).Interior.Color = RGB(198, 239, 206)
        wsPool.Cells(poolRow, 16).Font.Color = RGB(0, 97, 0)
        On Error GoTo ErrHandler
    End If

    ' Step 7b: Cost Breakdown — v13 layout format
    '   Line 1: S/C: [contract] | CARRIER [type] [SOC?]
    '   Line 2: GROUP: [group code] (if ONE or has group)
    '   Line 3: COST: O/F $x + ARB $x + ISPS $x + ...
    '   Line 4: HDL FEE: CAR COM xx - ACCOUNT - $x/box
    '   Line 5: HDL/customer: [TBD - set in CRM]
    '   Line 6: ---
    '   Line 7: FREIGHT TOTAL/BOX: $x
    '   Line 8: TOTAL (Nx): $x
    Dim sCostBreakdown As String: sCostBreakdown = ""
    Dim noteVal As String: noteVal = CStr(wsQ.Cells(r, 8).Value)
    Dim isSOC As Boolean
    isSOC = (InStr(UCase(source), "SOC") > 0) Or (InStr(UCase(noteVal), "SOC") > 0)

    ' --- Collect charges from ChargeBreakdown sheet ---
    Dim charges As String: charges = ""
    Dim chargeTotal As Double: chargeTotal = 0

    On Error Resume Next
    Dim wsCB As Worksheet
    Set wsCB = ThisWorkbook.Sheets("ChargeBreakdown")
    On Error GoTo ErrHandler

    If Not wsCB Is Nothing Then
        Dim sKey As String
        sKey = UCase(pol) & "|" & UCase(pod) & "|" & UCase(place) & "|" & _
               UCase(carrier) & "|" & UCase(contType) & "|" & UCase(noteVal)
        Dim cbLastRow As Long
        cbLastRow = wsCB.Cells(wsCB.Rows.Count, 1).End(xlUp).Row

        Dim rCB As Long
        For rCB = 2 To cbLastRow
            If UCase(CStr(wsCB.Cells(rCB, 1).Value)) = sKey Then
                Dim chName As String: chName = CStr(wsCB.Cells(rCB, 2).Value)
                Dim chAmt As Double: chAmt = CDbl(wsCB.Cells(rCB, 3).Value)

                ' Skip PUC/PREMIUM SOC charges for COC
                If Not isSOC Then
                    If InStr(UCase(chName), "PUC") > 0 Then GoTo SkipCharge
                    If InStr(UCase(chName), "PREMIUM") > 0 And InStr(UCase(chName), "SOC") > 0 Then GoTo SkipCharge
                    If InStr(UCase(chName), "SOC COST") > 0 Then GoTo SkipCharge
                End If

                ' Skip HANDLING FEE — has its own HDL FEE line below
                If InStr(UCase(chName), "HANDLING FEE") > 0 Then GoTo SkipCharge

                ' Short name mapping (FAK column names)
                Dim sn As String
                Select Case True
                    Case InStr(UCase(chName), "BASIC") > 0:   sn = "O/F"
                    Case InStr(UCase(chName), "ARB") > 0:     sn = "ARB"
                    Case InStr(UCase(chName), "ISPS") > 0:    sn = "ISPS"
                    Case InStr(UCase(chName), "OCS") > 0:     sn = "OCS/LSS"
                    Case InStr(UCase(chName), "PSS") > 0:     sn = "PSS/PUC"
                    Case InStr(UCase(chName), "EIC") > 0:     sn = "EIC/BAF"
                    Case InStr(UCase(chName), "WHA") > 0:     sn = "WHA"
                    Case InStr(UCase(chName), "PCS") > 0:     sn = "EFS"
                    Case InStr(UCase(chName), "GRI") > 0:     sn = "GRI"
                    Case InStr(UCase(chName), "GARMENT") > 0: sn = "GARMENT"
                    Case InStr(UCase(chName), "PREMIUM") > 0: sn = "PREM/HDL US"
                    Case InStr(UCase(chName), "EMF") > 0:     sn = "EMF"
                    Case InStr(UCase(chName), "DLF") > 0:     sn = "DLF"
                    Case InStr(UCase(chName), "COMMISSION") > 0: sn = "COM"
                    Case InStr(UCase(chName), "CARBON") > 0:  sn = "CARBON"
                    Case InStr(UCase(chName), "EFS") > 0:     sn = "EFS"
                    Case Else: sn = Left(chName, 10)
                End Select

                If chAmt > 0 Then
                    If charges <> "" Then charges = charges & " + "
                    charges = charges & sn & " $" & Format(chAmt, "#,##0")
                    chargeTotal = chargeTotal + chAmt
                End If
SkipCharge:
            End If
        Next rCB
    End If

    ' --- HDL FEE from CostBreakdown module (v13 proven rules) ---
    Dim hdlLine As String: hdlLine = ""
    Dim hdlAmt As Double: hdlAmt = 0
    On Error Resume Next
    Dim hdlRule As CostBreakdown.HdlRule
    hdlRule = CostBreakdown.GetHdlRule(carrier, pol, source, contType)
    hdlAmt = CostBreakdown.GetHdlAmount(hdlRule, contType)
    If hdlRule.comType <> "" Then
        hdlLine = "HDL FEE: " & hdlRule.comType & " - " & hdlRule.account
        If hdlAmt > 0 Then
            hdlLine = hdlLine & " - $" & Format(hdlAmt, "#,##0") & "/box"
        Else
            hdlLine = hdlLine & " - FREE"
        End If
    End If
    On Error GoTo ErrHandler

    ' --- Build tooltip header (Phase 4 format) ---
    Dim scLine As String
    Dim isFAK As Boolean: isFAK = InStr(UCase(source), "FAK") > 0
    Dim isFIX As Boolean: isFIX = InStr(UCase(source), "FIX") > 0
    Dim isSCFI As Boolean: isSCFI = InStr(UCase(source), "SCFI") > 0
    Dim contractLabel As String
    If isSCFI Then
        contractLabel = "SCFI"
    ElseIf isFIX Then
        contractLabel = "Special Rate"
    Else
        contractLabel = "FAK"
    End If
    ' Phase 4: new tooltip header format:
    '   Rate Type: FAK (SOC)
    '   Contract: 25-4402
    '   Group: FAK PSW SOC
    '   Group Code: 990146     <- only ONE + non-empty groupCode
    Dim socSuffix As String: socSuffix = IIf(isSOC, " (SOC)", "")
    scLine = "Rate Type: " & contractLabel & socSuffix & Chr(10) & _
             "Contract: " & IIf(contractNo <> "", contractNo, source) & Chr(10) & _
             "Group: " & groupRate
    If UCase(carrier) = "ONE" And groupCode <> "" Then
        scLine = scLine & Chr(10) & "Group Code: " & groupCode
    End If

    ' --- Assemble full breakdown (v13 layout) ---
    If charges <> "" Then
        sCostBreakdown = scLine & Chr(10) & _
            "COST: " & charges & Chr(10)
        If hdlLine <> "" Then
            sCostBreakdown = sCostBreakdown & hdlLine & Chr(10)
        End If
        sCostBreakdown = sCostBreakdown & _
            "HDL/customer: [TBD - set in CRM]" & Chr(10) & _
            "---" & Chr(10) & _
            "FREIGHT TOTAL/BOX: $" & Format(chargeTotal + hdlAmt, "#,##0") & Chr(10) & _
            "TOTAL (" & qty & "x): $" & Format((chargeTotal + hdlAmt) * qty, "#,##0")
    Else
        ' Fallback: no ChargeBreakdown data
        sCostBreakdown = scLine & Chr(10) & _
            "COST: ALL-IN $" & Format(buyRate, "#,##0") & Chr(10)
        If hdlLine <> "" Then
            sCostBreakdown = sCostBreakdown & hdlLine & Chr(10)
        End If
        sCostBreakdown = sCostBreakdown & _
            "HDL/customer: [TBD - set in CRM]" & Chr(10) & _
            "---" & Chr(10) & _
            "FREIGHT TOTAL/BOX: $" & Format(buyRate + hdlAmt, "#,##0") & Chr(10) & _
            "TOTAL (" & qty & "x): $" & Format((buyRate + hdlAmt) * qty, "#,##0")
    End If

    ' Cell: compact 1-line summary | Comment: full v13-format breakdown
    Dim freightPerBox As Double
    freightPerBox = chargeTotal + hdlAmt
    If freightPerBox = 0 Then freightPerBox = buyRate + hdlAmt

    Dim compactText As String
    compactText = carrier & " " & contractLabel
    If isSOC Then compactText = compactText & " SOC"
    compactText = compactText & " | $" & Format(freightPerBox, "#,##0") & "/box"
    If qty > 1 Then compactText = compactText & " x" & qty & " = $" & Format(freightPerBox * qty, "#,##0")

    ' Hidden col 35: compact text for programmatic access
    wsJ.Cells(nr, AJ_COST_BKD).Value = compactText
    wsJ.Cells(nr, AJ_COST_BKD).Font.Name = "Segoe UI"
    wsJ.Cells(nr, AJ_COST_BKD).Font.Size = 9
    wsJ.Cells(nr, AJ_COST_BKD).WrapText = False

    ' v4 — full breakdown shows as hover comment on COST col (visible col 17)
    ' so Nelson sees breakdown without scrolling to hidden cols.
    On Error Resume Next
    wsJ.Cells(nr, AJ_BUY).ClearComments
    wsJ.Cells(nr, AJ_BUY).AddComment sCostBreakdown
    wsJ.Cells(nr, AJ_BUY).Comment.Shape.TextFrame.AutoSize = True
    wsJ.Cells(nr, AJ_BUY).Comment.Shape.Width = 350

    ' v4 — mailto: hyperlink for EMAIL col 19
    ' Phase 4: pass contractNo (real contract #) instead of source (rate type).
    ' groupRate + groupCode are Optional params added in Phase 4c.
    Call ERPv14JobsAutomation.ApplyBookingMailto( _
        wsJ.Cells(nr, AJ_EMAIL), _
        crmID, pol, pod, place, carrier, contType, qty, contractNo, _
        groupRate, groupCode)
    On Error GoTo ErrHandler

    ' Feature 5 — Commission + Insurance prompts (BEFORE confirm MsgBox).
    Dim commissionPct As Double: commissionPct = 0
    Dim commInput As String
    commInput = Trim(InputBox("Commission % for this job (0-100, default 0)?", _
                              "Commission - " & quoteID, "0"))
    If commInput = "" Then Exit Sub  ' user cancelled
    On Error Resume Next
    commissionPct = CDbl(commInput)
    If Err.Number <> 0 Then commissionPct = 0
    On Error GoTo ErrHandler
    If commissionPct < 0 Then commissionPct = 0
    If commissionPct > 100 Then commissionPct = 100

    Dim insuranceInput As String
    insuranceInput = UCase(Trim(InputBox("Insurance required? (Y/N, default N)", _
                                        "Insurance - " & quoteID, "N")))
    If insuranceInput = "" Then Exit Sub  ' user cancelled
    Dim needsInsurance As Boolean
    needsInsurance = (insuranceInput = "Y" Or insuranceInput = "YES")

    ' Feature 5a — Write to Commission sheet (create if missing)
    Dim wsComm As Worksheet
    On Error Resume Next
    Set wsComm = ThisWorkbook.Sheets("Commission")
    On Error GoTo ErrHandler
    If wsComm Is Nothing Then
        Set wsComm = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsComm.Name = "Commission"
        wsComm.Cells(1, 1).Value = "JobID"
        wsComm.Cells(1, 2).Value = "QuoteID"
        wsComm.Cells(1, 3).Value = "Customer"
        wsComm.Cells(1, 4).Value = "Commission_Pct"
        wsComm.Cells(1, 5).Value = "Created"
        wsComm.Cells(1, 6).Value = "Status"
        wsComm.Range("A1:F1").Font.Bold = True
        wsComm.Range("A1:F1").Interior.Color = RGB(21, 128, 61)
        wsComm.Range("A1:F1").Font.Color = RGB(255, 255, 255)
    End If
    Dim commRow As Long
    commRow = wsComm.Cells(wsComm.Rows.Count, 1).End(xlUp).Row + 1
    If commRow < 2 Then commRow = 2
    wsComm.Cells(commRow, 1).Value = ""      ' JobID — Nelson fills in (FAST_ID set later)
    wsComm.Cells(commRow, 2).Value = quoteID
    wsComm.Cells(commRow, 3).Value = customer
    wsComm.Cells(commRow, 4).Value = commissionPct
    wsComm.Cells(commRow, 4).NumberFormat = "0.00"
    wsComm.Cells(commRow, 5).Value = Now
    wsComm.Cells(commRow, 5).NumberFormat = "dd/mm/yyyy hh:mm"
    wsComm.Cells(commRow, 6).Value = "PENDING"

    ' Feature 5b — Write to Insurance sheet if insurance=Y (create if missing)
    If needsInsurance Then
        Dim wsIns As Worksheet
        On Error Resume Next
        Set wsIns = ThisWorkbook.Sheets("Insurance")
        On Error GoTo ErrHandler
        If wsIns Is Nothing Then
            Set wsIns = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
            wsIns.Name = "Insurance"
            wsIns.Cells(1, 1).Value = "JobID"
            wsIns.Cells(1, 2).Value = "QuoteID"
            wsIns.Cells(1, 3).Value = "Customer"
            wsIns.Cells(1, 4).Value = "Required"
            wsIns.Cells(1, 5).Value = "Notes"
            wsIns.Cells(1, 6).Value = "Status"
            wsIns.Cells(1, 7).Value = "Created"
            wsIns.Range("A1:G1").Font.Bold = True
            wsIns.Range("A1:G1").Interior.Color = RGB(194, 65, 12)
            wsIns.Range("A1:G1").Font.Color = RGB(255, 255, 255)
        End If
        Dim insRow As Long
        insRow = wsIns.Cells(wsIns.Rows.Count, 1).End(xlUp).Row + 1
        If insRow < 2 Then insRow = 2
        wsIns.Cells(insRow, 1).Value = ""    ' JobID — Nelson fills in
        wsIns.Cells(insRow, 2).Value = quoteID
        wsIns.Cells(insRow, 3).Value = customer
        wsIns.Cells(insRow, 4).Value = "Y"
        wsIns.Cells(insRow, 5).Value = ""    ' Notes — blank, Nelson fills in
        wsIns.Cells(insRow, 6).Value = "PENDING"
        wsIns.Cells(insRow, 7).Value = Now
        wsIns.Cells(insRow, 7).NumberFormat = "dd/mm/yyyy hh:mm"
    End If

    ' Step 8: Confirm
    Dim commNote As String
    If commissionPct > 0 Then commNote = " | Comm: " & commissionPct & "%" Else commNote = ""
    Dim insNote As String
    If needsInsurance Then insNote = " | Insurance: YES" Else insNote = ""
    Call MsgBoxOrSilent("Quote " & quoteID & " marked WIN!" & vbCrLf & vbCrLf & _
           "CRM: " & crmID & vbCrLf & _
           "Container: " & contType & " x " & qty & _
           " (" & totalTEU & " TEU)" & vbCrLf & _
           "Sell: $" & Format(sellRate, "#,##0") & _
           " | Buy: $" & Format(buyRate, "#,##0") & vbCrLf & _
           "Profit: $" & Format(profit, "#,##0") & _
           " (" & Format(margin * 100, "0.0") & "%)" & commNote & insNote, _
           vbInformation, "WIN Confirmed")
    Exit Sub

ErrHandler:
    MsgBox "Error: " & Err.Description, vbCritical, "MarkQuoteWin"
End Sub

' ============================================================
'  FEATURE 1 — RE-NEGOTIATE (Operations tab, grpQuoteStatus)
'  Allows Nelson to revise markup for any container type on a
'  PENDING/LOST quote row and appends an audit remark.
' ============================================================
Public Sub OnAction_Renegotiate(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Re-neg"
        Exit Sub
    End If
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Navigate to Quotes sheet first!", vbExclamation, "Re-neg"
        Exit Sub
    End If

    Dim r As Long: r = Selection.Row
    If r < QUOTES_DATA_START Then
        MsgBox "Select a quote row (row " & QUOTES_DATA_START & "+)!", vbExclamation, "Re-neg"
        Exit Sub
    End If

    Dim qid As String: qid = Trim(CStr(wsQ.Cells(r, 1).Value))
    If qid = "" Then
        MsgBox "No quote in this row!", vbExclamation, "Re-neg"
        Exit Sub
    End If

    ' Col map: Buy 12-18, Mar 19-25, Sell 29-35
    ' Types: 20GP=col12/19/29, 40GP=13/20/30, 40HC=14/21/31,
    '        45HC=15/22/32, 40NOR=16/23/33, 20RF=17/24/34, 40RF=18/25/35
    Dim contNames(0 To 6) As String
    Dim buyCols(0 To 6) As Integer
    Dim marCols(0 To 6) As Integer
    Dim sellCols(0 To 6) As Integer
    contNames(0) = "20GP":  buyCols(0) = 12: marCols(0) = 19: sellCols(0) = 29
    contNames(1) = "40GP":  buyCols(1) = 13: marCols(1) = 20: sellCols(1) = 30
    contNames(2) = "40HC":  buyCols(2) = 14: marCols(2) = 21: sellCols(2) = 31
    contNames(3) = "45HC":  buyCols(3) = 15: marCols(3) = 22: sellCols(3) = 32
    contNames(4) = "40NOR": buyCols(4) = 16: marCols(4) = 23: sellCols(4) = 33
    contNames(5) = "20RF":  buyCols(5) = 17: marCols(5) = 24: sellCols(5) = 34
    contNames(6) = "40RF":  buyCols(6) = 18: marCols(6) = 25: sellCols(6) = 35

    ' PUC cols (parallel to Buy/Sell for 20GP/40GP/40HC)
    Dim pucCols(0 To 6) As Integer
    pucCols(0) = 26: pucCols(1) = 27: pucCols(2) = 28
    pucCols(3) = 0:  pucCols(4) = 0:  pucCols(5) = 0: pucCols(6) = 0

    Dim changeLog As String: changeLog = ""
    Dim ci As Integer
    For ci = 0 To 6
        Dim oldBuy As Double: oldBuy = 0
        Dim oldMar As Double: oldMar = 0
        Dim oldPUC As Double: oldPUC = 0
        If IsNumeric(wsQ.Cells(r, buyCols(ci)).Value) Then oldBuy = CDbl(wsQ.Cells(r, buyCols(ci)).Value)
        If IsNumeric(wsQ.Cells(r, marCols(ci)).Value) Then oldMar = CDbl(wsQ.Cells(r, marCols(ci)).Value)
        If pucCols(ci) > 0 And IsNumeric(wsQ.Cells(r, pucCols(ci)).Value) Then
            oldPUC = CDbl(wsQ.Cells(r, pucCols(ci)).Value)
        End If

        ' Only prompt for container types that have an existing buy rate
        If oldBuy > 0 Then
            Dim promptStr As String
            promptStr = contNames(ci) & " — current margin $" & Format(oldMar, "#,##0") & _
                        " (Buy $" & Format(oldBuy, "#,##0") & " + PUC $" & Format(oldPUC, "#,##0") & ")"
            Dim newMarStr As String
            newMarStr = Trim(InputBox("New markup for " & contNames(ci) & _
                                     " (current: $" & Format(oldMar, "#,##0") & ")?", _
                                     "Re-neg " & qid, CStr(CLng(oldMar))))
            If newMarStr = "" Then Exit Sub  ' user cancelled — abort entire re-neg

            Dim newMar As Double: newMar = 0
            On Error Resume Next
            newMar = CDbl(newMarStr)
            If Err.Number <> 0 Then newMar = oldMar
            On Error GoTo ErrHandler

            ' Update Mar_* + recalc Sell_*
            wsQ.Cells(r, marCols(ci)).Value = newMar
            wsQ.Cells(r, sellCols(ci)).Value = oldBuy + newMar + oldPUC
            wsQ.Cells(r, sellCols(ci)).NumberFormat = "$#,##0"

            ' Track change for remark (only when value actually changed)
            If Abs(newMar - oldMar) > 0.5 Then
                If changeLog <> "" Then changeLog = changeLog & "; "
                changeLog = changeLog & contNames(ci) & " $" & Format(oldMar, "#,##0") & _
                            ChrW(8594) & "$" & Format(newMar, "#,##0")
            End If
        End If
    Next ci

    ' Append remark + update StatusDate
    If Len(changeLog) > 0 Then
        Dim existRemark As String: existRemark = Trim(CStr(wsQ.Cells(r, 37).Value))
        Dim reNegTag As String
        reNegTag = "[Re-neg " & Format(Now, "dd-mmm") & "] " & changeLog
        If Len(existRemark) > 0 Then
            wsQ.Cells(r, 37).Value = existRemark & " | " & reNegTag
        Else
            wsQ.Cells(r, 37).Value = reNegTag
        End If
        wsQ.Cells(r, 38).Value = Now  ' StatusDate col 38
    End If

    Call MsgBoxOrSilent("Re-neg complete for " & qid & "." & vbCrLf & _
           IIf(Len(changeLog) > 0, "Changes: " & changeLog, "No values changed."), _
           vbInformation, "Re-neg")
    Exit Sub

ErrHandler:
    MsgBox "Re-neg error: " & Err.Description, vbCritical, "Re-neg"
End Sub

' ============================================================
'  FEATURE 4 — TARGET WATCH (Operations tab, grpAlerts)
'  Adds a watch row to Target_Watch sheet so price_watch.py
'  can alert when a carrier hits Nelson's target price.
' ============================================================
Public Sub OnAction_TargetAdd(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Target Watch"
        Exit Sub
    End If
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Navigate to Quotes sheet and select a quote row first!", vbExclamation, "Target Watch"
        Exit Sub
    End If

    Dim r As Long: r = Selection.Row
    If r < QUOTES_DATA_START Then
        MsgBox "Select a quote row (row " & QUOTES_DATA_START & "+)!", vbExclamation, "Target Watch"
        Exit Sub
    End If

    Dim qid As String: qid = Trim(CStr(wsQ.Cells(r, 1).Value))
    If qid = "" Then
        MsgBox "No quote in this row!", vbExclamation, "Target Watch"
        Exit Sub
    End If

    ' Read quote data
    Dim twCust As String: twCust = Trim(CStr(wsQ.Cells(r, 3).Value))
    Dim twPOL As String: twPOL = Trim(CStr(wsQ.Cells(r, 5).Value))
    Dim twPOD As String: twPOD = Trim(CStr(wsQ.Cells(r, 6).Value))
    Dim twCarrier As String: twCarrier = Trim(CStr(wsQ.Cells(r, 4).Value))
    Dim twContType As String: twContType = Trim(CStr(wsQ.Cells(r, 42).Value))
    If twContType = "" Then twContType = "20GP"  ' fallback

    ' Pick current sell price (first non-zero Sell_* col)
    Dim twCurrSell As Double: twCurrSell = 0
    Dim sc As Integer
    For sc = 29 To 35
        If IsNumeric(wsQ.Cells(r, sc).Value) And CDbl(wsQ.Cells(r, sc).Value) > 0 Then
            twCurrSell = CDbl(wsQ.Cells(r, sc).Value)
            Exit For
        End If
    Next sc

    ' Prompt — target price
    Dim targetStr As String
    targetStr = Trim(InputBox("Target price USD (e.g. 1500)?", _
                              "Target Watch - " & qid, ""))
    If targetStr = "" Then Exit Sub
    Dim targetUSD As Double
    On Error Resume Next
    targetUSD = CDbl(targetStr)
    If Err.Number <> 0 Or targetUSD <= 0 Then
        MsgBox "Invalid target price.", vbExclamation, "Target Watch"
        Exit Sub
    End If
    On Error GoTo ErrHandler

    ' Prompt — container type
    Dim twContInput As String
    twContInput = Trim(InputBox("Container type (20GP/40GP/40HC/ANY, default " & twContType & ")?", _
                                "Target Watch - " & qid, twContType))
    If twContInput = "" Then Exit Sub
    twContType = UCase(twContInput)

    ' Write to Target_Watch sheet
    Dim twRemark As String: twRemark = ""
    Call WriteTargetWatchRow(qid, twCust, twPOL, twPOD, twCarrier, twContType, _
                             targetUSD, twCurrSell, twRemark)

    MsgBox "Target $" & Format(targetUSD, "#,##0") & " added for " & _
           twCust & " " & twPOL & ChrW(8594) & twPOD & vbCrLf & _
           "price_watch.py will alert when a matching rate is found.", _
           vbInformation, "Target Watch"
    Exit Sub

ErrHandler:
    MsgBox "Target Watch error: " & Err.Description, vbCritical, "Target Watch"
End Sub

' Shared helper — writes one row to Target_Watch per docs/s1v2-target-watch-schema.md.
' Called by OnAction_TargetAdd. Also callable by Python via Application.Run for tests.
' Columns A-P per schema: Target_ID, Created, QuoteID, Customer, POL, POD,
'   Carrier, ContType, Target_USD, CurrentQuote_USD, Status, LastCheck,
'   Matched_Rate, Matched_Carrier, Matched_Date, Remark.
Public Sub WriteTargetWatchRow(qid As String, cust As String, pol As String, _
                                pod As String, carr As String, cont As String, _
                                target As Double, currQuote As Double, remark As String)
    On Error GoTo ErrHandler

    ' Ensure Target_Watch sheet exists with header
    Dim wsTW As Worksheet
    On Error Resume Next
    Set wsTW = ThisWorkbook.Sheets("Target_Watch")
    On Error GoTo ErrHandler

    If wsTW Is Nothing Then
        Set wsTW = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsTW.Name = "Target_Watch"
        ' Header: A-P per schema
        Dim hdr As Variant
        hdr = Array("Target_ID", "Created", "QuoteID", "Customer", "POL", "POD", _
                    "Carrier", "ContType", "Target_USD", "CurrentQuote_USD", "Status", _
                    "LastCheck", "Matched_Rate", "Matched_Carrier", "Matched_Date", "Remark")
        Dim hi As Integer
        For hi = 0 To UBound(hdr)
            wsTW.Cells(1, hi + 1).Value = hdr(hi)
        Next hi
        wsTW.Range("A1:P1").Font.Bold = True
        wsTW.Range("A1:P1").Interior.Color = RGB(30, 64, 175)
        wsTW.Range("A1:P1").Font.Color = RGB(255, 255, 255)
        wsTW.Rows(1).RowHeight = 22
    End If

    ' Idempotency: check if QuoteID + ContType + Target_USD already exists
    Dim twLR As Long: twLR = wsTW.Cells(wsTW.Rows.Count, 1).End(xlUp).Row
    Dim twR As Long
    For twR = 2 To twLR
        Dim existQid As String: existQid = Trim(CStr(wsTW.Cells(twR, 3).Value))
        Dim existCont As String: existCont = UCase(Trim(CStr(wsTW.Cells(twR, 8).Value)))
        Dim existTarget As Double: existTarget = 0
        If IsNumeric(wsTW.Cells(twR, 9).Value) Then existTarget = CDbl(wsTW.Cells(twR, 9).Value)
        If existQid = qid And existCont = UCase(cont) And Abs(existTarget - target) < 0.5 Then
            MsgBox "Target already exists for " & qid & " " & cont & " $" & Format(target, "#,##0") & _
                   " (row " & twR & ").", vbExclamation, "Target Watch"
            Exit Sub
        End If
    Next twR

    ' Generate Target_ID: TW-YYYYMMDD-NNN (3-digit sequence within today)
    Dim today As String: today = Format(Now, "yyyymmdd")
    Dim seqNum As Long: seqNum = 1
    For twR = 2 To twLR
        Dim existTwId As String: existTwId = Trim(CStr(wsTW.Cells(twR, 1).Value))
        If Left(existTwId, 11) = "TW-" & today & "-" Then
            Dim existSeq As Long
            On Error Resume Next
            existSeq = CLng(Mid(existTwId, 12, 3))
            If Err.Number = 0 And existSeq >= seqNum Then seqNum = existSeq + 1
            On Error GoTo ErrHandler
        End If
    Next twR
    Dim targetID As String
    targetID = "TW-" & today & "-" & Format(seqNum, "000")

    ' Insert row at bottom
    Dim newRow As Long: newRow = twLR + 1
    If newRow < 2 Then newRow = 2

    wsTW.Cells(newRow, 1).Value = targetID         ' A: Target_ID
    wsTW.Cells(newRow, 2).Value = Now              ' B: Created
    wsTW.Cells(newRow, 2).NumberFormat = "dd/mm/yyyy hh:mm"
    wsTW.Cells(newRow, 3).Value = qid              ' C: QuoteID
    wsTW.Cells(newRow, 4).Value = cust             ' D: Customer
    wsTW.Cells(newRow, 5).Value = pol              ' E: POL
    wsTW.Cells(newRow, 6).Value = pod              ' F: POD
    wsTW.Cells(newRow, 7).Value = carr             ' G: Carrier
    wsTW.Cells(newRow, 8).Value = UCase(cont)      ' H: ContType
    wsTW.Cells(newRow, 9).Value = target           ' I: Target_USD
    wsTW.Cells(newRow, 9).NumberFormat = "#,##0"
    wsTW.Cells(newRow, 10).Value = currQuote       ' J: CurrentQuote_USD
    wsTW.Cells(newRow, 10).NumberFormat = "#,##0"
    wsTW.Cells(newRow, 11).Value = "WATCHING"      ' K: Status (initial)
    ' L: LastCheck — Python fills in
    ' M: Matched_Rate — Python fills in
    ' N: Matched_Carrier — Python fills in
    ' O: Matched_Date — Python fills in
    wsTW.Cells(newRow, 16).Value = remark          ' P: Remark
    Exit Sub

ErrHandler:
    MsgBox "WriteTargetWatchRow error: " & Err.Description, vbCritical, "Target Watch"
End Sub

' ============================================================
'  FEATURE 7 — RELOAD VBA (Operations tab, grpAdv)
'  Saves + closes workbook, then WMI-launches bootstrap bat
'  that re-imports all .bas modules and reopens the xlsm.
' ============================================================
Public Sub OnAction_ReloadVBA(control As IRibbonControl)
    On Error GoTo ErrHandler

    If MsgBox("This will save + close the workbook, re-import VBA modules, then reopen." & vbCrLf & _
              "Excel will be closed briefly. Continue?", _
              vbYesNo + vbQuestion, "Reload VBA") = vbNo Then Exit Sub

    ' Find bootstrap bat (reimport-erp-vba.bat) via the same multi-base search used by Refresh Rates
    Dim bootstrapBat As String
    bootstrapBat = FindScriptRR("scripts\reimport-erp-vba.bat")
    If bootstrapBat = "" Then
        ' Fallback: try the Python script directly via a cmd wrapper
        bootstrapBat = FindScriptRR("scripts\reimport-erp-vba-modules.py")
        If bootstrapBat = "" Then
            MsgBox "scripts\reimport-erp-vba.bat (or reimport-erp-vba-modules.py) not found." & vbCrLf & _
                   "Check Engine_test repo path.", vbExclamation, "Reload VBA"
            Exit Sub
        End If
    End If

    Dim fullPath As String: fullPath = ThisWorkbook.FullName

    ' WMI Win32_Process.Create so child runs OUTSIDE Excel Job Object
    ' Per SYSTEM_STANDARDS §5.1 — Shell/wsh.Run children get killed when Excel exits.
    Dim bootCmd As String
    ' Detect if we have a .bat or .py
    If Right(LCase(bootstrapBat), 4) = ".bat" Then
        bootCmd = "cmd /c """"" & bootstrapBat & """ """ & fullPath & """"""
    Else
        ' Direct Python launch
        Dim pyExe As String: pyExe = "C:\Users\Nelson\anaconda3\python"
        bootCmd = "cmd /c """ & pyExe & " """ & bootstrapBat & """ """ & fullPath & """"""
    End If

    Dim wmi As Object
    Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
    Dim procId As Variant
    Dim rcCreate As Long
    rcCreate = wmi.Create(bootCmd, Null, Null, procId)
    If rcCreate <> 0 Then
        MsgBox "Could not launch VBA reload bootstrap (WMI rc=" & rcCreate & ").", _
               vbCritical, "Reload VBA"
        Exit Sub
    End If

    ' Save + close — bootstrap polls file lock (30s) then runs Python + reopens xlsm
    Application.StatusBar = "Reload VBA: closing workbook (re-import runs in background)..."
    Application.DisplayAlerts = False
    ThisWorkbook.Close SaveChanges:=True
    Exit Sub

ErrHandler:
    Application.DisplayAlerts = True
    Application.StatusBar = False
    MsgBox "Reload VBA error: " & Err.Description, vbCritical, "Reload VBA"
End Sub

Public Sub OnAction_MarkQuoteLost(control As IRibbonControl)
    ' P3 2026-04-12 — use Application.InputBox(Type:=2) for Unicode support.
    ' Old VBA InputBox() strips Vietnamese diacritics (đ/ê/ô... -> ? ?).
    ' Application.InputBox preserves UTF-16 text properly.
    On Error Resume Next
    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then Exit Sub
    If Not ActiveSheet.Name = wsQ.Name Then
        MsgBox "Navigate to Quotes sheet first!", vbExclamation, "Mark LOST"
        Exit Sub
    End If

    Dim r As Long: r = Selection.Row
    If r < 2 Then Exit Sub

    Dim reasonVar As Variant
    reasonVar = Application.InputBox( _
        Prompt:="Lý do LOST? (ghi tiếng Việt có dấu OK)", _
        Title:="Mark LOST - " & wsQ.Cells(r, 1).Value, _
        Type:=2)  ' Type:=2 = Text input, preserves Unicode
    If VarType(reasonVar) = vbBoolean Then Exit Sub  ' User clicked Cancel
    Dim reason As String: reason = CStr(reasonVar)
    If Len(Trim(reason)) = 0 Then Exit Sub

    wsQ.Cells(r, 36).Value = "LOST"
    wsQ.Cells(r, 37).Value = reason
    wsQ.Cells(r, 38).Value = Now
    Call MsgBoxOrSilent("Quote marked as LOST.", vbInformation, "ERP v14")
    On Error GoTo 0
End Sub

Public Sub OnAction_CheckAutoLost(control As IRibbonControl)
    ERPv14Core.AutoExpireOnOpen
    Call MsgBoxOrSilent("Auto-expire check complete.", vbInformation, "ERP v14")
End Sub

' ============================================================
'  CANCEL JOB — ADR-001 Option B (2026-04-12)
'  User cancels a booked job: move row from Active Jobs to
'  Cancelled_Jobs sheet (6 visible cols + QuoteID/CRMID hidden).
'  History preserved for analytics ("cancel rate per carrier").
' ============================================================
Public Sub OnAction_CancelJob(Optional control As IRibbonControl = Nothing)
    On Error GoTo ErrHandler

    ' Active Jobs v4 column constants (matches OnAction_MarkQuoteWin layout)
    ' Source of truth: ERP/core/active_jobs_cols.py
    Const AJ_DATA_START As Long = 8
    Const AJ_CRMID As Long = 4          ' CUSTOMER
    Const AJ_CARRIER As Long = 7
    Const AJ_BKG_NO As Long = 8
    Const AJ_ROUTING As Long = 20       ' hidden — raw "HPH-USLGB" for cancel log

    ' 1. Must be on Active Jobs sheet
    Dim wsJ As Worksheet
    Set wsJ = ERPv14Core.FindSheet("Active Jobs")
    If wsJ Is Nothing Then
        MsgBox "Active Jobs sheet not found!", vbExclamation, "Cancel Job"
        Exit Sub
    End If
    If Not ActiveSheet.Name = wsJ.Name Then
        MsgBox "Navigate to Active Jobs sheet first!", vbExclamation, "Cancel Job"
        Exit Sub
    End If

    ' 2. Row must be in data range (>= row 8)
    Dim r As Long: r = Selection.Row
    If r < AJ_DATA_START Then
        MsgBox "Select a job row (row " & AJ_DATA_START & "+)!", vbExclamation, "Cancel Job"
        Exit Sub
    End If

    Dim crmID As String: crmID = CStr(wsJ.Cells(r, AJ_CRMID).Value)
    Dim routing As String: routing = CStr(wsJ.Cells(r, AJ_ROUTING).Value)
    Dim bkgNo As String: bkgNo = CStr(wsJ.Cells(r, AJ_BKG_NO).Value)
    Dim carrier As String: carrier = CStr(wsJ.Cells(r, AJ_CARRIER).Value)

    If Len(Trim(crmID)) = 0 And Len(Trim(routing)) = 0 Then
        MsgBox "Empty row — nothing to cancel!", vbExclamation, "Cancel Job"
        Exit Sub
    End If

    ' 3. Prompt for booking# (if missing) and reason (Unicode-safe)
    If Len(Trim(bkgNo)) = 0 Then
        Dim bkgVar As Variant
        bkgVar = Application.InputBox( _
            Prompt:="Booking number (optional, for reference):", _
            Title:="Cancel Job - " & routing, _
            Type:=2)
        If VarType(bkgVar) = vbBoolean Then Exit Sub
        bkgNo = CStr(bkgVar)
    End If

    Dim reasonVar As Variant
    reasonVar = Application.InputBox( _
        Prompt:="Lý do cancel? (Vietnamese có dấu OK)", _
        Title:="Cancel Job - " & routing, _
        Type:=2)
    If VarType(reasonVar) = vbBoolean Then Exit Sub
    Dim reason As String: reason = CStr(reasonVar)
    If Len(Trim(reason)) = 0 Then
        MsgBox "Reason required to cancel.", vbExclamation, "Cancel Job"
        Exit Sub
    End If

    ' 4. Ensure Cancelled_Jobs sheet exists (lazy init with header)
    Dim wsCJ As Worksheet
    On Error Resume Next
    Set wsCJ = ThisWorkbook.Sheets("Cancelled_Jobs")
    On Error GoTo ErrHandler
    If wsCJ Is Nothing Then
        Set wsCJ = ThisWorkbook.Sheets.Add(After:=wsJ)
        wsCJ.Name = "Cancelled_Jobs"
        ' Header row (7 cols: 6 visible + QuoteID/CRMID for audit)
        wsCJ.Cells(1, 1).Value = "Customer"
        wsCJ.Cells(1, 2).Value = "Routing"
        wsCJ.Cells(1, 3).Value = "Carrier"
        wsCJ.Cells(1, 4).Value = "Booking_No"
        wsCJ.Cells(1, 5).Value = "Cancel_Date"
        wsCJ.Cells(1, 6).Value = "Cancel_Reason"
        wsCJ.Cells(1, 7).Value = "CRM_ID"  ' hidden audit link back to Active Jobs
        ' Format header: bold + blue fill
        Dim hdrRange As Range
        Set hdrRange = wsCJ.Range("A1:G1")
        hdrRange.Font.Bold = True
        hdrRange.Font.Color = vbWhite
        hdrRange.Font.Name = "Segoe UI"
        hdrRange.Font.Size = 10
        hdrRange.Interior.Color = RGB(239, 68, 68)  ' red-500 (cancel theme)
        hdrRange.HorizontalAlignment = xlCenter
        ' Column widths
        wsCJ.Columns(1).ColumnWidth = 20  ' Customer
        wsCJ.Columns(2).ColumnWidth = 28  ' Routing
        wsCJ.Columns(3).ColumnWidth = 10  ' Carrier
        wsCJ.Columns(4).ColumnWidth = 18  ' Booking_No
        wsCJ.Columns(5).ColumnWidth = 13  ' Cancel_Date
        wsCJ.Columns(6).ColumnWidth = 40  ' Cancel_Reason
        wsCJ.Columns(7).Hidden = True     ' CRM_ID hidden audit col
        wsCJ.Rows(1).RowHeight = 22
    End If

    ' 5. Append to Cancelled_Jobs (first empty row from bottom)
    Dim cjRow As Long
    cjRow = wsCJ.Cells(wsCJ.Rows.Count, 1).End(xlUp).Row + 1
    If cjRow < 2 Then cjRow = 2
    wsCJ.Cells(cjRow, 1).Value = crmID     ' Customer (from CRM_ID col)
    wsCJ.Cells(cjRow, 2).Value = routing
    wsCJ.Cells(cjRow, 3).Value = carrier
    wsCJ.Cells(cjRow, 4).Value = bkgNo
    wsCJ.Cells(cjRow, 5).Value = Now
    wsCJ.Cells(cjRow, 5).NumberFormat = "dd/mm hh:mm"
    wsCJ.Cells(cjRow, 6).Value = reason
    wsCJ.Cells(cjRow, 7).Value = crmID     ' hidden audit link

    ' Style the new row
    Dim newRng As Range
    Set newRng = wsCJ.Range(wsCJ.Cells(cjRow, 1), wsCJ.Cells(cjRow, 7))
    newRng.Font.Name = "Segoe UI"
    newRng.Font.Size = 10
    newRng.Borders.LineStyle = xlContinuous
    newRng.Borders.Color = RGB(200, 200, 200)

    ' 6. Delete the row from Active Jobs
    wsJ.Rows(r).Delete

    ' 7. Confirm via status bar (non-blocking)
    Application.StatusBar = "Cancelled: " & routing & " | " & bkgNo & " -> Cancelled_Jobs row " & cjRow
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Cancel Job error: " & Err.Description, vbCritical, "Cancel Job"
End Sub

' ============================================================
'  TAB 2: OPERATIONS — Reports
' ============================================================
Public Sub OnAction_MonthlyReport(control As IRibbonControl)
    ' v4 — delegate to ERPv14JobsAutomation.OnAction_MonthlyReportV4
    ' Old stub replaced 2026-04-14. New button in CustomUI uses the V4 handler
    ' directly; this wrapper keeps legacy .onAction bindings working.
    On Error Resume Next
    Application.Run "ERPv14JobsAutomation.OnAction_MonthlyReportV4", control
    If Err.Number <> 0 Then
        Call MsgBoxOrSilent( _
             "Monthly Report V4 module not imported yet." & vbCrLf & _
             "Import erp-v14-jobs-automation.bas into this workbook.", _
             vbExclamation, "Monthly Report")
    End If
    On Error GoTo 0
End Sub

Public Sub OnAction_JobsSummary(control As IRibbonControl)
    ERPv14Core.RefreshJobsSummary
    Call MsgBoxOrSilent("Jobs summary refreshed. Check Immediate Window for details.", _
           vbInformation, "ERP v14")
End Sub

' ============================================================
'  TAB 2: OPERATIONS — Tools
' ============================================================
Public Sub OnAction_RefreshColors(control As IRibbonControl)
    ERPv14Core.ApplyRateFreshnessColors
    Call MsgBoxOrSilent("Rate freshness colors applied.", vbInformation, "ERP v14")
End Sub

Public Sub OnAction_ClearSearch(control As IRibbonControl)
    On Error Resume Next
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub

    ' Reset search comboBox state (getText will return empty)
    m_SearchCarrier = ""
    m_SearchPOL = ""
    m_SearchPOD = ""
    m_SearchPlace = ""
    ' Fix 1: Exp resets to "Active only", not blank
    m_ExpPreset = EXP_PRESET_ACTIVE
    m_SearchExp = EXP_PRESET_ACTIVE
    m_SearchNote = ""

    Application.EnableEvents = False
    Dim c As Integer
    For c = 1 To 9
        ERPv14Core.RestorePlaceholder c
    Next c
    Application.EnableEvents = True
    ERPv14Core.ApplyQuickSearch

    ' Clear highlight colors
    Dim lr As Long: lr = ws.Cells(ws.Rows.Count, COL_POL).End(xlUp).Row
    If lr >= DATA_START_ROW Then
        Dim r As Long
        For r = DATA_START_ROW To lr
            Dim pc As Integer
            For pc = COL_20GP To COL_40RF
                ws.Cells(r, pc).Interior.ColorIndex = xlNone
            Next pc
        Next r
    End If

    ' Invalidate ribbon to clear comboBox text
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    On Error GoTo 0
End Sub

' ============================================================
'  TAB 2: OPERATIONS — Rate Data (Refresh + Version labels)
' ============================================================

' Refresh Rates — calls Python refresh-v14.py via async bootstrap.
' 2026-04-17 FIX (Nelson): previous implementation closed ThisWorkbook
' then called wsh.Run — Excel aborts VBA when host workbook closes,
' so Python never ran. New flow: Shell async bootstrap BEFORE close.
Public Sub OnAction_RefreshRates(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")

    ' Find the rates-only bootstrap (skips Outlook scan / rate_importer).
    Dim bootstrapBat As String: bootstrapBat = FindScriptRR("scripts\refresh-rates-bootstrap.bat")
    If bootstrapBat = "" Then
        MsgBox "scripts\refresh-rates-bootstrap.bat not found — check Engine_test repo path.", _
               vbExclamation, "Refresh Rates"
        Exit Sub
    End If

    If MsgBox("Refresh rates from Parquet?" & vbCrLf & _
              "File will close, refresh runs in background, then reopens.", _
              vbYesNo + vbQuestion, "Refresh Rates") = vbNo Then Exit Sub

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folderPath As String: folderPath = fso.GetParentFolderName(fullPath)
    Dim logFile As String: logFile = folderPath & "\refresh_log.txt"

    ' Launch via WMI Win32_Process.Create so the child runs OUTSIDE Excel's
    ' Job Object (Shell/wsh.Run children are killed when Excel exits).
    Dim bootCmd As String
    bootCmd = "cmd /c """"" & bootstrapBat & """ """ & fullPath & """ """ & logFile & """"""
    Dim wmi As Object
    Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
    Dim procId As Variant
    Dim rcCreate As Long
    rcCreate = wmi.Create(bootCmd, Null, Null, procId)
    If rcCreate <> 0 Then
        MsgBox "Could not launch refresh bootstrap (WMI rc=" & rcCreate & ").", _
               vbCritical, "Refresh Rates"
        Exit Sub
    End If

    ' Save + close. Bootstrap takes over.
    Application.StatusBar = "Refresh Rates: closing workbook (refresh runs in background)..."
    Application.DisplayAlerts = False
    ThisWorkbook.Save
    ThisWorkbook.Close SaveChanges:=False
    Exit Sub

ErrHandler:
    Application.DisplayAlerts = True
    Application.StatusBar = False
    MsgBox "Refresh error: " & Err.Description, vbCritical, "Refresh Rates"
End Sub

' Local FindScript for this module (the one in erp-v14-jobs-automation.bas is Private)
Private Function FindScriptRR(relPath As String) As String
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    Dim bases As Variant
    bases = Array( _
        "D:\NELSON\2. Areas\Engine_test\", _
        "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\", _
        fso.GetParentFolderName(ThisWorkbook.FullName) & "\..\..\..\" _
    )
    Dim i As Long, p As String
    For i = 0 To UBound(bases)
        p = CStr(bases(i)) & relPath
        p = Replace(p, "/", "\")
        If fso.FileExists(p) Then FindScriptRR = p: Exit Function
    Next i
    FindScriptRR = ""
End Function

' Last refresh timestamp — picks LATEST mtime across known refresh artefacts.
' Why multi-file: OneDrive sync sometimes rolls back refresh_status.txt to
' an older version after Python writes it (race condition on shared paths).
' refresh_all_log.txt updates reliably (append-only, less conflict-prone).
Public Sub GetLabel_LastRefresh(control As IRibbonControl, ByRef label As Variant)
    On Error Resume Next
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")

    Dim folder As String
    folder = ThisWorkbook.Path
    If Not fso.FolderExists(folder) Then folder = "D:\OneDrive\NelsonData\erp"

    Dim candidates(0 To 3) As String
    candidates(0) = folder & "\refresh_status.txt"
    candidates(1) = folder & "\refresh_all_log.txt"
    candidates(2) = folder & "\refresh_log.txt"
    candidates(3) = "D:\OneDrive\NelsonData\erp\refresh_all_log.txt"

    Dim latest As Date: latest = #1/1/2000#
    Dim i As Long
    For i = 0 To 3
        If fso.FileExists(candidates(i)) Then
            Dim dt As Date: dt = fso.GetFile(candidates(i)).DateLastModified
            If dt > latest Then latest = dt
        End If
    Next i

    If latest = #1/1/2000# Then
        label = "Last refresh: never"
    Else
        label = "Last refresh: " & Format(latest, "dd mmm hh:nn")
    End If
End Sub

' Rate Version labels — read from RateVersions sheet
Public Sub GetLabel_RateVer1(control As IRibbonControl, ByRef label As Variant)
    label = ReadRateVersion(1)
End Sub
Public Sub GetLabel_RateVer2(control As IRibbonControl, ByRef label As Variant)
    label = ReadRateVersion(2)
End Sub
Public Sub GetLabel_RateVer3(control As IRibbonControl, ByRef label As Variant)
    label = ReadRateVersion(3)
End Sub
Public Sub GetLabel_RateVer4(control As IRibbonControl, ByRef label As Variant)
    label = ReadRateVersion(4)
End Sub

Private Function ReadRateVersion(idx As Long) As String
    On Error Resume Next
    Dim wsRV As Worksheet
    Set wsRV = ThisWorkbook.Sheets("RateVersions")
    If wsRV Is Nothing Then
        If idx = 1 Then ReadRateVersion = "No rate data" Else ReadRateVersion = ""
        Exit Function
    End If

    Dim r As Long: r = idx + 1  ' row 2 = first version
    Dim vType As String: vType = Trim(CStr(wsRV.Cells(r, 1).Value))
    Dim vName As String: vName = Trim(CStr(wsRV.Cells(r, 2).Value))

    If vType = "" And vName = "" Then
        ReadRateVersion = ""
    Else
        ReadRateVersion = vType & ": " & vName
    End If
    On Error GoTo 0
End Function

' ============================================================
'  QUOTE IMAGE — Generate HTML quote → open in browser
'  Select rows on Quotes sheet → click Quote Image → browser opens
'  P5 2026-04-13 — Rewritten: Excel table → premium HTML (Option F)
' ============================================================
Public Sub OnAction_QuoteImage(Optional control As IRibbonControl = Nothing)
    On Error GoTo ErrHandler

    ' Quotes col map: 1=QuoteID 2=Date 3=Customer 4=Carrier
    '   5=POL 6=POD 7=Place 8=Note 9=Eff 10=Exp 11=Source
    '   29=Sell_20GP 30=Sell_40GP 31=Sell_40HC 32=Sell_45HC
    '   33=Sell_40NOR 34=Sell_20RF 35=Sell_40RF
    ' 2026-04-15: reefer fix — previously only read 29+31 (dry only), so
    ' reefer quotes rendered empty prices in the image. Now reads all 7
    ' Sell_* cols and picks the right pair per row (dry vs reefer).
    Const Q_CUST As Integer = 3
    Const Q_CARRIER As Integer = 4
    Const Q_POL As Integer = 5
    Const Q_POD As Integer = 6
    Const Q_PLACE As Integer = 7
    Const Q_NOTE As Integer = 8
    Const Q_EFF As Integer = 9
    Const Q_EXP As Integer = 10
    Const Q_SELL_20GP As Integer = 29
    Const Q_SELL_40GP As Integer = 30
    Const Q_SELL_40HC As Integer = 31
    Const Q_SELL_45HC As Integer = 32
    Const Q_SELL_40NOR As Integer = 33
    Const Q_SELL_20RF As Integer = 34
    Const Q_SELL_40RF As Integer = 35
    Const QUOTE_DIR As String = "D:\OneDrive\NelsonData\erp\quote-mockups\"

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        Call MsgBoxOrSilent("Quotes sheet not found!", vbExclamation, "Quote Image")
        Exit Sub
    End If
    If Not ActiveSheet.Name = wsQ.Name Then
        Call MsgBoxOrSilent("Navigate to Quotes sheet first!", vbExclamation, "Quote Image")
        Exit Sub
    End If

    ' ── Collect selected rows (multi-area Ctrl+click) ──
    Dim rowNums() As Long
    Dim rowCount As Long: rowCount = 0
    Dim selArea As Range
    Dim sr As Long, isDup As Boolean, chk As Long, ri As Long
    For Each selArea In Selection.Areas
        For ri = 1 To selArea.Rows.Count
            sr = selArea.Rows(ri).Row
            If sr >= 2 And Trim(wsQ.Cells(sr, 1).Value) <> "" Then
                isDup = False
                If rowCount > 0 Then
                    For chk = 1 To rowCount
                        If rowNums(chk) = sr Then isDup = True: Exit For
                    Next chk
                End If
                If Not isDup Then
                    rowCount = rowCount + 1
                    ReDim Preserve rowNums(1 To rowCount)
                    rowNums(rowCount) = sr
                End If
            End If
        Next ri
    Next selArea

    If rowCount = 0 Then
        Call MsgBoxOrSilent("Select quote rows (row 2+) first!", vbExclamation, "Quote Image")
        Exit Sub
    End If

    ' ── Read customer + date ──
    ' Bulk mode: caller set m_BulkCustomerName -> use that instead of row 1
    ' so the same selection renders N files for N different customers.
    Dim customer As String
    If Len(m_BulkCustomerName) > 0 Then
        customer = m_BulkCustomerName
    Else
        customer = Trim(CStr(wsQ.Cells(rowNums(1), Q_CUST).Value))
    End If
    Dim quoteDate As String: quoteDate = Format(wsQ.Cells(rowNums(1), 2).Value, "dd MMM yyyy")

    ' ── Build row data array ──
    ' Columns: 0=POL 1=Dest 2=Via 3=Carrier 4=Sell20 5=Sell40
    '          6=Svc 7=Routing 8=Valid 9=ContainerKind ("GP"/"RF")
    Dim d() As String
    ReDim d(1 To rowCount, 0 To 9)
    Dim i As Long, qr As Long
    Dim polCode As String, podName As String, placeName As String, noteRaw As String
    Dim destName As String, viaName As String, svcType As String, routing As String
    Dim effStr As String, expStr As String

    ' Aggregate mode detection — used for header bar labels.
    Dim cntDry As Long: cntDry = 0
    Dim cntRef As Long: cntRef = 0

    For i = 1 To rowCount
        qr = rowNums(i)
        polCode = UCase(Trim(CStr(wsQ.Cells(qr, Q_POL).Value)))
        podName = Trim(CStr(wsQ.Cells(qr, Q_POD).Value))
        placeName = Trim(CStr(wsQ.Cells(qr, Q_PLACE).Value))
        noteRaw = Trim(CStr(wsQ.Cells(qr, Q_NOTE).Value))

        ' Destination + via
        If placeName <> "" Then
            destName = UCase(placeName)
            If podName <> "" And UCase(podName) <> UCase(placeName) Then
                viaName = podName
            Else
                viaName = ""
            End If
        Else
            destName = UCase(podName)
            viaName = ""
        End If

        ' Parse note → SOC/COC + routing
        If InStr(1, noteRaw, "SOC", vbTextCompare) > 0 Then
            svcType = "SOC"
            routing = Trim(Replace(noteRaw, "SOC", "", , , vbTextCompare))
        Else
            svcType = "COC"
            routing = noteRaw
        End If
        routing = Trim(Replace(routing, "  ", " "))
        If routing = "" Then routing = "Direct"

        ' Valid date range
        effStr = "": expStr = ""
        If IsDate(wsQ.Cells(qr, Q_EFF).Value) Then effStr = Format(wsQ.Cells(qr, Q_EFF).Value, "dd MMM")
        If IsDate(wsQ.Cells(qr, Q_EXP).Value) Then expStr = Format(wsQ.Cells(qr, Q_EXP).Value, "dd MMM")

        ' Container pair — pick dry vs reefer per-row based on which
        ' Sell_* cells have a value. Reefer cells (20RF/40RF/40NOR) take
        ' precedence when present. Fixes 2026-04-15: reefer quotes had
        ' empty rates because QuoteImage only read cols 29+31 (dry).
        Dim v20gp As Double, v40gp As Double, v40hc As Double, v45hc As Double
        Dim v40nor As Double, v20rf As Double, v40rf As Double
        Dim pick20 As Double, pick40 As Double, kind As String
        v20gp = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_20GP).Value)
        v40gp = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_40GP).Value)
        v40hc = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_40HC).Value)
        v45hc = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_45HC).Value)
        v40nor = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_40NOR).Value)
        v20rf = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_20RF).Value)
        v40rf = ERPv14Core.SL(wsQ.Cells(qr, Q_SELL_40RF).Value)

        ' 2026-04-15: 40NOR (Non-Operating Reefer) is a DRY cargo rate — reefer
        ' box running unplugged, used when 40HC/40GP out of stock. Must NOT
        ' classify as reefer. True reefer only when 20RF or 40RF > 0.
        If v20rf > 0 Or v40rf > 0 Then
            ' True reefer row: 20RF + 40RF
            pick20 = v20rf
            pick40 = v40rf
            kind = "RF"
            cntRef = cntRef + 1
        Else
            ' Dry row: 20GP + (40HC, fallback 40NOR, fallback 40GP, fallback 45HC)
            pick20 = v20gp
            If v40hc > 0 Then
                pick40 = v40hc
            ElseIf v40nor > 0 Then
                pick40 = v40nor
            ElseIf v40gp > 0 Then
                pick40 = v40gp
            Else
                pick40 = v45hc
            End If
            kind = "GP"
            cntDry = cntDry + 1
        End If

        d(i, 0) = polCode
        d(i, 1) = destName
        d(i, 2) = viaName
        d(i, 3) = Trim(CStr(wsQ.Cells(qr, Q_CARRIER).Value))
        d(i, 4) = CStr(pick20)
        d(i, 5) = CStr(pick40)
        d(i, 6) = svcType
        d(i, 7) = routing
        d(i, 9) = kind
        If effStr <> "" And expStr <> "" And effStr <> expStr Then
            d(i, 8) = effStr & " &ndash; " & expStr
        ElseIf expStr <> "" Then
            d(i, 8) = expStr
        ElseIf effStr <> "" Then
            d(i, 8) = effStr
        Else
            d(i, 8) = ""
        End If
    Next i

    ' ── Build ordered POL + Dest lists ──
    Dim polOrd As Object: Set polOrd = CreateObject("Scripting.Dictionary")
    Dim destOrd As Object: Set destOrd = CreateObject("Scripting.Dictionary")
    Dim dk As String
    For i = 1 To rowCount
        If Not polOrd.Exists(d(i, 0)) Then polOrd.Add d(i, 0), polOrd.Count + 1
        dk = d(i, 0) & "|" & d(i, 1) & "|" & d(i, 2)
        If Not destOrd.Exists(dk) Then destOrd.Add dk, destOrd.Count + 1
    Next i

    ' ══════════════════════════════════════════════════════════
    '  HTML GENERATION — Option F premium layout
    ' ══════════════════════════════════════════════════════════
    Dim h As String
    Dim Q As String: Q = """"  ' helper for double-quote in HTML

    ' DOCTYPE + head
    h = "<!DOCTYPE html><html lang=" & Q & "vi" & Q & "><head>" & vbCrLf
    h = h & "<meta charset=" & Q & "UTF-8" & Q & ">" & vbCrLf
    h = h & "<title>Quote " & customer & "</title>" & vbCrLf
    h = h & "<style>" & vbCrLf & QuoteImageCSS() & vbCrLf & "</style>" & vbCrLf
    h = h & "</head><body>" & vbCrLf
    h = h & "<div class=" & Q & "quote" & Q & ">" & vbCrLf

    ' ── Header: logo + brand + customer ──
    h = h & "<div class=" & Q & "q-head" & Q & ">" & vbCrLf
    h = h & " <div class=" & Q & "brand" & Q & ">" & vbCrLf
    h = h & "  <img src=" & Q & QI_LogoDataURI() & Q & " alt=" & Q & "PPG" & Q & " class=" & Q & "logo" & Q & ">" & vbCrLf
    h = h & "  <div class=" & Q & "brand-text" & Q & ">" & vbCrLf
    h = h & "   <span class=" & Q & "brand-name" & Q & ">Pudong Prime Group</span>" & vbCrLf
    h = h & "   <span class=" & Q & "brand-sub" & Q & ">Ocean Freight Quotation</span>" & vbCrLf
    h = h & "  </div></div>" & vbCrLf
    h = h & " <div class=" & Q & "meta" & Q & ">" & vbCrLf
    h = h & "  <span class=" & Q & "customer" & Q & ">" & customer & "</span>" & vbCrLf
    h = h & "  <span class=" & Q & "date" & Q & ">" & quoteDate & " &middot; USD</span>" & vbCrLf
    h = h & " </div></div>" & vbCrLf

    ' ── Column header bar — labels reflect container kind mix ──
    '   All dry     → 20GP / 40HC
    '   All reefer  → 20RF / 40RF
    '   Mixed       → 20' / 40' (per-row badge shows kind)
    Dim hdr20 As String, hdr40 As String, isMixed As Boolean
    isMixed = (cntDry > 0 And cntRef > 0)
    If isMixed Then
        hdr20 = "20'": hdr40 = "40'"
    ElseIf cntRef > 0 Then
        hdr20 = "20RF": hdr40 = "40RF"
    Else
        hdr20 = "20GP": hdr40 = "40HC"
    End If

    h = h & "<div class=" & Q & "col-bar" & Q & ">"
    h = h & "<span>Carrier</span>"
    h = h & "<span class=" & Q & "r" & Q & ">" & hdr20 & "</span>"
    h = h & "<span class=" & Q & "r" & Q & ">" & hdr40 & "</span>"
    h = h & "<span>Valid</span>"
    h = h & "<span>Svc</span>"
    h = h & "<span>Routing</span>"
    h = h & "</div>" & vbCrLf

    ' ── POL → Dest → Rate rows ──
    Dim polKeys As Variant: polKeys = polOrd.Keys
    Dim destKeys As Variant: destKeys = destOrd.Keys
    Dim pk As Long, dki As Long, dkParts() As String
    Dim firstDest As Boolean, j As Long
    Dim destRows() As Long, drCount As Long
    Dim bestIdx As Long, bestPrice As Double, p40v As Long
    Dim rowCls As String, s20 As Long, s40 As Long, svcCls As String
    Dim di As Long

    For pk = 0 To polOrd.Count - 1
        polCode = CStr(polKeys(pk))

        ' POL gradient bar
        h = h & "<div class=" & Q & "pol-bar " & QI_POLClass(polCode) & Q & ">"
        h = h & polCode & " <span class=" & Q & "name" & Q & ">"
        h = h & QI_POLName(polCode) & "</span></div>" & vbCrLf

        firstDest = True
        For dki = 0 To destOrd.Count - 1
            dkParts = Split(CStr(destKeys(dki)), "|")
            If dkParts(0) <> polCode Then GoTo SkipDest

            ' Separator between dest blocks (not before first)
            If Not firstDest Then h = h & "<div class=" & Q & "dest-sep" & Q & "></div>" & vbCrLf
            firstDest = False

            ' Dest header
            h = h & "<div class=" & Q & "dest-hd" & Q & ">"
            h = h & "<span class=" & Q & "dot" & Q & ">&rsaquo;</span>"
            h = h & "<span class=" & Q & "dest" & Q & ">" & dkParts(1) & "</span>"
            If dkParts(2) <> "" Then
                h = h & "<span class=" & Q & "via" & Q & ">via " & dkParts(2) & "</span>"
            End If
            h = h & "</div>" & vbCrLf

            ' Collect rows matching this POL+Dest+Via
            drCount = 0
            For j = 1 To rowCount
                If d(j, 0) = dkParts(0) And d(j, 1) = dkParts(1) And d(j, 2) = dkParts(2) Then
                    drCount = drCount + 1
                    ReDim Preserve destRows(1 To drCount)
                    destRows(drCount) = j
                End If
            Next j

            ' Find best (lowest) price in this dest group
            bestIdx = 0: bestPrice = 999999
            For j = 1 To drCount
                p40v = CLng(d(destRows(j), 5))
                If p40v = 0 Then p40v = CLng(d(destRows(j), 4))
                If p40v > 0 And p40v < bestPrice Then bestPrice = p40v: bestIdx = j
            Next j

            ' Write rate rows
            For j = 1 To drCount
                di = destRows(j)
                If j = bestIdx Then
                    rowCls = "row best"
                ElseIf j Mod 2 = 0 Then
                    rowCls = "row z"
                Else
                    rowCls = "row"
                End If

                h = h & "<div class=" & Q & rowCls & Q & ">"

                ' Carrier + BEST badge
                h = h & "<span class=" & Q & "carrier" & Q & ">" & d(di, 3)
                If j = bestIdx Then h = h & " <span class=" & Q & "badge-best" & Q & ">BEST</span>"
                h = h & "</span>"

                ' Container-kind tag — only shown when the quote mixes dry
                ' and reefer rows (else the header already communicates kind).
                Dim kindTag As String: kindTag = ""
                If isMixed And d(di, 9) = "RF" Then
                    kindTag = " <span class=" & Q & "kind-rf" & Q & ">RF</span>"
                End If

                ' 20-col price (GP or RF per row)
                s20 = CLng(d(di, 4))
                h = h & "<span class=" & Q & "r price" & Q & ">"
                If s20 > 0 Then h = h & Format(s20, "#,##0") Else h = h & "&ndash;"
                h = h & kindTag & "</span>"

                ' 40-col price (HC or RF per row)
                s40 = CLng(d(di, 5))
                h = h & "<span class=" & Q & "r price" & Q & ">"
                If s40 > 0 Then h = h & Format(s40, "#,##0") Else h = h & "&ndash;"
                h = h & kindTag & "</span>"

                ' Valid dates
                h = h & "<span class=" & Q & "valid" & Q & ">" & d(di, 8) & "</span>"

                ' Service: SOC / COC
                If d(di, 6) = "SOC" Then svcCls = "svc soc" Else svcCls = "svc coc"
                h = h & "<span class=" & Q & svcCls & Q & ">" & d(di, 6) & "</span>"

                ' Routing
                h = h & "<span class=" & Q & "note" & Q & ">" & d(di, 7) & "</span>"
                h = h & "</div>" & vbCrLf
            Next j
SkipDest:
        Next dki
    Next pk

    ' ── Handling fee strip ──
    h = h & "<div class=" & Q & "hf-strip" & Q & ">"
    h = h & "<span class=" & Q & "icon" & Q & ">&rsaquo;</span>"
    h = h & "Local Charge &amp; Handling Fee: <b>$45</b> / shipment (US)"
    h = h & " &middot; <span class=" & Q & "note-ca" & Q & ">Canada: $85 / shipment</span>"
    h = h & "</div>" & vbCrLf

    ' ── CTA bar ──
    h = h & "<div class=" & Q & "cta-bar" & Q & ">"
    h = h & "<span class=" & Q & "msg" & Q & ">Ready to book?</span>"
    h = h & "<a href=" & Q & "#" & Q & " class=" & Q & "btn" & Q & ">Confirm Booking &rarr;</a>"
    h = h & "</div>" & vbCrLf

    ' ── Footer ──
    h = h & "<div class=" & Q & "foot" & Q & ">pudongprime.com</div>" & vbCrLf
    h = h & "</div>" & vbCrLf

    ' ── Copy button (floats above quote card) ──
    h = h & "<button id=" & Q & "copyBtn" & Q & " onclick=" & Q & "captureQuote()" & Q & ">"
    h = h & "&#128203; Copy Image</button>" & vbCrLf

    ' ── html2canvas CDN + capture script ──
    h = h & "<script src=" & Q & "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js" & Q & "></script>" & vbCrLf
    h = h & "<script>" & vbCrLf
    h = h & "async function captureQuote(){" & vbCrLf
    h = h & " const btn=document.getElementById('copyBtn');" & vbCrLf
    h = h & " btn.textContent='Rendering...';" & vbCrLf
    h = h & " btn.disabled=true;" & vbCrLf
    h = h & " try{" & vbCrLf
    h = h & "  const el=document.querySelector('.quote');" & vbCrLf
    h = h & "  const canvas=await html2canvas(el,{scale:3,backgroundColor:'#ffffff'," & vbCrLf
    h = h & "   logging:false,allowTaint:false});" & vbCrLf
    h = h & "  canvas.toBlob(async(blob)=>{" & vbCrLf
    h = h & "   try{" & vbCrLf
    h = h & "    await navigator.clipboard.write([new ClipboardItem({'image/png':blob})]);" & vbCrLf
    h = h & "    btn.textContent='\u2705 Copied! Paste into Zalo';" & vbCrLf
    h = h & "    btn.style.background='#22C55E';btn.style.color='#fff';" & vbCrLf
    h = h & "    setTimeout(()=>{btn.textContent='\uD83D\uDCCB Copy Image';" & vbCrLf
    h = h & "     btn.style.background='';btn.style.color='';btn.disabled=false;},3000);" & vbCrLf
    h = h & "   }catch(e){" & vbCrLf
    h = h & "    const a=document.createElement('a');a.href=canvas.toDataURL('image/png');" & vbCrLf
    h = h & "    a.download='quote-" & Replace(customer, " ", "-") & ".png';a.click();" & vbCrLf
    h = h & "    btn.textContent='\u2705 Downloaded!';btn.disabled=false;" & vbCrLf
    h = h & "    setTimeout(()=>{btn.textContent='\uD83D\uDCCB Copy Image';" & vbCrLf
    h = h & "     btn.style.background='';btn.style.color='';},3000);" & vbCrLf
    h = h & "   }" & vbCrLf
    h = h & "  },'image/png');" & vbCrLf
    h = h & " }catch(e){btn.textContent='Error: '+e.message;btn.disabled=false;}" & vbCrLf
    h = h & "}" & vbCrLf
    h = h & "</script>" & vbCrLf
    h = h & "</body></html>"

    ' ══════════════════════════════════════════════════════════
    '  SAVE + OPEN
    ' ══════════════════════════════════════════════════════════
    ' Bulk mode: caller provides per-customer output path; skip browser open
    ' and skip per-file MsgBox (bulk caller shows ONE summary at the end).
    Dim htmlPath As String
    Dim bulkMode As Boolean: bulkMode = (Len(m_BulkOutputPath) > 0)
    If bulkMode Then
        htmlPath = m_BulkOutputPath
    Else
        htmlPath = QUOTE_DIR & "_quote_live.html"
    End If

    Dim fNum As Integer: fNum = FreeFile
    Open htmlPath For Output As #fNum
    Print #fNum, h
    Close #fNum

    If Not bulkMode And Not g_TestMode Then
        Shell "cmd /c start " & Q & Q & " " & Q & htmlPath & Q, vbNormalFocus
    End If

    If Not bulkMode Then
        Call MsgBoxOrSilent("Quote opened in browser!" & vbCrLf & _
               "Click [Copy Image] button to capture HD image." & vbCrLf & _
               "Then Ctrl+V into Zalo/email." & vbCrLf & vbCrLf & _
               "Customer: " & customer & vbCrLf & _
               "POLs: " & polOrd.Count & " | Dests: " & destOrd.Count & _
               " | Lines: " & rowCount, vbInformation, "Quote Image")
    End If
    Exit Sub

ErrHandler:
    g_LastError = "QuoteImage ERR " & Err.Number & ": " & Err.Description
    Call MsgBoxOrSilent("Error: " & Err.Description, vbCritical, "Quote Image")
End Sub

' ============================================================
'  QUOTE IMAGE BULK — 1 selection x N customers (Option B)
'  Added 2026-04-16. Use case: Nelson has 15 rate rows on Quotes
'  sheet, wants to send personalized HTML to 10 customers without
'  duplicating 150 rows. Flow:
'    1. On Quotes sheet, select rate rows
'    2. Click "Quote Img Bulk" -> Op Ens "BulkRecipients" scratch
'       sheet (auto-populated from CRM on first use)
'    3. Nelson types "X" in col A next to wanted customers
'    4. Click "Quote Img Bulk" again -> N HTML files generated
' ============================================================
Public Sub OnAction_QuoteImageBulk(Optional control As IRibbonControl = Nothing)
    On Error GoTo EHBulk

    Const QUOTE_DIR As String = "D:\OneDrive\NelsonData\erp\quote-mockups\"

    ' Phase 1: validate we are on Quotes sheet with rows selected
    Dim wsQ As Worksheet: Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        Call MsgBoxOrSilent("Quotes sheet not found!", vbExclamation, "Quote Img Bulk")
        Exit Sub
    End If
    If ActiveSheet.Name <> wsQ.Name Then
        Call MsgBoxOrSilent("Navigate to Quotes sheet first, select rate rows, then click again.", _
            vbExclamation, "Quote Img Bulk")
        Exit Sub
    End If

    Dim selRowCount As Long: selRowCount = 0
    Dim selArea As Range, ri As Long, sr As Long
    For Each selArea In Selection.Areas
        For ri = 1 To selArea.Rows.Count
            sr = selArea.Rows(ri).Row
            If sr >= 2 And Trim(wsQ.Cells(sr, 1).Value) <> "" Then
                selRowCount = selRowCount + 1
            End If
        Next ri
    Next selArea

    If selRowCount = 0 Then
        Call MsgBoxOrSilent("Select quote rows (row 2+) on Quotes sheet first!", _
            vbExclamation, "Quote Img Bulk")
        Exit Sub
    End If

    ' Phase 2: ensure BulkRecipients scratch sheet exists + fresh
    Dim wsRec As Worksheet
    Set wsRec = EnsureBulkRecipientsSheet()

    ' Phase 3: read ticked customers
    Dim customers() As String
    Dim custCount As Long: custCount = 0
    Dim lr As Long: lr = wsRec.Cells(wsRec.Rows.Count, 2).End(xlUp).Row
    Dim rr As Long
    For rr = 2 To lr
        If UCase(Trim(CStr(wsRec.Cells(rr, 1).Value))) = "X" Then
            Dim custName As String
            custName = Trim(CStr(wsRec.Cells(rr, 2).Value))
            If Len(custName) > 0 Then
                custCount = custCount + 1
                ReDim Preserve customers(1 To custCount)
                customers(custCount) = custName
            End If
        End If
    Next rr

    If custCount = 0 Then
        ' First run or no ticks -> navigate user to BulkRecipients
        wsRec.Activate
        wsRec.Range("A2").Select
        Call MsgBoxOrSilent( _
            "No customers ticked yet." & vbCrLf & vbCrLf & _
            "How to use:" & vbCrLf & _
            " 1. Type 'X' in col A next to each customer you want" & vbCrLf & _
            " 2. Navigate back to Quotes sheet" & vbCrLf & _
            " 3. Make sure the same rate rows are still selected" & vbCrLf & _
            " 4. Click 'Quote Img Bulk' again" & vbCrLf & vbCrLf & _
            "You're now on BulkRecipients sheet. Tick away!", _
            vbInformation, "Quote Img Bulk")
        Exit Sub
    End If

    ' Phase 4: confirm
    Dim preview As String, i As Long
    preview = ""
    For i = 1 To custCount
        If i <= 8 Then
            preview = preview & " - " & customers(i) & vbCrLf
        ElseIf i = 9 Then
            preview = preview & " ... +" & (custCount - 8) & " more" & vbCrLf
            Exit For
        End If
    Next i

    If MsgBox("Generate " & custCount & " quote images?" & vbCrLf & vbCrLf & _
              preview & vbCrLf & _
              "Each file: " & selRowCount & " routes, personalized header." & vbCrLf & _
              "Output folder: " & QUOTE_DIR, _
              vbYesNo + vbQuestion, "Quote Img Bulk") = vbNo Then Exit Sub

    ' Phase 5: loop + generate via override
    Dim dateStamp As String: dateStamp = Format(Date, "YYYYMMDD")
    Dim generated As Long: generated = 0
    Dim failed As Long: failed = 0
    Dim lastPath As String: lastPath = ""

    Application.ScreenUpdating = False

    For i = 1 To custCount
        m_BulkCustomerName = customers(i)
        m_BulkOutputPath = QUOTE_DIR & "Quote_" & SafeFileName(customers(i)) & "_" & dateStamp & ".html"

        g_LastError = ""
        Call OnAction_QuoteImage(Nothing)

        If Len(g_LastError) > 0 Then
            failed = failed + 1
        Else
            generated = generated + 1
            lastPath = m_BulkOutputPath
        End If
    Next i

    ' Reset override state no matter what
    m_BulkCustomerName = ""
    m_BulkOutputPath = ""
    Application.ScreenUpdating = True

    ' Open output folder so Nelson sees the files immediately
    If generated > 0 And Not g_TestMode Then
        Shell "explorer.exe " & """" & QUOTE_DIR & """", vbNormalFocus
    End If

    Call MsgBoxOrSilent("Bulk complete!" & vbCrLf & vbCrLf & _
        "Generated: " & generated & " files" & vbCrLf & _
        "Failed: " & failed & vbCrLf & _
        "Routes per file: " & selRowCount & vbCrLf & vbCrLf & _
        "Files saved to: " & QUOTE_DIR & vbCrLf & _
        "(Folder opened in Explorer)", _
        vbInformation, "Quote Img Bulk")
    Exit Sub

EHBulk:
    m_BulkCustomerName = ""
    m_BulkOutputPath = ""
    Application.ScreenUpdating = True
    g_LastError = "OnAction_QuoteImageBulk #" & Err.Number & ": " & Err.Description
    MsgBox g_LastError, vbExclamation, "Quote Img Bulk"
End Sub

' Return the BulkRecipients scratch sheet. Creates + seeds from CRM on first
' use. On re-entry, keeps ticks intact so Nelson can reuse the last list.
Private Function EnsureBulkRecipientsSheet() As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets("BulkRecipients")
    On Error GoTo 0

    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = "BulkRecipients"
        ws.Cells(1, 1).Value = "Tick"
        ws.Cells(1, 2).Value = "Customer"
        ws.Cells(1, 3).Value = "Last Used"
        ws.Range("A1:C1").Font.Bold = True
        ws.Range("A1:C1").Interior.Color = RGB(59, 130, 246)
        ws.Range("A1:C1").Font.Color = RGB(255, 255, 255)
        ws.Columns("A").ColumnWidth = 6
        ws.Columns("B").ColumnWidth = 32
        ws.Columns("C").ColumnWidth = 14

        ' Populate from CRM
        Dim wsCRM As Worksheet
        On Error Resume Next
        Set wsCRM = ThisWorkbook.Sheets("CRM")
        On Error GoTo 0

        Dim outRow As Long: outRow = 2
        If Not wsCRM Is Nothing Then
            Dim lr As Long: lr = wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
            Dim r As Long
            For r = 2 To lr
                Dim nm As String: nm = Trim(CStr(wsCRM.Cells(r, 2).Value))
                If Len(nm) > 0 Then
                    ws.Cells(outRow, 2).Value = nm
                    outRow = outRow + 1
                End If
            Next r
        End If

        ' Empty-state hint
        If outRow = 2 Then
            ws.Cells(2, 2).Value = "(CRM sheet empty - type customer names in col B)"
        End If
    End If

    Set EnsureBulkRecipientsSheet = ws
End Function

' Sanitize customer name into a safe filename slug (letters/digits/dash/underscore).
Private Function SafeFileName(src As String) As String
    Dim s As String: s = Trim(src)
    Dim result As String: result = ""
    Dim i As Long, ch As String
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If (ch >= "0" And ch <= "9") Or (ch >= "A" And ch <= "Z") Or _
           (ch >= "a" And ch <= "z") Or ch = "-" Or ch = "_" Then
            result = result & ch
        ElseIf ch = " " Then
            result = result & "-"
        End If
    Next i
    If Len(result) = 0 Then result = "customer"
    If Len(result) > 40 Then result = Left(result, 40)
    SafeFileName = result
End Function

' ── POL code → full name ──
Private Function QI_POLName(code As String) As String
    Select Case UCase(code)
        Case "HPH": QI_POLName = "Hai Phong"
        Case "HCM", "SGN": QI_POLName = "Ho Chi Minh"
        Case "DAD": QI_POLName = "Da Nang"
        Case "UIH": QI_POLName = "Quy Nhon"
        Case "QNH": QI_POLName = "Quy Nhon"
        Case "VUT": QI_POLName = "Vung Tau"
        Case "CXR": QI_POLName = "Cam Ranh"
        Case Else:  QI_POLName = code
    End Select
End Function

' ── POL code → CSS class (hph=blue, hcm=teal, dad=purple) ──
Private Function QI_POLClass(code As String) As String
    Select Case UCase(code)
        Case "HPH": QI_POLClass = "hph"
        Case "HCM", "SGN": QI_POLClass = "hcm"
        Case "DAD": QI_POLClass = "dad"
        Case "UIH", "QNH": QI_POLClass = "uih"
        Case "VUT", "CXR": QI_POLClass = "vut"
        Case Else:  QI_POLClass = "hph"
    End Select
End Function

' ── Full CSS for quote HTML (Option F design) ──
Private Function QuoteImageCSS() As String
    Dim c As String
    c = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');" & vbCrLf
    c = c & "*{margin:0;padding:0;box-sizing:border-box}" & vbCrLf
    c = c & "body{font-family:'Inter',-apple-system,sans-serif;background:#F1F5F9;padding:20px;display:flex;justify-content:center}" & vbCrLf
    c = c & ".quote{width:740px;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 16px rgba(15,23,42,.07)}" & vbCrLf
    ' Header
    c = c & ".q-head{background:#fff;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #E2E8F0}" & vbCrLf
    c = c & ".q-head .brand{display:flex;align-items:center;gap:14px}" & vbCrLf
    c = c & ".q-head .logo{height:95px;width:auto;object-fit:contain}" & vbCrLf
    c = c & ".q-head .brand-text{display:flex;flex-direction:column}" & vbCrLf
    c = c & ".q-head .brand-name{font-size:15px;font-weight:700;color:#0F172A}" & vbCrLf
    c = c & ".q-head .brand-sub{font-size:10px;color:#94A3B8;letter-spacing:.5px;text-transform:uppercase}" & vbCrLf
    c = c & ".q-head .meta{text-align:right;display:flex;flex-direction:column;gap:2px}" & vbCrLf
    c = c & ".q-head .customer{font-size:15px;font-weight:700;color:#1E40AF}" & vbCrLf
    c = c & ".q-head .date{font-size:11px;color:#94A3B8}" & vbCrLf
    ' Column header
    c = c & ".col-bar{display:grid;grid-template-columns:80px 82px 82px 100px 52px 1fr;gap:0 6px;" & _
            "padding:7px 24px;background:#F8FAFC;border-bottom:2px solid #E2E8F0;" & _
            "font:600 10px/1 'Inter',sans-serif;color:#94A3B8;text-transform:uppercase;letter-spacing:.7px}" & vbCrLf
    c = c & ".col-bar .r{text-align:right}" & vbCrLf
    ' POL bar
    c = c & ".pol-bar{margin:8px 12px 0;padding:8px 14px;border-radius:8px;color:#fff;font-weight:700;font-size:13px;display:flex;align-items:center;gap:8px}" & vbCrLf
    c = c & ".pol-bar .name{font-weight:400;opacity:.7;font-size:11px}" & vbCrLf
    c = c & ".pol-bar.hph{background:linear-gradient(135deg,#1E40AF,#2563EB)}" & vbCrLf
    c = c & ".pol-bar.hcm{background:linear-gradient(135deg,#0D7377,#0EA5E9)}" & vbCrLf
    c = c & ".pol-bar.dad{background:linear-gradient(135deg,#6D28D9,#8B5CF6)}" & vbCrLf
    c = c & ".pol-bar.uih{background:linear-gradient(135deg,#B45309,#F59E0B)}" & vbCrLf
    c = c & ".pol-bar.vut{background:linear-gradient(135deg,#065F46,#10B981)}" & vbCrLf
    ' Dest header
    c = c & ".dest-hd{padding:8px 24px 4px;display:flex;align-items:baseline;gap:8px}" & vbCrLf
    c = c & ".dest-hd .dot{color:#CBD5E1;font-size:14px}" & vbCrLf
    c = c & ".dest-hd .dest{font-size:13px;font-weight:700;color:#1E293B}" & vbCrLf
    c = c & ".dest-hd .via{font-size:11px;color:#94A3B8}" & vbCrLf
    ' Rate row
    c = c & ".row{display:grid;grid-template-columns:80px 82px 82px 100px 52px 1fr;gap:0 6px;" & _
            "padding:7px 24px;font-size:12px;color:#475569;align-items:center;border-bottom:1px solid #F1F5F9}" & vbCrLf
    c = c & ".row:last-child{border-bottom:none}" & vbCrLf
    c = c & ".row .r{text-align:right;font-variant-numeric:tabular-nums}" & vbCrLf
    c = c & ".row .carrier{font-weight:600;color:#334155}" & vbCrLf
    c = c & ".row .price{font-weight:600}" & vbCrLf
    c = c & ".row .valid{color:#64748B;font-size:11px}" & vbCrLf
    c = c & ".row .svc{font-size:10px;font-weight:600;color:#64748B;text-align:center}" & vbCrLf
    c = c & ".row .svc.soc{color:#0D9488}" & vbCrLf
    c = c & ".row .svc.coc{color:#94A3B8}" & vbCrLf
    c = c & ".row .note{color:#64748B;font-size:11px;line-height:1.3}" & vbCrLf
    c = c & ".row.z{background:#F8FAFC}" & vbCrLf
    ' Best row
    c = c & ".row.best{background:#F0FDF4;border-left:4px solid #22C55E;padding-left:20px;border-bottom:1px solid #DCFCE7}" & vbCrLf
    c = c & ".row.best .carrier{color:#15803D;font-weight:700}" & vbCrLf
    c = c & ".row.best .price{color:#15803D;font-weight:800;font-size:15px}" & vbCrLf
    c = c & ".badge-best{display:inline-block;padding:1px 6px;border-radius:3px;background:#22C55E;color:#fff;" & _
            "font-size:9px;font-weight:700;letter-spacing:.3px;margin-left:5px;vertical-align:1px}" & vbCrLf
    ' Reefer tag (only rendered in mixed-mode quotes — header already signals kind when uniform)
    c = c & ".kind-rf{display:inline-block;padding:0 4px;margin-left:4px;border-radius:3px;" & _
            "background:#DBEAFE;color:#1E40AF;font-size:8px;font-weight:700;letter-spacing:.3px;" & _
            "vertical-align:1px;text-transform:uppercase}" & vbCrLf
    ' Dest separator
    c = c & ".dest-sep{height:1px;margin:4px 24px;background:#E2E8F0}" & vbCrLf
    ' Handling fee strip
    c = c & ".hf-strip{margin:6px 12px;padding:8px 16px;background:#F8FAFC;border:1px solid #E2E8F0;" & _
            "border-radius:8px;display:flex;align-items:center;gap:8px;font-size:11px;color:#475569}" & vbCrLf
    c = c & ".hf-strip .icon{font-size:14px}" & vbCrLf
    c = c & ".hf-strip b{color:#1E40AF;font-weight:700}" & vbCrLf
    c = c & ".hf-strip .note-ca{color:#92400E;font-weight:600}" & vbCrLf
    ' CTA bar
    c = c & ".cta-bar{background:linear-gradient(135deg,#1E40AF,#2563EB);padding:12px 24px;" & _
            "display:flex;justify-content:space-between;align-items:center;color:#fff}" & vbCrLf
    c = c & ".cta-bar .msg{font-size:12px;font-weight:500;opacity:.9}" & vbCrLf
    c = c & ".cta-bar .btn{padding:7px 18px;background:#fff;color:#1E40AF;font-size:12px;" & _
            "font-weight:700;border-radius:6px;text-decoration:none}" & vbCrLf
    ' Footer
    c = c & ".foot{padding:10px 24px;border-top:1px solid #E2E8F0;font-size:10px;color:#CBD5E1;" & _
            "display:flex;justify-content:flex-end;font-weight:600}" & vbCrLf
    ' Copy button — floats below quote card
    c = c & "#copyBtn{display:block;margin:16px auto 0;padding:12px 32px;font-size:14px;font-weight:700;" & _
            "font-family:'Inter',sans-serif;background:#1E40AF;color:#fff;border:none;border-radius:8px;" & _
            "cursor:pointer;transition:all .2s;letter-spacing:.3px}" & vbCrLf
    c = c & "#copyBtn:hover{background:#1D4ED8;transform:translateY(-1px);box-shadow:0 4px 12px rgba(30,64,175,.3)}" & vbCrLf
    c = c & "#copyBtn:disabled{opacity:.7;cursor:wait;transform:none}" & vbCrLf
    ' HiDPI text rendering
    c = c & "*{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility}" & vbCrLf
    QuoteImageCSS = c
End Function

' ── Read logo.png → base64 data URI (avoids tainted canvas in html2canvas) ──
Private Function QI_LogoDataURI() As String
    Const LOGO_PATH As String = "D:\OneDrive\NelsonData\erp\quote-mockups\logo.png"
    On Error GoTo Fallback

    ' Read binary file
    Dim fNum As Integer: fNum = FreeFile
    Dim fLen As Long
    Dim fBytes() As Byte

    Open LOGO_PATH For Binary Access Read As #fNum
    fLen = LOF(fNum)
    If fLen = 0 Then GoTo Fallback
    ReDim fBytes(0 To fLen - 1)
    Get #fNum, , fBytes
    Close #fNum

    ' Convert to Base64 using MSXML2.DOMDocument
    Dim xmlDoc As Object: Set xmlDoc = CreateObject("MSXML2.DOMDocument")
    Dim xmlNode As Object: Set xmlNode = xmlDoc.createElement("b64")
    xmlNode.DataType = "bin.base64"
    xmlNode.nodeTypedValue = fBytes

    QI_LogoDataURI = "data:image/png;base64," & Replace(Replace(xmlNode.Text, vbCr, ""), vbLf, "")
    Exit Function

Fallback:
    On Error Resume Next
    Close #fNum
    QI_LogoDataURI = "logo.png"
End Function

' ============================================================
'  PHASE 3 — BOOKING POOL HANDLERS
'  Ribbon group grpBookingPool (Operations tab)
'  3 Subs: NewKeepSpace, SyncPool, MarkExpired
' ============================================================

' ── Btn_NewKeepSpace_OnAction ────────────────────────────────
' Manual insert of a keep-space booking into the Booking Pool
' sheet with Status=HOLDING. Nelson uses this when he RQs
' internal space before a customer is confirmed.
Public Sub Btn_NewKeepSpace_OnAction(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim wsPool As Worksheet
    On Error Resume Next
    Set wsPool = ThisWorkbook.Sheets("Booking Pool")
    On Error GoTo ErrHandler
    If wsPool Is Nothing Then
        MsgBox "Sheet 'Booking Pool' not found!" & ChrW(10) & "Run Phase 1 setup first.", _
               vbExclamation, "New Keep Space"
        Exit Sub
    End If

    Dim bkg As String:          bkg = Trim(InputBox("BKG number (leave blank if pending):", "New Keep Space"))
    Dim carrier As String:      carrier = UCase(Trim(InputBox("Carrier (ONE/HPL/ZIM/...):", "New Keep Space")))
    Dim pol As String:          pol = UCase(Trim(InputBox("POL (HCM/HPH):", "New Keep Space")))
    Dim pod As String:          pod = UCase(Trim(InputBox("POD (LAX/TACOMA/USLAX/...):", "New Keep Space")))
    Dim contQty As String:      contQty = Trim(InputBox("Container x Qty (e.g. 1X40HC, 2X20GP):", "New Keep Space"))
    Dim etd As String:          etd = Trim(InputBox("ETD (e.g. 1May, 15/05/2026):", "New Keep Space"))
    Dim customerHint As String: customerHint = Trim(InputBox("Customer target (leave blank if none yet):", "New Keep Space"))

    ' Require minimum fields
    If carrier = "" Or pol = "" Or pod = "" Then
        MsgBox "Carrier, POL and POD are required.", vbExclamation, "New Keep Space"
        Exit Sub
    End If

    ' Parse container x qty — accept formats: 1X40HC, 1x40HC, 1 X 40HC
    Dim contType As String: contType = contQty
    Dim qty As Long:        qty = 1
    If InStr(UCase(contQty), "X") > 0 Then
        Dim parts() As String
        parts = Split(UCase(contQty), "X")
        On Error Resume Next
        qty = CLng(Val(Trim(parts(0))))
        If Err.Number <> 0 Or qty < 1 Then qty = 1
        On Error GoTo ErrHandler
        contType = Trim(parts(1))
    End If

    ' Find next empty row (col 1 AND col 2 both empty = truly empty)
    Dim nextRow As Long: nextRow = 2
    Do While wsPool.Cells(nextRow, 1).Value <> "" Or wsPool.Cells(nextRow, 2).Value <> ""
        nextRow = nextRow + 1
        If nextRow > 10000 Then Exit Do   ' safety guard
    Loop

    ' Build customer display string
    Dim custDisplay As String
    If Trim(customerHint) <> "" Then
        custDisplay = "[KEEP SPACE " & UCase(Trim(customerHint)) & "]"
    Else
        custDisplay = "[KEEP SPACE]"
    End If

    ' Write row per schema (20 cols):
    ' 1=BKG_No, 2=Carrier, 3=Customer, 4=POL, 5=POD, 6=Final_Dest,
    ' 7=Container, 8=Qty, 9=ETD, 10=ETA, 11=SI_CutOff, 12=CY_Close,
    ' 13=Vessel, 14=Voyage, 15=PO_Number, 16=Status, 17=Link_AJ_Row,
    ' 18=Date_Booked, 19=Source_Mail_ID, 20=Notes
    wsPool.Cells(nextRow, 1).Value = bkg
    wsPool.Cells(nextRow, 2).Value = carrier
    wsPool.Cells(nextRow, 3).Value = custDisplay
    wsPool.Cells(nextRow, 4).Value = pol
    wsPool.Cells(nextRow, 5).Value = pod
    wsPool.Cells(nextRow, 7).Value = contType
    wsPool.Cells(nextRow, 8).Value = qty
    wsPool.Cells(nextRow, 9).Value = etd
    wsPool.Cells(nextRow, 16).Value = "HOLDING"
    wsPool.Cells(nextRow, 18).Value = Now
    wsPool.Cells(nextRow, 18).NumberFormat = "dd/mm/yyyy hh:mm"
    wsPool.Cells(nextRow, 20).Value = "Manual entry"

    ' Highlight HOLDING rows in light yellow for visual distinction
    wsPool.Rows(nextRow).Interior.Color = RGB(255, 255, 204)

    MsgBox "Added to Booking Pool row " & nextRow & ChrW(10) & _
           custDisplay & ChrW(10) & _
           carrier & " | " & pol & "-" & pod & " | " & contType & " x" & qty & ChrW(10) & _
           "ETD: " & etd, _
           vbInformation, "New Keep Space — Added"
    Exit Sub
ErrHandler:
    MsgBox "Error: " & Err.Description, vbCritical, "Btn_NewKeepSpace_OnAction"
End Sub


' ── Btn_SyncPool_OnAction ────────────────────────────────────
' Delegates to sync-pool-flush.py via Shell. Python handles
' JSON parsing, dedup, and sheet writes (simpler + testable
' than VBA string parsing). VBA reads result file and reports.
Public Sub Btn_SyncPool_OnAction(control As IRibbonControl)
    On Error GoTo ErrHandler

    ' Locate Python executable
    Dim pyExe As String
    pyExe = "C:\Users\Nelson\anaconda3\pythonw.exe"

    ' Locate script — resolve relative to workbook path
    Dim scriptPath As String
    scriptPath = ThisWorkbook.Path & "\..\..\scripts\sync-pool-flush.py"

    ' Normalize path (remove ..\ segments via FileSystemObject)
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(pyExe) Then
        MsgBox "Python not found at:" & ChrW(10) & pyExe & ChrW(10) & ChrW(10) & _
               "Update pyExe path in Btn_SyncPool_OnAction.", _
               vbExclamation, "Sync Pool — Python Missing"
        Exit Sub
    End If

    Dim absScript As String
    On Error Resume Next
    absScript = fso.GetAbsolutePathName(scriptPath)
    On Error GoTo ErrHandler

    If Not fso.FileExists(absScript) Then
        MsgBox "Sync script not found:" & ChrW(10) & absScript, _
               vbExclamation, "Sync Pool — Script Missing"
        Exit Sub
    End If

    ' Result file written by sync-pool-flush.py
    Dim resultFile As String
    resultFile = fso.GetParentFolderName(absScript)
    resultFile = resultFile & "\..\email_engine\data\pool_sync_result.txt"
    On Error Resume Next
    resultFile = fso.GetAbsolutePathName(resultFile)
    On Error GoTo ErrHandler

    ' Delete old result so we can detect when new one is written
    On Error Resume Next
    If fso.FileExists(resultFile) Then fso.DeleteFile resultFile
    On Error GoTo ErrHandler

    ' Shell: run in normal focus so Nelson can see progress in console
    Dim cmd As String
    cmd = """" & pyExe & """ """ & absScript & """"
    Shell cmd, vbNormalFocus

    ' Wait up to 30 seconds for result file
    Dim t As Double: t = Timer
    Do While Not fso.FileExists(resultFile)
        DoEvents
        If Timer - t > 30 Then
            MsgBox "Sync timed out (30s). Check console window for errors.", _
                   vbExclamation, "Sync Pool"
            Exit Sub
        End If
    Loop

    ' Read result
    Dim ts As Object: Set ts = fso.OpenTextFile(resultFile, 1, False, -2)
    Dim resultMsg As String: resultMsg = ts.ReadAll
    ts.Close

    MsgBox resultMsg, vbInformation, "Sync Pool — Done"
    Exit Sub
ErrHandler:
    MsgBox "Error: " & Err.Description, vbCritical, "Btn_SyncPool_OnAction"
End Sub


' ── Btn_MarkExpired_OnAction ────────────────────────────────
' Scan Booking Pool: if Status=HOLDING AND Date_Booked > 30
' days ago → set Status=EXPIRED, clear row highlight.
Public Sub Btn_MarkExpired_OnAction(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim wsPool As Worksheet
    On Error Resume Next
    Set wsPool = ThisWorkbook.Sheets("Booking Pool")
    On Error GoTo ErrHandler
    If wsPool Is Nothing Then
        MsgBox "Sheet 'Booking Pool' not found!", vbExclamation, "Mark Expired"
        Exit Sub
    End If

    Dim expiredCount As Long: expiredCount = 0
    Dim skippedCount As Long: skippedCount = 0
    Dim cutoff As Date: cutoff = Now - 30  ' 30 days ago

    Dim lastRow As Long
    lastRow = wsPool.Cells(wsPool.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then
        MsgBox "Booking Pool is empty.", vbInformation, "Mark Expired"
        Exit Sub
    End If

    Dim r As Long
    For r = 2 To lastRow
        Dim status As String
        status = UCase(Trim(CStr(wsPool.Cells(r, 16).Value)))
        If status = "HOLDING" Then
            Dim dateBooked As Date
            On Error Resume Next
            dateBooked = CDate(wsPool.Cells(r, 18).Value)
            If Err.Number <> 0 Then
                skippedCount = skippedCount + 1
                Err.Clear
                On Error GoTo ErrHandler
            Else
                On Error GoTo ErrHandler
                If dateBooked < cutoff Then
                    wsPool.Cells(r, 16).Value = "EXPIRED"
                    wsPool.Cells(r, 16).Interior.Color = RGB(220, 220, 220)
                    wsPool.Cells(r, 16).Font.Color = RGB(128, 128, 128)
                    ' Clear row yellow highlight
                    wsPool.Rows(r).Interior.ColorIndex = xlNone
                    wsPool.Cells(r, 16).Interior.Color = RGB(220, 220, 220)
                    expiredCount = expiredCount + 1
                End If
            End If
        End If
    Next r

    Dim msg As String
    msg = "Mark Expired complete." & ChrW(10) & ChrW(10) & _
          "Expired: " & expiredCount & " row(s)" & ChrW(10) & _
          "Skipped (bad date): " & skippedCount & " row(s)"
    MsgBox msg, vbInformation, "Mark Expired"
    Exit Sub
ErrHandler:
    MsgBox "Error: " & Err.Description, vbCritical, "Btn_MarkExpired_OnAction"
End Sub


' ============================================================
'  RATE MIX CALCULATOR — Phase 1-3
'  FIX+FAK blend with tiered markup, 1-click Mix Quote.
'  Added 2026-04-22.
' ============================================================
'
' Module-level state for Rate Mix (declared in body section
' because module-level declarations section already closed above,
' but VBA allows Private declarations in standard modules at any
' point as long as they are outside Sub/Function bodies).
' Note: VBA actually requires ALL module-level declarations before
' the first Sub — these are placed here as commented reference;
' the actual declarations are in the module header section below
' as a patch block that must be inserted at the module declarations
' section. Since we cannot split a file mid-module in this edit,
' we use Static variables inside the helper subs below as a
' compatible workaround for runtime state isolation.
'
' STATE DESIGN: Use a dedicated init sub called once to set up
' module-scoped state via a Private Type stored in a module-level
' object. However, since VBA declarations must precede all Subs,
' we leverage a well-known VBA pattern: store state in a
' Scripting.Dictionary keyed singleton accessed via a Private
' Function that creates it on first call (lazy init).

' ── MixState — lazy-init singleton dictionary ───────────────
Private Function MixState() As Object
    Static oState As Object
    If oState Is Nothing Then
        Set oState = CreateObject("Scripting.Dictionary")
        oState("FixQty") = CLng(0)
        oState("FakQty") = CLng(0)
        oState("Ready") = False
        oState("Markup") = CCur(0)
        oState("PeerRow") = CLng(0)
        ' Blended rates sub-dict created on demand
    End If
    Set MixState = oState
End Function

' ── MixBlended — lazy-init sub-dictionary for per-cont rates ─
Private Function MixBlended() As Object
    Static oBlend As Object
    If oBlend Is Nothing Then
        Set oBlend = CreateObject("Scripting.Dictionary")
    End If
    Set MixBlended = oBlend
End Function

' ── TierMarkup — returns tiered markup based on FAK% ─────────
Private Function TierMarkup(ByVal fakPct As Double) As Currency
    Select Case True
        Case fakPct <= 33:  TierMarkup = CCur(100)
        Case fakPct <= 66:  TierMarkup = CCur(150)
        Case fakPct < 100:  TierMarkup = CCur(200)
        Case Else:          TierMarkup = CCur(250)
    End Select
End Function

' ── ComputeMix — core blend logic ────────────────────────────
Private Sub ComputeMix()
    On Error Resume Next
    Dim st As Object: Set st = MixState()
    Dim bd As Object: Set bd = MixBlended()

    st("Ready") = False
    bd.RemoveAll

    ' Guards
    If m_Carrier = "" Or m_POL = "" Or m_POD = "" Then Exit Sub
    Dim fixQty As Long: fixQty = CLng(st("FixQty"))
    Dim fakQty As Long: fakQty = CLng(st("FakQty"))
    If fixQty + fakQty = 0 Then Exit Sub
    If m_SourceRow = 0 Then Exit Sub

    ' Determine selected row type and what the peer type should be
    Dim srcType As String: srcType = UCase(Trim(m_Source))
    Dim oppType As String
    If InStr(srcType, "FAK") > 0 Then
        oppType = "FIX"
    ElseIf InStr(srcType, "FIX") > 0 Or InStr(srcType, "SPECIAL") > 0 Then
        oppType = "FAK"
    Else
        Exit Sub  ' SCFI or unknown — cannot blend
    End If

    ' 2026-04-22 BUG FIX (Nelson policy): FIX vs FAK blend MUST both be COC.
    ' SOC rates from FAK file cannot be used as peer for FIX (different cost structure).
    ' If selected row is SOC → no blend (user must select the COC row instead).
    Dim selNote As String: selNote = UCase(Trim(CStr(ThisWorkbook.Sheets("Pricing Dry").Cells(m_SourceRow, COL_NOTE).Value)))
    If InStr(selNote, "SOC") > 0 Then Exit Sub

    ' Find peer row in Pricing Dry: same Carrier+POL+POD+Place, opposite Source,
    ' AND Note does NOT contain "SOC" (must be COC to be valid peer).
    Dim wsP As Worksheet
    Set wsP = Nothing
    On Error Resume Next
    Set wsP = ThisWorkbook.Sheets("Pricing Dry")
    On Error GoTo 0
    If wsP Is Nothing Then Exit Sub

    Dim peerRow As Long: peerRow = 0
    Dim lastR As Long: lastR = wsP.Cells(wsP.Rows.Count, 1).End(xlUp).Row
    Dim bestEff As Date: bestEff = CDate("1900-01-01")
    Dim r As Long

    For r = 2 To lastR
        If UCase(Trim(CStr(wsP.Cells(r, COL_CARRIER).Value))) = UCase(m_Carrier) And _
           UCase(Trim(CStr(wsP.Cells(r, COL_POL).Value)))     = UCase(m_POL) And _
           UCase(Trim(CStr(wsP.Cells(r, COL_POD).Value)))     = UCase(m_POD) And _
           UCase(Trim(CStr(wsP.Cells(r, COL_PLACE).Value)))   = UCase(m_Place) Then
            Dim rSrc As String: rSrc = UCase(Trim(CStr(wsP.Cells(r, COL_SOURCE).Value)))
            Dim rNote As String: rNote = UCase(Trim(CStr(wsP.Cells(r, COL_NOTE).Value)))
            ' Peer must match opposite Source AND be COC (Note NOT containing SOC)
            If InStr(rSrc, oppType) > 0 And InStr(rNote, "SOC") = 0 Then
                ' Pick latest by Eff date (tiebreak: latest = best)
                Dim effVal As Date
                On Error Resume Next
                effVal = CDate(wsP.Cells(r, COL_EFF).Value)
                If Err.Number <> 0 Then effVal = CDate("1900-01-01")
                Err.Clear
                On Error GoTo 0
                If peerRow = 0 Or effVal >= bestEff Then
                    peerRow = r
                    bestEff = effVal
                End If
            End If
        End If
    Next r

    If peerRow = 0 Then Exit Sub
    st("PeerRow") = peerRow

    ' Determine which row is FIX and which is FAK
    Dim fixRow As Long, fakRow As Long
    If InStr(srcType, "FIX") > 0 Or InStr(srcType, "SPECIAL") > 0 Then
        fixRow = m_SourceRow: fakRow = peerRow
    Else
        fixRow = peerRow:     fakRow = m_SourceRow
    End If

    Dim totQty As Long: totQty = fixQty + fakQty
    Dim fakPct As Double: fakPct = (CDbl(fakQty) / CDbl(totQty)) * 100#
    st("Markup") = TierMarkup(fakPct)

    ' Blend rates for each container type
    ' Pricing Dry cols: COL_20GP=10, COL_40GP=11, COL_40HQ=12, COL_45HQ=13, COL_40NOR=14
    Dim contNames As Variant: contNames = Array("20GP", "40HC", "45HC", "40NOR")
    Dim contCols  As Variant: contCols  = Array(COL_20GP, COL_40HQ, COL_45HQ, COL_40NOR)

    Dim i As Long
    For i = 0 To 3
        Dim col As Long: col = CLng(contCols(i))
        Dim fixRate As Double: fixRate = Val(CStr(wsP.Cells(fixRow, col).Value))
        Dim fakRate As Double: fakRate = Val(CStr(wsP.Cells(fakRow, col).Value))
        If fixRate > 0 And fakRate > 0 Then
            Dim blendedRate As Double
            blendedRate = (CDbl(fixQty) * fixRate + CDbl(fakQty) * fakRate) / CDbl(totQty)
            bd(CStr(contNames(i))) = blendedRate
        End If
    Next i

    If bd.Count = 0 Then Exit Sub
    st("Ready") = True
End Sub

' ── BuildMixSellLabel — formats the ribbon label string ──────
Private Function BuildMixSellLabel() As String
    Dim st As Object: Set st = MixState()
    Dim bd As Object: Set bd = MixBlended()

    If Not CBool(st("Ready")) Then
        BuildMixSellLabel = "(select row + qty)"
        Exit Function
    End If

    Dim mk As Currency: mk = CCur(st("Markup"))
    Dim s As String: s = "Sell ($" & Format(mk, "#,##0") & " mk): "
    Dim parts As String: parts = ""
    Dim contList As Variant: contList = Array("20GP", "40HC", "45HC", "40NOR")
    Dim i As Long

    For i = 0 To 3
        Dim key As String: key = CStr(contList(i))
        If bd.Exists(key) Then
            Dim sellAmt As Double: sellAmt = CDbl(bd(key)) + CDbl(mk)
            If parts <> "" Then parts = parts & " | "
            parts = parts & key & " $" & Format(sellAmt, "#,##0")
        End If
    Next i

    If parts = "" Then parts = ChrW(9888) & " No peer"
    BuildMixSellLabel = s & parts
End Function

' ── RibbonInvalidateMixLabel — refresh mix ribbon controls ───
Private Sub RibbonInvalidateMixLabel()
    On Error Resume Next
    If Not ribbonUI Is Nothing Then
        ribbonUI.InvalidateControl "lblMixSell"
        ribbonUI.InvalidateControl "btnMixQuote"
    End If
End Sub

' ── Ribbon callbacks: OnChange ────────────────────────────────
Public Sub OnChange_MixFixQty(control As IRibbonControl, text As String)
    On Error Resume Next
    Dim st As Object: Set st = MixState()
    Dim v As Long: v = CLng(Val(text))
    If v < 0 Then v = 0
    st("FixQty") = v
    ComputeMix
    RibbonInvalidateMixLabel
End Sub

Public Sub OnChange_MixFakQty(control As IRibbonControl, text As String)
    On Error Resume Next
    Dim st As Object: Set st = MixState()
    Dim v As Long: v = CLng(Val(text))
    If v < 0 Then v = 0
    st("FakQty") = v
    ComputeMix
    RibbonInvalidateMixLabel
End Sub

' ── Ribbon callbacks: getText ─────────────────────────────────
Public Sub GetText_MixFixQty(control As IRibbonControl, ByRef text)
    Dim st As Object: Set st = MixState()
    Dim v As Long: v = CLng(st("FixQty"))
    If v = 0 Then text = "" Else text = CStr(v)
End Sub

Public Sub GetText_MixFakQty(control As IRibbonControl, ByRef text)
    Dim st As Object: Set st = MixState()
    Dim v As Long: v = CLng(st("FakQty"))
    If v = 0 Then text = "" Else text = CStr(v)
End Sub

' ── Ribbon callbacks: getLabel / getEnabled ───────────────────
Public Sub GetLabel_MixSell(control As IRibbonControl, ByRef label)
    label = BuildMixSellLabel()
End Sub

Public Sub GetEnabled_MixQuote(control As IRibbonControl, ByRef enabled)
    Dim st As Object: Set st = MixState()
    Dim fixQty As Long: fixQty = CLng(st("FixQty"))
    Dim fakQty As Long: fakQty = CLng(st("FakQty"))
    enabled = CBool(st("Ready")) And (fixQty > 0 Or fakQty > 0) And m_Customer <> ""
End Sub

' ── OnAction_MixQuote — Phase 3: write blended quote row ─────
Public Sub OnAction_MixQuote(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim st As Object: Set st = MixState()
    Dim bd As Object: Set bd = MixBlended()

    If Not CBool(st("Ready")) Then
        MsgBox "Rate Mix chua tinh xong. Chon row Pricing Dry + nhap FIX/FAK qty.", _
               vbExclamation, "Rate Mix"
        Exit Sub
    End If
    If m_Customer = "" Then
        MsgBox "Chua co customer — click cell customer truoc.", vbExclamation, "Rate Mix"
        Exit Sub
    End If

    Dim fixQty As Long: fixQty = CLng(st("FixQty"))
    Dim fakQty As Long: fakQty = CLng(st("FakQty"))
    Dim mk As Currency: mk = CCur(st("Markup"))

    ' Find Quotes sheet
    Dim wsQ As Worksheet
    Set wsQ = Nothing
    On Error Resume Next
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    On Error GoTo ErrHandler
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Rate Mix"
        Exit Sub
    End If

    ' Generate IDs
    Randomize
    Dim qid As String
    qid = "MIX-" & UCase(Format(Date, "DDMMM")) & "-" & _
          Format(Int((999 - 100 + 1) * Rnd + 100), "000")
    Dim qgid As String
    qgid = "QG-" & UCase(Format(Date, "DDMMM")) & "-" & _
           Format(Int((99 - 10 + 1) * Rnd + 10), "00")

    ' Reuse QuoteGroupID if same customer + same day (same pattern as OnAction_GenerateQuote)
    Dim prevCheckRow As Long: prevCheckRow = QUOTES_DATA_START + 1
    If Not IsEmpty(wsQ.Cells(prevCheckRow, 1).Value) Then
        Dim prevCust As String: prevCust = UCase(Trim(wsQ.Cells(prevCheckRow, 3).Value))
        Dim prevDate As String: prevDate = Format(wsQ.Cells(prevCheckRow, 2).Value, "DDMMM")
        Dim prevGid  As String: prevGid  = Trim(wsQ.Cells(prevCheckRow, 43).Value)
        If prevCust = UCase(Trim(m_Customer)) And prevDate = UCase(Format(Date, "DDMMM")) And prevGid <> "" Then
            qgid = prevGid
        End If
    End If

    ' Insert row at top of data
    wsQ.Rows(QUOTES_DATA_START).Insert Shift:=xlDown, CopyOrigin:=xlFormatFromLeftOrAbove
    Dim nr As Long: nr = QUOTES_DATA_START

    ' Write basic quote info (cols 1-11)
    wsQ.Cells(nr, 1)  = qid
    wsQ.Cells(nr, 2)  = Now
    wsQ.Cells(nr, 3)  = m_Customer
    wsQ.Cells(nr, 4)  = m_Carrier
    wsQ.Cells(nr, 5)  = m_POL
    wsQ.Cells(nr, 6)  = m_POD
    wsQ.Cells(nr, 7)  = m_Place
    wsQ.Cells(nr, 8)  = m_Note
    wsQ.Cells(nr, 9)  = m_Eff
    wsQ.Cells(nr, 10) = m_Exp
    If m_IsSOC Then wsQ.Cells(nr, 11) = "SOC" Else wsQ.Cells(nr, 11) = "COC"

    ' Container column mapping (mirrors OnAction_GenerateQuote layout):
    '   Buy:    20GP=12, 40GP=13, 40HC=14, 45HC=15, 40NOR=16, 20RF=17, 40RF=18
    '   Margin: 20GP=19, 40GP=20, 40HC=21, 45HC=22, 40NOR=23, 20RF=24, 40RF=25
    '   PUC:    20=26, 40=27, 40HC=28
    '   Sell:   20GP=29, 40GP=30, 40HC=31, 45HC=32, 40NOR=33, 20RF=34, 40RF=35
    Dim contMap As Object: Set contMap = CreateObject("Scripting.Dictionary")
    ' Array layout: buyCol, marCol, sellCol
    contMap.Add "20GP",  Array(12, 19, 29)
    contMap.Add "40HC",  Array(14, 21, 31)
    contMap.Add "45HC",  Array(15, 22, 32)
    contMap.Add "40NOR", Array(16, 23, 33)

    Dim contTypes As String: contTypes = ""
    Dim key As Variant
    For Each key In bd.Keys
        Dim keyStr As String: keyStr = CStr(key)
        If contMap.Exists(keyStr) Then
            Dim cols As Variant: cols = contMap(keyStr)
            Dim buyAmt As Double:  buyAmt  = CDbl(bd(keyStr))
            Dim sellAmt2 As Double: sellAmt2 = buyAmt + CDbl(mk)
            wsQ.Cells(nr, CLng(cols(0))) = buyAmt   ' Buy
            wsQ.Cells(nr, CLng(cols(1))) = CDbl(mk) ' Margin = tier markup
            wsQ.Cells(nr, CLng(cols(2))) = sellAmt2 ' Sell
            If contTypes <> "" Then contTypes = contTypes & ","
            contTypes = contTypes & keyStr
        End If
    Next key

    ' Status + metadata
    wsQ.Cells(nr, 36) = "PENDING"
    wsQ.Cells(nr, 37) = "MIX fix=" & fixQty & " fak=" & fakQty & _
                        " peer=" & CLng(st("PeerRow"))   ' Remark col 37
    wsQ.Cells(nr, 42) = UCase(contTypes)                 ' ContType col 42
    wsQ.Cells(nr, 43) = qgid                             ' QuoteGroupID col 43

    ' Format price columns
    Dim fc As Long
    For fc = 12 To 35: wsQ.Cells(nr, fc).NumberFormat = "$#,##0": Next fc

    Call MsgBoxOrSilent("Mix Quote " & qid & " created!" & vbCrLf & _
           "Customer: " & m_Customer & vbCrLf & _
           "Ratio: " & fixQty & " FIX + " & fakQty & " FAK" & vbCrLf & _
           "Containers blended: " & contTypes & vbCrLf & _
           "Tier markup: $" & Format(mk, "#,##0"), vbInformation, "Rate Mix")

    ' Reset state for next quote
    st("FixQty") = CLng(0)
    st("FakQty") = CLng(0)
    st("Ready") = False
    st("Markup") = CCur(0)
    st("PeerRow") = CLng(0)
    bd.RemoveAll
    RibbonInvalidateMixLabel
    Exit Sub

ErrHandler:
    g_LastError = "OnAction_MixQuote #" & Err.Number & ": " & Err.Description
    MsgBox "Error: " & Err.Description, vbCritical, "OnAction_MixQuote"
End Sub
