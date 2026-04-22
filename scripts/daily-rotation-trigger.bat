@echo off
:: daily-rotation-trigger.bat — Nelson Email Daily Rotation
:: Triggered by Windows Task Scheduler at 08:00 Mon-Fri

set PROJECT=D:\NELSON\2. Areas\Engine_test
set PYTHON=C:\Users\Nelson\anaconda3\python
set TRIGGER_SCRIPT=%PROJECT%\scripts\run_rotation_trigger.py

cd /d "%PROJECT%"

"%PYTHON%" "%TRIGGER_SCRIPT%"

if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ROTATION ERROR: exit code %ERRORLEVEL% >> "%PROJECT%\email_engine\logs\rotation_error.log"
    exit /b %ERRORLEVEL%
)

exit /b 0
