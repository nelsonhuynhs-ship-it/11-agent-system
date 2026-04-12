@echo off
REM =====================================================================
REM  run-erp-tests.bat
REM  Headless xlwings + pytest runner for ERP_Master_v14.xlsm.
REM
REM  Usage:
REM    run-erp-tests.bat              REM all integration tests
REM    run-erp-tests.bat -k smoke     REM only smoke tests
REM    run-erp-tests.bat -m slow      REM only slow-marked tests
REM
REM  Exit code: 0 = pass, 1+ = failures
REM =====================================================================
setlocal
set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%"

set PYTHON=C:\Users\Nelson\anaconda3\python.exe
if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    exit /b 2
)

"%PYTHON%" -m pytest tests/integration %*
set RC=%ERRORLEVEL%
endlocal & exit /b %RC%
