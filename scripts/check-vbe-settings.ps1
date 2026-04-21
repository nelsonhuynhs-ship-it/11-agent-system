foreach ($v in '6.0','6.5','7.0','7.1') {
    $k = "HKCU:\Software\Microsoft\VBA\$v\Common"
    if (Test-Path $k) {
        $val = Get-ItemProperty -Path $k -Name DefaultErrorTrapping -EA SilentlyContinue
        Write-Output ("VBA " + $v + ": DefaultErrorTrapping = " + $val.DefaultErrorTrapping)
        # Force set to 2 if not already
        if ($val.DefaultErrorTrapping -ne 2) {
            Set-ItemProperty -Path $k -Name DefaultErrorTrapping -Value 2 -Force
            Write-Output ("  -> set to 2 (Break on Unhandled Errors)")
        }
    }
}
