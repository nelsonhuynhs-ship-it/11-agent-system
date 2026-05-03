Write-Host "=== ALL POST REQUESTS IN LAST 200 LINES ==="
Get-Content 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log' -Tail 500 | Select-String -Pattern 'POST ' | Select-Object -Last 30 | ForEach-Object { $_.Line }

Write-Host "`n=== RECENT PREVIEW/SEND REQUESTS (any method) ==="
Get-Content 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log' -Tail 500 | Select-String -Pattern 'preview|send-next|send-now|run-today|send_email' | Select-Object -Last 20 | ForEach-Object { $_.Line }

Write-Host "`n=== ROTATION STATE JSON (if exists) ==="
$rot = 'D:\OneDrive\NelsonData\email\rotation_state.json'
if (Test-Path $rot) { Get-Content $rot -Raw } else { "Not found at $rot" }
