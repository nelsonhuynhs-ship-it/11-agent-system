Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*_test_pipeline*' } |
    ForEach-Object {
        Write-Host "Killing test_pipeline PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
Write-Host "Done."
