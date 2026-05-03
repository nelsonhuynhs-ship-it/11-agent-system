try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/version' -UseBasicParsing -TimeoutSec 10
    "OK " + $r.StatusCode + " " + $r.Content
} catch {
    "ERR: " + $_.Exception.Message
}
