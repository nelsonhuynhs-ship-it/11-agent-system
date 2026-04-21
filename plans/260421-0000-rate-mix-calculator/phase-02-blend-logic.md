# Phase 02 — Blend Logic (ComputeMix + TierMarkup + Peer Lookup)

**Priority:** P2 · **Status:** pending · **Effort:** 60m · **Depends on:** phase 01

## Context Links

- Overview: [plan.md](plan.md) — formula + markup tier + data flow
- Phase 01: [phase-01-ribbon-group.md](phase-01-ribbon-group.md) — stubs now get real bodies
- Canonical callbacks: `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`
- Column constants: same file line 101-116 (`COL_POD=2`, `COL_EFF=6`, `COL_EXP=7`, `COL_NOTE=8`, `COL_SOURCE=9`, `COL_40HQ=12`)
- Row-state capture pattern: same file line 704-714 (`m_Source = ERPv14Core.SS(ws.Cells(targetRow, COL_SOURCE).Value)`)
- Row-iteration pattern: same file line 1534-1545 (batch quote — iterates Pricing Dry cells with same col constants)

## Overview

Implement `ComputeMix()` sub: validates selected row is FIX or FAK, scans Pricing Dry for opposite-type peer on same lane, computes weighted blend, applies tier markup, populates module vars. Wire `GetLabel_MixSell` + `GetEnabled_MixQuote` to real state. No quote write yet (phase 03).

## Key Insights

- Selected-row state already captured in existing m_Source (line 710) + m_Buy40HC (line 42) when Nelson clicks a Pricing Dry row — reuse, don't re-read
- "Special Rate" and "FAK" are the only 2 valid values for Source col per Nelson's spec — case-insensitive match with `UCase`
- Lane key = Carrier+POL+POD+Place+Commodity (cols 4+1+2+3+5). Must ALL match for peer — otherwise blending different services
- Effective window overlap: peer row must have `Eff <= today <= Exp` (or selected row's Eff/Exp window intersect) — else we blend expired rate
- Markup tier is per-container (40HC only in MVP), not per-TEU — Nelson confirmed
- Avoid scanning Pricing Dry more than once per OnChange — cache the peer row lookup keyed by selected row# + qty combo

## Requirements

**Functional:**
- Given selected row FIX@$2000 + peer row FAK@$2800 + qty 1:2 → blend=$2533, markup=$275, sell=$2808 (exact match)
- Peer lookup: single scan, O(N) where N = Pricing Dry row count (~200 rows typical, <50ms)
- Status states (`m_MixStatus`) drive label text and button enable:
  - `"OK"` → `"Sell: $2,808 (blend $2,533 + $275)"` + button enabled
  - `"NO_PEER"` → `ChrW(9888) & " No FAK/FIX peer on this lane"` + button disabled
  - `"BAD_ROW"` → `ChrW(9888) & " Row not FIX/FAK"` + button disabled
  - `"ZERO_QTY"` → `"Sell: $—"` + button disabled
  - `""` (no row clicked) → `"Sell: $— (click a row first)"` + button disabled

**Non-functional:**
- Recompute <100ms on typical sheet
- No modal popups during compute (silent failure → status string)

## Architecture

**New private helpers:**

```
' Tier markup lookup — per-container USD
Private Function TierMarkup(fakPct As Double) As Long
    If fakPct <= 33 Then
        TierMarkup = 150
    ElseIf fakPct <= 66 Then
        TierMarkup = 200
    ElseIf fakPct < 100 Then
        TierMarkup = 275      ' midpoint of 250-300 band (MVP)
    Else
        TierMarkup = 350
    End If
End Function

' Scan Pricing Dry for row with same lane + opposite Source
' Returns row number, or 0 if not found
Private Function FindPeerRow(selRow As Long, selSource As String) As Long
    Dim ws As Worksheet
    Set ws = ERPv14Core.FindSheet("Pricing Dry")
    If ws Is Nothing Then FindPeerRow = 0: Exit Function

    Dim wantSource As String
    If InStr(UCase(selSource), "FAK") > 0 Then
        wantSource = "SPECIAL"
    ElseIf InStr(UCase(selSource), "SPECIAL") > 0 Then
        wantSource = "FAK"
    Else
        FindPeerRow = 0: Exit Function
    End If

    ' Anchors from selected row
    Dim selCarrier As String, selPOL As String, selPOD As String
    Dim selPlace As String, selCom As String
    selCarrier = UCase(Trim(ws.Cells(selRow, COL_CARRIER).Value))
    selPOL     = UCase(Trim(ws.Cells(selRow, COL_POL).Value))
    selPOD     = UCase(Trim(ws.Cells(selRow, COL_POD).Value))
    selPlace   = UCase(Trim(ws.Cells(selRow, COL_PLACE).Value))
    selCom     = UCase(Trim(ws.Cells(selRow, COL_COMMODITY).Value))

    Dim lastRow As Long, r As Long
    lastRow = ws.Cells(ws.Rows.Count, COL_CARRIER).End(xlUp).Row

    Dim bestRow As Long: bestRow = 0
    Dim bestEff As Date: bestEff = DateSerial(1900, 1, 1)

    For r = 2 To lastRow
        If r <> selRow Then
            If InStr(UCase(Trim(ws.Cells(r, COL_SOURCE).Value)), wantSource) > 0 Then
                If UCase(Trim(ws.Cells(r, COL_CARRIER).Value)) = selCarrier And _
                   UCase(Trim(ws.Cells(r, COL_POL).Value))     = selPOL     And _
                   UCase(Trim(ws.Cells(r, COL_POD).Value))     = selPOD     And _
                   UCase(Trim(ws.Cells(r, COL_PLACE).Value))   = selPlace   And _
                   UCase(Trim(ws.Cells(r, COL_COMMODITY).Value)) = selCom Then
                    ' Effective window check: Exp >= today
                    Dim rExp As Variant: rExp = ws.Cells(r, COL_EXP).Value
                    If IsDate(rExp) Then
                        If CDate(rExp) >= Date Then
                            ' 40HC must be positive
                            If ERPv14Core.SafeLong(ws.Cells(r, COL_40HQ).Value) > 0 Then
                                ' Prefer latest Eff
                                Dim rEff As Variant: rEff = ws.Cells(r, COL_EFF).Value
                                If IsDate(rEff) Then
                                    If CDate(rEff) >= bestEff Then
                                        bestEff = CDate(rEff)
                                        bestRow = r
                                    End If
                                ElseIf bestRow = 0 Then
                                    bestRow = r
                                End If
                            End If
                        End If
                    End If
                End If
            End If
        End If
    Next r
    FindPeerRow = bestRow
End Function

' Main compute — called on every OnChange + after row click
Public Sub ComputeMix()
    On Error GoTo fail
    m_MixStatus = ""
    m_MixBlended40HC = 0
    m_MixMarkup = 0
    m_MixSell40HC = 0
    m_MixPeerRow = 0

    ' Guard 1: row selected?
    If m_SourceRow <= 0 Or m_Source = "" Then
        m_MixStatus = "": Exit Sub
    End If

    ' Guard 2: row is FIX or FAK?
    Dim upSrc As String: upSrc = UCase(m_Source)
    If InStr(upSrc, "FAK") = 0 And InStr(upSrc, "SPECIAL") = 0 Then
        m_MixStatus = "BAD_ROW": Exit Sub
    End If

    ' Guard 3: both qty > 0? (allow 0 on one side = pure case)
    If m_FixQty < 0 Then m_FixQty = 0
    If m_FakQty < 0 Then m_FakQty = 0
    If (m_FixQty + m_FakQty) <= 0 Then
        m_MixStatus = "ZERO_QTY": Exit Sub
    End If

    ' Read selected row's 40HC
    Dim ws As Worksheet: Set ws = ERPv14Core.FindSheet("Pricing Dry")
    Dim selRate As Long: selRate = ERPv14Core.SafeLong(ws.Cells(m_SourceRow, COL_40HQ).Value)
    If selRate <= 0 Then m_MixStatus = "BAD_ROW": Exit Sub

    ' Decide which side selected row plays
    Dim fixRate As Long, fakRate As Long
    Dim peerRow As Long
    If InStr(upSrc, "SPECIAL") > 0 Then
        ' Selected = FIX; need FAK peer
        fixRate = selRate
        peerRow = FindPeerRow(m_SourceRow, m_Source)
        If peerRow = 0 Then m_MixStatus = "NO_PEER": Exit Sub
        fakRate = ERPv14Core.SafeLong(ws.Cells(peerRow, COL_40HQ).Value)
    Else
        ' Selected = FAK; need FIX peer
        fakRate = selRate
        peerRow = FindPeerRow(m_SourceRow, m_Source)
        If peerRow = 0 Then m_MixStatus = "NO_PEER": Exit Sub
        fixRate = ERPv14Core.SafeLong(ws.Cells(peerRow, COL_40HQ).Value)
    End If
    If fixRate <= 0 Or fakRate <= 0 Then m_MixStatus = "NO_PEER": Exit Sub

    ' Blend (integer math OK — cents irrelevant in freight)
    Dim totalQty As Long: totalQty = m_FixQty + m_FakQty
    m_MixBlended40HC = (CDbl(m_FixQty) * fixRate + CDbl(m_FakQty) * fakRate) / totalQty
    Dim fakPct As Double: fakPct = CDbl(m_FakQty) / totalQty * 100
    m_MixMarkup = TierMarkup(fakPct)
    m_MixSell40HC = CLng(m_MixBlended40HC + m_MixMarkup)
    m_MixPeerRow = peerRow
    m_MixStatus = "OK"
    Exit Sub
fail:
    m_MixStatus = ""
    g_LastError = "ComputeMix #" & Err.Number & ": " & Err.Description
End Sub
```

**Replace phase-01 stubs with real bodies:**

```
Public Sub GetLabel_MixSell(control As IRibbonControl, ByRef returnedVal)
    Select Case m_MixStatus
        Case "OK"
            returnedVal = "Sell: $" & Format(m_MixSell40HC, "#,##0") & _
                          " (blend $" & Format(CLng(m_MixBlended40HC), "#,##0") & _
                          " + $" & m_MixMarkup & ")"
        Case "NO_PEER"
            returnedVal = ChrW(9888) & " No peer FIX/FAK on this lane"
        Case "BAD_ROW"
            returnedVal = ChrW(9888) & " Selected row not FIX/FAK"
        Case "ZERO_QTY"
            returnedVal = "Sell: $— (enter FIX" & ChrW(215) & " / FAK" & ChrW(215) & ")"
        Case Else
            returnedVal = "Sell: $— (click a Pricing Dry row first)"
    End Select
End Sub

Public Sub GetEnabled_MixQuote(control As IRibbonControl, ByRef returnedVal)
    returnedVal = (m_MixStatus = "OK") And (m_Customer <> "")
End Sub
```

**Wire OnChange handlers (replace phase-01 stub body):**

```
Public Sub OnChange_FixQty(control As IRibbonControl, text As String)
    On Error Resume Next
    m_FixQty = ERPv14Core.SafeLong(text)
    Call ComputeMix
    If Not g_Ribbon Is Nothing Then
        g_Ribbon.InvalidateControl "lblMixSell"
        g_Ribbon.InvalidateControl "btnMixQuote"
    End If
End Sub
' (OnChange_FakQty mirrors)
```

**Hook into row-click path:** the existing row-click handler that populates `m_SourceRow` + `m_Source` must also call `ComputeMix` so the label updates when Nelson clicks different row. Find the sub that writes `m_SourceRow = targetRow` (line 711) and append `Call ComputeMix` + Invalidate.

## Related Code Files

**Modify (1):**
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — add 2 helpers (`TierMarkup`, `FindPeerRow`), 1 main (`ComputeMix`), replace 4 stub bodies, add 1 line to row-click handler

**Read for reference (no edit):**
- Line 697-720 (row-click state capture — pattern to emulate for invoking ComputeMix)
- Line 1534-1562 (batch quote row iteration — pattern for cell scanning)

## Implementation Steps

1. **Locate row-click handler** populating `m_SourceRow`: grep `m_SourceRow = targetRow` → identify enclosing sub name (likely `CaptureRowState` or similar).
2. **Add 2 helpers:** `TierMarkup`, `FindPeerRow` — place directly BEFORE the callback stubs section added in phase 01.
3. **Add main `ComputeMix` sub** below helpers.
4. **Replace 4 phase-01 stub bodies:** GetLabel_MixSell, GetEnabled_MixQuote, OnChange_FixQty (body), OnChange_FakQty (body).
5. **Hook into row-click handler:** append `Call ComputeMix` + 2 InvalidateControl calls right after `m_SourceRow = targetRow` line.
6. **Compile check** (Alt+F11 Debug > Compile).
7. **Reimport:** `python scripts/reimport-erp-vba-modules.py`.
8. **Smoke test:** open xlsm → click Pricing Dry row with Source="Special Rate" → type FIX×=1 FAK×=2 → label must show blended sell within 500ms. Verify number matches manual calc.
9. **Negative test:** click row with Source="FIXED" (not FIX/FAK) → label shows "⚠ Selected row not FIX/FAK".
10. **Negative test:** click FIX row on lane with no FAK peer → label "⚠ No peer FIX/FAK on this lane".

## Todo List

- [ ] 1. Identified row-click handler by name
- [ ] 2. TierMarkup + FindPeerRow helpers added, compile clean
- [ ] 3. ComputeMix body written with all 3 guards (row, type, qty)
- [ ] 4. 4 stubs replaced with live bodies
- [ ] 5. Row-click hook calls ComputeMix + invalidates
- [ ] 6. Compile passes
- [ ] 7. Reimport exit 0
- [ ] 8. Positive: 1:2 blend produces correct $2,808
- [ ] 9. BAD_ROW warning on non-FIX/FAK row
- [ ] 10. NO_PEER warning on isolated lane
- [ ] 11. ZERO_QTY state: clear both inputs → label "Sell: $—"
- [ ] 12. MIX QUOTE button: enabled only when m_MixStatus=OK AND Customer set

## Success Criteria

- 4 numeric scenarios from plan.md test matrix pass (pure FIX, balanced, FAK-heavy, pure FAK) within $1 rounding
- Row-click immediately refreshes label without requiring qty retype
- Button grey unless `OK` state AND customer combobox filled
- No modal popups during compute, no ribbon lag >200ms

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FindPeerRow ambiguous (multiple matches) | High | Med | Pick latest Eff; if tie, first match — log peerRow# in Remark at quote time (phase 03) |
| Commodity col blank on some rows → over-matches | Med | Med | Treat blank-vs-blank as match (common case: FAK has blank commodity) |
| COMMODITY col number unknown (plan assumed 5) | Low | High | Verify `COL_COMMODITY` const exists (it does, line 105) |
| Division by zero if both qty = 0 | Low | Critical | Guarded in ComputeMix; also getEnabled ensures button off |
| Double-precision float rounding on $2533.33 | Low | Low | Use `CLng` for final sell — freight rounds to dollar anyway |
| ERPv14Core.SafeLong not exported | Low | Med | Verify via grep; fallback `CLng(Val(text))` with On Error |
| Peer row's 40HC = 0 → blend corrupt | Med | High | FindPeerRow already filters `> 0`; ComputeMix double-checks |
| Row iteration on filtered sheet misses hidden rows | Low | Med | Iterate by row# (not by visible), use SpecialCells(xlCellTypeVisible)? NO — we want all rates, visible or not |

## Security Considerations

None (read-only of Pricing Dry, in-memory math).

## Next Steps

→ Phase 03: wire OnAction_MixQuote to insert row in Quotes sheet using blended values.
