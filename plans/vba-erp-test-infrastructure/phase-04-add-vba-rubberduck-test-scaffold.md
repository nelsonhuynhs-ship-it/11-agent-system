---
phase: 4
title: "Add VBA Rubberduck Test Scaffold"
status: completed
priority: P2
effort: "2h"
dependencies: [3]
---

# Phase 4: Add VBA Rubberduck Test Scaffold

## Overview
Rubberduck is the ONLY unit testing framework for VBA. Tests run inside Excel VBE — not automatable in CI. This phase creates: (1) a test template for new VBA features, (2) a Rubberduck test module for the most regression-prone feature (CostBreakdown), (3) a CONTRIBUTING.md rule: "new VBA feature = feature module + test module pair."

## Requirements
- Functional: Template test module that Rubberduck can execute in VBE
- Non-functional: No external dependencies beyond Rubberduck add-in

## Architecture

```
ERP/vba-v14-mirror/
  TestModule_Template.bas          ← scaffold for any new VBA feature
  TestModule_CostBreakdown.bas     ← full tests for CostBreakdown.bas
  TestModule_FastId.bas            ← full tests for basFastId.bas
```

**Rubberduck test naming convention:**
- Module: `TestModule_<FeatureName>.bas`
- Test class: `<FeatureName>Tests` (e.g., `CostBreakdownTests`)
- Setup: `Module_Setup()` — opens test data workbook
- Teardown: `Module_Teardown()` — closes test workbook
- Tests: `Test_<Scenario>()` — Assert.areEqual / areNotEqual / isTrue

## Rubberduck Test Template

```vba
' TestModule_<FeatureName>.bas
' Rubberduck Unit Test Module
' Unit tests for <FeatureName>.bas
' RULE: Every new VBA feature module needs a companion TestModule_*.bas
' Run: Rubberduck → Test Explorer → Run All
'==== Module Setup/Teardown ====
Private Sub Module_Setup()
    ' Open test data, set g_TestMode = True
    g_TestMode = True
End Sub

Private Sub Module_Teardown()
    ' Close test workbook, reset state
    g_TestMode = False
End Sub

'==== Test Cases ====
' Sub Test_<Scenario>()
'     Arrange
'     Dim input as String: input = "..."
'     Dim expected as Long: expected = 100
'     ' Act
'     Dim result as Long: result = fnFeatureName(input)
'     ' Assert
'     Assert.areEqual expected, result, "Description of what failed"
' End Sub
'
' Sub Test_<EdgeCase>()
'     ' ...
' End Sub
```

## Related Code Files
- Create: `ERP/vba-v14-mirror/TestModule_Template.bas`
- Create: `ERP/vba-v14-mirror/TestModule_CostBreakdown.bas`
- Create: `CONTRIBUTING.md` (or update existing)

## Implementation Steps

1. **Create `TestModule_Template.bas`** — full scaffold with Setup/Teardown/test examples
2. **Create `TestModule_CostBreakdown.bas`** — tests for:
   - `fnHdlRule_Apply()` — wharfage calculation
   - `fnCost_Total()` — total cost aggregation
   - Edge: missing carrier → returns 0
   - Edge: SOC container → no wharfage
3. **Create `TestModule_FastId.bas`** — tests for:
   - `fnGenerateNextFastId()` — correct sequence NF-YYMM-NNN
   - Edge: empty Active Jobs → starts at NF-YYMM-001
   - Edge: year roll-over
4. **Add to `CONTRIBUTING.md`** or `ERP_SYSTEM_GUIDE.md`:
   ```
   ## VBA Test Rule (BẮT BUỘC)
   Mỗi feature VBA mới phải có:
   1. Feature module: `bas<FeatureName>.bas`
   2. Test module: `TestModule_<FeatureName>.bas` (Rubberduck)
   3. Test coverage: happy path + 2 edge cases minimum
   ```
5. **Verify**: Open xlsm in Excel → Rubberduck → Test Explorer → confirm tests visible

## Success Criteria
- [ ] `TestModule_Template.bas` exists and Rubberduck can parse it
- [ ] `TestModule_CostBreakdown.bas` has ≥5 test cases covering cost calculation
- [ ] `CONTRIBUTING.md` or `ERP_SYSTEM_GUIDE.md` documents the VBA test rule
- [ ] Rubberduck Test Explorer shows all 3 test modules

## Risk Assessment
- **Risk**: Rubberduck not installed on developer's Excel
- **Mitigation**: Document installation in ERP_SYSTEM_GUIDE.md (one-time, ~5 min)
- **Risk**: VBA tests require live Excel → can't run in CI
- **Mitigation**: Python E2E tests (Phase 5) are the CI gate; VBA tests are developer-time quality gate
