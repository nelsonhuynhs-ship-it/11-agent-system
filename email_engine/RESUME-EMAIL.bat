@echo off
:: RESUME-EMAIL.bat — Clear kill switch, resume worker
title RESUME EMAIL WORKER
color 2F

echo.
echo ======================================================
echo   RESUME EMAIL WORKER
echo ======================================================
echo.
echo [1/2] Clearing kill switch...

:: API call (preferred)
curl -s -X POST -m 3 http://localhost:8100/api/email-rate/queue/kill-clear > nul 2>&1

:: Fallback: delete flag file directly
if exist "%~dp0data\KILL_SWITCH.flag" (
    del /Q "%~dp0data\KILL_SWITCH.flag"
)

if not exist "%~dp0data\KILL_SWITCH.flag" (
    echo [OK] Kill switch CLEARED
    echo.
    echo [2/2] Worker sẽ resume pick job trong 30 giây tới
) else (
    echo [ERROR] Không xóa được flag file
)

echo.
echo ======================================================
timeout /t 5
