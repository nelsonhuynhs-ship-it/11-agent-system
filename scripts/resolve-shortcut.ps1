$path = 'C:\Users\Nelson\OneDrive\Desktop\Nelson Email Dashboard.lnk'
if (-not (Test-Path $path)) { Write-Host "NOT FOUND: $path"; exit 1 }
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut($path)
Write-Host "TargetPath  :" $lnk.TargetPath
Write-Host "Arguments   :" $lnk.Arguments
Write-Host "WorkingDir  :" $lnk.WorkingDirectory
Write-Host "IconLocation:" $lnk.IconLocation
Write-Host "Description :" $lnk.Description
