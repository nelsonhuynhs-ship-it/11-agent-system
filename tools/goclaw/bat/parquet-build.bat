@echo off
REM Fox Spirit wrapper: Build Parquet from email data (Sunday 6am)
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\NELSON\2. Areas\Engine_test\email_engine\core\data_collector.py" parquet %*
