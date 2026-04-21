# Phase 01 — Ribbon Group + Callback Stubs

**Priority:** P2 · **Status:** pending · **Effort:** 45m

## Context Links

- Overview: [plan.md](plan.md)
- Canonical CustomUI: `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` (line 94 = grpQuoteAction start, insert BEFORE this)
- Canonical callbacks: `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` (line 66 = end of module vars block, inject new vars here)
- System rules: `docs/SYSTEM_STANDARDS.md` RULE 5.x (VBA), RULE 5.4 (reimport flow)
- Reimport script: `scripts/reimport-erp-vba-modules.py`
- CustomUI helper: `D:/OneDrive/NelsonData/erp/customui_utils.py`

## Overview

Add `grpRateMix` group to Pricing tab with 2 editBoxes (qty), 1 labelControl (live sell preview), 1 button (MIX QUOTE). Stub all 6 callback subs/functions returning placeholder values — real logic comes in phase 02.

## Key Insights

- grpRateMix must sit BETWEEN grpSellRate (line 81–91) and grpQuoteAction (line 94) — logical flow: select row → see sell → blend ratio → quote
- Cannot rewrite CustomUI_v14.xml wholesale — blocking plan (260420-1700) added btnSyncMilestones line 143-145. Use surgical insert, verify both changes present after.
- Module vars MUST be declared at TOP of .bas file (VBA requirement) — inject after line 66 (end of existing `Private m_Search*` block)
- No leading underscore in sub names (VBA rule per SYSTEM_STANDARDS)
- Ribbon callbacks need `Optional control As IRibbonControl = Nothing` signature to be discoverable

## Requirements

**Functional:**
- Nelson sees 2 input boxes labeled "FIX ×" and "FAK ×" (use `ChrW(215)` for multiplication sign)
- Live label "Sell: $—" renders immediately on tab load (no crash if no row selected)
- Button visible but ignored if inputs invalid (phase 02 adds real guard)

**Non-functional:**
- Ribbon reload <1s
- Zero regression on existing 16 Pricing tab controls

## Architecture

**XML block to insert (between line 91 `</group>` and line 94 `<group id="grpQuoteAction">`):**

```xml
<!-- GROUP 4b: RATE MIX (FIX+FAK blend) -->
<group id="grpRateMix" label="Rate Mix">
  <editBox id="ebFixQty" label="FIX ×" sizeString="00"
           getText="GetText_FixQty" onChange="OnChange_FixQty"
           screentip="So luong FIX (Special Rate) cont"/>
  <editBox id="ebFakQty" label="FAK ×" sizeString="00"
           getText="GetText_FakQty" onChange="OnChange_FakQty"
           screentip="So luong FAK cont"/>
  <labelControl id="lblMixSell" getLabel="GetLabel_MixSell"/>
  <button id="btnMixQuote" label="MIX QUOTE" size="large"
          imageMso="CreateTable" onAction="OnAction_MixQuote"
          getEnabled="GetEnabled_MixQuote"
          screentip="Quote 40HC voi gia blend FIX+FAK + tier markup"/>
</group>
```

**VBA module vars to add (inject after line 66 `Private m_SearchCarrier`):**

```
' --- Rate Mix state ---
Private m_FixQty As Long
Private m_FakQty As Long
Private m_MixPeerRow As Long
Private m_MixBlended40HC As Double
Private m_MixMarkup As Long
Private m_MixSell40HC As Long
Private m_MixStatus As String   ' "OK" | "NO_PEER" | "BAD_ROW" | "ZERO_QTY" | ""
```

**Callback stubs (append to END of file, before any trailing comment):**

```
' ========== RATE MIX CALLBACKS (phase 01 stubs) ==========

Public Sub GetText_FixQty(control As IRibbonControl, ByRef returnedVal)
    returnedVal = IIf(m_FixQty > 0, CStr(m_FixQty), "")
End Sub

Public Sub OnChange_FixQty(control As IRibbonControl, text As String)
    On Error Resume Next
    m_FixQty = ERPv14Core.SafeLong(text)
    ' phase 02: Call ComputeMix
    If Not g_Ribbon Is Nothing Then
        g_Ribbon.InvalidateControl "lblMixSell"
        g_Ribbon.InvalidateControl "btnMixQuote"
    End If
End Sub

Public Sub GetText_FakQty(control As IRibbonControl, ByRef returnedVal)
    returnedVal = IIf(m_FakQty > 0, CStr(m_FakQty), "")
End Sub

Public Sub OnChange_FakQty(control As IRibbonControl, text As String)
    On Error Resume Next
    m_FakQty = ERPv14Core.SafeLong(text)
    ' phase 02: Call ComputeMix
    If Not g_Ribbon Is Nothing Then
        g_Ribbon.InvalidateControl "lblMixSell"
        g_Ribbon.InvalidateControl "btnMixQuote"
    End If
End Sub

Public Sub GetLabel_MixSell(control As IRibbonControl, ByRef returnedVal)
    ' phase 01 stub — phase 02 returns real blended sell
    returnedVal = "Sell: $—"
End Sub

Public Sub GetEnabled_MixQuote(control As IRibbonControl, ByRef returnedVal)
    ' phase 01 stub — phase 02 gates on m_MixStatus = "OK"
    returnedVal = False
End Sub

Public Sub OnAction_MixQuote(Optional control As IRibbonControl = Nothing)
    ' phase 03 implementation
    MsgBox "MIX QUOTE not yet implemented (phase 03)", vbInformation, "Rate Mix"
End Sub
```

## Related Code Files

**Modify (2):**
- `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` — surgical insert
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — vars + stubs

**Read for pattern reference (no edit):**
- CustomUI_v14.xml line 62-91 (grpMargin + grpSellRate — closest precedent for editBox + label pattern)
- erp-v14-ribbon-callbacks.bas line 40-66 (module var declaration style)
- erp-v14-ribbon-callbacks.bas line 1254 (existing OnAction_GenerateQuote — pattern for guards + error handling)

**Create:** none

**Delete:** none

## Implementation Steps

1. **Backup first.** Copy ERP_Master_v14.xlsm + CustomUI_v14.xml + erp-v14-ribbon-callbacks.bas → `backups/YYYYMMDD-HHMM-pre-ratemix-phase01/`. Verify mtime + size.
2. **Verify blocking plan merged.** Grep CustomUI_v14.xml for `btnSyncMilestones` (line 143) and callbacks.bas for `Btn_SyncMilestones_OnAction`. If missing, STOP — blocking plan not yet landed.
3. **Edit CustomUI_v14.xml:** insert grpRateMix XML block between line 91 (`</group>` closing grpSellRate) and line 93 (comment `<!-- GROUP 5: QUOTE ACTION -->`). Preserve all other bytes.
4. **Edit erp-v14-ribbon-callbacks.bas:** inject 7 new `Private m_Mix*` / `m_Fix*` / `m_Fak*` var lines after the existing `Private m_Search*` block (~line 70).
5. **Append callback stubs** to END of .bas file (before last line if any comment/footer exists).
6. **Compile check:** open xlsm → Alt+F11 → Debug > Compile VBAProject. Must return "no errors". If error, check: no leading underscore, no missing `End Sub`, all `IRibbonControl` arguments present.
7. **Reimport:** run `python scripts/reimport-erp-vba-modules.py` (per RULE 5.4 canonical flow). Verify exit code 0.
8. **Re-open xlsm:** ribbon must show new "Rate Mix" group with 2 edit boxes + "Sell: $—" label + grey "MIX QUOTE" button (disabled via stub).
9. **Regression:** click any row in Pricing Dry → verify Mar/Sell groups still update. Click QUOTE (normal) → verify it still produces a row in Quotes sheet.

## Todo List

- [ ] 1. Dated backup folder created, 3 files copied, mtime verified
- [ ] 2. Blocking plan bytes confirmed present in both canonical files
- [ ] 3. CustomUI_v14.xml insert lands between correct line numbers (re-grep line count)
- [ ] 4. 7 module vars appear at top of .bas (between existing Private blocks)
- [ ] 5. 7 callback stubs appear at bottom of .bas, compile clean
- [ ] 6. Compile VBAProject returns no errors
- [ ] 7. reimport-erp-vba-modules.py exit 0
- [ ] 8. Ribbon shows grpRateMix visually correct
- [ ] 9. Regression: 1 normal QUOTE still works end-to-end

## Success Criteria

- Ribbon loads ≤1s, no error popup
- "Rate Mix" group visually between Sell Rate and Quote groups
- "MIX QUOTE" button renders disabled (grey)
- Typing in FIX× or FAK× persists (type `3`, click away, come back, still `3`)
- All existing Pricing tab controls functional (Margin, Sell, QUOTE, Batch)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CustomUI malformed → ribbon silent fail | Low | Critical | XML lint via `python -c "import xml.etree.ElementTree as ET; ET.parse('CustomUI_v14.xml')"` before reimport |
| Missed blocking plan merge → overwrites btnSyncMilestones | Med | Critical | Step 2 gate + step 9 regression includes Operations tab spot-check |
| Wrong insert line (off-by-one) → breaks XML | Low | Critical | Use line-anchored insert, not char offset; verify closing `</group>` count unchanged |
| `g_Ribbon` not declared globally (stub Invalidate crashes) | Med | High | Verify `g_Ribbon` exists before phase 01 (grep — it must, or existing ribbon doesn't work) |
| `ERPv14Core.SafeLong` not exported | Low | Med | Fallback: `CLng(Val(text))` with On Error Resume Next |

## Security Considerations

None (ribbon-only, no data writes in phase 01).

## Next Steps

→ Phase 02: wire ComputeMix to scan Pricing Dry for peer row + compute blend + gate button.
