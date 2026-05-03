$log = 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log'

Write-Host "=== LAST 50 LINES ==="
Get-Content $log -Tail 50

Write-Host "`n=== POST /api/rotation/* requests in last 500 lines ==="
Get-Content $log -Tail 500 |
    Select-String -Pattern 'POST.*rotation|run-today|preview-in-outlook|ROTATION_BG|ROTATION_SKIP|queue_to_outlook|build_daily_plan'

Write-Host "`n=== ANY ERROR/WARNING in last 200 lines ==="
Get-Content $log -Tail 200 |
    Select-String -Pattern 'ERROR|WARN|Traceback|Exception'
