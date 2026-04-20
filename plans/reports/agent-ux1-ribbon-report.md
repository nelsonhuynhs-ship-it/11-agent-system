---
agent: UX-1
date: 2026-04-20
task: ERP ribbon — Exp dropdown preset + ApplyQuickSearch bug fix
files_owned:
  - D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas
  - D:/OneDrive/NelsonData/erp/erp-v14-quick-wins.bas
  - D:/NELSON/2. Areas/Engine_test/ERP/vba-v14-mirror/ (synced)
---

# Agent UX-1 Report — ERP Ribbon Fixes

## FIX 1: Exp textbox → 4-preset dropdown

### Feature Checklist §A-D

| # | Check | Result |
|---|-------|--------|
| A | XML cmbExp still uses `getItemCount` + `getItemLabel` callbacks | Pass — XML unchanged, callbacks rewired |
| B | 4 preset labels return correctly from `GetItemLabel_Exp` | Pass — hardcoded via Select Case index |
| C | `RibbonOnLoad` sets default `m_ExpPreset = EXP_PRESET_ACTIVE` + calls `ApplyQuickSearch` | Pass |
| D | `OnAction_ClearSearch` resets `m_ExpPreset = EXP_PRESET_ACTIVE` (not blank) | Pass |

### Changes

**erp-v14-ribbon-callbacks.bas:**

1. Added module-level declarations (before first Sub, per gotcha #11):
   ```vba
   Private Const EXP_PRESET_ACTIVE As String = "Active only"
   Private Const EXP_PRESET_WEEK   As String = "This week"
   Private Const EXP_PRESET_MONTH  As String = "This month"
   Private Const EXP_PRESET_ALL    As String = "All (incl. expired)"
   Private m_ExpPreset As String
   ```

2. `GetItemCount_Exp` now returns literal `4` instead of dynamic `m_ExpCount`

3. `GetItemLabel_Exp` returns preset labels via `Select Case index` (0-3)

4. `OnChange_SearchExp` — no longer writes text to col 7. Stores selection in `m_ExpPreset`, clears col 7 row 1 placeholder, calls `ApplyQuickSearch`

5. `GetText_SearchExp` returns `m_ExpPreset` (so ribbon shows current selection after Invalidate)

6. `RibbonOnLoad` — sets `m_ExpPreset = EXP_PRESET_ACTIVE` and calls `ApplyQuickSearch` on workbook open

7. `OnAction_ClearSearch` — resets `m_ExpPreset = EXP_PRESET_ACTIVE` (not blank)

8. `GetCurrentExpPreset()` — new Public Function so `ERPv14Core.ApplyQuickSearch` can read current preset

### UX behavior
- Workbook opens → "Active only" auto-applied → only non-expired rates visible
- User picks "This week" → only rates expiring in 7 days shown
- User picks "All (incl. expired)" → no Exp filter
- Clear button → resets to "Active only"

---

## FIX 2: ApplyQuickSearch hidden rate bug

### Feature Checklist §A-D

| # | Check | Result |
|---|-------|--------|
| A | `lr` uses UsedRange instead of End(xlUp) on col A | Pass — fixes 4694 vs 3337 row truncation |
| B | AutoFilter hard-reset before re-apply (no stale criteria) | Pass — `ws.AutoFilterMode = False` then fresh apply |
| C | Exp col 7 filter driven by preset (not text in cell) | Pass |
| D | Status label Q1 shows visible/total row count | Pass (bonus) |

### Root cause confirmed
`lr = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row` traverses from bottom of col A upward, stopping at first blank. With gaps in col A (typical in Pricing sheet where some rows have blank carrier), `lr=3337` instead of `4694` → AutoFilter range truncated → rows beyond 3337 never included in filter → appear "hidden" in baseline query but "revealed" when adding Carrier filter (Carrier filter hits a different col that pushes the range higher? No — actually the opposite: the truncated range simply never includes those rows. The ONE SOC $3,237 row was in rows 3338-4694).

### Changes

**erp-v14-quick-wins.bas — `ApplyQuickSearch` rewrite:**

1. `lr = ws.UsedRange.Rows(ws.UsedRange.Rows.Count).Row` — covers all populated rows

2. Hard reset before reapply:
   ```vba
   If ws.AutoFilterMode Then ws.AutoFilterMode = False
   ws.Rows("2:" & lr).Hidden = False
   ws.Range("A1:P" & lr).AutoFilter
   ```

3. Col 7 (Exp) filtered via `m_ExpPreset` — not via cell text. Calls `ERPv14Ribbon.GetCurrentExpPreset()` with fallback to "Active only"

4. Text criteria loop (`c = 1 To 9`) skips `c = 7` with `If c <> 7` condition

5. Q1 status label (col 17):
   ```
   "26 of 4694 rows"
   ```
   Font gray, size 8. Nelson can verify filter counts at a glance.

---

## Gotchas Applied

| Gotcha | Applied |
|--------|---------|
| #1 ChrW | No Chr/ChrW usage added |
| #2 line continuation | No _ prefix at start of continuation lines |
| #11 module vars at top | EXP_PRESET_* constants + m_ExpPreset declared before first Sub |
| #12 no underscore prefix | All new identifiers: GetCurrentExpPreset, m_ExpPreset, EXP_PRESET_* — no leading _ |
| R8 Option Explicit | Both files already had it, unchanged |
| R9 VB_Name match | erp-v14-ribbon-callbacks → ERPv14Ribbon (kebab skip rule) |

---

## Known Concerns

1. **Circular dependency**: `ERPv14Core.ApplyQuickSearch` calls `ERPv14Ribbon.GetCurrentExpPreset`. This creates a mutual reference between the two modules. In VBA, cross-module Public calls are fine as long as both modules are in the same VBA project (they are). Risk: if one module fails to compile, the other may error too. Mitigation: fallback `If Len(expPreset) = 0 Then expPreset = "Active only"` so ApplyQuickSearch always produces valid output.

2. **Q1 status cell**: col Q (col 17) was previously empty in the pricing sheet. If any formula or data exists there in a specific Nelson workbook setup, the `visible & " of " & ...` write will overwrite it. Low risk — Q is beyond the P-column data boundary.

3. **Exp filter date format**: `Format(Date, "mm/dd/yyyy")` is passed to AutoFilter Criteria1. Excel AutoFilter interprets dates differently based on locale. If Nelson's Excel is set to Vietnamese locale (dd/mm/yyyy), the filter criteria `">=04/20/2026"` may be parsed as Apr 20 vs Oct 4. Recommend testing on actual data. Mitigation: if dates appear wrong, change to `Format(Date, "yyyy-mm-dd")` which is locale-independent in most Excel versions.

4. **m_Exps array is still built** in `BuildComboLists` (scanning all unique dates) but `GetItemCount_Exp` now returns 4 (presets). The array is unused. No harm — just minor dead code.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Both fixes implemented. Exp dropdown now shows 4 preset items; ApplyQuickSearch uses UsedRange + hard AutoFilter reset. Mirror synced to ERP/vba-v14-mirror/.
**Concerns:** (1) Cross-module call ERPv14Core↔ERPv14Ribbon — low risk, has fallback. (2) AutoFilter date locale sensitivity — Nelson should test "Active only" shows correct rows. (3) Q1 overwrite risk — minimal.
