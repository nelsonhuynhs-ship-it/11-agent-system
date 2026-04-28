---
phase: 3
title: E2E test cases + verify
status: pending
effort_loc: ~60 LOC pytest + 4 e2e cases
owner: MM M2.7
depends_on: [phase-01, phase-02]
---

# Phase 3 — E2E test + verify-erp gates

## Test infrastructure available
Plan `260426-erp-e2e-test-automation` đã build xlwings + ERPv14TestE2E wrapper. PASS 5/5 historical cases. Em extend infra này, không build từ đầu.

- Runner: `Engine_test/plans/260426-erp-e2e-test-automation/e2e_runner.py`
- Cases: `Engine_test/plans/260426-erp-e2e-test-automation/e2e_test_cases.json`
- VBA wrapper: `D:/OneDrive/NelsonData/erp/erp-v14-test-e2e.bas` (module ERPv14TestE2E)

## Step 1: Add VBA test wrapper macros
Append to `D:/OneDrive/NelsonData/erp/erp-v14-test-e2e.bas`:

```vba
' ============================================================
'  Phase 3 (260428) — Smart Quote Img tests
' ============================================================

' Test: smart group detection from Pricing sheet
Public Function TestE2E_QuoteImg_FromPricing(customerName As String, contCSV As String) As String
    On Error GoTo EH
    g_TestMode = True

    ' Setup: set customer + create 2 quotes (different POD)
    m_Customer = customerName
    ' Pre-condition: caller already populated m_* via TestE2E_GenerateQuote 2x
    
    ' Activate Pricing sheet (simulate Sếp standing on Pricing)
    Dim wsP As Worksheet: Set wsP = ERPv14Core.GetActivePricingSheet()
    If wsP Is Nothing Then TestE2E_QuoteImg_FromPricing = "FAIL:no_pricing_sheet": Exit Function
    wsP.Activate

    ' Call the smart dispatcher
    Call OnAction_QuoteImage(Nothing)

    ' Check: should now be on Quotes sheet
    If ActiveSheet.Name <> "Quotes" Then
        TestE2E_QuoteImg_FromPricing = "FAIL:did_not_switch_to_quotes:active=" & ActiveSheet.Name
        Exit Function
    End If

    g_TestMode = False
    TestE2E_QuoteImg_FromPricing = "OK:switched_to_quotes"
    Exit Function
EH:
    g_TestMode = False
    TestE2E_QuoteImg_FromPricing = "FAIL:" & Err.Description
End Function

' Test: smart group detection — count rows in latest group
Public Function TestE2E_QuoteImg_LatestGroupCount(expectedRows As Long) As String
    On Error GoTo EH
    g_TestMode = True

    Dim wsQ As Worksheet: Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then TestE2E_QuoteImg_LatestGroupCount = "FAIL:no_quotes_sheet": Exit Function
    wsQ.Activate

    ' Clear any prior selection — force smart mode
    wsQ.Cells(1, 1).Select  ' header row → not "real" selection per dispatcher

    Dim rowNums() As Long, rowCount As Long
    Call QuoteImage_CollectLatestGroup(wsQ, rowNums, rowCount)

    g_TestMode = False
    If rowCount = expectedRows Then
        TestE2E_QuoteImg_LatestGroupCount = "OK:rows=" & rowCount
    Else
        TestE2E_QuoteImg_LatestGroupCount = "FAIL:expected=" & expectedRows & " got=" & rowCount
    End If
    Exit Function
EH:
    g_TestMode = False
    TestE2E_QuoteImg_LatestGroupCount = "FAIL:" & Err.Description
End Function

' Test: backward compat — explicit selection wins over smart
Public Function TestE2E_QuoteImg_ExplicitSelection(targetRow As Long) As String
    On Error GoTo EH
    g_TestMode = True

    Dim wsQ As Worksheet: Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then TestE2E_QuoteImg_ExplicitSelection = "FAIL:no_quotes_sheet": Exit Function
    wsQ.Activate
    wsQ.Rows(targetRow).Select  ' explicit row selection

    Dim rowNums() As Long, rowCount As Long
    Call QuoteImage_CollectFromSelection(wsQ, rowNums, rowCount)

    g_TestMode = False
    If rowCount = 1 And rowNums(1) = targetRow Then
        TestE2E_QuoteImg_ExplicitSelection = "OK:row=" & rowNums(1)
    Else
        TestE2E_QuoteImg_ExplicitSelection = "FAIL:expected=" & targetRow & " count=" & rowCount
    End If
    Exit Function
EH:
    g_TestMode = False
    TestE2E_QuoteImg_ExplicitSelection = "FAIL:" & Err.Description
End Function

' Test: filter cache restore
Public Function TestE2E_FilterRestore(sheetName As String, _
                                       seedCarrier As String, seedPOL As String, _
                                       seedPOD As String, seedPlace As String) As String
    On Error GoTo EH
    g_TestMode = True

    ' Seed module-level filter state
    ERPv14Ribbon.m_SearchCarrier = seedCarrier
    ERPv14Ribbon.m_SearchPOL = seedPOL
    ERPv14Ribbon.m_SearchPOD = seedPOD
    ERPv14Ribbon.m_SearchPlace = seedPlace

    ' Cache it
    Call ERPv14Ribbon.CacheSearchState(sheetName)

    ' Wipe state (simulate sheet activate doing reset)
    ERPv14Ribbon.m_SearchCarrier = ""
    ERPv14Ribbon.m_SearchPOL = ""
    ERPv14Ribbon.m_SearchPOD = ""
    ERPv14Ribbon.m_SearchPlace = ""

    ' Restore
    Dim restored As Boolean
    restored = ERPv14Ribbon.TryRestoreSearchState(sheetName)

    g_TestMode = False
    If Not restored Then
        TestE2E_FilterRestore = "FAIL:restore_returned_false"
        Exit Function
    End If
    If ERPv14Ribbon.m_SearchCarrier = seedCarrier And _
       ERPv14Ribbon.m_SearchPOL = seedPOL And _
       ERPv14Ribbon.m_SearchPOD = seedPOD And _
       ERPv14Ribbon.m_SearchPlace = seedPlace Then
        TestE2E_FilterRestore = "OK:restored"
    Else
        TestE2E_FilterRestore = "FAIL:state_mismatch"
    End If
    Exit Function
EH:
    g_TestMode = False
    TestE2E_FilterRestore = "FAIL:" & Err.Description
End Function
```

NOTE: `m_Search*` privately scoped — need to either change them `Public` (preferred for testability) hoặc add public getter/setter. Keep simple: change Private to Public for these specific module vars only.

## Step 2: Append cases to `e2e_test_cases.json`

```json
[
  {
    "id": "case-07-quote-img-from-pricing",
    "title": "Smart Quote Img from Pricing sheet auto-jumps to Quotes",
    "description": "Phase 1 — sheet auto-switch behavior",
    "macro": "ERPv14TestE2E.TestE2E_QuoteImg_FromPricing",
    "macro_args": ["TEST_CUST_E2E", "20GP"],
    "preconditions": [
      "Generate at least 1 quote for TEST_CUST_E2E today first via TestE2E_GenerateQuote"
    ],
    "expected_outputs": {"return_value_starts_with": "OK:switched_to_quotes"},
    "ribbon_region": [0, 0, 1920, 220],
    "result_region": [0, 100, 1400, 700]
  },
  {
    "id": "case-08-quote-img-latest-group-count",
    "title": "Smart group detection counts correct rows",
    "description": "Phase 1 — latest group walks contiguous matching customer+date",
    "macro": "ERPv14TestE2E.TestE2E_QuoteImg_LatestGroupCount",
    "macro_args": [3],
    "preconditions": [
      "Generate exactly 3 quotes for same customer same day"
    ],
    "expected_outputs": {"return_value_starts_with": "OK:rows=3"},
    "ribbon_region": [0, 0, 1920, 220],
    "result_region": [0, 100, 1400, 700]
  },
  {
    "id": "case-09-quote-img-explicit-selection",
    "title": "Backward compat: explicit row selection wins over smart",
    "description": "Phase 1 — power user picks 1 row",
    "macro": "ERPv14TestE2E.TestE2E_QuoteImg_ExplicitSelection",
    "macro_args": [10],
    "preconditions": [
      "Quotes sheet has data at row 10"
    ],
    "expected_outputs": {"return_value_starts_with": "OK:row=10"},
    "ribbon_region": [0, 0, 1920, 220],
    "result_region": [0, 100, 1400, 700]
  },
  {
    "id": "case-10-filter-cache-restore",
    "title": "Filter cache survives sheet switch",
    "description": "Phase 2 — CacheSearchState + TryRestoreSearchState round-trip",
    "macro": "ERPv14TestE2E.TestE2E_FilterRestore",
    "macro_args": ["Pricing Dry", "ONE", "HPH", "USLAX", "ARB"],
    "expected_outputs": {"return_value_starts_with": "OK:restored"},
    "ribbon_region": [0, 0, 1920, 220],
    "result_region": [0, 100, 1400, 700]
  }
]
```

## Step 3: Run gates (sequential)

```bash
# Gate 1: VBA static lint (R1-R9 from verify-erp.bat)
cd "d:/NELSON/2. Areas/Engine_test"
scripts/verify-erp.bat
# Must exit 0

# Gate 2: Reimport modules
python scripts/reimport-erp-vba-modules.py
# Must succeed

# Gate 3: E2E run
python plans/260426-erp-e2e-test-automation/e2e_runner.py \
    --cases plans/260426-erp-e2e-test-automation/e2e_test_cases.json \
    --filter "case-07,case-08,case-09,case-10"
# All 4 new cases must PASS
# Plus existing 6 must still PASS (no regression)
```

## Acceptance for entire plan
- [x] verify-erp.bat exit 0
- [x] reimport-erp-vba-modules.py success
- [x] e2e_runner.py: case-01..06 (existing) PASS — no regression
- [x] e2e_runner.py: case-07..10 (new) PASS
- [x] Manual smoke test guide written to `reports/smoke-test-guide.md` for Sếp

## Output
Generate completion report `reports/phase-03-completion.md` with:
- Test results table (all 10 cases)
- LOC delta (added/modified per file)
- Backup file location for rollback
- Next steps (Sếp manual smoke test)
