"""
notify.py  –  Windows system-tray balloon notification helper
=============================================================
Sends a non-blocking Windows notification (bottom-right corner)
without any third-party package.

Uses PowerShell + System.Windows.Forms.NotifyIcon via subprocess.
The popup auto-dismisses after ~5 seconds.

Usage
-----
    from notify import toast
    toast("Email Engine", "Scan complete: 3 routed, 12 skipped", kind="info")
    toast("Email Engine", "Outlook not running!", kind="error")
"""

from __future__ import annotations

import subprocess
import logging

log = logging.getLogger(__name__)

# Map kind → Windows ToolTipIcon enum name
_ICON_MAP = {
    "info":    "Info",
    "warning": "Warning",
    "error":   "Error",
    "none":    "None",
}


def toast(title: str, message: str, kind: str = "info", duration_ms: int = 6000) -> None:
    """
    Show a Windows system-tray balloon notification.

    Parameters
    ----------
    title       : Notification title (bold text)
    message     : Body text
    kind        : 'info' | 'warning' | 'error' | 'none'
    duration_ms : How long the balloon stays visible (ms, default 6 s)
    """
    icon_name = _ICON_MAP.get(kind.lower(), "Info")

    # Escape single quotes in title/message to avoid PowerShell injection
    safe_title   = title.replace("'", "`'")
    safe_message = message.replace("'", "`'")

    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing       | Out-Null
$n           = New-Object System.Windows.Forms.NotifyIcon
$n.Icon      = [System.Drawing.SystemIcons]::Application
$n.Visible   = $true
$n.ShowBalloonTip({duration_ms}, '{safe_title}', '{safe_message}', [System.Windows.Forms.ToolTipIcon]::{icon_name})
Start-Sleep -Milliseconds {duration_ms + 500}
$n.Dispose()
"""

    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as exc:
        # Never let notification errors crash the main engine
        log.debug("Toast notification failed (non-critical): %s", exc)
