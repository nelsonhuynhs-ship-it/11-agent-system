@echo off
title Nelson Outlook Send Agent
cd /d "%~dp0\.."
python email_engine/outlook_send_agent.py
pause
