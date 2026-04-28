

Now I have enough data. Let me write the full review.

---

# Code Review Report — Quote Img Smart Upgrade

## Summary
Total issues: 1 critical (block promote), 2 medium, 0 low

## Verdict
**APPROVE_WITH_FIXES** — Code is logically sound and spec-compliant for core functionality. Phase 1 + Phase 2 core logic is correct. However, there is 1 compile-time issue in the Phase 3 test wrappers that will prevent `e2e_runner.py` from running.

## Score
**7.5/10** — Core implementation correct, test wrappers need fixes before E2E can run.

---

## Critical issues (block promote)

### 1. Test wrappers call non-existent public setters — runtime error

- File: `erp-v14-test-e2e.bas:224-227`
- Description: `TestE2E_FilterRestore` calls `ERPv14Ribbon.SetSearchCarrier`, `SetSearchPOL`, `SetSearchPOD`, `SetSearchPlace` — but no such Public Sub exists in `erp-v14-ribbon-callbacks.bas`. The module has `m_SearchCarrier` etc. as `Private`. This will cause runtime error 445 (object doesn't support this method) or compile error.
- Current code:
  ```vba
  ERPv14Ribbon.SetSearchCarrier seedCarrier      ' ← DOES NOT EXIST
  ERPv14Ribbon.SetSearchPOL seedPOL              ' ← DOES NOT EXIST
  ERPv14Ribbon.SetSearchPOD seedPOD              ' ← DOES NOT EXIST
  ERPv14Ribbon.SetSearchPlace seedPlace          ' ← DOES NOT EXIST
  ```
- Suggested fix — add missing public setters at line ~109 (before first Sub), matching the getter pattern already present in the module:
  ```vba
  Public Sub SetSearchCarrier(text As String): m_SearchCarrier = text: End Sub
  Public Sub SetSearchPOL(text As String): m_SearchPOL = text: End Sub
  Public Sub SetSearchPOD(text As String): m_SearchPOD = text: End Sub
  Public Sub SetSearchPlace(text As String): m_SearchPlace = text: End Sub
  ```
  Alternative: change test wrapper to use `CacheSearchState` only (seed state via the existing module-level Private vars through a test helper, but this is not possible without setters).

---

## Minor issues (fix before merge)

### 2. `m_SearchExp` is cached but `m_ExpPreset` is not

- File: `erp-v14-ribbon-callbacks.bas:117` (CacheSearchState)
- Description: `m_SearchExp` is cached but `m_ExpPreset` (the current Exp dropdown selection, line 98) is NOT cached/restored. When user filters by expiry preset on Dry, switches to Quotes, returns to Dry — the "Active only / This week / This month / All" state is lost. This is arguably out of spec (spec only says `m_SearchExp`, not `m_ExpPreset`), but it creates a subtle UX inconsistency.
- Suggested fix: add to `CacheSearchState`:
  ```vba
  m_CachedExpPreset = m_ExpPreset
  ```
  And to `TryRestoreSearchState`:
  ```vba
  m_ExpPreset = m_CachedExpPreset
  ```
  And add the declaration at line ~102:
  ```vba
  Private m_CachedExpPreset As String
  ```

### 3. `m_SearchNote` is not cached (inconsistency with the 7-state variables)

- File: `erp-v14-ribbon-callbacks.bas:71,112`
- Description: `m_SearchNote` (line 71, search note combobox) exists as a module-level Private var but is NOT included in `CacheSearchState`. The other 6 search state vars (Carrier, POL, POD, Place, Exp, SourceFilter, SocFilter) are all cached. `m_SearchNote` should be included for completeness — otherwise a user who types a note filter, switches sheets, returns — note text is silently lost.
- Suggested fix: Add `m_CachedSearchNote` to the cache block (lines 97-105) and include it in `CacheSearchState` / `TryRestoreSearchState`.

---

## Style/nitpicks (optional)

### 4. `QuoteImage_CollectLatestGroup` uses `IsEmpty()` check then `Trim()` check

- File: `erp-v14-ribbon-callbacks.bas:3379-3381`
- Description: The check `IsEmpty(wsQ.Cells(startRow, 1).Value) Or Trim(...) = ""` covers both cases but the `IsEmpty` check is slightly misleading — a cell with an empty string `""` is not technically `IsEmpty`; `IsEmpty` returns True only for truly uninitialized Variant cells. In practice the code works because `Trim(CStr(...)) = ""` catches the empty string case, and the spec intent is clear.
- Suggested fix (optional): simplify to `Trim(CStr(wsQ.Cells(startRow, 1).Value)) = ""` — more correct for Excel cell semantics and fewer branches.

---

## Spec compliance

| Check | Result | Detail |
|-------|--------|--------|
| **Phase 1 spec match** | ✅ YES | Smart dispatcher with `useSmartMode` flag, `QuoteImage_CollectFromSelection` (explicit selection, Private), `QuoteImage_CollectLatestGroup` (smart, Private), `QuoteImage_RenderRows` (renderer, Private) — all match phase-01 spec. |
| **Phase 2 spec match** | ✅ YES | `CacheSearchState`, `TryRestoreSearchState`, `ClearCachedState` all implemented as public helpers. Module-level cache vars are all Private (spec: "keep m_Search* Private"). `OnAction_ClearSearch` calls `ClearCachedState` at line 3030. `Workbook_SheetDeactivate` caches on leave. `Workbook_SheetActivate` tries restore first, falls back to original 2026-04-22 reset for Dry↔Reefer. ✅ |
| **CustomUI screentip-only change** | ✅ YES | `CustomUI_v14.xml` line 192-194: only `screentip` attribute updated, `label`, `onAction`, `id`, `imageMso`, `size` all unchanged. ✅ |
| **Test wrappers complete (4 functions)** | ❌ NO — BROKEN | `TestE2E_QuoteImg_FromPricing`, `TestE2E_QuoteImg_LatestGroupCount`, `TestE2E_QuoteImg_ExplicitSelection` — these 3 only call existing public subs/functions and read-only operations → should work. `TestE2E_FilterRestore` calls 4 non-existent public setters → broken. |

---

## Scope safety check

| Item | Status | Notes |
|------|--------|-------|
| `m_SearchCarrier/POL/POD/Place/Exp` | ✅ Private | All remained Private. New cache vars `m_Cached*` are also Private. No Private→Public upgrades. |
| New public helpers | ✅ Correct | `CacheSearchState`, `TryRestoreSearchState`, `ClearCachedState` — all properly Public with `On Error Resume Next` guard. |
| Existing Public subs unchanged | ✅ Verified | All existing Public subs (OnAction_*, GetText_*, GetPressed_*, etc.) unchanged. |

---

## DOMAIN-ERP / Constants usage

| Check | Status | Notes |
|-------|--------|-------|
| Col 43 = QuoteGroupID | ✅ Used | Lines 3385, 3396 in `QuoteImage_CollectLatestGroup` — hardcoded `43` (not constant, but col 43 is QuoteGroupID per DOMAIN-ERP) |
| Row 5 = QUOTES_DATA_START | ✅ Used | Line 3378: `startRow = QUOTES_DATA_START` |
| Col 3 = Customer | ✅ Used | Line 3383, 3394: `Q_CUST As Integer = 3` (local const in `QuoteImage_RenderRows`) |
| Col 2 = Date | ✅ Used | Line 3384, 3395: `Format(wsQ.Cells(startRow, 2).Value, "yyyy-mm-dd")` |
| QUOTES_DATA_START used vs hardcode 5 | ✅ Used | Line 3378 uses constant, not literal `5` |

---

## Backward compat verification

| Scenario | Expected behavior | Code result |
|----------|-------------------|-------------|
| Quotes sheet, select N rows → QuoteImage | Render those N rows | ✅ `QuoteImage_CollectFromSelection` called when `hasRealSelection = True` |
| Quotes sheet, no selection → QuoteImage | Auto-pick latest group | ✅ `QuoteImage_CollectLatestGroup` called via `useSmartMode` |
| Pricing sheet → QuoteImage | Jump to Quotes + render group | ✅ `useSmartMode = True` from start, `wsQ.Activate` at line 3328 |
| No quotes today | MsgBox, no crash | ✅ `rowCount = 0` check at line 3320-3324 |
| Empty Quotes sheet | Exit Sub early | ✅ `IsEmpty/Trim empty` check at line 3379-3381 |
| Multi-area Ctrl+click selection | Collect all rows, dedup | ✅ Nested For loops over `Selection.Areas` at line 3348-3365 |
| QuoteGroupID empty | Fall back to customer+date | ✅ `ElseIf cust = refCust And dt = refDate` at line 3401-3402 |

---

## vba-gotchas verification

| Gotcha | Status | Notes |
|--------|--------|-------|
| #1 Chr→ChrW for Unicode | ✅ Not applicable | No `Chr()` calls in changed code |
| #2 Line continuation `_X` trap | ✅ Not applicable | No `& _` continuations with `_X` start in changed lines |
| #4 Break on All Errors | ✅ N/A | Not code-changeable in review |
| #6 `wb.save()` strips customUI | ✅ Not applicable | No Python openpyxl save in changed VBA code |
| #11 Declarations after first Sub | ✅ Pass | All new declarations (`m_Cached*`, `m_HasCachedState`) at module top, before any Sub/Function. Cache helpers (Public Sub) appear at correct position. |

---

## Final recommendation

- **Ready to promote canonical:** NO
- **Reason:** Phase 3 test wrapper `TestE2E_FilterRestore` calls 4 non-existent public setters — this will runtime-error before any E2E test can execute.
- **Fixes needed before re-review:**
  1. Add `SetSearchCarrier`, `SetSearchPOL`, `SetSearchPOD`, `SetSearchPlace` public subs to `erp-v14-ribbon-callbacks.bas` (4 lines total, one-liner subs).
  2. Optionally add `m_CachedExpPreset` / `m_CachedSearchNote` cache entries for robustness (minor).

After fix #1, re-run `verify-erp.bat` + `e2e_runner.py` to confirm green.

---

REVIEW_VERDICT: APPROVE_WITH_FIXES
