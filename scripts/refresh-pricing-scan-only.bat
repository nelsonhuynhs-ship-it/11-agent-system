@echo off
REM refresh-pricing-scan-only.bat -- scan only, no import
REM Use when you want to preview pending rate emails

title Scan Pricing Emails (no import)

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"

cd /d "%REPO%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to %REPO%
    pause
    exit /b 1
)

echo ================================================================
echo   SCAN PRICING EMAILS (no import) -- %date% %time%
echo ================================================================
echo.
"%PY%" "%REPO%\Pricing_Engine\rate_importer.py" --days 7 --scan-only
echo.
pause
