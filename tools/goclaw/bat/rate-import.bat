@echo off
REM Fox Spirit wrapper: Import freight rates into Parquet
REM Usage: rate-import.bat [--days 1]
set "PYTHON=C:\Users\Nelson\anaconda3\python.exe"
"%PYTHON%" "D:\NELSON\2. Areas\Engine_test\Pricing_Engine\rate_importer.py" %*
