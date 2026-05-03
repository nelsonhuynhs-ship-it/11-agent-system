try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/preview-in-outlook?markup=20&force=true' `
        -Method POST -UseBasicParsing -TimeoutSec 180
    Write-Host "[OK] Status $($r.StatusCode)"
    Write-Host "Response:"
    Write-Host $r.Content

    # Extract token for run-today
    $j = $r.Content | ConvertFrom-Json
    if ($j.preview_token) {
        Write-Host "`n[TOKEN] $($j.preview_token)"
        $j.preview_token | Out-File 'D:\NELSON\2. Areas\Engine_test\_token.txt' -Encoding ascii -NoNewline
        Write-Host "Token saved to _token.txt for run-today"
    }
} catch {
    Write-Host "[ERR] $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "BODY: $($reader.ReadToEnd())"
    }
}
