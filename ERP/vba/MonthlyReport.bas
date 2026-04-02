Attribute VB_Name = "MonthlyReport"
Option Explicit

' ============================================================
'  MONTHLY REPORT EXPORT — ERP V13
'  Exports Active Jobs filtered by FAST_JOB_NO month
'  to a new sheet (e.g. "FEB 2026" format).
' ============================================================

Public Sub ExportMonthlyReport(control As IRibbonControl)
    On Error GoTo ErrHandler

    ' Step 1 — Input month
    Dim reportMonth As String
    Dim defaultMonth As String
    Dim prevMo As Integer
    prevMo = Month(Date) - 1
    If prevMo < 1 Then prevMo = 12
    Dim prevYr As Integer
    prevYr = Year(Date)
    If prevMo = 12 Then prevYr = prevYr - 1
    defaultMonth = Format(prevYr, "0000") & "-" & Format(prevMo, "00")

    reportMonth = InputBox( _
        "Enter report month (YYYY-MM):" & vbCrLf & vbCrLf & _
        "System will export all Active Jobs where" & vbCrLf & _
        "FAST_JOB_NO (col AL) matches this month." & vbCrLf & vbCrLf & _
        "Example: 2026-02 exports all SE2602/XXXX jobs", _
        "Monthly Report Export", defaultMonth)
    If Len(Trim(reportMonth)) = 0 Then Exit Sub
    If Not reportMonth Like "20##-##" Then
        MsgBox "Invalid format. Use YYYY-MM", vbExclamation, "Report"
        Exit Sub
    End If

    ' Step 2 — Collect matching jobs
    Dim wsJobs As Worksheet
    Set wsJobs = ThisWorkbook.Sheets("Active Jobs")
    Dim lastRow As Long
    lastRow = wsJobs.Cells(wsJobs.Rows.Count, "A").End(xlUp).Row

    Dim matchRows() As Long
    Dim matchCount As Long: matchCount = 0

    Dim i As Long
    For i = 8 To lastRow
        Dim jobNo As String
        jobNo = Trim(CStr(wsJobs.Cells(i, "AL").Value))
        If Len(jobNo) >= 9 Then
            ' Extract YYMM from SE2602/XXXX
            Dim yy As String: yy = "20" & Mid(jobNo, 3, 2)
            Dim mm As String: mm = Mid(jobNo, 5, 2)
            If yy & "-" & mm = reportMonth Then
                matchCount = matchCount + 1
                ReDim Preserve matchRows(1 To matchCount)
                matchRows(matchCount) = i
            End If
        End If
    Next i

    If matchCount = 0 Then
        MsgBox "No jobs found for " & reportMonth & vbCrLf & vbCrLf & _
               "Check that FAST_JOB_NO (col AL) is filled in Active Jobs.", _
               vbInformation, "Report"
        Exit Sub
    End If

    ' Step 3 — Sheet name (FEB 2026 format)
    Dim moNames(1 To 12) As String
    moNames(1) = "JAN": moNames(2) = "FEB": moNames(3) = "MAR"
    moNames(4) = "APR": moNames(5) = "MAY": moNames(6) = "JUN"
    moNames(7) = "JUL": moNames(8) = "AUG": moNames(9) = "SEP"
    moNames(10) = "OCT": moNames(11) = "NOV": moNames(12) = "DEC"
    Dim moNum As Integer: moNum = CInt(Mid(reportMonth, 6, 2))
    Dim yrStr As String: yrStr = Left(reportMonth, 4)
    Dim sheetName As String
    sheetName = moNames(moNum) & " " & yrStr

    Application.DisplayAlerts = False
    On Error Resume Next
    ThisWorkbook.Sheets(sheetName).Delete
    On Error GoTo ErrHandler
    Application.DisplayAlerts = True

    Dim wsR As Worksheet
    Set wsR = ThisWorkbook.Sheets.Add( _
        After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
    wsR.Name = sheetName

    ' Step 4 — Headers
    wsR.Cells(1, 1) = "No"
    wsR.Cells(1, 2) = "SHIPPER/" & Chr(10) & "CONSIGNEE"
    wsR.Cells(1, 3) = "POL/POD"
    wsR.Cells(1, 4) = "FINAL DEST"
    wsR.Cells(1, 5) = "ETD"
    wsR.Cells(1, 6) = "ETA"
    wsR.Cells(1, 7) = "CARRIER/" & Chr(10) & "COLOADER"
    wsR.Cells(1, 8) = "HBL"
    wsR.Cells(1, 9) = "JOB NO"
    wsR.Cells(1, 10) = "Volume"
    wsR.Cells(1, 18) = "Buying"
    wsR.Cells(1, 19) = "Selling"
    wsR.Cells(1, 20) = "Profit" & Chr(10) & "Share"
    wsR.Cells(1, 21) = "KICK BACK"
    wsR.Cells(1, 24) = "Net" & Chr(10) & "Profit"

    ' Row 2 sub-headers
    wsR.Cells(2, 10) = "AIR": wsR.Cells(2, 11) = "LCL"
    wsR.Cells(2, 12) = "20RF": wsR.Cells(2, 13) = "20'"
    wsR.Cells(2, 14) = "40'": wsR.Cells(2, 15) = "HC"
    wsR.Cells(2, 16) = "40RF": wsR.Cells(2, 17) = "45"
    wsR.Cells(2, 21) = "Client"
    wsR.Cells(2, 22) = "Carrier"
    wsR.Cells(2, 23) = "Tax"

    ' Merge headers
    wsR.Range("A1:A2").Merge: wsR.Range("B1:B2").Merge
    wsR.Range("C1:C2").Merge: wsR.Range("D1:D2").Merge
    wsR.Range("E1:E2").Merge: wsR.Range("F1:F2").Merge
    wsR.Range("G1:G2").Merge: wsR.Range("H1:H2").Merge
    wsR.Range("I1:I2").Merge
    wsR.Range("J1:Q1").Merge
    wsR.Range("R1:R2").Merge: wsR.Range("S1:S2").Merge
    wsR.Range("T1:T2").Merge
    wsR.Range("U1:W1").Merge
    wsR.Range("X1:X2").Merge

    ' Header styling
    With wsR.Range("A1:X2")
        .Font.Name = "Calibri"
        .Font.Size = 10
        .Font.Bold = True
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
        .WrapText = True
    End With
    wsR.Range("A1:X1").Interior.Color = RGB(31, 78, 121)
    wsR.Range("A1:X1").Font.Color = RGB(255, 255, 255)
    wsR.Range("A2:X2").Interior.Color = RGB(189, 215, 238)

    ' Step 5 — Write data rows
    Dim dataRow As Long: dataRow = 3
    Dim rowNum As Integer: rowNum = 1

    For i = 1 To matchCount
        Dim srcRow As Long: srcRow = matchRows(i)

        ' Parse routing from col F: "HCM-CHICAGO, IL VIA LAX/LGB"
        Dim routing As String
        routing = Trim(CStr(wsJobs.Cells(srcRow, "F").Value))
        Dim polVal As String, podVal As String, destVal As String
        Dim dashPos As Long: dashPos = InStr(routing, "-")
        Dim viaPos As Long: viaPos = InStr(UCase(routing), " VIA ")
        If dashPos > 0 Then
            polVal = Trim(Left(routing, dashPos - 1))
        Else
            polVal = routing
        End If
        If viaPos > 0 Then
            podVal = Trim(Mid(routing, viaPos + 5))
            destVal = Trim(Mid(routing, dashPos + 1, viaPos - dashPos - 1))
        ElseIf dashPos > 0 Then
            podVal = ""
            destVal = Trim(Mid(routing, dashPos + 1))
        Else
            podVal = "": destVal = ""
        End If

        ' Container → volume column
        Dim contVal As String
        contVal = UCase(Trim(CStr(wsJobs.Cells(srcRow, "P").Value)))
        Dim qtyVal As Integer
        qtyVal = Val(wsJobs.Cells(srcRow, "Q").Value)
        If qtyVal = 0 Then qtyVal = 1
        Dim volCol As Integer
        Select Case contVal
            Case "20GP": volCol = 13
            Case "40GP": volCol = 14
            Case "40HC", "40HQ": volCol = 15
            Case "45HQ": volCol = 17
            Case "20RF": volCol = 12
            Case "40RF": volCol = 16
            Case Else: volCol = 14
        End Select

        ' Parse carrier kickback from AJ text
        Dim ajText As String
        ajText = Trim(CStr(wsJobs.Cells(srcRow, "AJ").Value))
        Dim comPct As Double: comPct = 35
        If InStr(ajText, "CAR COM 10") > 0 Then comPct = 10
        Dim hdlNum As Double: hdlNum = 0
        Dim dPos As Long
        dPos = InStrRev(ajText, "- $")
        If dPos > 0 Then
            Dim hdlRaw As String
            hdlRaw = Mid(ajText, dPos + 3)
            Dim slashPos As Long: slashPos = InStr(hdlRaw, "/")
            If slashPos > 0 Then hdlRaw = Left(hdlRaw, slashPos - 1)
            hdlNum = Val(Replace(Trim(hdlRaw), ",", ""))
        End If
        Dim nelsonPct As Double
        If comPct = 10 Then nelsonPct = 90 Else nelsonPct = 65
        Dim carrierKB As Double: carrierKB = 0
        If hdlNum > 0 Then
            carrierKB = (hdlNum / nelsonPct * 100) * (comPct / 100) * qtyVal
            carrierKB = Int(carrierKB * 1000) / 1000
        End If

        ' Tax = carrier KB x 26.9%
        Dim taxAmt As Double
        taxAmt = Int(carrierKB * 0.269 * 1000) / 1000

        ' Profit share = HDL x qty (until CRM)
        Dim profitShare As Double
        profitShare = hdlNum * qtyVal

        ' Financial values
        Dim selRate As Double: selRate = Val(wsJobs.Cells(srcRow, "S").Value)
        Dim buyRate As Double: buyRate = Val(wsJobs.Cells(srcRow, "T").Value)

        ' Write row
        wsR.Cells(dataRow, 1) = rowNum
        wsR.Cells(dataRow, 2) = wsJobs.Cells(srcRow, "D").Value
        wsR.Cells(dataRow, 3) = polVal & "-" & podVal
        wsR.Cells(dataRow, 4) = destVal
        wsR.Cells(dataRow, 5) = wsJobs.Cells(srcRow, "I").Value
        wsR.Cells(dataRow, 6) = wsJobs.Cells(srcRow, "K").Value
        wsR.Cells(dataRow, 7) = wsJobs.Cells(srcRow, "N").Value
        wsR.Cells(dataRow, 8) = wsJobs.Cells(srcRow, "AN").Value
        wsR.Cells(dataRow, 9) = wsJobs.Cells(srcRow, "AL").Value
        wsR.Cells(dataRow, volCol) = qtyVal
        wsR.Cells(dataRow, 18) = buyRate * qtyVal
        wsR.Cells(dataRow, 19) = selRate * qtyVal
        wsR.Cells(dataRow, 20) = profitShare
        wsR.Cells(dataRow, 21) = 0
        wsR.Cells(dataRow, 22) = carrierKB
        wsR.Cells(dataRow, 23) = taxAmt
        wsR.Cells(dataRow, 24).FormulaR1C1 = _
            "=RC[-5]-RC[-6]+RC[-4]+RC[-2]-RC[-1]"

        ' Formatting
        wsR.Cells(dataRow, 5).NumberFormat = "DD-MMM-YY"
        wsR.Cells(dataRow, 6).NumberFormat = "DD-MMM-YY"
        Dim fmtCol As Variant
        For Each fmtCol In Array(18, 19, 20, 22, 23, 24)
            wsR.Cells(dataRow, CLng(fmtCol)).NumberFormat = "#,##0.000"
        Next fmtCol

        ' Alternate row color
        If rowNum Mod 2 = 0 Then
            wsR.Range(wsR.Cells(dataRow, 1), wsR.Cells(dataRow, 24)).Interior.Color = RGB(235, 241, 250)
        End If

        dataRow = dataRow + 1
        rowNum = rowNum + 1
    Next i

    ' Step 6 — Totals row
    Dim totRow As Long: totRow = dataRow
    wsR.Range(wsR.Cells(totRow, 1), wsR.Cells(totRow, 24)).Font.Bold = True
    wsR.Range(wsR.Cells(totRow, 1), wsR.Cells(totRow, 24)).Interior.Color = RGB(189, 215, 238)

    Dim sumCols As Variant
    sumCols = Array(12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24)
    Dim scIdx As Variant
    For Each scIdx In sumCols
        Dim cNum As Long: cNum = CLng(scIdx)
        Dim cLtr As String
        cLtr = Split(wsR.Cells(1, cNum).Address, "$")(1)
        wsR.Cells(totRow, cNum).Formula = _
            "=SUM(" & cLtr & "3:" & cLtr & (totRow - 1) & ")"
        wsR.Cells(totRow, cNum).NumberFormat = "#,##0.000"
    Next scIdx

    ' Step 7 — Column widths
    wsR.Columns("A").ColumnWidth = 4
    wsR.Columns("B").ColumnWidth = 18
    wsR.Columns("C").ColumnWidth = 13
    wsR.Columns("D").ColumnWidth = 20
    wsR.Columns("E").ColumnWidth = 10
    wsR.Columns("F").ColumnWidth = 10
    wsR.Columns("G").ColumnWidth = 12
    wsR.Columns("H").ColumnWidth = 15
    wsR.Columns("I").ColumnWidth = 15
    Dim jCol As Long
    For jCol = 10 To 17
        wsR.Columns(jCol).ColumnWidth = 4
    Next jCol
    For jCol = 18 To 24
        wsR.Columns(jCol).ColumnWidth = 11
    Next jCol

    ' Borders
    With wsR.Range("A1:X" & totRow).Borders
        .LineStyle = xlContinuous
        .Weight = xlThin
        .Color = RGB(189, 215, 238)
    End With

    ' Freeze panes
    wsR.Activate
    wsR.Range("A3").Select
    ActiveWindow.FreezePanes = True
    wsR.Range("A1").Select

    MsgBox sheetName & " - " & matchCount & " jobs exported." & vbCrLf & vbCrLf & _
           "Note: HBL from col AN, JOB NO from col AL." & vbCrLf & _
           "Note: Client kickback = $0 until CRM built." & vbCrLf & _
           "Note: Profit share = HDL fee default until CRM built." & vbCrLf & vbCrLf & _
           "Review Net Profit column before saving.", _
           vbInformation, "Report Complete"
    Exit Sub

ErrHandler:
    MsgBox "Error in ExportMonthlyReport: " & Err.Description, vbCritical, "Error"
End Sub
