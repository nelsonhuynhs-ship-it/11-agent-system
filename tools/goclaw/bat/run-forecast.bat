@echo off
REM Fox Spirit wrapper: Run weekly forecast pipeline (Sunday 6:30am)
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\OneDrive\NelsonData\pricing\forecast\run_forecast.py" %*
