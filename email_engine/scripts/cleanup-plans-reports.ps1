# cleanup-plans-reports.ps1 — email_engine plans/reports retention
# Run: powershell -ExecutionPolicy Bypass -File scripts/cleanup-plans-reports.ps1
# Keep: 30 days, archive older to plans/archive/

$PlansDir = "D:/NELSON/2. Areas/Engine_test/plans"
$ReportsDir = "$PlansDir/reports"
$ArchiveDir = "$PlansDir/archive"
$MaxAgeDays = 30
$Cutoff = (Get-Date).AddDays(-$MaxAgeDays)

Write-Host "=== Plans/Reports Cleanup ===" -ForegroundColor Cyan
Write-Host "Removing reports older than $MaxAgeDays days..."

$FilesRemoved = 0

# Clean old reports (not in archive/)
$ReportFiles = Get-ChildItem -Path $ReportsDir -File -Filter "*.md" -ErrorAction SilentlyContinue
foreach ($File in $ReportFiles) {
    if ($File.LastWriteTime -lt $Cutoff) {
        $SizeKB = [math]::Round($File.Length / 1KB, 1)
        Remove-Item -Path $File.FullName -Force
        Write-Host "  Removed report: $($File.Name) ($SizeKB KB)" -ForegroundColor DarkGray
        $FilesRemoved++
    }
}

# Clean old top-level plan spec files (not phase files, not archive/)
$SpecFiles = Get-ChildItem -Path $PlansDir -File -Filter "executor-log-*.md" -ErrorAction SilentlyContinue
foreach ($File in $SpecFiles) {
    if ($File.LastWriteTime -lt $Cutoff) {
        $SizeKB = [math]::Round($File.Length / 1KB, 1)
        Remove-Item -Path $File.FullName -Force
        Write-Host "  Removed spec: $($File.Name) ($SizeKB KB)" -ForegroundColor DarkGray
        $FilesRemoved++
    }
}

Write-Host ""
Write-Host "Done. Files removed: $FilesRemoved" -ForegroundColor Green
Write-Host "Archive contents:" -ForegroundColor Yellow
Get-ChildItem -Path $ArchiveDir -Directory | ForEach-Object { Write-Host "  $($_.Name)" }
