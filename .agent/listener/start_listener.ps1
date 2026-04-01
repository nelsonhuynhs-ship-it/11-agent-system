# ============================================================
#  CTO Agent v2 - Telegram Listener (PowerShell)
#  GoClaw Upgrades: Debouncer (1000ms), Intent routing
# ============================================================

$ErrorActionPreference = "Stop"

# -- Configuration --
$BOT_TOKEN = "8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys"
$NELSON_CHAT_ID = 5398948978
$POLL_INTERVAL = 3
$POLL_TIMEOUT = 30
$DEBOUNCE_MS = 1000

$WORKSPACE = "D:\NELSON\2. Areas\PricingSystem\Engine_test"
$AGENTS_DIR = Join-Path $WORKSPACE ".agent\agents"
$MEMORY_DIR = Join-Path $WORKSPACE ".agent\memory"
$LOG_FILE = Join-Path $WORKSPACE ".agent\listener\listener.log"

$BASE_URL = "https://api.telegram.org/bot$BOT_TOKEN"

# Track state
$global:lastUpdateId = 0
$global:debounceBuffer = @{}
$global:debounceTimers = @{}

# Emoji helpers
function E_Robot  { return [char]::ConvertFromUtf32(0x1F916) }
function E_Check  { return [char]0x2705 }
function E_Alert  { return [char]0x26A0 }
function E_Stop   { return [char]::ConvertFromUtf32(0x1F6A8) }
function E_Gear   { return [char]0x2699 }
function E_Clip   { return [char]::ConvertFromUtf32(0x1F4CB) }
function E_Chart  { return [char]::ConvertFromUtf32(0x1F4CA) }
function E_Quest  { return [char]0x2753 }

# -- Logging --
function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

# -- Telegram API --
function Send-TelegramMessage {
    param([string]$Text)
    try {
        $body = @{
            chat_id = $NELSON_CHAT_ID
            text    = $Text
        }
        $json = $body | ConvertTo-Json -Compress
        $response = Invoke-RestMethod -Uri "$BASE_URL/sendMessage" -Method POST -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
        return $response.ok
    }
    catch {
        Write-Log "ERROR sending message: $_"
        return $false
    }
}

function Get-Updates {
    try {
        $offset = $global:lastUpdateId + 1
        $url = "$BASE_URL/getUpdates?offset=$offset&timeout=$POLL_TIMEOUT"
        $response = Invoke-RestMethod -Uri $url -Method GET -TimeoutSec ($POLL_TIMEOUT + 10)
        if ($response.ok -and $response.result) {
            return $response.result
        }
        return @()
    }
    catch {
        Write-Log "ERROR getting updates: $_"
        Start-Sleep -Seconds 5
        return @()
    }
}

# -- Command Router --
function Invoke-CTOAgent {
    param([string]$Command)
    Write-Log "Routing to CTO Agent: $Command"
    try {
        $agentScript = Join-Path $AGENTS_DIR "cto_agent.py"
        $output = python $agentScript $Command 2>&1
        Write-Log "CTO Agent output: $($output | Out-String)"
        return $true
    }
    catch {
        Write-Log "CTO Agent error: $_"
        $msg = "$(E_Stop) CTO Agent error: $_"
        Send-TelegramMessage $msg
        return $false
    }
}

# ============================================================
#  UPGRADE 2: Message Debouncer (GoClaw Layer 2)
#  Buffer messages per sender for 1000ms before processing.
#  Media/files bypass debounce immediately.
# ============================================================
function Add-ToDebounceBuffer {
    param(
        [string]$Key,
        [string]$Text,
        [bool]$HasMedia
    )

    # Media bypasses debounce
    if ($HasMedia) {
        Write-Log "DEBOUNCE: Media detected, bypassing for key=$Key"
        Invoke-CTOAgent $Text
        return
    }

    # Add to buffer
    if (-not $global:debounceBuffer.ContainsKey($Key)) {
        $global:debounceBuffer[$Key] = @()
    }
    $global:debounceBuffer[$Key] += $Text
    $global:debounceTimers[$Key] = Get-Date

    Write-Log "DEBOUNCE: Buffered message for key=$Key (total: $($global:debounceBuffer[$Key].Count))"
}

function Flush-DebounceBuffer {
    $now = Get-Date
    $keysToFlush = @()

    foreach ($key in @($global:debounceTimers.Keys)) {
        $lastTime = $global:debounceTimers[$key]
        $elapsed = ($now - $lastTime).TotalMilliseconds

        if ($elapsed -ge $DEBOUNCE_MS) {
            $keysToFlush += $key
        }
    }

    foreach ($key in $keysToFlush) {
        $messages = $global:debounceBuffer[$key]
        if ($messages -and $messages.Count -gt 0) {
            if ($messages.Count -eq 1) {
                $merged = $messages[0]
            }
            else {
                $merged = $messages -join "`n"
                Write-Log "DEBOUNCE: Merged $($messages.Count) messages for key=$key"
            }
            Invoke-CTOAgent $merged
        }
        $global:debounceBuffer.Remove($key)
        $global:debounceTimers.Remove($key)
    }
}

# -- Startup Sequence --
function Start-CTOAgent {
    Write-Log "=========================================="
    Write-Log "CTO Agent v2 Listener starting..."
    Write-Log "Upgrades: Intent, Debounce, Isolated HTTP, Steer"
    Write-Log "Workspace: $WORKSPACE"
    Write-Log "=========================================="

    # Ensure directories exist
    @($AGENTS_DIR, $MEMORY_DIR, (Split-Path $LOG_FILE)) | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -Path $_ -ItemType Directory -Force | Out-Null
        }
    }

    # Step 1: Read active context
    $contextFile = Join-Path $MEMORY_DIR "05_active_context.md"
    $contextSummary = ""
    $erpVersion = "V13"

    if (Test-Path $contextFile) {
        $content = Get-Content $contextFile -Raw -Encoding UTF8
        if ($content -match "ERP Build\s*\|\s*(\S+)") {
            $erpVersion = $Matches[1]
        }
        if ($content -match "Date:\*\*\s*(.+)") {
            $contextSummary = "Last session: $($Matches[1])"
        }
    }
    else {
        $contextSummary = "No active context found (first run)"
    }

    # Step 2: Send online message
    $nl = "`n"
    $onlineMsg = "$(E_Robot) CTO Agent v3 online." + $nl
    $onlineMsg += "ERP: $erpVersion. Ready for tasks." + $nl + $nl
    $onlineMsg += "Phase 1: Task Board | Phase 2: Mailbox | Phase 3: Parallel" + $nl
    $onlineMsg += "Commands: /task /status /pause /rollback /log" + $nl
    $onlineMsg += $contextSummary

    Send-TelegramMessage $onlineMsg
    Write-Log "Startup message sent. ERP: $erpVersion"

    # Step 3: Start Phase 3 specialist threads
    Write-Log "Starting Phase 3 specialist threads..."
    try {
        $startSpecialists = Join-Path $AGENTS_DIR "cto_agent.py"
        python -c "import sys; sys.path.insert(0, r'$AGENTS_DIR'); import cto_agent; cto_agent.start_specialists()" 2>&1
        Write-Log "Specialist threads initialized"
    }
    catch {
        Write-Log "Specialist thread startup skipped: $_"
    }

    # Step 4: Begin polling loop
    Write-Log "Starting polling loop (interval: ${POLL_INTERVAL}s, debounce: ${DEBOUNCE_MS}ms)..."
    Poll-Loop
}

# -- Main Polling Loop --
function Poll-Loop {
    while ($true) {
        try {
            $updates = Get-Updates

            foreach ($update in $updates) {
                $global:lastUpdateId = $update.update_id

                # Extract message
                $msg = $update.message
                if (-not $msg) {
                    continue
                }

                $chatId = $msg.chat.id
                $text = $msg.text
                $sender = $msg.from.first_name

                # WHITELIST CHECK
                if ($chatId -ne $NELSON_CHAT_ID) {
                    Write-Log "BLOCKED: Unauthorized sender $sender (chat_id: $chatId)"
                    continue
                }

                if ([string]::IsNullOrWhiteSpace($text)) {
                    continue
                }

                Write-Log "Received from Nelson: $text"

                # Check for media (bypass debounce)
                $hasMedia = ($null -ne $msg.document) -or ($null -ne $msg.photo) -or ($null -ne $msg.video)

                # Debounce key: chatID:senderID
                $senderId = $msg.from.id
                $debounceKey = "${chatId}:${senderId}"

                # Slash commands with immediate effect bypass debounce
                $immediateCommands = @("/status", "/pause", "/rollback", "/log", "/approve", "/reject")
                if ($text -in $immediateCommands) {
                    Write-Log "Immediate command: $text (bypass debounce)"
                    Invoke-CTOAgent $text
                }
                elseif ($text -match "^/task\s+") {
                    # /task commands also bypass debounce (they are explicit)
                    Write-Log "Task command: $text (bypass debounce)"
                    Invoke-CTOAgent $text
                }
                else {
                    # Regular messages go through debouncer
                    Add-ToDebounceBuffer -Key $debounceKey -Text $text -HasMedia $hasMedia
                }
            }

            # Flush debounce buffer for messages older than DEBOUNCE_MS
            Flush-DebounceBuffer
        }
        catch {
            Write-Log "Poll loop error: $_"
            Start-Sleep -Seconds 5
        }

        Start-Sleep -Seconds $POLL_INTERVAL
    }
}

# -- Entry Point --
Start-CTOAgent
