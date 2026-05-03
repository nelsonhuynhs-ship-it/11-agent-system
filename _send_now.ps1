# Direct send: bypass dashboard JS — call API directly with force=true
Write-Host "=== STEP 1: Preview with force=true ==="
$r1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/preview-in-outlook?markup=20&force=true' `
    -Method POST -UseBasicParsing -TimeoutSec 180
Write-Host "Status: $($r1.StatusCode)"
$j1 = $r1.Content | ConvertFrom-Json
Write-Host "Token: $($j1.preview_token)"
Write-Host "Plan total: $($j1.plan_total)"
$token = $j1.preview_token

if (-not $token) {
    Write-Host "[FAIL] No token returned. BODY:"
    Write-Host $r1.Content
    exit 1
}

Write-Host "`n=== STEP 2: Run-today with force=true ==="
$body = @{
    user_markup = 20
    preview_token = $token
    force = $true
} | ConvertTo-Json

$r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/run-today' `
    -Method POST -Body $body -ContentType 'application/json' `
    -UseBasicParsing -TimeoutSec 60
Write-Host "Status: $($r2.StatusCode)"
Write-Host "Response: $($r2.Content)"

Write-Host "`n=== STEP 3: Wait 5s for background task to enqueue ==="
Start-Sleep -Seconds 5

Write-Host "`n=== STEP 4: Check queue ==="
python "D:\NELSON\2. Areas\Engine_test\_diag_queue.py"
