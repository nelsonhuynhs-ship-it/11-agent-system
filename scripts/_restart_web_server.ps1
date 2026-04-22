$conn = Get-NetTCPConnection -LocalPort 8100 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  Stop-Process -Id $conn.OwningProcess -Force
  Write-Host "Killed PID $($conn.OwningProcess) on port 8100"
  Start-Sleep -Seconds 2
}
Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'web_server.py' -WorkingDirectory 'D:\NELSON\2. Areas\Engine_test\email_engine' -RedirectStandardError 'D:\NELSON\2. Areas\Engine_test\email_engine\pythonw_err.log'
Write-Host "Started new web_server on port 8100"
