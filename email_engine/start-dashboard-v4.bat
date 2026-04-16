@echo off
title Nelson Email Dashboard v4
cd /d "%~dp0\.."

echo.
echo ================================================
echo   NELSON EMAIL DASHBOARD v4
echo   API: http://localhost:8100
echo ================================================
echo.

:: Kill anything on port 8100
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8100.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start web_server.py on port 8100
start "Nelson Email API :8100" /min cmd /c "cd /d email_engine && python web_server.py 2>&1"

:: Wait for API to start
timeout /t 3 /nobreak >nul

:: Start FAST worker (Phase 01) — 3 threads, looping, real send mode.
:: Drop email_engine\data\KILL_SWITCH.flag to pause sends.
:: Add --dry-run to the line below to test without sending.
start "Nelson Worker" /min cmd /c "cd /d email_engine && python outlook_queue_worker.py --workers 3 --loop 2>&1"

:: Open dashboard in browser
start "" "plans\visuals\email-dashboard-v4.html"

echo [OK] API started on :8100
echo [OK] FAST worker started (3 threads, loop)
echo [OK] Dashboard opened in browser
echo.
echo Closing this window in 3 seconds...
timeout /t 3 /nobreak >nul
