Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*web_server*' } |
    Select-Object ProcessId, CommandLine | Format-List
