# Simulate exactly what dashboard does (NO force=true)
Write-Host "=== Test: Dashboard call /preview-in-outlook?markup=20 (NO force) ==="
try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/preview-in-outlook?markup=20' `
        -Method POST -UseBasicParsing -TimeoutSec 60
    Write-Host "[OK] Status $($r.StatusCode)"
    Write-Host "Response: $($r.Content)"
} catch {
    $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 'N/A' }
    Write-Host "[ERR HTTP $code] $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "BODY: $($reader.ReadToEnd())"
    }
}
