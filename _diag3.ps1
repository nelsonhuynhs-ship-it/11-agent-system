Write-Host "=== CURRENT ROTATION STATUS (today) ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/today' -UseBasicParsing -TimeoutSec 10).Content
} catch { "ERR: " + $_.Exception.Message }

Write-Host "`n=== PROGRESS ==="
try {
    (Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/progress' -UseBasicParsing -TimeoutSec 10).Content
} catch { "ERR: " + $_.Exception.Message }

Write-Host "`n=== FIND ALL RUN-TODAY / SEND-NEXT / SEND HITS TODAY (25/04) ==="
Get-Content 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log' | Select-String -Pattern 'run-today|send-next|preview-in-outlook|send-now' | ForEach-Object { $_.Line }

Write-Host "`n=== ROTATION FILES IN ONEDRIVE ==="
Get-ChildItem 'D:\OneDrive\NelsonData\email\' -Filter '*rotation*' -Recurse -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime | Format-Table -AutoSize

Write-Host "`n=== LAST BATCH LOG ==="
$bat = 'D:\OneDrive\NelsonData\email\config\rotation_quota.json'
if (Test-Path $bat) { Write-Host "quota config:"; Get-Content $bat -Raw }
