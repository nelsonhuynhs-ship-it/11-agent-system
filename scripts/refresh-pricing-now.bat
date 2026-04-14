@echo off
REM refresh-pricing-now.bat -- one-click pricing update
REM Double-click when new rate emails arrive in Outlook:
REM   1. Scan Outlook (last 3 days) -> download attachments to incoming/
REM   2. Classify + import into Cleaned_Master_History.parquet
REM   3. Print result (X files, Y rates new)
REM After: Excel -> Operations tab -> "Refresh Rates"

title Refresh Pricing - Nelson Freight

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"

cd /d "%REPO%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to %REPO%
    pause
    exit /b 1
)

echo ================================================================
echo   REFRESH PRICING - Nelson Freight ERP
echo   %date%  %time%
echo ================================================================
echo.
echo [1/2] Scan Outlook + import to parquet (30-60 seconds)
echo       - Scan last 3 days
echo       - Download rate files to incoming/
echo       - Import into Cleaned_Master_History.parquet
echo       - Move processed files to processed/
echo.

"%PY%" "%REPO%\Pricing_Engine\rate_importer.py" --days 3
set RC=%errorlevel%

echo.
echo ================================================================
if %RC% neq 0 (
    echo [ERROR] rate_importer exit code %RC% -- see log above
) else (
    echo [OK] Parquet updated.
    echo.
    echo [2/2] NEXT -- open ERP_Master_v14.xlsm:
    echo       Operations tab ^> Rate Data ^> "Refresh Rates"
    echo       = new rates will load into Pricing Dry / Reefer sheets.
)
echo ================================================================
echo.
pause
