# Quick handoff update — run at end of each session
# Usage: .\scripts\handoff-update.ps1 "summary of what you did"

param([string]$Summary)

if (-not $Summary) {
    Write-Host "Usage: .\scripts\handoff-update.ps1 'what you did this session'"
    exit 1
}

$Machine = $env:COMPUTERNAME
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"

Write-Host ""
Write-Host "=== Updating handoff context ==="
Write-Host "Machine: $Machine"
Write-Host "Time: $Timestamp"
Write-Host "Summary: $Summary"

git add ".agent\handoff.md"
git commit -m "handoff: $Machine -- $Summary"
git push origin main

Write-Host "=== Handoff pushed. Other machines can git pull to see context. ==="
