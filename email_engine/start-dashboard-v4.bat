@echo off
title Nelson Email Dashboard v6
cd /d "%~dp0\.."

echo.
echo ================================================
echo   NELSON EMAIL DASHBOARD v6
echo   API: http://localhost:8100
echo ================================================
echo.

:: Kill anything on port 8100
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8100.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Start web_server.py on port 8100 — PowerShell Start-Process -WindowStyle Hidden
:: (pushd+start /b in bat has cwd inheritance bug for pythonw). This way is reliable.
:: Logs captured to email_engine\pythonw_err.log for debug.
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'web_server.py' -WorkingDirectory '%~dp0' -RedirectStandardError '%~dp0pythonw_err.log'"

:: Wait for API to start
timeout /t 6 /nobreak >nul

:: Start worker — 3 threads, looping, real send mode. Hidden via pythonw.
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'outlook_queue_worker.py','--workers','3','--loop' -WorkingDirectory '%~dp0' -RedirectStandardError '%~dp0worker_err.log'"

:: Open dashboard in browser
start "" "plans\visuals\email-dashboard-v6.html"

echo [OK] API started on :8100
echo [OK] FAST worker started (3 threads, loop)
echo [OK] Dashboard opened in browser
echo.
echo Closing this window in 3 seconds...
timeout /t 3 /nobreak >nul
