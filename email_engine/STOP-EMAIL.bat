@echo off
:: STOP-EMAIL.bat — Emergency kill switch for Nelson Email Worker
:: Double-click anywhere (Desktop shortcut) to pause worker IMMEDIATELY.
:: Worker will stop picking new jobs from queue within 30s.
:: In-flight email (already handed to Outlook Outbox) cannot be recalled.
::
:: Resume: open dashboard → click green "DISARM" button
::   OR double-click RESUME-EMAIL.bat
::   OR manually delete email_engine\data\KILL_SWITCH.flag

title STOP EMAIL WORKER
color 4F

echo.
echo ======================================================
echo   STOP EMAIL WORKER
echo ======================================================
echo.
echo [1/2] Engaging kill switch...

:: Use curl to call API (if API alive) — instant, structured response
curl -s -X POST -m 3 http://localhost:8100/api/email-rate/queue/kill > nul 2>&1

:: Fallback: directly create flag file (works even if web_server dead)
echo engaged_at=%date% %time% > "%~dp0data\KILL_SWITCH.flag"

if exist "%~dp0data\KILL_SWITCH.flag" (
    echo [OK] Kill switch ARMED
    echo.
    echo [2/2] Checking worker response...
    timeout /t 2 /nobreak >nul
    echo.
    echo      Worker sẽ dừng pick job mới trong 30 giây.
    echo      Email đã trong Outlook Outbox vẫn gửi tiếp.
    echo.
    echo      Để resume: mở dashboard -^> click "DISARM"
    echo                 HOẶC xóa file: data\KILL_SWITCH.flag
) else (
    echo [ERROR] Không tạo được flag file
    echo         Kiểm tra permission hoặc path
)

echo.
echo ======================================================
timeout /t 10
