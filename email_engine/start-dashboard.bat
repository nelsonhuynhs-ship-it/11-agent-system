@echo off
title Nelson Email Dashboard
cd /d "%~dp0\.."

echo.
echo ================================================
echo   NELSON EMAIL DASHBOARD
echo   URL: http://localhost:8100/
echo   Version shown in UI header (read from /api/version)
echo ================================================
echo.

:: Kill anything on port 8100
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8100.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: REM Kill any existing outlook_queue_worker.py processes (prevents stacking) — DISABLED 2026-04-30 (graph-only migration)
:: powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*outlook_queue_worker*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Start web_server.py on port 8100 (hidden via pythonw)
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'web_server.py' -WorkingDirectory '%~dp0' -RedirectStandardError '%~dp0pythonw_err.log'"

:: Wait for API to start (poll /api/version up to 20s)
set /a tries=0
:wait_api
timeout /t 1 /nobreak >nul
set /a tries+=1
curl -s -o nul -w "%%{http_code}" http://localhost:8100/api/version 2>nul | findstr "200" >nul
if %errorlevel%==0 goto api_ready
if %tries% geq 20 goto api_timeout
goto wait_api

:api_timeout
echo [WARN] API did not respond in 20s - check pythonw_err.log
goto skip_worker

:api_ready
echo [OK] API ready on :8100

:: Outlook COM queue worker disabled 2026-04-27 — Smart Send now uses Graph API
:: directly via background thread (see web_server.py _do_send_built_emails).
:: To re-enable for Outlook COM rollback: set EMAIL_SEND_BACKEND=outlook in .env
:: AND uncomment the line below.
::powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'outlook_queue_worker.py','--workers','3','--loop' -WorkingDirectory '%~dp0' -RedirectStandardError '%~dp0worker_err.log'"
echo [INFO] Outlook queue worker SKIPPED (Graph API backend, see .env)

:skip_worker
:: Open dashboard via URL (NEVER file:// - API calls need http://)
start "" "http://localhost:8100/"
echo [OK] Dashboard opened in browser
echo.
echo Closing this window in 3 seconds...
timeout /t 3 /nobreak >nul
