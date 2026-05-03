Write-Host "=== OUTLOOK QUEUE DB STATE ==="
$db = 'D:\NELSON\2. Areas\Engine_test\email_engine\data\outlook_queue.db'
if (Test-Path $db) {
    python -c "import sqlite3; c = sqlite3.connect(r'$db'); cur = c.cursor(); cur.execute(\"SELECT batch_id, status, COUNT(*) FROM email_queue GROUP BY batch_id, status ORDER BY batch_id DESC LIMIT 30\"); [print(r) for r in cur.fetchall()]; cur.execute(\"SELECT batch_id, enqueued_at FROM email_queue WHERE batch_id LIKE 'ROT_%' ORDER BY enqueued_at DESC LIMIT 3\"); print('--- latest ROT batches:'); [print(r) for r in cur.fetchall()]"
} else {
    Write-Host "DB not found"
}

Write-Host "`n=== QUEUE WORKER PROCESS DETAILS (PID 25116) ==="
Get-WmiObject Win32_Process -Filter "ProcessId=25116" -ErrorAction SilentlyContinue | Select-Object CommandLine, CreationDate | Format-List

Write-Host "`n=== WEB SERVER PROCESS (PID 27248) ==="
Get-WmiObject Win32_Process -Filter "ProcessId=27248" -ErrorAction SilentlyContinue | Select-Object CommandLine | Format-List
