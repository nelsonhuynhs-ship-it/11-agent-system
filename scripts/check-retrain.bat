@echo off
REM =====================================================================
REM  check-retrain.bat
REM  Nightly cron entry: evaluate retrain signals, spawn run_forecast.py
REM  if any signal trips.
REM
REM  Schedule via Task Scheduler:
REM    Daily 02:00 Asia/Saigon, run whether user logged in or not
REM
REM  Usage:
REM    check-retrain.bat           REM evaluate + spawn if needed
REM    check-retrain.bat --dry-run  REM evaluate only, no spawn
REM    check-retrain.bat --force    REM bypass signal check
REM =====================================================================
setlocal
set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%"

set PYTHON=C:\Users\Nelson\anaconda3\python.exe
if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    exit /b 2
)

"%PYTHON%" -m Pricing_Engine.forecast_retrain.check_retrain %*
set RC=%ERRORLEVEL%
endlocal & exit /b %RC%
