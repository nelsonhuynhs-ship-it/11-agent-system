# VBA Rubberduck Testing Guide

## What is Rubberduck?

Rubberduck is a free, open-source VBA add-in that provides unit testing, code inspection, and refactoring tools for Excel VBA.

- **Website**: https://rubberduck-vba.com/
- **GitHub**: https://github.com/rubberduck-vba/Rubberduck
- **Unit Testing**: Write `Assert.*` test methods that Rubberduck executes in the VBE

**Limitation**: VBA tests run inside Excel VBE — not automatable in CI/CD. Python E2E tests (`tests/integration/`) are the CI gate. VBA Rubberduck tests are a developer-time quality tool.

## Installation

1. Download Rubberduck from https://rubberduck-vba.com/downloads
2. Run the installer (one-time, ~2 minutes)
3. Open Excel → VBE (Alt+F11) → Add-ins menu → Rubberduck
4. If not visible: Tools → Add-ins → Browse → select Rubberduck add-in

## Writing Your First Test

### 1. Create a test module

In the VBE Project Explorer:
- Right-click your project → Insert → Module → Name it `TestModule_<FeatureName>`

### 2. Add test methods

```vba
Attribute VB_Name = "TestModule_FastId"
Option Explicit

' Module Setup — runs before each test
Private Sub Module_Setup()
    ERPv14Ribbon.SetTestMode True
End Sub

' Module Teardown — runs after each test
Private Sub Module_Teardown()
    ERPv14Ribbon.SetTestMode False
End Sub

' Happy path test
Private Sub Test_fnGenerateNextFastId_ValidSequence()
    ' Arrange
    Dim lastId As String: lastId = "NF-2605-001"

    ' Act
    Dim nextId As String: nextId = fnGenerateNextFastId(lastId)

    ' Assert
    Assert.areEqual "NF-2605-002", nextId, _
        "Next Fast ID should increment sequence number"
End Sub

' Edge case: empty first job
Private Sub Test_fnGenerateNextFastId_EmptyFirstJob()
    ' Arrange
    Dim lastId As String: lastId = ""

    ' Act
    Dim nextId As String: nextId = fnGenerateNextFastId(lastId)

    ' Assert
    Assert.areEqual "NF-" & Format(Now, "YYMM") & "-001", nextId, _
        "Empty last ID should start at 001 for current month"
End Sub
```

## Rubberduck Assertions

| Method | Usage |
|--------|-------|
| `Assert.areEqual expected, actual` | Check equality |
| `Assert.areNotEqual expected, actual` | Check inequality |
| `Assert.isTrue value` | Check True |
| `Assert.isFalse value` | Check False |
| `Assert.isNothing object` | Check Nothing |
| `Assert.fail "message"` | Force failure |
| `On Error GoTo ErrHandler` pattern | Test error handling |

## Running Tests

1. **Single test**: Click inside a test method → Run button (or F5)
2. **All tests in module**: Right-click module → Run
3. **Test Explorer**: Rubberduck menu → Test Explorer → Run All

## Test Naming Convention

| Element | Convention | Example |
|---------|-----------|---------|
| Test module | `TestModule_<FeatureName>` | `TestModule_CostBreakdown` |
| Test class | (VBA has no classes in this context) | — |
| Test method | `Test_<Function>_<Scenario>` | `Test_GetHdlRule_HPL_FAK` |

## When to Write VBA Tests

**Write VBA tests when:**
- Implementing new business logic in a `bas*.bas` module
- Modifying cost calculation or pricing logic
- Changing quote generation flow
- Any VBA function that transforms data

**Skip VBA tests when:**
- Editing only UI/ribbon layout (hard to unit test)
- Editing comments/documentation
- Trivial one-liner changes

## Existing Rubberduck Tests

See `ERP/vba-v14-mirror/TestModule_*.bas` for examples:
- `TestModule_CostBreakdown.bas` — HDL rule + wharfage + total cost
- `TestModule_Template.bas` — template for new modules
