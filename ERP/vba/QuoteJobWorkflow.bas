' ============================================
' QUOTE-JOB WORKFLOW MACROS v9
' Option C: Single-Row Dynamic Markup (editable)
' + Quick Search + Job Cost/Profit
' ============================================

' ── LAYOUT CONSTANTS v6 — Right Sidebar ──
' Row 1: Data headers (POL, POD, Place, ..., 40RF)
' Row 2+: Pricing data
' Sidebar: Columns R-W (18-23), controls stacked vertically
' R1:W1 = Title bar "PRICING ENGINE"
' R3:S3 = POL search, R4:S4 = POD, R5:S5 = Place
' R6:S6 = Quick preset
' R9:S9 = Carrier dropdown
' R11:X11 = Carrier markup values (per container)
' R13:X13 = Global ALL markup values
' R16:S16 = PUC Route
' R18:U18 = PUC values
' R21:W21 = Customer
' R22:W22 = Generate Quote button
' Hidden base price columns: X(24) through AD(30)

Const DATA_START_ROW As Integer = 2
Const DATA_HEADER_ROW As Integer = 1
Const CUSTOMER_COL As Integer = 19    ' S21
Const CUSTOMER_ROW As Integer = 21
Const PRESET_COL As Integer = 19      ' S6
Const PRESET_ROW As Integer = 6
Const CARRIER_DROPDOWN_COL As Integer = 19  ' S9
Const CARRIER_DROPDOWN_ROW As Integer = 9
Const MARKUP_FIRST_COL As Integer = 18     ' R11 (carrier markup start)
Const MARKUP_VAL_ROW As Integer = 11       ' Carrier markup values row
Const GLOBAL_ROW As Integer = 13           ' R13 = ALL global markup
Const SEARCH_POL_COL As Integer = 19       ' S3
Const SEARCH_POD_COL As Integer = 19       ' S4
Const SEARCH_PLACE_COL As Integer = 19     ' S5
Const SEARCH_POL_ROW As Integer = 3
Const SEARCH_POD_ROW As Integer = 4
Const SEARCH_PLACE_ROW As Integer = 5
Const HIDDEN_BASE_COL As Integer = 24      ' X = hidden base price start

' Data column positions
Const COL_POL As Integer = 1
Const COL_POD As Integer = 2
Const COL_PLACE As Integer = 3
Const COL_CARRIER As Integer = 4
Const COL_COMMODITY As Integer = 5
Const COL_EFF As Integer = 6
Const COL_EXP As Integer = 7
Const COL_NOTE As Integer = 8
Const COL_SOURCE As Integer = 9
Const COL_FIRST_PRICE As Integer = 10  ' J = 20GP price

' Active Jobs column positions
Const JOB_SELLING_COL As Integer = 19      ' S
Const JOB_BUYING_COL As Integer = 20       ' T
Const JOB_PROFIT_COL As Integer = 21       ' U
Const JOB_MARGIN_COL As Integer = 22       ' V
Const JOB_COST_BKD_COL As Integer = 36     ' AJ
Const JOB_EMAIL_COL As Integer = 37        ' AK

' Markup_Store sheet name
Const STORE_SHEET As String = "Markup_Store"


Function FindSheet(searchName As String) As Worksheet
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Sheets
        If InStr(LCase(ws.Name), LCase(searchName)) > 0 Then
            Set FindSheet = ws
            Exit Function
        End If
    Next ws
    Set FindSheet = Nothing
End Function


Function GetContainerPriceCol(contType As String) As Integer
    Select Case contType
        Case "20GP": GetContainerPriceCol = 10  ' J
        Case "40GP": GetContainerPriceCol = 11  ' K
        Case "40HQ": GetContainerPriceCol = 12  ' L
        Case "45HQ": GetContainerPriceCol = 13  ' M
        Case "40NOR": GetContainerPriceCol = 14 ' N
        Case "20RF": GetContainerPriceCol = 15  ' O
        Case "40RF": GetContainerPriceCol = 16  ' P
        Case Else: GetContainerPriceCol = 0
    End Select
End Function


' Get the hidden base price column index for a container type
Function GetContainerBaseCol(contType As String) As Integer
    Select Case contType
        Case "20GP": GetContainerBaseCol = 24  ' X
        Case "40GP": GetContainerBaseCol = 25  ' Y
        Case "40HQ": GetContainerBaseCol = 26  ' Z
        Case "45HQ": GetContainerBaseCol = 27  ' AA
        Case "40NOR": GetContainerBaseCol = 28 ' AB
        Case "20RF": GetContainerBaseCol = 29  ' AC
        Case "40RF": GetContainerBaseCol = 30  ' AD
        Case Else: GetContainerBaseCol = 0
    End Select
End Function


' ════════════════════════════════════════════════════════════════
' SAVE CARRIER MARKUP — Saves J2:P2 values to Markup_Store
' ════════════════════════════════════════════════════════════════

Sub SaveCarrierMarkup(carrierName As String)
    Dim wsStore As Worksheet
    Dim wsPrice As Worksheet
    Dim r As Long
    
    Set wsPrice = FindSheet("Pricing")
    
    On Error Resume Next
    Set wsStore = ThisWorkbook.Sheets(STORE_SHEET)
    On Error GoTo 0
    If wsStore Is Nothing Then Exit Sub
    
    For r = 2 To wsStore.Cells(wsStore.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsStore.Cells(r, 1).Value)) = UCase(Trim(carrierName)) Then
            Dim i As Integer
            For i = 0 To 6
                Dim val As Variant
                val = wsPrice.Cells(CARRIER_DROPDOWN_ROW, MARKUP_FIRST_COL + i).Value
                If IsNumeric(val) Then
                    wsStore.Cells(r, 2 + i).Value = CDbl(val)
                Else
                    wsStore.Cells(r, 2 + i).Value = 0
                End If
            Next i
            Exit Sub
        End If
    Next r
End Sub


' ════════════════════════════════════════════════════════════════
' LOAD CARRIER MARKUP — Loads selected carrier values into J2:P2
' ════════════════════════════════════════════════════════════════

Sub LoadCarrierMarkup(carrierName As String)
    Dim wsStore As Worksheet
    Dim wsPrice As Worksheet
    Dim r As Long
    
    Set wsPrice = FindSheet("Pricing")
    
    On Error Resume Next
    Set wsStore = ThisWorkbook.Sheets(STORE_SHEET)
    On Error GoTo 0
    If wsStore Is Nothing Then Exit Sub
    
    For r = 2 To wsStore.Cells(wsStore.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsStore.Cells(r, 1).Value)) = UCase(Trim(carrierName)) Then
            Dim i As Integer
            For i = 0 To 6
                wsPrice.Cells(CARRIER_DROPDOWN_ROW, MARKUP_FIRST_COL + i).Value = wsStore.Cells(r, 2 + i).Value
            Next i
            Exit Sub
        End If
    Next r
    
    Dim j As Integer
    For j = 0 To 6
        wsPrice.Cells(CARRIER_DROPDOWN_ROW, MARKUP_FIRST_COL + j).Value = 0
    Next j
End Sub


' ════════════════════════════════════════════════════════════════
' SAVE GLOBAL MARKUP — Saves J3:P3 values to Markup_Store (ALL row)
' ════════════════════════════════════════════════════════════════

Sub SaveGlobalMarkup()
    Dim wsStore As Worksheet
    Dim wsPrice As Worksheet
    
    Set wsPrice = FindSheet("Pricing")
    
    On Error Resume Next
    Set wsStore = ThisWorkbook.Sheets(STORE_SHEET)
    On Error GoTo 0
    If wsStore Is Nothing Then Exit Sub
    
    Dim i As Integer
    For i = 0 To 6
        Dim val As Variant
        val = wsPrice.Cells(GLOBAL_ROW, MARKUP_FIRST_COL + i).Value
        If IsNumeric(val) Then
            wsStore.Cells(2, 2 + i).Value = CDbl(val)
        Else
            wsStore.Cells(2, 2 + i).Value = 0
        End If
    Next i
End Sub


' ════════════════════════════════════════════════════════════════
' HANDLE MARKUP CHANGE — Called by Worksheet_Change event
' Detects changes in I2 (carrier switch), J2-P2 (carrier markup),
' J3-P3 (global markup), A2-C2 (quick search)
' ════════════════════════════════════════════════════════════════

Sub HandlePricingSheetChange(ByVal Target As Range)
    Dim ws As Worksheet
    Set ws = Target.Worksheet
    
    ' Check if change is on the Pricing Dashboard
    If InStr(ws.Name, "Pricing") = 0 Then Exit Sub
    
    Dim r As Long, c As Long
    r = Target.Row
    c = Target.Column
    
    Application.EnableEvents = False
    On Error GoTo CleanUp
    
    ' Case 1: Carrier dropdown changed (I2) — save old, load new
    If r = CARRIER_DROPDOWN_ROW And c = CARRIER_DROPDOWN_COL Then
        ' Load the new carrier's markup values
        LoadCarrierMarkup CStr(Target.Value)
        GoTo CleanUp
    End If
    
    ' Case 2: Carrier markup changed (J2-P2) — save to Markup_Store
    If r = CARRIER_DROPDOWN_ROW And c >= MARKUP_FIRST_COL And c <= MARKUP_FIRST_COL + 6 Then
        Dim carrierName As String
        carrierName = ws.Cells(CARRIER_DROPDOWN_ROW, CARRIER_DROPDOWN_COL).Value
        SaveCarrierMarkup carrierName
        Application.Calculate  ' Force recalculate all formulas
        GoTo CleanUp
    End If
    
    ' Case 3: Global markup changed (J3-P3) — save to Markup_Store
    If r = GLOBAL_ROW And c >= MARKUP_FIRST_COL And c <= MARKUP_FIRST_COL + 6 Then
        SaveGlobalMarkup
        Application.Calculate  ' Force recalculate all formulas
        GoTo CleanUp
    End If
    
    ' Case 4: Quick search changed (A2-C2) — auto-filter
    If r = SEARCH_ROW And c >= SEARCH_POL_COL And c <= SEARCH_PLACE_COL Then
        ApplyQuickSearch
        GoTo CleanUp
    End If

CleanUp:
    Application.EnableEvents = True
End Sub


' ════════════════════════════════════════════════════════════════
' APPLY QUICK SEARCH — Auto-filter data table from A2/B2/C2
' ════════════════════════════════════════════════════════════════

Sub ApplyQuickSearch()
    Dim ws As Worksheet
    Set ws = FindSheet("Pricing")
    
    Dim polVal As String, podVal As String, placeVal As String
    polVal = Trim(ws.Cells(SEARCH_ROW, SEARCH_POL_COL).Value)
    podVal = Trim(ws.Cells(SEARCH_ROW, SEARCH_POD_COL).Value)
    placeVal = Trim(ws.Cells(SEARCH_ROW, SEARCH_PLACE_COL).Value)
    
    If ws.AutoFilterMode Then
        If ws.FilterMode Then ws.ShowAllData
    End If
    
    If polVal <> "" Then
        ws.Range("A" & DATA_HEADER_ROW).AutoFilter Field:=COL_POL, Criteria1:=polVal
    End If
    If podVal <> "" Then
        ' Wildcard: "USLAX" sẽ bắt cả "USLAX/LGB", "USLAX/NJ", "USLGB"
        ws.Range("A" & DATA_HEADER_ROW).AutoFilter Field:=COL_POD, Criteria1:="*" & podVal & "*"
    End If
    If placeVal <> "" Then
        ws.Range("A" & DATA_HEADER_ROW).AutoFilter Field:=COL_PLACE, Criteria1:="*" & placeVal & "*"
    End If
End Sub


Sub ClearQuickSearch()
    Dim ws As Worksheet
    Set ws = FindSheet("Pricing")
    
    ws.Cells(SEARCH_ROW, SEARCH_POL_COL).Value = ""
    ws.Cells(SEARCH_ROW, SEARCH_POD_COL).Value = ""
    ws.Cells(SEARCH_ROW, SEARCH_PLACE_COL).Value = ""
    
    If ws.AutoFilterMode Then
        If ws.FilterMode Then ws.ShowAllData
    End If
End Sub


' ════════════════════════════════════════════════════════════════
' APPLY QUICK PRESET — Shows/hides container price columns
' ════════════════════════════════════════════════════════════════

Sub ApplyQuickPreset()
    Dim ws As Worksheet
    Set ws = ActiveSheet
    
    Dim preset As String
    preset = UCase(Trim(ws.Cells(PRESET_ROW, PRESET_COL).Value))
    
    Dim allConts As Variant
    allConts = Array("20GP", "40GP", "40HQ", "45HQ", "40NOR", "20RF", "40RF")
    
    Dim showList As String
    Select Case preset
        Case "DRY":    showList = "20GP,40HQ"
        Case "REEFER": showList = "20RF,40RF"
        Case "FULL":   showList = "20GP,40GP,40HQ"
        Case "ALL":    showList = "20GP,40GP,40HQ,45HQ,40NOR,20RF,40RF"
        Case Else:     showList = ""
    End Select
    
    If showList = "" Then Exit Sub
    
    Dim i As Integer
    Dim contType As String
    Dim priceCol As Integer
    For i = 0 To UBound(allConts)
        contType = allConts(i)
        priceCol = GetContainerPriceCol(contType)
        ws.Columns(priceCol).Hidden = Not (InStr(showList, contType) > 0)
    Next i
End Sub


' ════════════════════════════════════════════════════════════════
' GENERATE QUOTE — Creates quote lines from visible filtered rows
' ════════════════════════════════════════════════════════════════

Sub GenerateQuote()
    Dim wsPrice As Worksheet
    Dim wsQuotes As Worksheet
    Dim nextRow As Long
    Dim r As Long
    Dim quoteID As String
    Dim customerName As String
    
    Set wsPrice = ActiveSheet
    Set wsQuotes = FindSheet("Quotes")
    
    If wsQuotes Is Nothing Then
        MsgBox "Cannot find Quotes sheet!", vbExclamation
        Exit Sub
    End If
    
    customerName = Trim(wsPrice.Cells(CUSTOMER_ROW, CUSTOMER_COL).Value)
    If customerName = "" Then
        MsgBox "Please enter Customer name in cell B4!", vbExclamation
        Exit Sub
    End If
    
    quoteID = UCase(Format(Date, "DDMMM")) & "-" & Format(Int((999 - 100 + 1) * Rnd + 100), "000")
    
    nextRow = wsQuotes.Cells(wsQuotes.Rows.Count, 1).End(xlUp).Row + 1
    If nextRow < 3 Then nextRow = 3
    
    Dim allConts As Variant
    allConts = Array("20GP", "40GP", "40HQ", "45HQ", "40NOR", "20RF", "40RF")
    
    Dim countCopied As Integer
    countCopied = 0
    
    ' Safety check: count visible rows first
    Dim lastRow As Long
    lastRow = wsPrice.Cells(wsPrice.Rows.Count, COL_POL).End(xlUp).Row
    
    If lastRow >= DATA_START_ROW Then
        Dim visibleCount As Long
        On Error Resume Next
        visibleCount = wsPrice.Range("A" & DATA_START_ROW & ":A" & lastRow).SpecialCells(xlCellTypeVisible).Count
        On Error GoTo 0
        
        If visibleCount > 200 Then
            If MsgBox(visibleCount & " rows visible. Generate quote for ALL?" & vbCrLf & _
                      "Tip: Use Quick Search to filter first.", vbYesNo + vbQuestion) = vbNo Then
                Exit Sub
            End If
        End If
    End If
    
    For r = DATA_START_ROW To lastRow
        If wsPrice.Rows(r).Hidden = False Then
            If wsPrice.Cells(r, COL_POL).Value <> "" Then
            
                Dim i As Integer
                For i = 0 To UBound(allConts)
                    Dim contType As String
                    Dim priceCol As Integer
                    Dim baseCol As Integer
                    Dim finalPrice As Double
                    Dim basePrice As Double
                    
                    contType = allConts(i)
                    priceCol = GetContainerPriceCol(contType)
                    baseCol = GetContainerBaseCol(contType)
                    
                    If wsPrice.Columns(priceCol).Hidden Then GoTo NextCont
                    
                    If IsNumeric(wsPrice.Cells(r, priceCol).Value) Then
                        finalPrice = wsPrice.Cells(r, priceCol).Value
                    Else
                        finalPrice = 0
                    End If
                    
                    ' Base price from hidden columns (raw cost)
                    If baseCol > 0 And IsNumeric(wsPrice.Cells(r, baseCol).Value) Then
                        basePrice = wsPrice.Cells(r, baseCol).Value
                    Else
                        basePrice = 0
                    End If
                    
                    ' Add PUC to buying rate if SOC — auto-lookup from PUC_Lookup by Place
                    Dim pucValue As Double
                    pucValue = 0
                    If UCase(Trim(wsPrice.Cells(r, COL_NOTE).Value)) = "SOC" Then
                        ' Auto-lookup PUC from PUC_Lookup sheet using Place matching
                        Dim wsPUC As Worksheet
                        On Error Resume Next
                        Set wsPUC = ThisWorkbook.Sheets("PUC_Lookup")
                        On Error GoTo 0
                        If Not wsPUC Is Nothing Then
                            Dim pucLkCol As Integer
                            Select Case contType
                                Case "20GP", "20RF": pucLkCol = 2   ' Col B
                                Case "40GP", "40NOR": pucLkCol = 3  ' Col C
                                Case "40HQ", "45HQ": pucLkCol = 4  ' Col D
                                Case "40RF": pucLkCol = 5           ' Col E
                                Case Else: pucLkCol = 0
                            End Select
                            If pucLkCol > 0 Then
                                Dim placeVal As String
                                placeVal = UCase(Trim(wsPrice.Cells(r, COL_PLACE).Value))
                                Dim pr As Long
                                For pr = 2 To wsPUC.Cells(wsPUC.Rows.Count, 1).End(xlUp).Row
                                    If InStr(1, placeVal, UCase(Trim(wsPUC.Cells(pr, 1).Value)), vbTextCompare) > 0 Then
                                        If IsNumeric(wsPUC.Cells(pr, pucLkCol).Value) Then
                                            pucValue = CDbl(wsPUC.Cells(pr, pucLkCol).Value)
                                        End If
                                        Exit For
                                    End If
                                Next pr
                            End If
                        End If
                    End If
                    
                    ' Buying rate = base + PUC (actual cost)
                    Dim buyingRate As Double
                    buyingRate = basePrice + pucValue
                    
                    If finalPrice > 0 Then
                        wsQuotes.Cells(nextRow, 1) = quoteID
                        wsQuotes.Cells(nextRow, 2) = Now
                        wsQuotes.Cells(nextRow, 3) = customerName
                        wsQuotes.Cells(nextRow, 4) = wsPrice.Cells(r, COL_POL).Value
                        wsQuotes.Cells(nextRow, 5) = wsPrice.Cells(r, COL_POD).Value
                        wsQuotes.Cells(nextRow, 6) = wsPrice.Cells(r, COL_PLACE).Value
                        wsQuotes.Cells(nextRow, 7) = wsPrice.Cells(r, COL_CARRIER).Value
                        wsQuotes.Cells(nextRow, 8) = ""
                        wsQuotes.Cells(nextRow, 9) = wsPrice.Cells(r, COL_COMMODITY).Value
                        wsQuotes.Cells(nextRow, 10) = contType
                        wsQuotes.Cells(nextRow, 11) = finalPrice       ' Selling rate (base+PUC+markup)
                        wsQuotes.Cells(nextRow, 12) = wsPrice.Cells(r, COL_EFF).Value
                        wsQuotes.Cells(nextRow, 13) = wsPrice.Cells(r, COL_EXP).Value
                        wsQuotes.Cells(nextRow, 14) = wsPrice.Cells(r, COL_NOTE).Value
                        wsQuotes.Cells(nextRow, 15) = "PENDING"
                        wsQuotes.Cells(nextRow, 16) = Now
                        wsQuotes.Cells(nextRow, 17) = buyingRate       ' Buying rate (base+PUC)
                        
                        nextRow = nextRow + 1
                        countCopied = countCopied + 1
                    End If

NextCont:
                Next i
            End If
        End If
    Next r
    
    If countCopied = 0 Then
        MsgBox "No visible pricing rows with price > 0 found!" & vbCrLf & _
               "Tip: Use Quick Search or Excel filter first.", vbExclamation
        Exit Sub
    End If
    
    On Error Resume Next
    ThisWorkbook.Save
    If Err.Number <> 0 Then
        MsgBox "Quote created but auto-save failed. Please save manually (Ctrl+S).", vbExclamation
        Err.Clear
    End If
    On Error GoTo 0
    
    MsgBox "Quote " & quoteID & " created!" & vbCrLf & _
           "Customer: " & customerName & vbCrLf & _
           "Lines: " & countCopied, vbInformation
End Sub


' ════════════════════════════════════════════════════════════════
' MARK QUOTE WIN — Creates Job with Buying Rate, Profit, Margin
' + Cost Breakdown + Email Booking Link
' ════════════════════════════════════════════════════════════════

Sub MarkQuoteWin()
    Dim wsQuotes As Worksheet
    Dim wsJobs As Worksheet
    Dim selectedRow As Long
    Dim quoteID As String
    Dim jobID As String
    Dim nextJobRow As Long
    Dim quantity As Integer
    Dim volume As Integer
    Dim contType As String
    Dim sellingRate As Double
    Dim buyingRate As Double
    Dim profit As Double
    Dim margin As Double
    Dim revenue As Double
    
    Set wsQuotes = ActiveSheet
    selectedRow = Selection.Row
    
    If selectedRow < 3 Then
        MsgBox "Select a quote data row (row 3+)!", vbExclamation
        Exit Sub
    End If
    
    quoteID = wsQuotes.Cells(selectedRow, 1).Value
    If quoteID = "" Then
        MsgBox "No quote in this row!", vbExclamation
        Exit Sub
    End If
    
    Dim currentStatus As String
    currentStatus = wsQuotes.Cells(selectedRow, 15).Value
    
    If currentStatus = "WIN" Then
        MsgBox "Already marked as WIN!", vbExclamation
        Exit Sub
    End If
    
    If InStr(currentStatus, "LOST") > 0 Then
        If MsgBox("Quote was " & currentStatus & ". Confirm WIN anyway?", vbYesNo + vbQuestion) = vbNo Then
            Exit Sub
        End If
    End If
    
    ' Ask for quantity
    Dim qtyInput As String
    qtyInput = InputBox("Enter Container Quantity:", "Mark WIN", "1")
    If qtyInput = "" Then Exit Sub
    quantity = CInt(qtyInput)
    If quantity < 1 Then quantity = 1
    
    ' Container type and volume
    contType = wsQuotes.Cells(selectedRow, 10).Value
    If contType = "20GP" Or contType = "20RF" Then
        volume = quantity * 1
    Else
        volume = quantity * 2
    End If
    
    ' Selling and Buying rates
    sellingRate = 0
    buyingRate = 0
    If IsNumeric(wsQuotes.Cells(selectedRow, 11).Value) Then
        sellingRate = CDbl(wsQuotes.Cells(selectedRow, 11).Value)
    End If
    If IsNumeric(wsQuotes.Cells(selectedRow, 17).Value) Then
        buyingRate = CDbl(wsQuotes.Cells(selectedRow, 17).Value)
    End If
    
    ' Calculate profit and margin
    revenue = sellingRate * quantity
    profit = (sellingRate - buyingRate) * quantity
    If revenue > 0 Then
        margin = (profit / revenue) * 100
    Else
        margin = 0
    End If
    
    ' Find Jobs sheet
    Set wsJobs = FindSheet("Active")
    If wsJobs Is Nothing Then Set wsJobs = FindSheet("Jobs")
    If wsJobs Is Nothing Then
        MsgBox "Cannot find Active Jobs sheet!", vbExclamation
        Exit Sub
    End If
    
    ' Generate Job ID — format: DD/MM-NN (customer sequential in month)
    Dim customer As String
    customer = wsQuotes.Cells(selectedRow, 3).Value
    Dim custJobCount As Integer
    custJobCount = 0
    Dim jr As Long
    For jr = 8 To wsJobs.Cells(wsJobs.Rows.Count, 1).End(xlUp).Row
        If wsJobs.Cells(jr, 4).Value = customer Then
            ' Check if same month
            Dim jobDateStr As String
            jobDateStr = wsJobs.Cells(jr, 1).Value
            If InStr(jobDateStr, "/" & Format(Month(Date), "00")) > 0 Then
                custJobCount = custJobCount + 1
            End If
        End If
    Next jr
    custJobCount = custJobCount + 1
    jobID = Format(Day(Date), "0") & "/" & Format(Month(Date), "00") & "-" & Format(custJobCount, "00")
    
    ' Find next row in Jobs
    nextJobRow = wsJobs.Cells(wsJobs.Rows.Count, 1).End(xlUp).Row + 1
    If nextJobRow < 8 Then nextJobRow = 8
    
    wsJobs.Cells(nextJobRow, 1) = jobID                                        ' A: Job_ID
    ' B: Quote_ID — REMOVED per user request
    wsJobs.Cells(nextJobRow, 4) = customer                                     ' D: Customer_Name
    ' F: Routing — format: POL-PLACE VIA POD
    Dim pol As String, pod As String, place As String
    pol = wsQuotes.Cells(selectedRow, 4).Value
    pod = wsQuotes.Cells(selectedRow, 5).Value
    place = wsQuotes.Cells(selectedRow, 6).Value
    If place <> "" Then
        wsJobs.Cells(nextJobRow, 6) = pol & "-" & place & " VIA " & pod
    Else
        wsJobs.Cells(nextJobRow, 6) = pol & "-" & pod
    End If
    wsJobs.Cells(nextJobRow, 14) = wsQuotes.Cells(selectedRow, 7).Value        ' N: Carrier
    wsJobs.Cells(nextJobRow, 15) = wsQuotes.Cells(selectedRow, 9).Value        ' O: Contract_Type
    wsJobs.Cells(nextJobRow, 16) = contType                                    ' P: Container_Type
    wsJobs.Cells(nextJobRow, 17) = quantity                                    ' Q: Quantity
    wsJobs.Cells(nextJobRow, 18) = volume                                      ' R: Volume
    wsJobs.Cells(nextJobRow, JOB_SELLING_COL) = sellingRate                    ' S: Selling_Rate
    wsJobs.Cells(nextJobRow, JOB_BUYING_COL) = buyingRate                      ' T: Buying_Rate
    wsJobs.Cells(nextJobRow, JOB_PROFIT_COL) = profit                          ' U: Profit
    wsJobs.Cells(nextJobRow, JOB_MARGIN_COL) = Round(margin, 1)                ' V: Profit_Margin
    wsJobs.Cells(nextJobRow, 23) = "Booked"                                    ' W: Status
    ' AH: Created_Date — REMOVED per user request
    
    ' Cost Breakdown — VLOOKUP from BasicCost_Lookup hidden sheet
    Dim carrier As String
    carrier = wsQuotes.Cells(selectedRow, 7).Value
    
    Dim costBreakdown As String
    Dim bcKey As String
    Dim bcContract As String
    Dim bcGroup As String
    bcKey = UCase(Trim(pol)) & "|" & UCase(Trim(pod)) & "|" & UCase(Trim(place)) & "|" & UCase(Trim(carrier)) & "|" & contType & "|" & UCase(Trim(CStr(wsQuotes.Cells(selectedRow, 14).Value)))
    
    ' Try VLOOKUP from BasicCost_Lookup
    Dim wsBC As Worksheet
    On Error Resume Next
    Set wsBC = ThisWorkbook.Sheets("BasicCost_Lookup")
    On Error GoTo 0
    
    bcContract = ""
    bcGroup = ""
    costBreakdown = ""
    
    If Not wsBC Is Nothing Then
        Dim bcR As Long
        Dim bestRow As Long
        Dim bestDiff As Double
        Dim bcTotalCharge As Double
        bestRow = 0
        bestDiff = 999999999#
        
        For bcR = 2 To wsBC.Cells(wsBC.Rows.Count, 1).End(xlUp).Row
            If UCase(Trim(CStr(wsBC.Cells(bcR, 1).Value))) = bcKey Then
                ' Found matching key — check TotalCharge (col 5) closeness to buyingRate
                bcTotalCharge = 0
                If IsNumeric(wsBC.Cells(bcR, 5).Value) Then
                    bcTotalCharge = CDbl(wsBC.Cells(bcR, 5).Value)
                End If
                
                Dim diff As Double
                diff = Abs(bcTotalCharge - buyingRate)
                If diff < bestDiff Then
                    bestDiff = diff
                    bestRow = bcR
                End If
            End If
        Next bcR
        
        ' Use the closest matching entry
        If bestRow > 0 Then
            bcContract = wsBC.Cells(bestRow, 2).Value
            bcGroup = wsBC.Cells(bestRow, 3).Value
            costBreakdown = wsBC.Cells(bestRow, 4).Value
        End If
    End If
    
    ' If no lookup found, build simplified breakdown
    If costBreakdown = "" Then
        Dim markupTotal As Double
        markupTotal = sellingRate - buyingRate
        costBreakdown = "COST: O/F $" & Format(buyingRate, "#,##0")
        If markupTotal > 0 Then
            costBreakdown = costBreakdown & " + MARKUP $" & Format(markupTotal, "#,##0")
        End If
    End If
    
    wsJobs.Cells(nextJobRow, JOB_COST_BKD_COL) = costBreakdown
    wsJobs.Cells(nextJobRow, JOB_COST_BKD_COL).Font.Name = "Consolas"
    wsJobs.Cells(nextJobRow, JOB_COST_BKD_COL).Font.Size = 9
    wsJobs.Cells(nextJobRow, JOB_COST_BKD_COL).WrapText = True
    
    ' Email Booking Request — Rules v2.0
    Dim volStr As String
    Dim contCode As String
    Select Case contType
        Case "20GP": contCode = "20DC"
        Case "40GP": contCode = "40DC"
        Case "40HQ": contCode = "40HC"
        Case "45HQ": contCode = "45HC"
        Case Else:   contCode = contType
    End Select
    volStr = quantity & "X" & contCode
    
    ' Determine DRY vs REEFER
    Dim isReefer As Boolean
    isReefer = (contType = "20RF" Or contType = "40RF")
    
    ' POL full name mapping
    Dim polFull As String
    Dim defaultGW As String
    Dim showMTPickup As Boolean
    Select Case pol
        Case "HCM":
            polFull = "HO CHI MINH, VN": defaultGW = "20 TONS": showMTPickup = True
        Case "HPH":
            polFull = "HAI PHONG, VN": defaultGW = "17 TONS": showMTPickup = False
        Case "DAD":
            polFull = "DA NANG, VN": defaultGW = "17 TONS": showMTPickup = False
        Case "UIH":
            polFull = "QUI NHON, VN": defaultGW = "17 TONS": showMTPickup = False
        Case "VUT":
            polFull = "VUNG TAU, VN": defaultGW = "20 TONS": showMTPickup = True
        Case Else
            polFull = pol: defaultGW = "20 TONS": showMTPickup = False
    End Select
    
    ' Contract display — REEFER prefix
    Dim contractDisplay As String
    If bcContract <> "" Then
        If isReefer Then
            contractDisplay = "REEFER " & bcContract
        Else
            contractDisplay = bcContract
        End If
    Else
        contractDisplay = "(N/A)"
    End If
    
    ' Group rate display — always show, N/A if empty
    Dim groupDisplay As String
    If bcGroup <> "" And bcGroup <> "N/A" Then
        groupDisplay = bcGroup
    Else
        groupDisplay = "N/A"
    End If
    
    ' Carrier display (e.g. "ONE SOC")
    Dim carrierDisplay As String
    carrierDisplay = carrier
    
    ' Route for subject: POL-PLACE VIA POD
    Dim routeForSubject As String
    If place <> "" Then
        routeForSubject = pol & "-" & place & " VIA " & pod
    Else
        routeForSubject = pol & "-" & pod
    End If
    
    Dim NL As String
    NL = "%0D%0A"
    
    ' Subject: CUSTOMER BOOKING | ROUTE | CONT | CARRIER | NELSON |
    Dim emailSubject As String
    emailSubject = customer & " BOOKING | " & routeForSubject & " | " & volStr & " | " & carrierDisplay & " | NELSON |"
    
    ' Body
    Dim emailBody As String
    emailBody = "Dear Mira Cus Team/Pudong," & NL & NL & _
                "Please help me release the booking as below info:" & NL & _
                "- Carrier: " & carrierDisplay & NL & _
                "- Contract number: " & contractDisplay & NL & _
                "- Group rate for USCA only (based on pricing's rate, if any): " & groupDisplay & NL & _
                "- NAC (if any): Actual NAC" & NL & _
                "- POL: " & polFull & NL & _
                "- POD: " & pod & NL & _
                "- FND/DEL: " & place & NL & _
                "- ETD: " & NL & _
                "- CMD: " & NL & _
                "- HS code: " & NL & _
                "- Volume: " & volStr & NL & _
                "- Gross Weight per container (GW): " & defaultGW & NL & _
                "- Stuffing place: WAREHOUSE" & NL
    
    ' MT pickup — only HCM (default), VUT
    If showMTPickup Then
        emailBody = emailBody & _
                    "- MT pick up: ICD TANAMEXCO" & NL & _
                    "- Full return: ICD TANAMEXCO" & NL
    End If
    
    ' CMA Payment Term
    If carrier = "CMA" Then
        emailBody = emailBody & "- Payment term: PREPAID" & NL
    End If
    
    ' Reefer section
    If isReefer Then
        emailBody = emailBody & _
                    "- REEFER CONTAINER" & NL & _
                    "  Temperature: -18C" & NL & _
                    "  Ventilation: CLOSED" & NL & _
                    "  Humidity: NO" & NL
    End If
    
    emailBody = emailBody & _
                "- Special Remark: HOT SHIPMENT, CONT SACH TOT" & NL & NL & _
                "With warmest regards," & NL & _
                "Nelson Huynh" & NL & _
                "Sales Team Leader" & NL & NL & _
                "Remark: *For any important message, please copy to my superior, Mrs Jessie (Sale Manageress), at jessie@pudongprime.vn." & NL & NL & _
                "Pudong Prime International Co Ltd" & NL & _
                "(Ho Chi Minh Branch)" & NL & _
                "L'MAK The Signature, 147 - 147BIS Hai Ba Trung Street, Xuan Hoa Ward, Ho Chi MinhCity" & NL & _
                "Phone: +84 28 36362111 ext. 162" & NL & _
                "Cell: +84 931.301.014" & NL & _
                "E-mail: nelson@pudongprime.vn" & NL & _
                "Skype: huynhyohan" & NL & _
                "Web-site: www.pudongprime.com" & NL & _
                "Office: Vietnam | China | USA"
    
    Dim mailto As String
    mailto = "mailto:?subject=" & emailSubject & "&body=" & emailBody
    
    wsJobs.Cells(nextJobRow, JOB_EMAIL_COL).Hyperlinks.Add _
        Anchor:=wsJobs.Cells(nextJobRow, JOB_EMAIL_COL), _
        Address:=mailto, _
        TextToDisplay:="Request BKG"
    wsJobs.Cells(nextJobRow, JOB_EMAIL_COL).Font.Color = RGB(5, 99, 193)
    wsJobs.Cells(nextJobRow, JOB_EMAIL_COL).Font.Bold = True
    wsJobs.Cells(nextJobRow, JOB_EMAIL_COL).Font.Size = 10
    
    ' Format profit cells
    If profit > 0 Then
        wsJobs.Cells(nextJobRow, JOB_PROFIT_COL).Font.Color = RGB(0, 128, 0)
    ElseIf profit < 0 Then
        wsJobs.Cells(nextJobRow, JOB_PROFIT_COL).Font.Color = RGB(192, 0, 0)
    End If
    wsJobs.Cells(nextJobRow, JOB_MARGIN_COL).NumberFormat = "0.0%"
    wsJobs.Cells(nextJobRow, JOB_MARGIN_COL).Value = margin / 100  ' Store as decimal
    
    ' Update Quote status
    wsQuotes.Cells(selectedRow, 15) = "WIN"
    wsQuotes.Cells(selectedRow, 16) = Now
    wsQuotes.Cells(selectedRow, 19) = quantity
    wsQuotes.Cells(selectedRow, 20) = volume
    wsQuotes.Cells(selectedRow, 21) = jobID
    wsQuotes.Cells(selectedRow, 15).Interior.Color = RGB(0, 176, 80)
    wsQuotes.Cells(selectedRow, 15).Font.Color = RGB(255, 255, 255)
    
    MsgBox "Quote " & quoteID & " = WIN!" & vbCrLf & vbCrLf & _
           "Container: " & contType & " x " & quantity & vbCrLf & _
           "Volume: " & volume & " TEU" & vbCrLf & _
           "Selling: $" & Format(sellingRate, "#,##0") & vbCrLf & _
           "Buying: $" & Format(buyingRate, "#,##0") & vbCrLf & _
           "Profit: $" & Format(profit, "#,##0") & " (" & Format(margin, "0.0") & "%)" & vbCrLf & vbCrLf & _
           "Job " & jobID & " created!" & vbCrLf & _
           "📧 Email link added!", vbInformation
End Sub


Sub MarkQuoteLost()
    Dim wsQuotes As Worksheet
    Dim selectedRow As Long
    Dim reason As String
    
    Set wsQuotes = ActiveSheet
    selectedRow = Selection.Row
    
    If selectedRow < 3 Then
        MsgBox "Select a quote data row!", vbExclamation
        Exit Sub
    End If
    
    reason = InputBox("Reason for LOST:", "Mark Lost", "")
    
    wsQuotes.Cells(selectedRow, 15) = "LOST"
    wsQuotes.Cells(selectedRow, 16) = Now
    wsQuotes.Cells(selectedRow, 14) = reason
    wsQuotes.Cells(selectedRow, 15).Interior.Color = RGB(192, 0, 0)
    wsQuotes.Cells(selectedRow, 15).Font.Color = RGB(255, 255, 255)
    
    MsgBox "Marked as LOST.", vbInformation
End Sub


Sub CheckAutoLost()
    Dim ws As Worksheet
    Dim r As Long
    Dim autoCount As Integer
    
    Set ws = FindSheet("Quotes")
    If ws Is Nothing Then Exit Sub
    
    autoCount = 0
    For r = 3 To ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
        If ws.Cells(r, 15).Value = "PENDING" Then
            If IsDate(ws.Cells(r, 2).Value) Then
                If Date - ws.Cells(r, 2).Value > 7 Then
                    ws.Cells(r, 15) = "AUTO-LOST"
                    ws.Cells(r, 16) = Now
                    ws.Cells(r, 15).Interior.Color = RGB(192, 0, 0)
                    ws.Cells(r, 15).Font.Color = RGB(255, 255, 255)
                    autoCount = autoCount + 1
                End If
            End If
        End If
    Next r
    
    If autoCount > 0 Then
        MsgBox autoCount & " quotes marked as AUTO-LOST.", vbInformation
    Else
        MsgBox "No quotes to auto-mark.", vbInformation
    End If
End Sub


' ════════════════════════════════════════════════════════════════
' ADD BUTTONS
' ════════════════════════════════════════════════════════════════

Sub AddDashboardButtons()
    Dim ws As Worksheet
    Dim btn As Button
    
    Set ws = ActiveSheet
    On Error Resume Next
    ws.Buttons.Delete
    On Error GoTo 0
    
    Set btn = ws.Buttons.Add(350, 55, 100, 25)
    btn.Text = "Apply Preset"
    btn.OnAction = "ApplyQuickPreset"
    btn.Font.Bold = True
    
    Set btn = ws.Buttons.Add(350, 85, 210, 30)
    btn.Text = "GENERATE QUOTE"
    btn.OnAction = "GenerateQuote"
    btn.Font.Bold = True
    btn.Font.Size = 11
    
    Set btn = ws.Buttons.Add(50, 25, 100, 22)
    btn.Text = "Apply Search"
    btn.OnAction = "ApplyQuickSearch"
    btn.Font.Bold = True
    
    Set btn = ws.Buttons.Add(160, 25, 80, 22)
    btn.Text = "Clear"
    btn.OnAction = "ClearQuickSearch"
    
    MsgBox "Dashboard buttons added!", vbInformation
End Sub


Sub AddQuoteButtons()
    Dim ws As Worksheet
    Dim btn As Button
    
    Set ws = ActiveSheet
    On Error Resume Next
    ws.Buttons.Delete
    On Error GoTo 0
    
    Set btn = ws.Buttons.Add(400, 5, 80, 28)
    btn.Text = "Mark WIN"
    btn.OnAction = "MarkQuoteWin"
    btn.Font.Bold = True
    
    Set btn = ws.Buttons.Add(490, 5, 80, 28)
    btn.Text = "Mark LOST"
    btn.OnAction = "MarkQuoteLost"
    btn.Font.Bold = True
    
    Set btn = ws.Buttons.Add(580, 5, 100, 28)
    btn.Text = "Check Auto-Lost"
    btn.OnAction = "CheckAutoLost"
    btn.Font.Bold = True
    
    MsgBox "Quote buttons added!", vbInformation
End Sub
