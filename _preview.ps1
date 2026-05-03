try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/rotation/preview-in-outlook?markup=20&force=true' -Method POST -UseBasicParsing -TimeoutSec 180
    "OK " + $r.StatusCode + "`n" + $r.Content
} catch {
    "ERR: " + $_.Exception.Message
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        "BODY: " + $reader.ReadToEnd()
    }
}
