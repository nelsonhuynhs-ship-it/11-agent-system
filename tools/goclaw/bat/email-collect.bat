@echo off
REM Fox Spirit wrapper: Collect emails from Outlook (hourly 8:30-17:30)
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\NELSON\2. Areas\Engine_test\email_engine\core\data_collector.py" %*
