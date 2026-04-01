@echo off
title Nelson Freight Bot v5
echo ========================================
echo   Nelson Freight Bot v5 - Auto Starter
echo ========================================
echo.

cd /d "%~dp0"

:loop
echo [%date% %time%] Starting bot v5...
python bot_v5.py
echo.
echo [%date% %time%] Bot stopped (exit code: %errorlevel%)
echo Restarting in 10 seconds... (Ctrl+C to stop)
timeout /t 10 /nobreak >nul
goto loop
