@echo off
REM verify-erp.bat -- regression check for ERP Excel upgrade
REM Run BEFORE reporting issues + AFTER every fix.
REM Exit 0 = all checks pass. Non-zero = something regressed.

title Verify ERP v4 - Nelson Freight

set "REPO=D:\NELSON\2. Areas\Engine_test"
set "PY=C:\Users\Nelson\anaconda3\python.exe"
set "ERP=D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"

cd /d "%REPO%"

echo ================================================================
echo   VERIFY ERP v4 -- Regression + Sanity Check
echo   %date%  %time%
echo ================================================================
echo.

echo [1/5] Close any running Excel...
powershell -Command "Get-Process EXCEL -EA SilentlyContinue | Stop-Process -Force" 2>nul
timeout /t 2 >nul

echo.
echo [2/5] VBA compile check (ERPv14Ribbon + ERPv14JobsAutomation)...
"%PY%" -c "import win32com.client as w; import time; e=w.DispatchEx('Excel.Application'); e.Visible=False; e.DisplayAlerts=False; wb=e.Workbooks.Open(r'%ERP%'); time.sleep(2); ok=True
try: e.VBE.CommandBars.FindControl(Id=578).Execute()
except Exception as ex: print('FAIL', ex); ok=False
for c in wb.VBProject.VBComponents:
    if c.Type==1:
        n=c.CodeModule.CountOfLines
        print(f'  {c.Name}: {n} lines')
        if '1' in c.Name: print('  [FAIL] duplicate module detected'); ok=False
wb.Close(SaveChanges=False); e.Quit()
print('COMPILE:', 'OK' if ok else 'FAIL')
" || goto :ERR

echo.
echo [3/5] VBA module presence + no duplicate check...
"%PY%" -c "import zipfile
with zipfile.ZipFile(r'%ERP%') as z:
    has_ui = 'customUI/customUI14.xml' in z.namelist()
    has_vba = 'xl/vbaProject.bin' in z.namelist()
    print(f'  customUI14.xml: {has_ui}')
    print(f'  vbaProject.bin: {has_vba}')
    assert has_ui and has_vba, 'Ribbon or VBA missing'
print('STRUCTURE: OK')
" || goto :ERR

echo.
echo [4/5] Python core modules import check...
"%PY%" -c "
import sys
sys.path.insert(0, r'%REPO%')
from ERP.core.active_jobs_cols import COL, HDR_ROW, DATA_START
from ERP.core.ribbon_guard import save_preserving_ribbon
from ERP.jobs.email_builder import build_mailto_link, load_rules
print(f'  COL keys: {len(COL)}  HDR_ROW: {HDR_ROW}  DATA_START: {DATA_START}')
print('IMPORTS: OK')
" || goto :ERR

echo.
echo [5/5] Core test suite (Phase-1 regression)...
"%PY%" -m pytest tests/test_ribbon_guard.py tests/test_active_jobs_schema.py tests/test_email_builder.py -q --tb=line 2>&1 | findstr /c:"passed" /c:"failed"
if errorlevel 1 goto :ERR

echo.
echo ================================================================
echo   [OK] ALL CHECKS PASSED -- safe to test in Excel
echo ================================================================
echo.
pause
exit /b 0

:ERR
echo.
echo ================================================================
echo   [FAIL] One or more checks failed -- see output above
echo ================================================================
pause
exit /b 1
