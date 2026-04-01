@echo off
REM ═══════════════════════════════════════════
REM Nelson — Daily Data Sync PC → VPS
REM Schedule: daily at 07:30 via Task Scheduler
REM ═══════════════════════════════════════════

SET VPS=root@14.225.207.145
SET LOCAL=D:\NELSON\2. Areas\PricingSystem\Engine_test
echo === Nelson Data Sync to VPS: %date% %time% ===

REM Step 1: Export 30-day Parquet slice
echo [1/4] Exporting 30-day Parquet...
python "%LOCAL%\Pricing_Engine\export_30day.py"

REM Step 2: Sync Parquet to VPS
echo [2/4] Syncing Parquet...
scp "%LOCAL%\Pricing_Engine\data\rates_30day.parquet" %VPS%:/opt/nelson/data/

REM Step 3: Sync Email DB to VPS
echo [3/4] Syncing Email DB...
scp "%LOCAL%\email_engine\logs\shipments.db" %VPS%:/opt/nelson/data/

REM Step 4: Sync memory files
echo [4/4] Syncing memory...
scp "%LOCAL%\.agent\memory\05_active_context.md" %VPS%:/opt/nelson/memory/
scp "%LOCAL%\.agent\memory\lesson_learned.md" %VPS%:/opt/nelson/memory/
scp "%LOCAL%\.agent\memory\backlog.md" %VPS%:/opt/nelson/memory/

echo === Sync complete: %date% %time% ===
