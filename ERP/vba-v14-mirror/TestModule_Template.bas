' ============================================================
'  TestModule_<FeatureName>.bas
'  Rubberduck Unit Test Module
'
'  RULE: Every new VBA feature module (bas<Feature>.bas)
'        MUST have a companion TestModule_<Feature>.bas
'        with >= 3 test cases (1 happy path + 2 edge cases).
'
'  How to run:
'    1. Open ERP_Master_v14.xlsm in Excel
'    2. Rubberduck → Test Explorer → Run All
'    3. All tests pass → safe to commit
'
'  Install Rubberduck:
'    https://rubberduck-vba.com/ (free, open source)
'    One-time setup: open VBE → Add-ins → Rubberduck → Install
' ============================================================

Attribute VB_Name = "TestModule_<FeatureName>"
Option Explicit

' ===== Module Setup / Teardown =====
' Run once before all tests in this module
Private Sub Module_Setup()
    ' Open test data workbook, enable test mode, configure fixtures
    ERPv14Ribbon.SetTestMode True
    ' Example: create test Active Jobs rows
    ' Call SeedTestJobs
End Sub

' Run once after all tests in this module
Private Sub Module_Teardown()
    ' Close test workbook, cleanup, reset state
    ERPv14Ribbon.SetTestMode False
    ' Example: delete test rows
End Sub

' ===== Test Cases =====

' Happy path: valid input produces expected output
Private Sub Test_<FeatureName>_<HappyPath>()
    ' Arrange
    Dim input As String: input = "valid_value"
    Dim expected As Long: expected = 100

    ' Act
    Dim result As Long: result = fn<FeatureName>(input)

    ' Assert
    Assert.areEqual expected, result, _
        "<FeatureName> should return correct value for valid input"
End Sub

' Edge case: empty input returns zero/false
Private Sub Test_<FeatureName>_<EdgeCase1>()
    ' Arrange
    Dim input As String: input = ""

    ' Act
    Dim result As Long: result = fn<FeatureName>(input)

    ' Assert
    Assert.areEqual 0&, result, _
        "<FeatureName> should return 0 for empty input"
End Sub

' Edge case: invalid input returns error value
Private Sub Test_<FeatureName>_<EdgeCase2>()
    ' Arrange
    Dim input As String: input = "INVALID"

    ' Act
    On Error GoTo ErrHandler
    Dim result As Long: result = fn<FeatureName>(input)
    Err.Clear
    Assert.fail "Expected error for invalid input"
    Exit Sub
ErrHandler:
    ' Assert error was raised
    Assert.areEqual 5&, Err.Number, "Expected error 5 for invalid input"
    On Error GoTo 0
End Sub

' ===== Helper Functions =====
' (Add test-specific helpers here, if needed)
