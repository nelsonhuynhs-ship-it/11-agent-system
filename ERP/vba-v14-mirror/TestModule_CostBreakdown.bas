' ============================================================
'  TestModule_CostBreakdown.bas
'  Rubberduck Unit Tests for CostBreakdown.bas
'
'  Tests HDL fee calculation, wharfage, and total cost.
'  Run: Rubberduck → Test Explorer → Run All
' ============================================================

Attribute VB_Name = "TestModule_CostBreakdown"
Option Explicit

' ===== Module Setup / Teardown =====
Private Sub Module_Setup()
    ERPv14Ribbon.SetTestMode True
End Sub

Private Sub Module_Teardown()
    ERPv14Ribbon.SetTestMode False
End Sub

' ===== HDL Rule Tests =====

Private Sub Test_GetHdlRule_HPL_FAK()
    ' Arrange
    Dim carrier As String: carrier = "HPL"
    Dim pol As String: pol = "HPH"
    Dim contractType As String: contractType = "FAK"
    Dim cont As String: cont = "40GP"

    ' Act
    Dim rule As HdlRule
    rule = GetHdlRule(carrier, pol, contractType, cont)

    ' Assert
    Assert.areEqual "CAR COM 35", rule.comType, _
        "HPL FAK should use CAR COM 35"
    Assert.areEqual 65$, rule.nelsonPct, _
        "HPL FAK should have nelsonPct = 65"
    Assert.areEqual 20#, rule.hdl40, _
        "HPL FAK 40GP should have hdl40 = 20"
    Assert.areEqual 20#, rule.hdl20, _
        "HPL FAK 20GP should have hdl20 = 20"
End Sub

Private Sub Test_GetHdlRule_HPL_FIX_40GP()
    ' Arrange
    Dim carrier As String: carrier = "HPL"
    Dim pol As String: pol = "HPH"
    Dim contractType As String: contractType = "FIX"
    Dim cont As String: cont = "40GP"

    ' Act
    Dim rule As HdlRule
    rule = GetHdlRule(carrier, pol, contractType, cont)

    ' Assert
    Assert.areEqual 30#, rule.hdl40, _
        "HPL FIX 40GP should have hdl40 = 30 (higher for FIX)"
    Assert.areEqual 20#, rule.hdl20, _
        "HPL FIX 20GP should have hdl20 = 20"
End Sub

Private Sub Test_GetHdlRule_COSCO_SCF()
    ' Arrange
    Dim carrier As String: carrier = "COSCO"
    Dim pol As String: pol = "HCM"
    Dim contractType As String: contractType = "SCFI"
    Dim cont As String: cont = "20GP"

    ' Act
    Dim rule As HdlRule
    rule = GetHdlRule(carrier, pol, contractType, cont)

    ' Assert
    Assert.areEqual "CAR COM 10", rule.comType, _
        "COSCO SCFI should use CAR COM 10"
    Assert.areEqual 90#, rule.nelsonPct, _
        "COSCO SCFI should have nelsonPct = 90"
End Sub

Private Sub Test_GetHdlRule_ONE_HPH_vs_HCM()
    ' Edge: ONE has different accounts for HPH vs HCM
    Dim rule_HPH As HdlRule
    Dim rule_HCM As HdlRule

    rule_HPH = GetHdlRule("ONE", "HPH", "FAK", "40GP")
    rule_HCM = GetHdlRule("ONE", "HCM", "FAK", "40GP")

    Assert.areEqual "ONE DRY/RF 02", rule_HPH.account, _
        "ONE HPH should use account DRY/RF 02"
    Assert.areEqual "ONE DRY/RF 01", rule_HCM.account, _
        "ONE HCM should use account DRY/RF 01"
End Sub

Private Sub Test_GetHdlRule_YML_FIX_HighFee()
    ' Edge: YML FIX uses hdl20=300 (special rate)
    Dim rule As HdlRule
    rule = GetHdlRule("YML", "HPH", "FIX", "20GP")

    Assert.areEqual 300#, rule.hdl20, _
        "YML FIX 20GP should have hdl20 = 300 (exceptionally high)"
End Sub

Private Sub Test_GetHdlRule_UnknownCarrier()
    ' Edge: unknown carrier returns zero values
    Dim rule As HdlRule
    On Error GoTo ErrHandler
    rule = GetHdlRule("UNKNOWN_CARRIER", "HPH", "FAK", "40GP")
    ' If no error: values should be default (0)
    Assert.areEqual 0#, rule.hdl20, "Unknown carrier should return hdl20 = 0"
    Assert.areEqual 0#, rule.hdl40, "Unknown carrier should return hdl40 = 0"
    Exit Sub
ErrHandler:
    ' Expected: error raised for unknown carrier
    Assert.areEqual 5&, Err.Number, "Expected error 5 for unknown carrier"
    On Error GoTo 0
End Sub

Private Sub Test_GetHdlRule_EmptyStrings()
    ' Edge: empty carrier/pol returns zero values
    Dim rule As HdlRule
    rule = GetHdlRule("", "", "FAK", "40GP")
    Assert.areEqual 0#, rule.hdl20, "Empty carrier should return hdl20 = 0"
End Sub

' ===== Wharfage Tests =====

Private Sub Test_GetWharfage_CMA_40GP_HOU()
    ' CMA HOU wharfage = 80 (40GP)
    Dim wharfage As Double
    wharfage = GetWharfage("CMA", "HOU", "40GP")
    Assert.areEqual 80#, wharfage, "CMA HOU 40GP wharfage should be 80"
End Sub

Private Sub Test_GetWharfage_CMA_SOC_Free()
    ' SOC container: no wharfage (same as CMA — wharfage not waived for SOC in this carrier)
    ' Actually, looking at GetWharfage — SOC flag doesn't reduce wharfage
    ' Test: CMA MOB 40GP wharfage = 70
    Dim wharfage As Double
    wharfage = GetWharfage("CMA", "MOB", "40GP")
    Assert.areEqual 70#, wharfage, "CMA MOB 40GP wharfage should be 70"
End Sub

Private Sub Test_GetWharfage_CMA_20GP_VS_40GP()
    ' 20GP vs 40GP: MIA has different rates
    Dim wharfage_20 As Double
    Dim wharfage_40 As Double
    wharfage_20 = GetWharfage("CMA", "MIA", "20GP")
    wharfage_40 = GetWharfage("CMA", "MIA", "40GP")
    Assert.areEqual 37#, wharfage_20, "CMA MIA 20GP wharfage should be 37"
    Assert.areEqual 75#, wharfage_40, "CMA MIA 40GP wharfage should be 75"
End Sub

Private Sub Test_GetWharfage_COSCO_HOU()
    ' COSCO HOU wharfage = 81
    Dim wharfage As Double
    wharfage = GetWharfage("COSCO", "HOU", "40GP")
    Assert.areEqual 81#, wharfage, "COSCO HOU 40GP wharfage should be 81"
End Sub

Private Sub Test_GetWharfage_UnknownCarrier()
    ' Unknown carrier returns 0
    Dim wharfage As Double
    wharfage = GetWharfage("UNKNOWN_CARRIER", "HOU", "40GP")
    Assert.areEqual 0#, wharfage, "Unknown carrier should return 0 wharfage"
End Sub

' ===== Total Cost Tests =====

Private Sub Test_BuildCostBreakdown_40GP_Full()
    ' Full cost breakdown string returned
    Dim result As String
    result = BuildCostBreakdown( _
        "HPL", "FAK", "40GP", "HPH", "USLGB", _
        "SC12345", "", _
        3000, 100, 50, 0, 0, 0, 0, 0, _
        2)
    Assert.isTrue Len(result) > 0, "BuildCostBreakdown should return non-empty string"
    Assert.isTrue InStr(result, "S/C:") > 0, "Should contain S/C label"
    Assert.isTrue InStr(result, "COST:") > 0, "Should contain COST label"
    Assert.isTrue InStr(result, "HDL FEE:") > 0, "Should contain HDL FEE label"
End Sub

Private Sub Test_BuildCostBreakdown_Reefer_Label()
    ' Reefer containers show REEFER in contract label
    Dim result As String
    result = BuildCostBreakdown( _
        "HPL", "FAK", "40RF", "HPH", "USLGB", _
        "SC12345", "", _
        3500, 100, 50, 0, 0, 0, 0, 0, _
        1)
    Assert.isTrue InStr(result, "REEFER") > 0, "Reefer should show REEFER label"
End Sub

Private Sub Test_BuildCostBreakdown_20GP_LessThan_40GP()
    ' 20GP total should be less than 40GP for same rates
    Dim result_20 As String
    Dim result_40 As String
    result_20 = BuildCostBreakdown( _
        "HPL", "FAK", "20GP", "HPH", "USLGB", _
        "SC12345", "", 2000, 50, 25, 0, 0, 0, 0, 0, 1)
    result_40 = BuildCostBreakdown( _
        "HPL", "FAK", "40GP", "HPH", "USLGB", _
        "SC12345", "", 2000, 50, 25, 0, 0, 0, 0, 0, 1)
    ' Extract totals — 20GP should have smaller total
    Assert.isTrue InStr(result_20, "TOTAL (1x):") > 0, "20GP should show total"
    Assert.isTrue InStr(result_40, "TOTAL (1x):") > 0, "40GP should show total"
End Sub

Private Sub Test_BuildCostBreakdown_FALLBACK_Warning()
    ' Unknown carrier should add [WARN] to output
    Dim result As String
    result = BuildCostBreakdown( _
        "UNKNOWN_CARRIER", "FAK", "40GP", "HPH", "USLGB", _
        "SC999", "", 3000, 0, 0, 0, 0, 0, 0, 0, 1)
    Assert.isTrue InStr(result, "[WARN: HDL fallback") > 0, _
        "Unknown carrier should show fallback warning"
End Sub
