@echo off
REM Fox Spirit wrapper: Auto-campaign email orchestrator
REM Queries rates from VPS FastAPI, sends via local Outlook COM.
REM
REM Usage:
REM   auto-campaign.bat --dry-run --tier HOT,WARM_A --count 10
REM   auto-campaign.bat --auto-tier --count 100 --batches 5
REM   auto-campaign.bat --preview 3
REM   auto-campaign.bat --report-only

set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set "TOOLS_DIR=D:\NELSON\2. Areas\Engine_test\tools\goclaw"

REM Ensure env vars are set for API + Telegram
if not defined API_BASE set "API_BASE=http://14.225.207.145:8100"

"%PYTHON%" "%TOOLS_DIR%\auto-campaign.py" %*
