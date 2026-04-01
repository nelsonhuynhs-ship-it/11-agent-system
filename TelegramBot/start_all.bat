@echo off
title Nelson System — All Services
echo ========================================
echo   N.E.L.S.O.N — Starting All Services
echo ========================================
echo.

REM Service 1: Dashboard API (port 8000)
echo [%time%] Starting Dashboard API on port 8000...
start "Dashboard API" cmd /k "cd /d D:\NELSON\2. Areas\PricingSystem\Engine_test\.agent\agents && python dashboard_api.py"

timeout /t 3 /nobreak >nul

REM Service 2: Nelson Freight Bot v5
echo [%time%] Starting Bot v5...
start "Nelson Bot v5" cmd /k "cd /d D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot && python bot_v5.py"

echo.
echo ========================================
echo   All services started!
echo   Dashboard: http://localhost:8000
echo   Bot: Telegram polling active
echo ========================================
echo.
echo Press any key to close this window...
pause >nul
