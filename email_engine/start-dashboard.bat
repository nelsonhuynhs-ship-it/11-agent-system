@echo off
title Nelson Email Dashboard v2
cd /d "%~dp0"

:: Kill old server if running on 8231
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8231.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start server + open browser
echo.
echo ================================================
echo   NELSON EMAIL DASHBOARD v2
echo   Starting on http://localhost:8231
echo ================================================
echo.

start "" http://localhost:8231
python web_server.py
pause
