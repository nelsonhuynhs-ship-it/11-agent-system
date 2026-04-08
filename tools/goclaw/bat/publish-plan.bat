@echo off
REM Fox Spirit wrapper: Publish aggregated plan as beautiful HTML
REM Auto-starts serve-plans.py on port 8765 if not already running.
REM
REM Usage:
REM   publish-plan.bat --title "Plan name" --input "path/to/plan.md"
REM   publish-plan.bat --title "Plan" --input plan.md --slug custom-slug

set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
set "PYTHONW=C:\Users\Nelson\anaconda3\pythonw.exe"
if not exist "%PYTHON%" set "PYTHON=python"
if not exist "%PYTHONW%" set "PYTHONW=pythonw"

set "TOOLS_DIR=D:\NELSON\2. Areas\Engine_test\tools\goclaw"

REM Auto-start serve-plans.py if port 8765 is not LISTENING.
REM Uses wmic process call create + pythonw.exe — most reliable detach on Windows
REM (survives regardless of caller context: Fox exec, cmd, powershell).
netstat -ano | findstr "LISTENING" | findstr ":8765" > nul 2>&1
if errorlevel 1 (
    wmic process call create "%PYTHONW% \"%TOOLS_DIR%\serve-plans.py\"" > nul 2>&1
    REM Give the server a moment to bind the port
    ping -n 2 127.0.0.1 > nul
)

"%PYTHON%" "%TOOLS_DIR%\publish-plan.py" %*
