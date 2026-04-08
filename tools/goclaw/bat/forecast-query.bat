@echo off
REM Fox Spirit wrapper: Query forecast for a route (e.g. forecast-query USLAX 40HQ)
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\NELSON\2. Areas\Engine_test\tools\goclaw\forecast-query.py" %*
