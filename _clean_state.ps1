Write-Host "=== STEP 1: Verify queue is empty ==="
python "D:\NELSON\2. Areas\Engine_test\_diag_queue.py"

Write-Host "`n=== STEP 2: Check active processes ==="
Write-Host "-- Web server (port 8100):"
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*web_server.py*' } |
    Select-Object ProcessId, CommandLine | Format-List

Write-Host "-- Outlook queue worker:"
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*outlook_queue_worker*' } |
    Select-Object ProcessId, CommandLine | Format-List

Write-Host "-- Outlook desktop:"
Get-Process OUTLOOK -ErrorAction SilentlyContinue | Select-Object Id, StartTime | Format-Table -AutoSize

Write-Host "`n=== STEP 3: Kill switch status ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/email-rate/queue/kill-status' -UseBasicParsing -TimeoutSec 5).Content
} catch { "ERR: $($_.Exception.Message)" }

Write-Host "`n=== STEP 4: Today rotation state ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/today' -UseBasicParsing -TimeoutSec 10).Content
} catch { "ERR: $($_.Exception.Message)" }

Write-Host "`n=== STEP 5: Dashboard URL ==="
Write-Host "http://localhost:8100/"
