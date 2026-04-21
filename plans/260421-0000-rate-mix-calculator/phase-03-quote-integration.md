# Phase 03 — Quote Integration (1-click MIX QUOTE)

**Priority:** P2 · **Status:** pending · **Effort:** 45m · **Depends on:** phase 02

## Context Links

- Overview: [plan.md](plan.md)
- Phase 02: [phase-02-blend-logic.md](phase-02-blend-logic.md) — m_Mix* vars populated when OK
- Existing quote writer: `erp-v14-ribbon-callbacks.bas:1254` (`OnAction_GenerateQuote`) — reuse sheet-insert + header pattern
- Quotes header definition: same file line 1275-1281 (36 cols: QuoteID...StatusDate)
- QUOTES_HEADER_ROW=4, QUOTES_DATA_START=5 constants

## Overview

Implement `OnAction_MixQuote` to write ONE row into Quotes sheet using blended 40HC values. Reuse pattern from `OnAction_GenerateQuote` (row insert at top, QuoteID gen, header init) — but tagged with `Source="MIX (XF:YA)"` and Remark carrying audit trail (peer row#, blend value, fak%).

## Key Insights

- Don't call OnAction_GenerateQuote recursively — it runs container picker which we don't want (MVP is 40HC only)
- Must inherit the "insert at top" pattern (line 1331) so Mix quotes appear at QUOTES_DATA_START=5 like regular quotes — maintains Nelson's no-scroll UX
- QuoteID format: `DDMMM-NNN` — reuse exact line 1327 pattern
- Header init guard (line 1273) must also be honored — first Mix quote on empty sheet still writes headers
- Leave 20GP/40GP/45HC/40NOR/20RF/40RF cols BLANK (not 0) — downstream reports distinguish "not quoted" from "quoted $0"
- Eff/Exp: use MIN of selected + peer row (more conservative = earliest expiry wins)

## Requirements

**Functional:**
- Click MIX QUOTE → insert 1 row in Quotes at row 5 (push existing down)
- Columns written: QuoteID, Date, Customer, Carrier, POL, POD, Place, Via(blank), Eff, Exp, Source, Buy_40HC, Mar_40HC, Sell_40HC, Remark, Status, StatusDate
- Columns explicitly blank: Buy_20GP, Buy_40GP, Buy_45HC, Buy_40NOR, Buy_20RF, Buy_40RF, Mar_* (all except 40HC), Sell_* (all except 40HC), PUC_*
- Source col: `"MIX (" & m_FixQty & "F:" & m_FakQty & "A)"`
- Remark col: `"MIX blend=$" & CLng(m_MixBlended40HC) & " fak%=" & Round(fakPct) & " FIX_row=" & fixRow & " FAK_row=" & fakRow`
- After insert: MsgBox confirmation `"MIX quote " & qid & " created. Sell 40HC = $" & m_MixSell40HC`
- Reset inputs? NO — Nelson often quotes same mix to multiple customers. Leave m_FixQty/m_FakQty intact.

**Non-functional:**
- Single write < 200ms
- No freeze, no regression on Quotes sheet formatting

## Architecture

**Replace phase-01 MsgBox stub with full body:**

```
Public Sub OnAction_MixQuote(Optional control As IRibbonControl = Nothing)
    On Error GoTo fail

    ' Re-validate (defense in depth even though button disabled when invalid)
    If m_MixStatus <> "OK" Then
        MsgBox "Rate Mix not ready: " & m_MixStatus, vbExclamation, "Rate Mix"
        Exit Sub
    End If
    If m_Customer = "" Then
        MsgBox "Enter Customer first!", vbExclamation, "Rate Mix"
        Exit Sub
    End If

    Dim wsQ As Worksheet: Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        MsgBox "Quotes sheet not found!", vbExclamation, "Rate Mix"
        Exit Sub
    End If

    ' Header init (same pattern as OnAction_GenerateQuote line 1273)
    If IsEmpty(wsQ.Cells(QUOTES_HEADER_ROW, 1).Value) Then
        Dim h As Variant
        h = Array("QuoteID", "Date", "Customer", "Carrier", "POL", "POD", _
                  "Place", "Via", "Eff", "Exp", "Source", _
                  "Buy_20GP", "Buy_40GP", "Buy_40HC", "Buy_45HC", "Buy_40NOR", "Buy_20RF", "Buy_40RF", _
                  "Mar_20GP", "Mar_40GP", "Mar_40HC", "Mar_45HC", "Mar_40NOR", "Mar_20RF", "Mar_40RF", _
                  "PUC_20", "PUC_40", "PUC_40HC", _
                  "Sell_20GP", "Sell_40GP", "Sell_40HC", "Sell_45HC", "Sell_40NOR", "Sell_20RF", "Sell_40RF", _
                  "Status", "Remark", "StatusDate")
        Dim hi As Integer
        For hi = 0 To UBound(h): wsQ.Cells(QUOTES_HEADER_ROW, hi + 1).Value = h(hi): Next hi
        wsQ.Range("A" & QUOTES_HEADER_ROW & ":AL" & QUOTES_HEADER_ROW).Font.Bold = True
    End If

    ' Derive FIX/FAK row#s for audit
    Dim fixRow As Long, fakRow As Long
    If InStr(UCase(m_Source), "SPECIAL") > 0 Then
        fixRow = m_SourceRow: fakRow = m_MixPeerRow
    Else
        fakRow = m_SourceRow: fixRow = m_MixPeerRow
    End If

    ' Compute conservative Eff/Exp (min of 2 rows)
    Dim ws As Worksheet: Set ws = ERPv14Core.FindSheet("Pricing Dry")
    Dim effSel As Variant, effPeer As Variant
    Dim expSel As Variant, expPeer As Variant
    effSel = ws.Cells(m_SourceRow, COL_EFF).Value
    effPeer = ws.Cells(m_MixPeerRow, COL_EFF).Value
    expSel = ws.Cells(m_SourceRow, COL_EXP).Value
    expPeer = ws.Cells(m_MixPeerRow, COL_EXP).Value

    Dim quoteEff As Variant, quoteExp As Variant
    If IsDate(effSel) And IsDate(effPeer) Then
        quoteEff = IIf(CDate(effSel) > CDate(effPeer), effSel, effPeer)   ' latest Eff = safest
    ElseIf IsDate(effSel) Then
        quoteEff = effSel
    Else
        quoteEff = effPeer
    End If
    If IsDate(expSel) And IsDate(expPeer) Then
        quoteExp = IIf(CDate(expSel) < CDate(expPeer), expSel, expPeer)   ' earliest Exp = safest
    ElseIf IsDate(expSel) Then
        quoteExp = expSel
    Else
        quoteExp = expPeer
    End If

    ' QuoteID (reuse line 1327 pattern)
    Dim qid As String
    qid = UCase(Format(Date, "DDMMM")) & "-" & Format(Int((999 - 100 + 1) * Rnd + 100), "000")

    ' Insert row at top of data block (line 1331 pattern)
    wsQ.Rows(QUOTES_DATA_START).Insert Shift:=xlDown, CopyOrigin:=xlFormatFromLeftOrAbove
    Dim nr As Long: nr = QUOTES_DATA_START

    ' Compute fak% for Remark
    Dim fakPct As Double
    fakPct = CDbl(m_FakQty) / (m_FixQty + m_FakQty) * 100

    ' Fill cols (blank unspecified ones — do not overwrite inherited formatting from insert)
    wsQ.Cells(nr, 1).Value = qid
    wsQ.Cells(nr, 2).Value = Date
    wsQ.Cells(nr, 3).Value = m_Customer
    wsQ.Cells(nr, 4).Value = m_Carrier
    wsQ.Cells(nr, 5).Value = m_POL
    wsQ.Cells(nr, 6).Value = m_POD
    wsQ.Cells(nr, 7).Value = m_Place
    ' col 8 Via = blank
    wsQ.Cells(nr, 9).Value = quoteEff
    wsQ.Cells(nr, 10).Value = quoteExp
    wsQ.Cells(nr, 11).Value = "MIX (" & m_FixQty & "F:" & m_FakQty & "A)"
    ' Buy cols 12-18: only col 14 (Buy_40HC) written
    wsQ.Cells(nr, 14).Value = CLng(m_MixBlended40HC)
    ' Mar cols 19-25: only col 21 (Mar_40HC) written
    wsQ.Cells(nr, 21).Value = m_MixMarkup
    ' PUC cols 26-28: blank
    ' Sell cols 29-35: only col 31 (Sell_40HC) written
    wsQ.Cells(nr, 31).Value = m_MixSell40HC
    ' Status / Remark / StatusDate
    wsQ.Cells(nr, 36).Value = "PENDING"
    wsQ.Cells(nr, 37).Value = "MIX blend=$" & CLng(m_MixBlended40HC) & _
                              " fak%=" & Format(fakPct, "0") & _
                              " FIX_row=" & fixRow & " FAK_row=" & fakRow
    wsQ.Cells(nr, 38).Value = Now

    MsgBox "MIX quote " & qid & " created." & vbCrLf & _
           "Sell 40HC = $" & Format(m_MixSell40HC, "#,##0"), _
           vbInformation, "Rate Mix"
    Exit Sub
fail:
    g_LastError = "OnAction_MixQuote #" & Err.Number & ": " & Err.Description
    MsgBox "Rate Mix quote failed. See g_LastError.", vbCritical, "Rate Mix"
End Sub
```

**Column index verification:** use header row 4 read-once cache instead of hardcoded offsets? **NO for MVP** — matches existing OnAction_GenerateQuote style (hardcoded per line 1283-1331). If Quotes schema drifts, both subs break together — acceptable tradeoff for KISS.

## Related Code Files

**Modify (1):**
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — replace phase-01 MsgBox stub body

**Read for reference (no edit):**
- Same file line 1254-1413 (OnAction_GenerateQuote — pattern source)
- Same file line 1331 (row insert at top)

**Unchanged:**
- Quotes sheet schema (reuses existing 36+2 cols)
- No new module, no new .bas file

## Implementation Steps

1. **Locate phase-01 stub** `OnAction_MixQuote` at bottom of callbacks .bas.
2. **Replace body** with full implementation above.
3. **Compile check** (Alt+F11).
4. **Reimport** via `reimport-erp-vba-modules.py`.
5. **Live test:** select Pricing Dry row FIX COSCO HPH→USLAX Special Rate $2000; enter ebFixQty=1, ebFakQty=2; select Customer from combo; click MIX QUOTE.
6. **Verify Quotes sheet row 5:** QuoteID present, Customer match, Source="MIX (1F:2A)", Buy_40HC=2533, Mar_40HC=275, Sell_40HC=2808, Status=PENDING, Remark contains row numbers.
7. **Verify all other cont cols blank** (not zero) on row 5.
8. **Verify insert shifted** previous quotes down (row 6 = previous row 5).
9. **Verify formatting preserved** (bold header row 4, number formats on sell cols).
10. **Regression:** click normal QUOTE button → still produces all-container quote at row 5 (pushing MIX quote to row 6).

## Todo List

- [ ] 1. Stub body replaced
- [ ] 2. Compile clean
- [ ] 3. Reimport exit 0
- [ ] 4. Live MIX QUOTE produces correctly formatted row
- [ ] 5. Numerical values match phase-02 calc
- [ ] 6. Other cont cols verified blank
- [ ] 7. Row insert shifts existing down
- [ ] 8. Remark contains audit trail (blend$, fak%, row#s)
- [ ] 9. Confirmation MsgBox displays correct sell
- [ ] 10. Regression: normal QUOTE still works

## Success Criteria

- Quote row visually indistinguishable from normal quote EXCEPT Source="MIX (...)" tag
- Audit trail in Remark sufficient to reconstruct blend math 6 months later
- Zero corruption on Quotes sheet (count of rows = previous + 1, no duplicate headers, no stray cells)
- Customer receives clean $-figure in downstream Word template (no "MIX" leakage into customer-facing text)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Quotes sheet col layout drifts from hardcoded 14/21/31 | Low | Critical | Phase 04 test case: "verify Buy_40HC header at col 14" |
| Row insert corrupts merged cells / conditional formatting | Low | Med | Use `CopyOrigin:=xlFormatFromLeftOrAbove` (same as existing line 1331) |
| QuoteID collision (random 100-999 on same day) | Low | Low | Same risk exists in OnAction_GenerateQuote — accept as-is; Nelson notices duplicate |
| Word template doesn't recognize "MIX" Source | Med | Med | Out of MVP scope — Word template uses Sell_40HC only, Source col not referenced |
| Nelson clicks MIX QUOTE twice → 2 rows | Med | Low | Acceptable (user error); no dedup logic (KISS) |
| Blended cost differs from peer row's Note (e.g. note says "all-in") | Low | Med | Note col NOT inherited by MIX quote → avoids misleading "all-in" carry-over |
| MIX quote shows in Price Watch scanner → false alert | Med | Med | Price Watch filters on Status=PENDING + Source NOT LIKE "MIX%" — **add filter in phase 04 as optional hardening** |

## Security Considerations

- Remark col contains row numbers — internal audit only, never exposed to customer
- No external writes; all ops on same xlsm

## Next Steps

→ Phase 04: 3-scenario manual test + rollback drill + optional Price Watch filter tweak.
