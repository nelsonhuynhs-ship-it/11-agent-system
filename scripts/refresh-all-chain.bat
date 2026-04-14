@echo off
REM refresh-all-chain.bat -- Internal helper called by "Refresh All" ribbon button.
REM Runs rate_importer --import-pending, then (optionally) refresh-v14.py.
REM
REM Usage:
REM   refresh-all-chain.bat <xlsm_path> [log_path]
REM Exit:
REM   0 = both steps succeeded
REM   1 = step 1 (import) failed
REM   2 = step 2 (refresh-v14) failed

setlocal

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"
set "XLSM=%~1"
set "LOGF=%~2"
if "%LOGF%"=="" set "LOGF=%~dp1refresh_all_log.txt"

echo ================================================================ > "%LOGF%"
echo [refresh-all-chain] %date% %time%                                 >> "%LOGF%"
echo XLSM: %XLSM%                                                      >> "%LOGF%"
echo ================================================================ >> "%LOGF%"

REM Step 1: rate_importer --import-pending
echo.                                                                  >> "%LOGF%"
echo [STEP 1] rate_importer --import-pending                           >> "%LOGF%"
"%PY%" "%REPO%\Pricing_Engine\rate_importer.py" --import-pending >> "%LOGF%" 2>&1
if errorlevel 1 (
    echo [ERROR] Step 1 failed  >> "%LOGF%"
    exit /b 1
)

REM Step 2: refresh-v14.py (only if xlsm path provided — skip if chain called without xlsm)
if "%XLSM%"=="" (
    echo [SKIP] No xlsm path — skipping refresh-v14  >> "%LOGF%"
    exit /b 0
)

echo.                                                                  >> "%LOGF%"
echo [STEP 2] refresh-v14.py "%XLSM%"                                  >> "%LOGF%"

set "REFRESHER=D:\OneDrive\NelsonData\erp\refresh-v14.py"
if not exist "%REFRESHER%" set "REFRESHER=%REPO%\ERP\core\refresh-v14.py"

"%PY%" "%REFRESHER%" "%XLSM%" >> "%LOGF%" 2>&1
if errorlevel 1 (
    echo [ERROR] Step 2 failed  >> "%LOGF%"
    exit /b 2
)

echo.                                                                  >> "%LOGF%"
echo [refresh-all-chain] DONE                                          >> "%LOGF%"
exit /b 0
