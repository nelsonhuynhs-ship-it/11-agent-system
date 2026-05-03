Write-Host "=== PYTHON PROCESSES ==="
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, StartTime, ProcessName | Format-Table -AutoSize

Write-Host "=== OUTLOOK PROCESS ==="
Get-Process OUTLOOK -ErrorAction SilentlyContinue | Select-Object Id, StartTime | Format-Table -AutoSize

Write-Host "=== EXCEL PROCESS ==="
Get-Process EXCEL -ErrorAction SilentlyContinue | Select-Object Id, StartTime | Format-Table -AutoSize

Write-Host "=== QUEUE KILL STATUS ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/email-rate/queue/kill-status' -UseBasicParsing -TimeoutSec 5).Content
} catch { "ERR: " + $_.Exception.Message }

Write-Host "`n=== BATCH STATUS ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/batch-status' -UseBasicParsing -TimeoutSec 5).Content
} catch { "ERR: " + $_.Exception.Message }

Write-Host "`n=== LAST 60 LINES SERVER LOG ==="
Get-Content 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log' -Tail 60 | Select-String -Pattern 'preview-in-outlook|send-next|outlook_queue|send_email|queue_worker|Outbox|rotation|batch|POST|MailItem'
