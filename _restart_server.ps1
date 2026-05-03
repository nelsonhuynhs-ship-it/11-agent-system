Stop-Process -Id 26128 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$logPath = 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log'
if (Test-Path $logPath) { Clear-Content $logPath }
Start-Process -FilePath 'python' -ArgumentList 'email_engine\web_server.py' `
    -WorkingDirectory 'D:\NELSON\2. Areas\Engine_test' `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError ($logPath + '.err')
Start-Sleep -Seconds 8
try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/version' -UseBasicParsing -TimeoutSec 5
    'OK ' + $r.StatusCode + ' ' + $r.Content
} catch {
    'NOT READY: ' + $_.Exception.Message
}
