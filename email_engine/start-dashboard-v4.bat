@echo off
title Nelson Email Dashboard v5
cd /d "%~dp0\.."

echo.
echo ================================================
echo   NELSON EMAIL DASHBOARD v5
echo   API: http://localhost:8100
echo ================================================
echo.

:: Kill anything on port 8100
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8100.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start web_server.py on port 8100 — pythonw hides CMD entirely (2026-04-19)
:: Log redirect to file (email_engine.log already set up in code via RotatingFileHandler)
:: Emergency stop: use ARM button on dashboard OR double-click STOP-EMAIL.bat
pushd email_engine
start "" /b pythonw web_server.py
popd

:: Wait for API to start (pythonw has slower startup than python due to no console flush)
timeout /t 5 /nobreak >nul

:: Start worker — 3 threads, looping, real send mode. Hidden via pythonw.
pushd email_engine
start "" /b pythonw outlook_queue_worker.py --workers 3 --loop
popd

:: Open dashboard in browser
start "" "plans\visuals\email-dashboard-v5.html"

echo [OK] API started on :8100
echo [OK] FAST worker started (3 threads, loop)
echo [OK] Dashboard opened in browser
echo.
echo Closing this window in 3 seconds...
timeout /t 3 /nobreak >nul
