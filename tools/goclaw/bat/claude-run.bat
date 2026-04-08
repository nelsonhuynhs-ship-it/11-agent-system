@echo off
REM Fox Spirit wrapper: Invoke Claude Code CLI on a project
REM Force env vars + PATH (GoClaw Lite exec may strip or not propagate these)
set "USERPROFILE=C:\Users\Nelson"
set "APPDATA=C:\Users\Nelson\AppData\Roaming"
set "LOCALAPPDATA=C:\Users\Nelson\AppData\Local"
set "HOME=C:\Users\Nelson"
set "HOMEDRIVE=C:"
set "HOMEPATH=\Users\Nelson"
set "USERNAME=Nelson"
set "PATH=C:\Users\Nelson\anaconda3;C:\Users\Nelson\anaconda3\Scripts;C:\Program Files\nodejs;C:\Users\Nelson\AppData\Roaming\npm;C:\Windows\System32;C:\Windows;%PATH%"
REM Delegate to Python wrapper (use full path as fallback)
"C:\Users\Nelson\anaconda3\python.exe" "D:\NELSON\2. Areas\Engine_test\tools\goclaw\claude-run.py" %*
