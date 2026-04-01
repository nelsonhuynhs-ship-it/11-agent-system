@echo off
REM ============================================
REM   NELSON FREIGHT — 1-CLICK DEPLOY
REM   PC Home → GitHub → VPS
REM   Usage: double-click to run
REM ============================================

echo.
echo ============================================
echo   NELSON FREIGHT DEPLOY
echo   %date% %time%
echo ============================================
echo.

REM --- Step 1: Git push ---
echo [1/2] Pushing to GitHub...
cd /d "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
git add -A
git status --short
git commit -m "deploy: %date:~-4%-%date:~4,2%-%date:~7,2% %time:~0,5%"
git push origin main

if %errorlevel% neq 0 (
    echo [ERROR] Git push failed!
    pause
    exit /b 1
)
echo [OK] GitHub push done
echo.

REM --- Step 2: SSH deploy ---
echo [2/2] Deploying to VPS...
ssh -i C:\Users\ADMIN\.ssh\id_nelson_vps_new root@14.225.207.145 "bash /home/nelson/deploy.sh"

if %errorlevel% neq 0 (
    echo [ERROR] VPS deploy failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   DEPLOY COMPLETE!
echo   API:    http://14.225.207.145:8100
echo   WebApp: http://14.225.207.145:3003
echo   Domain: https://nelsonfreight.pro.vn
echo ============================================
echo.
pause
