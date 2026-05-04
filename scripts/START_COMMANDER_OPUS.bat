@echo off
REM START_COMMANDER_OPUS.bat - Commander Bot (Opus / Anthropic)
REM Bot: @claude_bot | Token: read from TELEGRAM_BOT_TOKEN env var
title OPUS Commander Launcher

REM ---- Clean Anthropic/MiniMax env to avoid leak ----
set "ANTHROPIC_BASE_URL="
set "ANTHROPIC_AUTH_TOKEN="
set "ANTHROPIC_MODEL="
set "ANTHROPIC_DEFAULT_OPUS_MODEL="
set "ANTHROPIC_DEFAULT_SONNET_MODEL="
set "ANTHROPIC_DEFAULT_HAIKU_MODEL="
set "ANTHROPIC_SMALL_FAST_MODEL="
set "API_TIMEOUT_MS="
set "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="

REM ---- TELEGRAM PLUGIN: bot token from env var (NOT hardcoded) ----
REM TELEGRAM_STATE_DIR separates access.json/bot.pid from other bot instances
set "TELEGRAM_STATE_DIR=C:\Users\Nelson\.claude\channels\telegram-opus"

REM ---- Launch with cmd /k so window stays open on crash ----
start "OPUS-COMMANDER" cmd /k "echo --- ENV CHECK --- & echo TELEGRAM_BOT_TOKEN=%TELEGRAM_BOT_TOKEN:~0,12%...%TELEGRAM_BOT_TOKEN:~-4% & echo TELEGRAM_STATE_DIR=%TELEGRAM_STATE_DIR% & echo Expected bot: @claude_bot & echo ----------------- & "C:\Users\Nelson\AppData\Roaming\npm\claude.cmd" --settings "C:\Users\Nelson\AppData\Roaming\Claude\commander-settings.json" --channels plugin:telegram@claude-plugins-official"

echo.
echo [OK] OPUS-COMMANDER window opened. Check ENV CHECK banner.
echo.
echo Bot expected: @claude_bot
echo Token must be set in TELEGRAM_BOT_TOKEN env var.
echo.
pause
