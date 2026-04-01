@echo off
REM ============================================
REM   AUTO DEPLOY — Nelson Freight
REM   HOME PC → GitHub → VPS
REM   Usage: double-click or run from terminal
REM ============================================

echo.
echo ============================================
echo   NELSON FREIGHT AUTO DEPLOY
echo   %date% %time%
echo ============================================
echo.

REM --- Step 1: Git push to GitHub ---
echo [1/3] Pushing to GitHub...
cd /d "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
git add -A
git status --short
git commit -m "deploy: auto-deploy %date:~-4%-%date:~4,2%-%date:~7,2%"
git push origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Git push failed!
    pause
    exit /b 1
)
echo [OK] GitHub push done
echo.

REM --- Step 2: SSH to VPS and deploy ---
echo [2/3] Deploying to VPS...
ssh root@14.225.207.145 "cd /home/nelson/_repo_temp && git pull origin main && cp -r webapp/* /home/nelson/webapp/ && cd /home/nelson/webapp && npm run build && systemctl restart nelson-webapp3003 && echo 'DEPLOY OK' && systemctl status nelson-webapp3003 --no-pager | head -5"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] VPS deploy failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   [3/3] DEPLOY COMPLETE!
echo   WebApp: http://14.225.207.145:3003
echo ============================================
echo.
pause
