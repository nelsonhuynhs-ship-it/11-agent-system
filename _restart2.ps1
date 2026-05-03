Stop-Process -Id 25424 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
$logPath = 'D:\NELSON\2. Areas\Engine_test\logs\web_server_debug.log'
if (Test-Path $logPath) { Clear-Content $logPath }
if (Test-Path ($logPath + '.err')) { Clear-Content ($logPath + '.err') }
Start-Process -FilePath 'python' -ArgumentList 'email_engine\web_server.py' `
    -WorkingDirectory 'D:\NELSON\2. Areas\Engine_test' `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError ($logPath + '.err')

# Poll /api/version up to 60s
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/version' -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) {
            'READY after ' + (($i + 1) * 3) + 's: ' + $r.Content
            $ok = $true
            break
        }
    } catch {}
}
if (-not $ok) { 'FAILED to start within 60s' }
