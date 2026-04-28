---
phase: 2
title: Filter restore khi Sheet Deactivate/Activate
status: pending
effort_loc: ~30 VBA
owner: MM M2.7
depends_on: phase-01
---

# Phase 2 — Search filter restore on sheet switch

## Problem (Sếp's complaint)
Sếp filter Pricing với POL=HPH POD=USLAX Place=ARB → sang sheet Quotes → quay lại Pricing.
**Triệu chứng**: Bảng giá phía dưới TRỐNG, nhưng combobox vẫn dính HPH/USLAX/ARB. Phải bấm Clear Search → gõ lại từ đầu.

## Root cause
File `erp-v14-thisworkbook.txt` line 20-34 — `Workbook_SheetActivate`:
1. Line 26: `ClearAllSearchPlaceholders Sh` — clear row 1 placeholders
2. Line 32: `ResetToggleFilters` — reset SCFI/FAK/FIX/SOC toggle (per 2026-04-22 decision)

Module-level `m_SearchCarrier/POL/POD/Place` KHÔNG bị reset → text combobox vẫn còn. Nhưng filter logic đã reset toggle + applyQuickSearch chạy lại với toggle empty → ra kết quả khác → bảng "trống".

## Spec đã chốt
- Khi Sếp **rời** Pricing sheet (sang sheet khác) → cache toàn bộ search state vào module-level vars
- Khi Sếp **quay lại CÙNG** Pricing sheet (Dry→Quotes→Dry, KHÔNG phải Dry→Reefer→Dry) → restore state + re-apply filter
- Khi Sếp đổi giữa 2 Pricing sheets (Dry↔Reefer) → giữ nguyên 2026-04-22 decision (reset, fresh start)

## Implementation

### Step 1: Add cache module variables (top of `erp-v14-ribbon-callbacks.bas`)
```vba
' === Filter cache for sheet switch restore (Phase 2 - 260428) ===
Private m_CachedSheetName As String
Private m_CachedSearchCarrier As String
Private m_CachedSearchPOL As String
Private m_CachedSearchPOD As String
Private m_CachedSearchPlace As String
Private m_CachedSearchExp As String
Private m_CachedSourceFilter As String
Private m_CachedSocFilter As Boolean
Private m_HasCachedState As Boolean
```

### Step 2: Public helpers in `erp-v14-ribbon-callbacks.bas`
```vba
Public Sub CacheSearchState(sheetName As String)
    On Error Resume Next
    m_CachedSheetName = sheetName
    m_CachedSearchCarrier = m_SearchCarrier
    m_CachedSearchPOL = m_SearchPOL
    m_CachedSearchPOD = m_SearchPOD
    m_CachedSearchPlace = m_SearchPlace
    m_CachedSearchExp = m_SearchExp
    m_CachedSourceFilter = m_SourceFilter
    m_CachedSocFilter = m_SocFilter
    m_HasCachedState = True
End Sub

Public Function TryRestoreSearchState(sheetName As String) As Boolean
    On Error Resume Next
    TryRestoreSearchState = False
    If Not m_HasCachedState Then Exit Function
    If m_CachedSheetName <> sheetName Then Exit Function

    m_SearchCarrier = m_CachedSearchCarrier
    m_SearchPOL = m_CachedSearchPOL
    m_SearchPOD = m_CachedSearchPOD
    m_SearchPlace = m_CachedSearchPlace
    m_SearchExp = m_CachedSearchExp
    m_SourceFilter = m_CachedSourceFilter
    m_SocFilter = m_CachedSocFilter
    TryRestoreSearchState = True
End Function

Public Sub ClearCachedState()
    m_HasCachedState = False
End Sub
```

### Step 3: Modify ThisWorkbook events in `erp-v14-thisworkbook.txt`

**Add new event `Workbook_SheetDeactivate`:**
```vba
Private Sub Workbook_SheetDeactivate(ByVal Sh As Object)
    On Error Resume Next
    ' Cache state when leaving a Pricing sheet
    If InStr(1, Sh.Name, "Pricing", vbTextCompare) > 0 Then
        ERPv14Ribbon.CacheSearchState Sh.Name
    End If
End Sub
```

**Modify existing `Workbook_SheetActivate` (line 20-34):**
```vba
Private Sub Workbook_SheetActivate(ByVal Sh As Object)
    On Error Resume Next
    ' Only react when entering a pricing sheet
    If InStr(1, Sh.Name, "Pricing", vbTextCompare) = 0 Then Exit Sub

    ' Try restore cached state for SAME sheet (e.g. Dry→Quotes→Dry)
    Dim restored As Boolean
    restored = ERPv14Ribbon.TryRestoreSearchState(Sh.Name)

    If restored Then
        ' Restored — re-apply filter, do NOT reset toggles
        Application.EnableEvents = False
        ERPv14Core.ApplyQuickSearch
        Application.EnableEvents = True
        ' Refresh ribbon to show comboBox text + toggle state
        If Not ERPv14Ribbon.ribbonUI Is Nothing Then
            ERPv14Ribbon.ribbonUI.Invalidate
        End If
    Else
        ' Different sheet (Dry↔Reefer) — original 2026-04-22 behavior
        ERPv14Core.ClearAllSearchPlaceholders Sh
        ERPv14Ribbon.RefreshRibbonFromSheet Sh
        ERPv14Ribbon.ResetToggleFilters
    End If

    ' Clear cache after restore attempt (one-shot)
    ERPv14Ribbon.ClearCachedState
    On Error GoTo 0
End Sub
```

### Step 4: Edge cases handled
- Sếp đổi Dry → Reefer (different Pricing sheets) → cached for Dry, but Activate fires for Reefer → `TryRestoreSearchState("Pricing Reefer")` returns False (cached name = "Pricing Dry") → fallback to original reset behavior. ✓
- Sếp đổi Pricing → Quotes → Pricing (same sheet) → cache name match → restore. ✓
- Sếp open file lần đầu → no cache → fallback to original reset. ✓
- Sếp click Clear Search button → existing `OnAction_ClearSearch` zeroes `m_Search*` directly + calls `ClearCachedState` to invalidate cache. (Add 1 line at end of `OnAction_ClearSearch` line ~2980)

### Step 5: Update OnAction_ClearSearch
Add at end of existing `OnAction_ClearSearch` (line 2941-2981):
```vba
    ' Phase 2 (260428): invalidate restore cache so user's "fresh start" sticks
    ClearCachedState
```

## Acceptance (cho phase này)

| Test | Pass criteria |
|------|--------------|
| Filter Pricing Dry → sang Quotes → quay lại Dry | Bảng giá hiện y nguyên, combobox + toggle giữ |
| Filter Pricing Dry → sang Pricing Reefer | Reset (giữ nguyên decision 2026-04-22) |
| Filter Pricing Dry → bấm Clear Search → sang Quotes → quay lại Dry | Empty (cache invalidated) |
| Open file lần đầu, ApplyQuickSearch chạy lần đầu | Không crash, filter rỗng |

## Files modified
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` (add 3 helpers + module vars + 1 line in OnAction_ClearSearch)
- `D:/OneDrive/NelsonData/erp/erp-v14-thisworkbook.txt` (modify SheetActivate + add SheetDeactivate)

After edit, sync to mirror.
