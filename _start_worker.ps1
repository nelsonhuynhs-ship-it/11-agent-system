# Kill any orphan worker first
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*outlook_queue_worker*' } |
    ForEach-Object {
        Write-Host "Killing orphan worker PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Seconds 1

# Clear stale worker log
$workerLog = 'D:\NELSON\2. Areas\Engine_test\email_engine\worker_err.log'
if (Test-Path $workerLog) { Clear-Content $workerLog }

# Start worker (3 threads, looping, real send) — hidden via pythonw
Start-Process -WindowStyle Hidden -FilePath 'pythonw' `
    -ArgumentList 'outlook_queue_worker.py','--workers','3','--loop' `
    -WorkingDirectory 'D:\NELSON\2. Areas\Engine_test\email_engine' `
    -RedirectStandardError $workerLog

Start-Sleep -Seconds 3

# Verify worker started
$worker = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*outlook_queue_worker*' }

if ($worker) {
    Write-Host "[OK] Worker started - PID $($worker.ProcessId)"
    $worker | Select-Object ProcessId, CommandLine, CreationDate | Format-List
} else {
    Write-Host "[FAIL] Worker not running - checking error log"
    if (Test-Path $workerLog) { Get-Content $workerLog -Tail 30 }
}
