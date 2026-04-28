

## Fact
Mirror is complete for all 3 phases (~100% written), but Phase 3 execution was killed mid-run. No E2E test has ever run.

## Critical finding
`TestE2E_FilterRestore` (case-10) calls `ERPv14Ribbon.SetSearchCarrier` etc. — **these public accessors don't exist** in `erp-v14-ribbon-callbacks.bas`. The module vars `m_SearchCarrier/POL/POD/Place` are Private with no getter/setter. This will crash at runtime.

## Items requiring action before DONE
1. **Add 4 Public Property Let/Get** for `m_SearchCarrier/POL/POD/Place` (~8 LOC in ribbon-callbacks.bas)
2. **Confirm `erp-v14-test-e2e.bas` synced to OneDrive canonical** — Python runner needs it
3. **Run E2E tests** — case-07..10 never executed, case-01..06 never regression-tested

## Suggested deploy script
Written to `reports/master-executor-audit.md` — pre-flight Excel check, timestamped backup, mirror→canonical sync, verify-erp.bat gate, reimport step.

## Risks if promoted now
case-10 crashes immediately. No test verification exists at all.

**Recommend: CONDITIONAL** — fix missing property accessors (~15 min) + run E2E tests → then promote.

---

Full report: `d:/NELSON/2. Areas/Engine_test/plans/260428-quote-img-smart-upgrade/reports/master-executor-audit.md`

AUDIT_VERDICT: NEEDS_WORK
tion before DONE

### 1. Broken API: `SetSearchCarrier/ POL/ POD/ Place` not found
**Severity: HIGH**

`TestE2E_FilterRestore` (line 224-236 in erp-v14-test-e2e.bas) calls:
```vba
ERPv14Ribbon.SetSearchCarrier seedCarrier
ERPv14Ribbon.SetSearchPOL seedPOL
...
ERPv14Ribbon.GetSearchCarrier
...
```

But `erp-v14-ribbon-callbacks.bas` has NO `SetSearch*` or `GetSearch*` public methods. The private vars are `m_SearchCarrier`, `m_SearchPOL`, `m_SearchPOD`, `m_SearchPlace` (lines 66-71). The test will fail at runtime with "Invalid procedure call".

**Fix needed in `erp-v14-ribbon-callbacks.bas`:**
Add public getter/setter wrappers:
```vba
Public Property Get SearchCarrier() As String: SearchCarrier = m_SearchCarrier: End Property
Public Property Let SearchCarrier(v As String): m_SearchCarrier = v: End Property
Public Property Get SearchPOL() As String: SearchPOL = m_SearchPOL: End Property
Public Property Let SearchPOL(v As String): m_SearchPOL = v: End Property
Public Property Get SearchPOD() As String: SearchPOD = m_SearchPOD: End Property
Public Property Let SearchPOD(v As String): m_SearchPOD = v: End Property
Public Property Get SearchPlace() As String: SearchPlace = m_SearchPlace: End Property
Public Property Let SearchPlace(v As String): m_SearchPlace = v: End Property
```
Or rename test to use direct assignment via `CacheSearchState` with pre-seeded module vars — but Phase 2 spec says "change Private to Public for these module vars" which is the simpler fix.

### 2. No `erp-v14-test-e2e.bas` in OneDrive canonical
**Severity: MEDIUM**

Phase-03 spec says add wrappers to `D:/OneDrive/NelsonData/erp/erp-v14-test-e2e.bas`. The mirror has it, but it's unclear if it was synced to canonical. If the canonical file on OneDrive does not have the Phase 3 wrappers, `e2e_runner.py` will fail.

**Verify:** Copy mirror → OneDrive canonical for erp-v14-test-e2e.bas before deploy.

### 3. `OnAction_ClearSearch` — note line 3030 says `ClearCachedState` but no arguments
**Status: OK**

Confirmed present at line 3030. ✓

### 4. Screentip — verified correct
**Status: OK**

`CustomUI_v14.xml` line 194 screentip matches spec exactly. ✓

---

## Suggested deploy script (do NOT auto-run)

```bat
@echo off
setlocal enabledelayedexpansion

set "PLAN=Quote Img Smart Upgrade 260428"
set "TIMESTAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "BACKUP_DIR=D:\OneDrive\NelsonData\erp\backups"
set "MIRROR_DIR=D:\NELSON\2. Areas\Engine_test\ERP\vba-v14-mirror"

echo [PRE-FLIGHT] Checking for open Excel...
tasklist /fi "IMAGENAME eq EXCEL.EXE" /nh | findstr /i "EXCEL.EXE" >nul
if not errorlevel 1 (
    echo.
    echo   ERROR: Excel is running. Please close ALL Excel windows first.
    echo   Use Task Manager to confirm no EXCEL.EXE processes remain.
    echo.
    echo   Cannot proceed until Excel is closed.
    echo.
    goto :fail
)

echo [STEP 1] Creating timestamped backup of canonical...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
copy /y "D:\OneDrive\NelsonData\erp\erp-v14-ribbon-callbacks.bas" "%BACKUP_DIR%\erp-v14-ribbon-callbacks.bas.bak.%TIMESTAMP%" >nul
copy /y "D:\OneDrive\NelsonData\erp\erp-v14-thisworkbook.txt" "%BACKUP_DIR%\erp-v14-thisworkbook.txt.bak.%TIMESTAMP%" >nul
copy /y "D:\OneDrive\NelsonData\erp\erp-v14-test-e2e.bas" "%BACKUP_DIR%\erp-v14-test-e2e.bas.bak.%TIMESTAMP%" >nul
copy /y "D:\OneDrive\NelsonData\erp\CustomUI_v14.xml" "%BACKUP_DIR%\CustomUI_v14.xml.bak.%TIMESTAMP%" >nul
echo   Backup done: %BACKUP_DIR%\*.bak.%TIMESTAMP%

echo [STEP 2] Syncing mirror to canonical (4 files)...
copy /y "%MIRROR_DIR%\erp-v14-ribbon-callbacks.bas" "D:\OneDrive\NelsonData\erp\erp-v14-ribbon-callbacks.bas"
copy /y "%MIRROR_DIR%\erp-v14-thisworkbook.txt" "D:\OneDrive\NelsonData\erp\erp-v14-thisworkbook.txt"
copy /y "%MIRROR_DIR%\erp-v14-test-e2e.bas" "D:\OneDrive\NelsonData\erp\erp-v14-test-e2e.bas"
copy /y "%MIRROR_DIR%\CustomUI_v14.xml" "D:\OneDrive\NelsonData\erp\CustomUI_v14.xml"
echo   Sync done.

echo [STEP 3] Running VBA static lint (verify-erp.bat)...
cd /d "D:\NELSON\2. Areas\Engine_test"
call scripts\verify-erp.bat
if errorlevel 1 (
    echo.
    echo   FAIL: verify-erp.bat returned error %errorlevel%
    echo   Rollback: copy "%BACKUP_DIR%\*.bak.%TIMESTAMP%" D:\OneDrive\NelsonData\erp\
    goto :fail
)
echo   verify-erp.bat PASSED (exit 0)

echo [STEP 4] Reimporting VBA modules...
python scripts\reimport-erp-vba-modules.py
if errorlevel 1 (
    echo.
    echo   FAIL: reimport-erp-vba-modules.py returned error %errorlevel%
    echo   Rollback required — see STEP 3 error message.
    goto :fail
)
echo   reimport-erp-vba-modules.py PASSED

echo.
echo ================================================
echo   DEPLOY SUCCESS: %PLAN%
echo   Backup: %BACKUP_DIR%\*.bak.%TIMESTAMP%
echo ================================================
exit /b 0

:fail
echo.
echo ================================================
echo   DEPLOY FAILED: %PLAN%
echo   Manual rollback required.
echo ================================================
exit /b 1
```

---

## Risks if promoted now

1. **Runtime error in case-10** — `TestE2E_FilterRestore` will crash on first call because `SetSearchCarrier` etc. do not exist. E2E run will show "ERR: 449: Argument not optional" or similar.
2. **Missing test-e2e.bas in canonical** — if OneDrive doesn't have the Phase 3 wrappers, Python runner may fail to find the macros.
3. **No actual E2E test results** — the plan was killed mid-Phase-3. No test run has been executed. case-07..10 have never been proven to PASS.

---

## Recommendation to Sếp

**Promote to canonical: CONDITIONAL**

**Rationale:** All 3 phases are fully written in the mirror. But Phase 3 execution was cut — no test run completed. One runtime bug confirmed (missing property accessors for search state). Before promote:
1. Fix the `SetSearch*`/`GetSearch*` missing methods (add Public Property Let/Get for each `m_Search*` var)
2. Confirm `erp-v14-test-e2e.bas` is synced to OneDrive canonical
3. Run `e2e_runner.py --filter case-07,case-08,case-09,case-10` — all 4 must pass + case-01..06 no regression
4. Only then copy mirror → canonical + run deploy script

These 3 steps are small (~15 min work). The code is structurally complete — just needs one API fix + test verification before going live.

---

## Summary of findings

| Item | Status |
|------|--------|
| Phase 1 code (smart dispatcher, 3 helpers, render) | COMPLETE |
| Phase 2 code (cache/restore, events, ClearCachedState) | COMPLETE |
| Phase 3 code (4 test wrappers) | COMPLETE |
| Phase 3 JSON cases (case-07..10) | COMPLETE |
| CustomUI screentip | COMPLETE |
| SetSearch*/GetSearch* public accessors | MISSING (runtime bug) |
| Phase 3 E2E test run executed | NOT DONE |
| OneDrive canonical synced (test-e2e.bas) | UNCONFIRMED |

AUDIT_VERDICT: NEEDS_WORK