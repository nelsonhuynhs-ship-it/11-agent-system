Write-Host "=== PROCESS CHECK ==="
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*outlook_queue_worker*' -or $_.CommandLine -like '*web_server*' } |
    Select-Object ProcessId, CreationDate, CommandLine | Format-List

Write-Host "`n=== WORKER ERR LOG (tail 30) ==="
$wlog = 'D:\NELSON\2. Areas\Engine_test\email_engine\worker_err.log'
if (Test-Path $wlog) {
    Get-Content $wlog -Tail 30
} else { Write-Host "NO worker_err.log" }

Write-Host "`n=== RECENT LOGS ==="
Get-ChildItem 'D:\NELSON\2. Areas\Engine_test\email_engine\logs\' -Filter '*.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 5 |
    Format-Table Name, LastWriteTime, Length -AutoSize

Write-Host "`n=== Search for run-today / ROTATION_BG / preview-in-outlook in last 200 lines ==="
$dlog = 'D:\NELSON\2. Areas\Engine_test\email_engine\logs\web_server_debug.log'
if (Test-Path $dlog) {
    Get-Content $dlog -Tail 300 |
        Select-String -Pattern 'run-today|ROTATION_BG|preview-in-outlook|queue_to_outlook|build_daily_plan|ROTATION_SKIP'
} else { Write-Host "NO web_server_debug.log" }
