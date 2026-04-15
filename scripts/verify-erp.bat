@echo off
REM verify-erp.bat -- regression gate for ERP v4
REM Exit 0 = all checks pass. Non-zero = regression detected.
REM Called: before commit, after any ERP edit, by CI.

setlocal
title Verify ERP v4 - Nelson Freight

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"
set "ERP=D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"

cd /d "%REPO%"

echo ================================================================
echo   VERIFY ERP v4 -- Regression + Sanity Check
echo   %date%  %time%
echo ================================================================
echo.

echo [1/5] Close any running Excel...
powershell -NoProfile -Command "Get-Process EXCEL -EA SilentlyContinue | Stop-Process -Force" 2>nul
powershell -NoProfile -Command "Start-Sleep -Seconds 2" >nul

echo.
echo [2/5] XLSM structure (customUI14.xml + vbaProject.bin)...
"%PY%" "%REPO%\scripts\check_zip_structure.py" "%ERP%"
if errorlevel 1 goto :ERR

echo.
echo [3/5] VBA modules (required present, no duplicates)...
"%PY%" "%REPO%\scripts\check_vba_modules.py" "%ERP%"
if errorlevel 1 goto :ERR

echo.
echo [4/5] Python core imports (COL, ribbon_guard, email_builder)...
"%PY%" "%REPO%\scripts\check_imports.py"
if errorlevel 1 goto :ERR

echo.
echo [5/5] Core pytest (ribbon_guard + schema + email_builder)...
"%PY%" -m pytest tests\test_ribbon_guard.py tests\test_active_jobs_schema.py tests\test_email_builder.py -q --tb=line
if errorlevel 1 goto :ERR

echo.
echo ================================================================
echo   [OK] ALL CHECKS PASSED -- safe to test in Excel
echo ================================================================
echo.
exit /b 0

:ERR
echo.
echo ================================================================
echo   [FAIL] One or more checks failed -- see output above
echo   Do NOT commit until fixed.
echo ================================================================
exit /b 1
