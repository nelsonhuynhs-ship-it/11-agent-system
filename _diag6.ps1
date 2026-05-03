Get-ChildItem 'D:\NELSON\2. Areas\Engine_test' -Recurse -Filter '*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-4) } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 15 |
    Format-Table FullName, LastWriteTime, Length -AutoSize -Wrap
