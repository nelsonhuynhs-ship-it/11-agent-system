@echo off
REM Fox Spirit wrapper: Query freight rates from DuckDB/Parquet
REM Usage: query-rate.bat --pol HPH --pod LAX --container 40HQ
python "D:\NELSON\2. Areas\Engine_test\tools\goclaw\query-rate.py" %*
