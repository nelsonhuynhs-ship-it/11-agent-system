# cleanup-logs.ps1 — email_engine log + executor-log cleanup
# Run: powershell -ExecutionPolicy Bypass -File scripts/cleanup-logs.ps1
# Keep: 7 days, delete older

$EmailEngine = "D:/NELSON/2. Areas/Engine_test/email_engine"
$MaxAgeDays = 7
$Cutoff = (Get-Date).AddDays(-$MaxAgeDays)

Write-Host "=== email_engine Cleanup ===" -ForegroundColor Cyan
Write-Host "Removing logs + executor-logs older than $MaxAgeDays days..."

$Patterns = @(
    "$EmailEngine\*.log",
    "$EmailEngine\core\*.log",
    "$EmailEngine\logs\*.log",
    "$EmailEngine\core\executor-log.md",
    "$EmailEngine\core\minimax\executor-log.md",
    "$EmailEngine\.cache\*.log"
)

$TotalFreed = 0

foreach ($Pattern in $Patterns) {
    $Files = Get-ChildItem -Path $Pattern -File -ErrorAction SilentlyContinue
    foreach ($File in $Files) {
        if ($File.LastWriteTime -lt $Cutoff) {
            $SizeKB = [math]::Round($File.Length / 1KB, 1)
            Remove-Item -Path $File.FullName -Force
            Write-Host "  Removed: $($File.Name) ($SizeKB KB)" -ForegroundColor DarkGray
            $TotalFreed += $File.Length
        }
    }
}

$FreedMB = [math]::Round($TotalFreed / 1MB, 2)
Write-Host ""
Write-Host "Done. Freed: $FreedMB MB" -ForegroundColor Green
