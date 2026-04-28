@echo off
setlocal enabledelayedexpansion
REM Deploy: Quote Img Smart Upgrade 260428

set "PLAN=Quote Img Smart Upgrade 260428"
set "TIMESTAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "BACKUP_DIR=D:\OneDrive\NelsonData\erp\backups"
set "MIRROR_DIR=D:\NELSON\2. Areas\Engine_test\ERP\vba-v14-mirror"
set "CANONICAL_DIR=D:\OneDrive\NelsonData\erp"
set "REPO_DIR=D:\NELSON\2. Areas\Engine_test"

echo.
echo ================================================
echo   DEPLOY: %PLAN%
echo ================================================
echo.

echo [PRE-FLIGHT] Checking for open Excel...
tasklist /fi "IMAGENAME eq EXCEL.EXE" /nh 2>nul | findstr /i "EXCEL.EXE" >nul
if not errorlevel 1 (
    echo   ERROR: Excel is running. Close all Excel windows first.
    exit /b 1
)
echo   OK: no EXCEL.EXE
echo.

echo [STEP 1] Creating timestamped backup...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
copy /y "%CANONICAL_DIR%\erp-v14-ribbon-callbacks.bas" "%BACKUP_DIR%\erp-v14-ribbon-callbacks.bas.bak.%TIMESTAMP%" >nul
copy /y "%CANONICAL_DIR%\erp-v14-thisworkbook.txt"     "%BACKUP_DIR%\erp-v14-thisworkbook.txt.bak.%TIMESTAMP%" >nul
copy /y "%CANONICAL_DIR%\erp-v14-test-e2e.bas"         "%BACKUP_DIR%\erp-v14-test-e2e.bas.bak.%TIMESTAMP%" >nul
copy /y "%CANONICAL_DIR%\CustomUI_v14.xml"             "%BACKUP_DIR%\CustomUI_v14.xml.bak.%TIMESTAMP%" >nul
copy /y "%CANONICAL_DIR%\ERP_Master_v14.xlsm"          "%BACKUP_DIR%\ERP_Master_v14.xlsm.bak.%TIMESTAMP%" >nul
echo   Backup: %BACKUP_DIR%\*.bak.%TIMESTAMP%
echo.

echo [STEP 2] Sync mirror to canonical...
copy /y "%MIRROR_DIR%\erp-v14-ribbon-callbacks.bas" "%CANONICAL_DIR%\erp-v14-ribbon-callbacks.bas"
copy /y "%MIRROR_DIR%\erp-v14-thisworkbook.txt"     "%CANONICAL_DIR%\erp-v14-thisworkbook.txt"
copy /y "%MIRROR_DIR%\erp-v14-test-e2e.bas"         "%CANONICAL_DIR%\erp-v14-test-e2e.bas"
copy /y "%MIRROR_DIR%\CustomUI_v14.xml"             "%CANONICAL_DIR%\CustomUI_v14.xml"
echo   Sync done.
echo.

echo [STEP 3] Static lint...
cd /d "%REPO_DIR%"
call scripts\verify-erp.bat
if errorlevel 1 (
    echo   FAIL: verify-erp.bat exit %errorlevel%. Rolling back...
    copy /y "%BACKUP_DIR%\erp-v14-ribbon-callbacks.bas.bak.%TIMESTAMP%" "%CANONICAL_DIR%\erp-v14-ribbon-callbacks.bas" >nul
    copy /y "%BACKUP_DIR%\erp-v14-thisworkbook.txt.bak.%TIMESTAMP%"     "%CANONICAL_DIR%\erp-v14-thisworkbook.txt" >nul
    copy /y "%BACKUP_DIR%\erp-v14-test-e2e.bas.bak.%TIMESTAMP%"         "%CANONICAL_DIR%\erp-v14-test-e2e.bas" >nul
    copy /y "%BACKUP_DIR%\CustomUI_v14.xml.bak.%TIMESTAMP%"             "%CANONICAL_DIR%\CustomUI_v14.xml" >nul
    echo   Rollback complete.
    exit /b 1
)
echo   verify-erp.bat PASSED
echo.

echo [STEP 4] Reimport VBA modules into ERP_Master_v14.xlsm...
python scripts\reimport-erp-vba-modules.py
if errorlevel 1 (
    echo   FAIL: reimport exit %errorlevel%
    echo   Canonical synced. Workbook NOT updated. Re-run after fix.
    exit /b 1
)
echo   reimport PASSED
echo.

echo ================================================
echo   DEPLOY SUCCESS
echo ================================================
echo   Backup: %BACKUP_DIR%\*.bak.%TIMESTAMP%
echo   Next: open ERP_Master_v14.xlsm and run smoke test
echo.
exit /b 0
