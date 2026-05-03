@echo off
REM Kill web_server on port 8100 and start a fresh one.
REM Nelson: double-click this after ANY edit to email_engine/*.py or email_rules.yaml.
powershell -ExecutionPolicy Bypass -File "%~dp0_restart_web_server.ps1"
echo.
echo Waiting 10s for server to come up...
timeout /t 10 /nobreak >nul
curl -s -o nul -w "web_server HTTP %%{http_code}\n" http://localhost:8100/api/version
pause
