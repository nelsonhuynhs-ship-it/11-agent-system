@echo off
REM ===============================================================
REM  refresh-pricing-now.bat — one-click pricing update
REM  Khi có email rate mới về Outlook, double-click file này để:
REM    1. Scan Outlook (last 3 days) -> download attachments vào incoming/
REM    2. Classify + import vào Cleaned_Master_History.parquet
REM    3. In ra kết quả (X files, Y rates new)
REM  Sau đó: Excel -> Operations tab -> "Refresh Rates"
REM ===============================================================

chcp 65001 >nul 2>&1
title Refresh Pricing - Nelson Freight

set REPO=D:\NELSON\2. Areas\Engine_test
set PY=C:\Users\Nelson\anaconda3\python.exe

cd /d "%REPO%" || (echo [ERROR] Cannot cd to %REPO% & pause & exit /b 1)

echo ================================================================
echo   REFRESH PRICING — Nelson Freight ERP
echo   %date%  %time%
echo ================================================================
echo.
echo [1/2] Scan Outlook + import vao parquet (thoi gian: ~30-60 giay)
echo       - Scan 3 ngay gan nhat
echo       - Download file rate moi vao incoming/
echo       - Import vao Cleaned_Master_History.parquet
echo       - Move file xong vao processed/
echo.

"%PY%" "%REPO%\Pricing_Engine\rate_importer.py" --days 3
set RC=%errorlevel%

echo.
echo ================================================================
if %RC% neq 0 (
    echo [ERROR] rate_importer exit code %RC% — xem log tren
) else (
    echo [OK] Parquet da cap nhat.
    echo.
    echo [2/2] BUOC CUOI — mo ERP_Master_v14.xlsm:
    echo       Operations tab ^> Rate Data ^> "Refresh Rates"
    echo       = gia moi se ve Pricing Dry / Reefer sheets.
)
echo ================================================================
echo.
pause
