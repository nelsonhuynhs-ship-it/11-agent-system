@echo off
REM reimport-erp-vba.bat — wrapper for OnAction_ReloadVBA button
REM
REM Called via WMI Win32_Process.Create from VBA per SYSTEM_STANDARDS §5.1.
REM Steps:
REM   1. Poll for xlsm file lock release (Excel closed)
REM   2. Run reimport-erp-vba-modules.py
REM   3. Reopen xlsm via file association (start "")
REM
REM Args: %1 = absolute path to xlsm (optional, defaults to canonical)

setlocal enabledelayedexpansion
title Reload VBA Modules — Nelson Freight ERP v14

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"
if not exist "%PY%" set "PY=C:\Users\ADMIN\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

set "XLSM=%~1"
if "%XLSM%"=="" set "XLSM=D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"

echo ================================================================
echo   Reload VBA Modules
echo   %date%  %time%
echo ================================================================
echo.
echo XLSM:   %XLSM%
echo Python: %PY%
echo.

REM Step 1: poll file lock (wait up to 30s for Excel to release)
echo [1/3] Waiting for xlsm file lock to release...
set /a TRIES=0
:WAIT_LOCK
set /a TRIES+=1
powershell -NoProfile -Command "try { $fs = [IO.File]::Open('%XLSM%', 'Open', 'ReadWrite', 'None'); $fs.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if %TRIES% geq 30 (
        echo [ERR] xlsm still locked after 30s. Abort.
        pause
        exit /b 2
    )
    timeout /t 1 /nobreak >nul
    goto :WAIT_LOCK
)
echo   Lock released after %TRIES%s.

REM Step 2: reimport VBA
echo.
echo [2/3] Re-importing .bas modules via python...
"%PY%" "%REPO%\scripts\reimport-erp-vba-modules.py"
if errorlevel 1 (
    echo [ERR] reimport failed. See output above.
    pause
    exit /b 3
)

REM Step 3: reopen xlsm via file association
echo.
echo [3/3] Reopening xlsm...
start "" "%XLSM%"

echo.
echo ================================================================
echo   [OK] Reload complete. Excel should reopen shortly.
echo ================================================================
timeout /t 3 >nul
exit /b 0
