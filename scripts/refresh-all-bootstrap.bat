@echo off
REM refresh-all-bootstrap.bat — Async launcher for Refresh All
REM
REM Problem: VBA `wsh.Run("cmd /c chain.bat", 0, True)` AFTER
REM `ThisWorkbook.Close` never executes because closing the workbook
REM terminates the VBA macro mid-flight (Excel docs: closing host wb
REM forcibly aborts its own running code).
REM
REM Solution: VBA calls this bootstrap ASYNC via `Shell ..., vbHide`
REM BEFORE `ThisWorkbook.Close`. Bootstrap waits for Excel to release
REM the xlsm file lock, then runs the chain, then reopens Excel.
REM
REM Usage (from VBA):
REM   Shell """scripts\refresh-all-bootstrap.bat"" ""<xlsm>"" ""<log>""", vbHide
REM   ThisWorkbook.Save
REM   ThisWorkbook.Close SaveChanges:=False
REM   Exit Sub
REM
REM Exit codes:
REM   0 = chain succeeded, Excel reopened
REM   1 = chain step 1 (rate_importer) failed
REM   2 = chain step 2 (refresh-v14) failed
REM   9 = xlsm still locked after 30s — refresh skipped

setlocal EnableExtensions EnableDelayedExpansion

set "XLSM=%~1"
set "LOGF=%~2"
set "REPO=D:\NELSON\2. Areas\Engine_test"

if "%XLSM%"=="" (
    echo [bootstrap] ERROR: xlsm arg missing > "%LOGF%"
    exit /b 9
)
if "%LOGF%"=="" set "LOGF=%~dp1refresh_all_log.txt"

echo ================================================================ > "%LOGF%"
echo [bootstrap] %date% %time% >> "%LOGF%"
echo XLSM: %XLSM% >> "%LOGF%"
echo ================================================================ >> "%LOGF%"

REM Wait for Excel to release file lock (up to 30 seconds, poll every 500ms).
REM Uses the "try to open for append" trick: if the file is exclusively locked
REM by Excel, the redirect fails silently; when Excel closes, it succeeds.
set "LOCKED=1"
for /L %%i in (1,1,60) do (
    if "!LOCKED!"=="1" (
        2>nul (
            (call ) 9>>"%XLSM%"
        ) && (
            set "LOCKED=0"
            echo [bootstrap] xlsm unlocked after %%i polls ^(~500ms each^) >> "%LOGF%"
        )
        if "!LOCKED!"=="1" (
            REM Sleep ~500ms without installing extra tooling
            ping -n 1 -w 500 127.0.0.1 >nul
        )
    )
)

if "!LOCKED!"=="1" (
    echo [bootstrap] ERROR: xlsm still locked after 30s — aborting >> "%LOGF%"
    REM Best-effort: try to reopen anyway so user isn't left with no Excel window
    start "" "%XLSM%"
    exit /b 9
)

echo [bootstrap] Running chain... >> "%LOGF%"
call "%REPO%\scripts\refresh-all-chain.bat" "%XLSM%" "%LOGF%"
set "CHAINRC=!ERRORLEVEL!"
echo [bootstrap] Chain exit code: !CHAINRC! >> "%LOGF%"

echo [bootstrap] Reopening Excel: %XLSM% >> "%LOGF%"
start "" "%XLSM%"

echo [bootstrap] Done %date% %time% >> "%LOGF%"
exit /b !CHAINRC!
