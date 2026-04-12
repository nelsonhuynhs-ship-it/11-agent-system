# Phase 5 — VBA Patches (Markup Per-Lane)

Main agent owns the two `.bas` files under `D:/OneDrive/NelsonData/erp/`. This
document contains the EXACT diffs main agent applies after reviewing them.

**DO NOT** apply these patches blindly — read each file's current state first
with the Read tool, verify the `Find` block matches byte-for-byte, then apply
the `Replace` block.

After all three patches are applied, main agent must:
1. Run `python scripts/migrate-markup-store.py --dry-run` (sanity check).
2. Run `python scripts/migrate-markup-store.py` (live migrate — writes xlsm).
3. Re-import the two `.bas` files via `python scripts/reimport-erp-vba.py`
   (requires Excel "Trust access to the VBA project object model" enabled).
4. Run `python -m pytest tests/integration/test_erp_lane_mapper.py -v`
   (18 parametrized cases should now pass).

---

## Patch 1: Add `GetLaneFromPOD` to `ERPv14Core` module

**File:** `D:/OneDrive/NelsonData/erp/erp-v14-quick-wins.bas`

**Action:** Append to the END of the file (after the last existing line, which
is the `' (These stubs are only used if the full modules are NOT imported)`
comment near line 332). Do NOT modify any existing function.

**Content to append:**

```vba

' ============================================================
'  LANE MAPPER — added 2026-04-11 (Phase 5)
' ============================================================
' Maps a POD string to a lane group for markup lookup.
' Mirrors the lane map used by forecast/market report.
' Returns "WC" / "EC" / "GULF" / "*" (default fallback).
Public Function GetLaneFromPOD(pod As String) As String
    Dim p As String: p = UCase(Trim(pod))
    If Len(p) = 0 Then GetLaneFromPOD = "*": Exit Function

    ' WC ports
    If InStr(p, "LAX") > 0 Or InStr(p, "LGB") > 0 Or InStr(p, "LONG BEACH") > 0 _
        Or InStr(p, "OAK") > 0 Or InStr(p, "OAKLAND") > 0 _
        Or InStr(p, "SEA") > 0 Or InStr(p, "TAC") > 0 Or InStr(p, "TACOMA") > 0 _
        Or InStr(p, "VANCOUVER") > 0 Or InStr(p, "PORTLAND") > 0 Then
        GetLaneFromPOD = "WC": Exit Function
    End If

    ' EC ports
    If InStr(p, "NYC") > 0 Or InStr(p, "NEW YORK") > 0 _
        Or InStr(p, "BOS") > 0 Or InStr(p, "BOSTON") > 0 _
        Or InStr(p, "SAV") > 0 Or InStr(p, "CHS") > 0 Or InStr(p, "CHARLESTON") > 0 _
        Or InStr(p, "BAL") > 0 Or InStr(p, "MIA") > 0 Or InStr(p, "MIAMI") > 0 _
        Or InStr(p, "NORFOLK") > 0 Or InStr(p, "JAX") > 0 Or InStr(p, "JACKSONVILLE") > 0 _
        Or InStr(p, "MONTREAL") > 0 Or InStr(p, "TORONTO") > 0 Or InStr(p, "HALIFAX") > 0 Then
        GetLaneFromPOD = "EC": Exit Function
    End If

    ' GULF ports
    If InStr(p, "HOU") > 0 Or InStr(p, "HOUSTON") > 0 _
        Or InStr(p, "NOLA") > 0 Or InStr(p, "NEW ORLEANS") > 0 _
        Or InStr(p, "MOBILE") > 0 Then
        GetLaneFromPOD = "GULF": Exit Function
    End If

    GetLaneFromPOD = "*"  ' fallback
End Function
```

**Note on test case `"BALTIMORE" → "EC"`:** matches because the function
checks `InStr(p, "BAL") > 0`. Similarly `"SEATTLE" → "WC"` matches because
`InStr(p, "SEA") > 0`. These are intentional prefix matches.

---

## Patch 2: Replace `LoadMarkupForCarrier` in `erp-v14-ribbon-callbacks.bas`

**File:** `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`
**Line range:** 529–551 (inclusive, current state verified 2026-04-11)

**Find exactly:**

```vba
Private Sub LoadMarkupForCarrier(cn As String)
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0
    m_Mar45HC = 0: m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim r As Long
    For r = 2 To wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            m_Mar20GP = ERPv14Core.SL(wsM.Cells(r, 2).Value)
            m_Mar40GP = ERPv14Core.SL(wsM.Cells(r, 3).Value)
            m_Mar40HC = ERPv14Core.SL(wsM.Cells(r, 4).Value)
            m_Mar45HC = ERPv14Core.SL(wsM.Cells(r, 5).Value)
            m_Mar40NOR = ERPv14Core.SL(wsM.Cells(r, 6).Value)
            m_Mar20RF = ERPv14Core.SL(wsM.Cells(r, 7).Value)
            m_Mar40RF = ERPv14Core.SL(wsM.Cells(r, 8).Value)
            Exit Sub
        End If
    Next r
End Sub
```

**Replace with:**

```vba
Private Sub LoadMarkupForCarrier(cn As String)
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0
    m_Mar45HC = 0: m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)
    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim foundExact As Long: foundExact = 0
    Dim foundDefault As Long: foundDefault = 0
    Dim r As Long
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            Dim rowLane As String
            rowLane = UCase(Trim(wsM.Cells(r, 2).Value))
            If rowLane = lane Then
                foundExact = r
                Exit For
            ElseIf rowLane = "*" Or Len(rowLane) = 0 Then
                foundDefault = r  ' keep scanning for exact lane match
            End If
        End If
    Next r

    Dim useRow As Long
    If foundExact > 0 Then
        useRow = foundExact
    ElseIf foundDefault > 0 Then
        useRow = foundDefault
    Else
        Exit Sub
    End If

    ' Columns shifted +1 because Lane was inserted at col 2
    m_Mar20GP = ERPv14Core.SL(wsM.Cells(useRow, 3).Value)
    m_Mar40GP = ERPv14Core.SL(wsM.Cells(useRow, 4).Value)
    m_Mar40HC = ERPv14Core.SL(wsM.Cells(useRow, 5).Value)
    m_Mar45HC = ERPv14Core.SL(wsM.Cells(useRow, 6).Value)
    m_Mar40NOR = ERPv14Core.SL(wsM.Cells(useRow, 7).Value)
    m_Mar20RF = ERPv14Core.SL(wsM.Cells(useRow, 8).Value)
    m_Mar40RF = ERPv14Core.SL(wsM.Cells(useRow, 9).Value)
End Sub
```

**Behavior change:**
- Computes `lane = GetLaneFromPOD(m_POD)` before searching.
- Scans all rows for matching carrier; prefers exact `(carrier, lane)` match,
  else falls back to the `*` (default) row, else leaves margins at 0.
- Column indices shift +1 (Mar20GP now at col 3 instead of col 2) because
  Lane is inserted at col 2 by the migration script.

---

## Patch 3: Replace `SaveMarkupForCarrier` in `erp-v14-ribbon-callbacks.bas`

**File:** `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`
**Line range:** 553–573 (inclusive, current state verified 2026-04-11)

**Find exactly:**

```vba
Private Sub SaveMarkupForCarrier(cn As String)
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim r As Long
    For r = 2 To wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) Then
            wsM.Cells(r, 2).Value = m_Mar20GP
            wsM.Cells(r, 3).Value = m_Mar40GP
            wsM.Cells(r, 4).Value = m_Mar40HC
            wsM.Cells(r, 5).Value = m_Mar45HC
            wsM.Cells(r, 6).Value = m_Mar40NOR
            wsM.Cells(r, 7).Value = m_Mar20RF
            wsM.Cells(r, 8).Value = m_Mar40RF
            Exit Sub
        End If
    Next r
End Sub
```

**Replace with:**

```vba
Private Sub SaveMarkupForCarrier(cn As String)
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ThisWorkbook.Sheets("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Or cn = "" Then Exit Sub

    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)
    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim r As Long, found As Long: found = 0
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(Trim(cn)) _
           And UCase(Trim(wsM.Cells(r, 2).Value)) = lane Then
            found = r
            Exit For
        End If
    Next r
    If found = 0 Then
        found = lastRow + 1
        wsM.Cells(found, 1).Value = cn
        wsM.Cells(found, 2).Value = lane
    End If

    ' Columns shifted +1 because Lane is at col 2
    wsM.Cells(found, 3).Value = m_Mar20GP
    wsM.Cells(found, 4).Value = m_Mar40GP
    wsM.Cells(found, 5).Value = m_Mar40HC
    wsM.Cells(found, 6).Value = m_Mar45HC
    wsM.Cells(found, 7).Value = m_Mar40NOR
    wsM.Cells(found, 8).Value = m_Mar20RF
    wsM.Cells(found, 9).Value = m_Mar40RF
End Sub
```

**Behavior change:**
- Computes `lane = GetLaneFromPOD(m_POD)` before searching.
- Matches by BOTH carrier AND lane. If no exact `(carrier, lane)` row exists,
  appends a new row at `lastRow + 1` with both fields populated.
- Column indices shift +1 (same reason as Patch 2).

**Invariant:** After save, Nelson editing ONE on a WC quote never overwrites
ONE's EC row — they live on separate rows keyed by `(Carrier, Lane)`.

---

## Rollout order (main agent checklist)

1. Read the current state of `erp-v14-ribbon-callbacks.bas:529-573` and
   `erp-v14-quick-wins.bas` tail with the Read tool. Confirm the `Find`
   blocks above match byte-for-byte.
2. Apply Patch 1 (append to quick-wins.bas).
3. Apply Patch 2 (replace Load in ribbon-callbacks.bas).
4. Apply Patch 3 (replace Save in ribbon-callbacks.bas).
5. `python scripts/migrate-markup-store.py --dry-run` — verify row count
   looks sane and no surprises.
6. `python scripts/migrate-markup-store.py` — actually migrate the xlsm
   (backup is automatic). Verify that `Markup_Store` col 2 is now `Lane`
   and all existing rows have `*`.
7. `python scripts/reimport-erp-vba.py` — push the updated `.bas` files
   back into the xlsm via win32com.
8. `python -m pytest tests/integration/test_erp_lane_mapper.py -v` —
   18 parametrized cases should now pass (was skipping before the
   re-import).
9. Manual smoke: open ERP, select a WC route for ONE, edit margin; switch
   to an EC route for ONE; confirm margin is NOT the WC value (loads the
   `*` default row OR a separate EC row after first EC save).

## Rollback

If anything goes wrong after Patch 2/3:
1. Restore the xlsm from
   `D:/OneDrive/NelsonData/pricing/_backup/pre-p5-markup-migration/<ts>/ERP_Master_v14.xlsm`.
2. Revert the two `.bas` files via `git checkout` (they live under
   `D:/OneDrive/NelsonData/erp/` which is tracked).
3. Re-import the old VBA with `scripts/reimport-erp-vba.py`.
