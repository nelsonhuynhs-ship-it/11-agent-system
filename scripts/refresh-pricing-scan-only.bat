@echo off
REM refresh-pricing-scan-only.bat — chi scan, khong import
REM Dung khi Nelson muon xem co email rate moi hay khong ma chua muon import

chcp 65001 >nul 2>&1
title Scan Pricing Emails (no import)

set REPO=D:\NELSON\2. Areas\Engine_test
set PY=C:\Users\Nelson\anaconda3\python.exe

cd /d "%REPO%" || (echo [ERROR] Cannot cd & pause & exit /b 1)

echo ================================================================
echo   SCAN PRICING EMAILS (no import) — %date% %time%
echo ================================================================
echo.
"%PY%" "%REPO%\Pricing_Engine\rate_importer.py" --days 7 --scan-only
echo.
pause
