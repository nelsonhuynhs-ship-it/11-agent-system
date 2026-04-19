$paths = @(
    'C:\Users\Nelson\OneDrive\Desktop\STOP Email.lnk',
    'C:\Users\Nelson\OneDrive\Desktop\Resume Email.lnk'
)
$sh = New-Object -ComObject WScript.Shell
foreach ($p in $paths) {
    Write-Host ""
    Write-Host "=== $p ==="
    if (-not (Test-Path $p)) { Write-Host "NOT FOUND"; continue }
    $lnk = $sh.CreateShortcut($p)
    Write-Host "Target      :" $lnk.TargetPath
    Write-Host "Arguments   :" $lnk.Arguments
    Write-Host "WorkingDir  :" $lnk.WorkingDirectory
    Write-Host "Description :" $lnk.Description
}
