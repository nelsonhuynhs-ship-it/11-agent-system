@echo off
REM refresh-rates-bootstrap.bat — Async launcher for "Refresh Rates" button.
REM Same async pattern as refresh-all-bootstrap.bat but skips rate_importer
REM (Outlook scan). Just runs refresh-v14.py to pull Parquet -> Excel.

setlocal EnableExtensions EnableDelayedExpansion

set "XLSM=%~1"
set "LOGF=%~2"
set "PY=C:\Users\Nelson\anaconda3\python.exe"
set "REFRESHER=D:\OneDrive\NelsonData\erp\refresh-v14.py"

if "%XLSM%"=="" (
    echo [bootstrap-rates] ERROR: xlsm arg missing > "%LOGF%"
    exit /b 9
)
if "%LOGF%"=="" set "LOGF=%~dp1refresh_log.txt"
if not exist "%REFRESHER%" set "REFRESHER=D:\NELSON\2. Areas\Engine_test\ERP\core\refresh-v14.py"

echo ================================================================ > "%LOGF%"
echo [bootstrap-rates] %date% %time% >> "%LOGF%"
echo XLSM: %XLSM% >> "%LOGF%"
echo ================================================================ >> "%LOGF%"

set "LOCKED=1"
for /L %%i in (1,1,60) do (
    if "!LOCKED!"=="1" (
        2>nul (
            (call ) 9>>"%XLSM%"
        ) && (
            set "LOCKED=0"
            echo [bootstrap-rates] xlsm unlocked after %%i polls >> "%LOGF%"
        )
        if "!LOCKED!"=="1" (
            ping -n 1 -w 500 127.0.0.1 >nul
        )
    )
)

if "!LOCKED!"=="1" (
    echo [bootstrap-rates] ERROR: xlsm still locked after 30s >> "%LOGF%"
    start "" "%XLSM%"
    exit /b 9
)

echo [bootstrap-rates] Running refresh-v14.py... >> "%LOGF%"
"%PY%" "%REFRESHER%" "%XLSM%" >> "%LOGF%" 2>&1
set "RC=!ERRORLEVEL!"
echo [bootstrap-rates] refresh-v14 exit: !RC! >> "%LOGF%"

echo [bootstrap-rates] Reopening Excel... >> "%LOGF%"
start "" "%XLSM%"

echo [bootstrap-rates] Done %date% %time% >> "%LOGF%"
exit /b !RC!
