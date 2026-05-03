$log = 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log'

Write-Host "=== ALL POST requests (full log) ==="
Get-Content $log | Select-String -Pattern 'POST.*rotation' | Select-Object -Last 20

Write-Host "`n=== ALL preview-in-outlook requests (with query string) ==="
Get-Content $log | Select-String -Pattern 'preview-in-outlook' | Select-Object -Last 10

Write-Host "`n=== Search 'force=true' anywhere ==="
Get-Content $log | Select-String -Pattern 'force=true|force.*true' | Select-Object -Last 10

Write-Host "`n=== Last 5 minutes activity (timestamp) ==="
$now = Get-Date
$cutoff = $now.AddMinutes(-12)
Write-Host "Cutoff: $cutoff"
Get-Content $log -Tail 100 | Select-Object -Last 30
