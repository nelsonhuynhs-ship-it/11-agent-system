Attribute VB_Name = "CostBreakdown"
Option Explicit

' ============================================================
'  COST BREAKDOWN ENGINE — ERP V13
'  Verified data from FAK 18MAR source file.
'  HDL Fee, Wharfage, and BuildCostBreakdown.
' ============================================================

' --- HDL Rule Type ---
Public Type HdlRule
    hdl20       As Double       ' for 20GP/20RF
    hdl40       As Double       ' for 40GP/40HC/40RF/45HQ
    comType     As String       ' "CAR COM 35" or "CAR COM 10"
    nelsonPct   As Double       ' 65 or 90
    account     As String
End Type

' ============================================================
'  GET HDL RULE — Carrier + POL + Contract Type
' ============================================================
Public Function GetHdlRule(carrier As String, pol As String, _
                           contractType As String, cont As String) As HdlRule
    Dim R As HdlRule
    Dim isFAK As Boolean, isFIX As Boolean, isSCFI As Boolean
    isFAK = InStr(UCase(contractType), "FAK") > 0
    isFIX = InStr(UCase(contractType), "FIX") > 0
    isSCFI = InStr(UCase(contractType), "SCFI") > 0

    Select Case UCase(Trim(carrier))

        Case "HPL"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = "HPL - PUDONG SHANGHAI"
            If isFIX Then
                R.hdl20 = 20: R.hdl40 = 30
            ElseIf isSCFI Then
                R.hdl20 = 10: R.hdl40 = 10
            Else
                R.hdl20 = 20: R.hdl40 = 20
            End If

        Case "ONE"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            If UCase(Trim(pol)) = "HPH" Then
                R.account = "ONE DRY/RF 02"
            Else
                R.account = "ONE DRY/RF 01"
            End If
            R.hdl20 = 20: R.hdl40 = 20

        Case "YML"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = "YML DRY/RF"
            If isFIX Then
                R.hdl20 = 300: R.hdl40 = 300
            Else
                R.hdl20 = 20: R.hdl40 = 20
            End If

        Case "MSC"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = "MSC DRY/RF"
            R.hdl20 = 25: R.hdl40 = 25

        Case "CMA", "CMA CGM"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            If UCase(Trim(pol)) = "HPH" Then
                R.account = "CMA DRY 02"
            Else
                R.account = "CMA DRY 01"
            End If
            If isFIX Then
                R.hdl20 = 0: R.hdl40 = 0
            Else
                R.hdl20 = 15: R.hdl40 = 15
            End If

        Case "COSCO"
            R.comType = "CAR COM 10": R.nelsonPct = 90
            R.account = "COSCO DRY/RF"
            If InStr(UCase(cont), "RF") > 0 Then
                R.hdl20 = 100: R.hdl40 = 100
            Else
                R.hdl20 = 25: R.hdl40 = 25
            End If

        Case "ZIM"
            R.comType = "CAR COM 10": R.nelsonPct = 90
            R.account = "ZIM DRY/RF"
            R.hdl20 = 30: R.hdl40 = 30

        Case "WHL", "WANHAI"
            If UCase(Trim(pol)) = "HCM" Then
                R.comType = "CAR COM 10": R.nelsonPct = 90
                R.account = "WHL DRY"
            Else
                R.comType = "CAR COM 35": R.nelsonPct = 65
                Select Case UCase(Trim(pol))
                    Case "HPH": R.account = "WHL DRY 02"
                    Case "UIH": R.account = "WHL DRY 03"
                    Case "DAD": R.account = "WHL DRY 04"
                    Case Else:  R.account = "WHL DRY"
                End Select
            End If
            R.hdl20 = 25: R.hdl40 = 25

        Case "HMM"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = "HMM DRY/RF"
            If isFIX Then
                R.hdl20 = 100: R.hdl40 = 100
            Else
                R.hdl20 = 40: R.hdl40 = 40
            End If

        Case "EMC", "EVERGREEN"
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = "EMC DRY/RF"
            R.hdl20 = 25: R.hdl40 = 25

        Case Else
            R.comType = "CAR COM 35": R.nelsonPct = 65
            R.account = carrier & " (FALLBACK)"
            R.hdl20 = 20: R.hdl40 = 20
    End Select

    GetHdlRule = R
End Function

' ============================================================
'  GET HDL AMOUNT — by container type
' ============================================================
Public Function GetHdlAmount(R As HdlRule, cont As String) As Double
    If UCase(cont) = "20GP" Or UCase(cont) = "20RF" Then
        GetHdlAmount = R.hdl20
    Else
        GetHdlAmount = R.hdl40
    End If
End Function

' ============================================================
'  GET WHARFAGE — Carrier + POD + Container
' ============================================================
Public Function GetWharfage(carrier As String, pod As String, _
                            cont As String) As Double
    Dim wha As Double: wha = 0
    Dim is20 As Boolean
    is20 = (UCase(cont) = "20GP" Or UCase(cont) = "20RF")
    Dim podU As String: podU = UCase(Trim(pod))

    Select Case UCase(Trim(carrier))
        Case "CMA", "CMA CGM"
            Select Case podU
                Case "HOU", "HOUSTON":         wha = 80
                Case "MOB", "MOBILE":          wha = 70
                Case "NEW", "NEW ORLEANS":     wha = 85
                Case "MIA", "MIAMI":           wha = 75
                Case "FPT", "PORT EVERGLADES": wha = 45
                Case "BOS", "BOSTON":           wha = 55
                Case "TPA", "TAMPA":           wha = 50
                Case Else: wha = 0
            End Select
        Case "ONE"
            Select Case podU
                Case "HOU", "HOUSTON":     wha = 90
                Case "MOB", "MOBILE":      wha = 80
                Case "NEW", "NEW ORLEANS": wha = 85
                Case "YHZ", "HALIFAX":     wha = 85
                Case "YVR", "VANCOUVER"
                    If is20 Then wha = 55 Else wha = 110
                Case Else: wha = 0
            End Select
        Case "COSCO"
            Select Case podU
                Case "HOU", "HOUSTON":     wha = 81
                Case "MOB", "MOBILE":      wha = 60
                Case "NEW", "NEW ORLEANS": wha = 68
                Case "MIA", "MIAMI"
                    If is20 Then wha = 37 Else wha = 75
                Case Else: wha = 0
            End Select
        Case Else: wha = 0
    End Select
    GetWharfage = wha
End Function

' ============================================================
'  BUILD COST BREAKDOWN — Main function
' ============================================================
Public Function BuildCostBreakdown( _
    carrier As String, contractType As String, _
    cont As String, pol As String, pod As String, _
    sc As String, groupCode As String, _
    of_ As Double, arb As Double, isps As Double, _
    puc As Double, eic As Double, ocs As Double, _
    wha As Double, goh As Double, _
    qty As Integer) As String

    Dim R As HdlRule
    R = GetHdlRule(carrier, pol, contractType, cont)
    Dim hdlAmt As Double
    hdlAmt = GetHdlAmount(R, cont)

    Dim isFIX As Boolean
    isFIX = InStr(UCase(contractType), "FIX") > 0
    Dim isReefer As Boolean
    isReefer = InStr(UCase(cont), "RF") > 0

    ' Contract label
    Dim contractLabel As String
    If isReefer Then
        contractLabel = "REEFER - " & sc
    Else
        contractLabel = sc
    End If

    ' Build cost parts — only non-zero charges
    Dim costParts As String: costParts = ""
    If of_ > 0 Then costParts = costParts & "O/F $" & Format(of_, "#,##0") & " + "
    If arb > 0 Then costParts = costParts & "ARB $" & Format(arb, "#,##0") & " + "
    If isps > 0 Then costParts = costParts & "ISPS $" & Format(isps, "#,##0") & " + "
    If puc > 0 Then costParts = costParts & "PUC $" & Format(puc, "#,##0") & " + "
    If eic > 0 Then costParts = costParts & "EIC/BAF $" & Format(eic, "#,##0") & " + "
    If ocs > 0 Then costParts = costParts & "OCS/GRI $" & Format(ocs, "#,##0") & " + "
    If wha > 0 Then costParts = costParts & "WHA $" & Format(wha, "#,##0") & " + "
    If goh > 0 Then costParts = costParts & "GOH $" & Format(goh, "#,##0") & " + "
    If Len(costParts) > 3 Then
        costParts = Left(costParts, Len(costParts) - 3)
    End If

    ' HDL display
    Dim hdlDisplay As String
    If isFIX And UCase(Trim(carrier)) = "HPL" Then
        hdlDisplay = "20/30 FOR 20/40 (" & cont & ": $" & _
                     Format(hdlAmt, "#,##0") & "/box)"
    Else
        hdlDisplay = "$" & Format(hdlAmt, "#,##0") & "/box"
    End If

    ' ONE group line
    Dim groupLine As String: groupLine = ""
    If UCase(Trim(carrier)) = "ONE" And Len(Trim(groupCode)) > 0 Then
        groupLine = "GROUP: " & groupCode & Chr(10)
    End If

    ' Calculate totals
    Dim freightTotal As Double
    freightTotal = of_ + arb + isps + puc + eic + ocs + wha + goh
    Dim totalPerBox As Double
    totalPerBox = freightTotal + hdlAmt
    Dim totalQty As Double
    totalQty = totalPerBox * qty

    ' Fallback warning
    Dim warnLine As String: warnLine = ""
    If InStr(R.account, "FALLBACK") > 0 Then
        warnLine = Chr(10) & "[WARN: HDL fallback - verify with pricing]"
    End If

    ' Assemble
    BuildCostBreakdown = _
        "S/C: " & contractLabel & " | " & carrier & _
        " " & IIf(isFIX, "FIX", "FAK") & _
        IIf(InStr(UCase(contractType), "SOC") > 0, " SOC", "") & Chr(10) & _
        groupLine & _
        "COST: " & costParts & Chr(10) & _
        "HDL FEE: " & R.comType & " - " & R.account & _
        " - " & hdlDisplay & Chr(10) & _
        "HDL/customer: [TBD - set in CRM]" & Chr(10) & _
        "---" & Chr(10) & _
        "FREIGHT TOTAL/BOX: $" & Format(freightTotal, "#,##0") & Chr(10) & _
        "TOTAL (" & qty & "x): $" & Format(totalQty, "#,##0") & _
        warnLine
End Function
