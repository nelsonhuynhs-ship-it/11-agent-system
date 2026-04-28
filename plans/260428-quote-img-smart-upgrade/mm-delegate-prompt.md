# MM M2.7 — Execute Plan: Quote Img Smart Upgrade

You are MiniMax M2.7 working as Nelson Freight ERP implementation engineer. Opus brain has done the spec + design. Your job: implement + test until E2E green.

## Working directory
```
d:/NELSON/2. Areas/Engine_test/
```
All relative paths below are from this working directory.

## Plan to execute (READ FULLY before starting)
1. `plans/260428-quote-img-smart-upgrade/plan.md` — overview + success criteria
2. `plans/260428-quote-img-smart-upgrade/phase-01-quote-img-smart.md` — VBA modify (`OnAction_QuoteImage` smart dispatcher)
3. `plans/260428-quote-img-smart-upgrade/phase-02-filter-restore.md` — VBA add (sheet deactivate/activate filter cache)
4. `plans/260428-quote-img-smart-upgrade/phase-03-e2e-test.md` — E2E test cases + run gates

## Critical rules (do NOT violate)

1. **Edit canonical FIRST** in `D:/OneDrive/NelsonData/erp/` (or wsl-mounted equivalent). Mirror in `Engine_test/ERP/vba-v14-mirror/` is sync-target only.
2. **Backup before edit** — copy each .bas file to `<file>.bak.260428` before any modification.
3. **NO new ribbon buttons** — Sếp explicit reject. Modify existing `btnQuoteImage` only.
4. **Keep label "Quote Img"** unchanged. Update screentip only.
5. **Backward compat preserved** — explicit selection ≥row 2 with QuoteID still wins over smart auto-detect.
6. **Apply VBA standards** per `docs/ERP_V14_VBA_STANDARDS.md` and `docs/vba-gotchas.md`:
   - WMI launch pattern (not Shell)
   - On Error GoTo for new public subs
   - ChrW for Unicode
   - No `wb.save()` without preserve_ribbon
7. **NO commit** — Sếp will commit manually after smoke test.

## Execution order

### Phase 1 (target: ~15 min)
- Edit `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`:
  - Backup → `<file>.bak.260428`
  - Refactor `OnAction_QuoteImage` (line ~3224) into:
    - `OnAction_QuoteImage` (smart dispatcher — public)
    - `QuoteImage_RenderRows` (private — existing render logic, now takes rowNums + count as params)
    - `QuoteImage_CollectFromSelection` (private)
    - `QuoteImage_CollectLatestGroup` (private — new logic: walk down from row 5, match QuoteGroupID col 43, fallback customer+date)
- Edit `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml`:
  - Update screentip on `btnQuoteImage` (label + onAction unchanged)
- Sync mirror:
  ```bash
  cp "D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas" "ERP/vba-v14-mirror/"
  cp "D:/OneDrive/NelsonData/erp/CustomUI_v14.xml" "ERP/vba-v14-mirror/"
  ```

### Phase 2 (target: ~10 min)
- Edit `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`:
  - Add module-level cache vars (top of file with other Private declarations)
  - Add 3 public helpers: `CacheSearchState`, `TryRestoreSearchState`, `ClearCachedState`
  - Append 1 line to `OnAction_ClearSearch` (line ~2980): `ClearCachedState`
  - **CRITICAL**: change `m_SearchCarrier`, `m_SearchPOL`, `m_SearchPOD`, `m_SearchPlace` from Private to Public — required for E2E test wrapper to seed state. Document this in code comment with link to phase-03 spec.
- Edit `D:/OneDrive/NelsonData/erp/erp-v14-thisworkbook.txt`:
  - Add new `Workbook_SheetDeactivate` event
  - Modify `Workbook_SheetActivate` per spec (try restore first, fallback to original reset)
- Sync mirror

### Phase 3 (target: ~15 min)
- Append 4 wrapper macros to `D:/OneDrive/NelsonData/erp/erp-v14-test-e2e.bas`:
  - `TestE2E_QuoteImg_FromPricing`
  - `TestE2E_QuoteImg_LatestGroupCount`
  - `TestE2E_QuoteImg_ExplicitSelection`
  - `TestE2E_FilterRestore`
- Append 4 cases to `plans/260426-erp-e2e-test-automation/e2e_test_cases.json`:
  - case-07 through case-10
- Sync mirror for `erp-v14-test-e2e.bas`

### Verify gates (sequential — STOP on first fail)
```bash
cd "d:/NELSON/2. Areas/Engine_test"

# Gate 1: Static lint
scripts/verify-erp.bat
# Expect: exit 0

# Gate 2: Reimport modules to live workbook
python scripts/reimport-erp-vba-modules.py
# Expect: success message

# Gate 3: Existing tests still pass (no regression)
python plans/260426-erp-e2e-test-automation/e2e_runner.py \
    --cases plans/260426-erp-e2e-test-automation/e2e_test_cases.json
# Expect: case-01..06 PASS + case-07..10 PASS = 10/10
```

## When ANY gate fails
1. Read error output carefully
2. Fix root cause (not symptom — apply systematic-debugging skill)
3. Re-run gate
4. Max 3 fix attempts per gate. If still fail → STOP, write detailed failure report, exit.

## Output (write before exit)

Write `plans/260428-quote-img-smart-upgrade/reports/phase-03-completion.md`:
```markdown
# Phase 3 — Completion Report

**Status:** PASS | PARTIAL | FAIL
**Date:** 2026-04-28
**Duration:** Xm

## Files modified
| File | Type | LOC ± | Backup |
|------|------|-------|--------|
| ... | ... | ... | ... |

## Gate results
| Gate | Result | Detail |
|------|--------|--------|
| verify-erp.bat | PASS/FAIL | ... |
| reimport | PASS/FAIL | ... |
| e2e (10 cases) | X/10 PASS | breakdown |

## Manual smoke test for Sếp
1. ... (concrete steps)
2. ...

## Rollback (if needed)
```bash
cp <file>.bak.260428 <file>  # for each backed up file
python scripts/reimport-erp-vba-modules.py
```

## Next steps for Opus
- ...
```

Write `plans/260428-quote-img-smart-upgrade/reports/smoke-test-guide.md` for Sếp:
- Step-by-step user-facing test (in Vietnamese, plain language, no VBA jargon)
- "Anh mở ERP, làm A, B, C → kết quả mong đợi: ảnh quote nhóm hiện ra"
- 5 scenarios from the HTML spec at `D:/OneDrive/NelsonData/reports/2026-04-28/quote-workflow-upgrade.html`

## Final report convention
When done, last line of stdout MUST be exactly:
```
PHASE_RESULT: PASS|PARTIAL|FAIL
```
Opus parses this to know status without reading entire output.

## Permissions
- You may write/edit any file in `D:/OneDrive/NelsonData/erp/` and `Engine_test/ERP/vba-v14-mirror/` and `Engine_test/plans/260428-*/` and `Engine_test/plans/260426-*/e2e_test_cases.json`.
- You may run `scripts/verify-erp.bat`, `python scripts/reimport-erp-vba-modules.py`, `python plans/260426-erp-e2e-test-automation/e2e_runner.py`.
- DO NOT touch ERP_Master_v14.xlsm directly (only via reimport script).
- DO NOT git commit/push.
- DO NOT modify any file outside the scope listed above.

GO.
