@echo off
REM Fox Spirit wrapper: Health check Nelson Freight system
REM Call real script at absolute path, return JSON
python "D:\NELSON\2. Areas\Engine_test\tools\goclaw\check-health.py" %*
