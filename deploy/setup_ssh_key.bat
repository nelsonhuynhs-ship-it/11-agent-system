@echo off
REM ============================================
REM   SETUP SSH KEY for auto-deploy
REM   Run this ONE TIME to enable passwordless SSH
REM ============================================

echo.
echo This will copy your SSH key to VPS so future deploys don't need password.
echo You will be asked for VPS root password ONE LAST TIME.
echo.

REM Use ssh-copy-id equivalent for Windows
type C:\Users\ADMIN\.ssh\id_ed25519.pub | ssh root@14.225.207.145 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo SSH KEY INSTALLED OK"

echo.
echo Testing passwordless SSH...
ssh -o PasswordAuthentication=no root@14.225.207.145 "echo SUCCESS - no password needed && hostname"

echo.
pause
