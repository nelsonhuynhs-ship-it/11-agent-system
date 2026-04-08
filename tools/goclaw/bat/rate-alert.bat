@echo off
REM Fox Spirit wrapper: Rate Alert — detect price changes after import
REM Usage: rate-alert.bat [--dry-run] [--threshold-pct 10]
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\NELSON\2. Areas\Engine_test\tools\goclaw\rate-alert.py" %*
