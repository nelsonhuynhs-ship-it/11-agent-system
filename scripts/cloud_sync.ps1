<#
.SYNOPSIS
    Smart Cloud Sync — So sánh & copy data files từ Cloud/USB về PC Home
.DESCRIPTION
    Quét folder cloud, tìm file trùng tên với local, so sánh size + date,
    chỉ copy file mới hơn hoặc lớn hơn. Hiện bảng so sánh trước khi copy.
.USAGE
    .\cloud_sync.ps1 -CloudPath "D:\OneDrive\FreightData"
    .\cloud_sync.ps1 -CloudPath "E:\USB_Backup"
    .\cloud_sync.ps1 -CloudPath "C:\Users\ADMIN\Downloads"  # nếu tải từ cloud về Downloads
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$CloudPath,
    
    [switch]$AutoCopy,     # Tự động copy không hỏi
    [switch]$DryRun        # Chỉ hiện bảng, không copy
)

$ErrorActionPreference = "Stop"
$BASE = "D:\NELSON\2. Areas\PricingSystem\Engine_test"

# === Files quan trọng cần sync ===
$IMPORTANT_FILES = @(
    @{ Local = "Pricing_Engine\data\Cleaned_Master_History.parquet"; Desc = "Master Parquet (giá cước)" },
    @{ Local = "Pricing_Engine\data\Cleaned_Master_History_normalized.parquet"; Desc = "Normalized Parquet" },
    @{ Local = "email_engine\data\shipment_state.json"; Desc = "Shipment state (owner info)" },
    @{ Local = "email_engine\data\customer_rules.json"; Desc = "Customer ownership rules" },
    @{ Local = "Pricing_Engine\data\PUC_SOC.xlsx"; Desc = "PUC/SOC data" },
    @{ Local = "Pricing_Engine\data\carrier_rules.json"; Desc = "Carrier rules" },
    @{ Local = "TelegramBot\data\freight_bot.db"; Desc = "Bot SQLite DB" },
    @{ Local = "Pricing_Engine\data\FREE TIME AT ORIGIN 2025.xlsx"; Desc = "Freetime data" }
)

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   CLOUD SYNC — Smart Data File Comparator   " -ForegroundColor Cyan  
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Cloud folder: $CloudPath" -ForegroundColor Yellow
Write-Host "  Local base:   $BASE" -ForegroundColor Yellow
Write-Host ""

# Validate cloud path
if (-not (Test-Path $CloudPath)) {
    Write-Host "  ERROR: Cloud folder khong ton tai: $CloudPath" -ForegroundColor Red
    exit 1
}

# === STEP 1: Scan cloud folder for ALL matching files ===
Write-Host "  Scanning cloud folder..." -ForegroundColor Gray

$cloudFiles = Get-ChildItem -Path $CloudPath -Recurse -File | Where-Object {
    $_.Extension -in '.parquet','.json','.xlsx','.xlsm','.db','.csv'
}

Write-Host "  Found $($cloudFiles.Count) data files in cloud folder" -ForegroundColor Gray
Write-Host ""

# === STEP 2: Match cloud files against local ===
$results = @()

foreach ($cf in $cloudFiles) {
    # Try to find matching local file by name
    $localMatches = Get-ChildItem -Path $BASE -Recurse -File -Filter $cf.Name -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike "*\_backup\*" -and $_.FullName -notlike "*\_archived*" -and $_.FullName -notlike "*\node_modules\*" }
    
    foreach ($lf in $localMatches) {
        $relPath = $lf.FullName -replace [regex]::Escape("$BASE\"), ''
        
        $cloudSizeKB = [math]::Round($cf.Length / 1KB, 1)
        $localSizeKB = [math]::Round($lf.Length / 1KB, 1)
        $sizeDiff = $cloudSizeKB - $localSizeKB
        
        $cloudDate = $cf.LastWriteTime
        $localDate = $lf.LastWriteTime
        
        # Determine action
        $action = "SKIP"
        $reason = "Same"
        
        if ($cloudDate -gt $localDate -and [math]::Abs($sizeDiff) -gt 1) {
            $action = "COPY"
            $reason = "Cloud newer + different size"
        }
        elseif ($cloudDate -gt $localDate) {
            $action = "COPY"
            $reason = "Cloud newer"
        }
        elseif ($cloudSizeKB -gt $localSizeKB * 1.1) {
            $action = "REVIEW"
            $reason = "Cloud larger but older"
        }
        elseif ($cf.Length -eq $lf.Length -and $cloudDate -eq $localDate) {
            $action = "SKIP"
            $reason = "Identical"
        }
        
        $results += [PSCustomObject]@{
            FileName   = $cf.Name
            LocalPath  = $relPath
            Action     = $action
            Reason     = $reason
            CloudDate  = $cloudDate.ToString("MM/dd HH:mm")
            LocalDate  = $localDate.ToString("MM/dd HH:mm")
            CloudKB    = $cloudSizeKB
            LocalKB    = $localSizeKB
            DiffKB     = if ($sizeDiff -gt 0) { "+$sizeDiff" } else { "$sizeDiff" }
            CloudFull  = $cf.FullName
            LocalFull  = $lf.FullName
        }
    }
    
    # File exists in cloud but NOT in local
    if ($localMatches.Count -eq 0) {
        # Check if it's an important file
        $importantMatch = $IMPORTANT_FILES | Where-Object { 
            (Split-Path $_.Local -Leaf) -eq $cf.Name 
        }
        
        if ($importantMatch) {
            $targetPath = Join-Path $BASE $importantMatch.Local
            $results += [PSCustomObject]@{
                FileName   = $cf.Name
                LocalPath  = $importantMatch.Local
                Action     = "NEW"
                Reason     = "Missing locally — $($importantMatch.Desc)"
                CloudDate  = $cf.LastWriteTime.ToString("MM/dd HH:mm")
                LocalDate  = "—"
                CloudKB    = [math]::Round($cf.Length / 1KB, 1)
                LocalKB    = 0
                DiffKB     = "+$([math]::Round($cf.Length / 1KB, 1))"
                CloudFull  = $cf.FullName
                LocalFull  = $targetPath
            }
        }
    }
}

# === STEP 3: Also check important files specifically ===
foreach ($imp in $IMPORTANT_FILES) {
    $localPath = Join-Path $BASE $imp.Local
    $fileName = Split-Path $imp.Local -Leaf
    
    # Skip if already matched
    if ($results | Where-Object { $_.FileName -eq $fileName }) { continue }
    
    $cloudMatch = $cloudFiles | Where-Object { $_.Name -eq $fileName }
    
    if (-not $cloudMatch -and (Test-Path $localPath)) {
        $lf = Get-Item $localPath
        $results += [PSCustomObject]@{
            FileName   = $fileName
            LocalPath  = $imp.Local
            Action     = "NO_CLOUD"
            Reason     = "Not found in cloud folder"
            CloudDate  = "—"
            LocalDate  = $lf.LastWriteTime.ToString("MM/dd HH:mm")
            CloudKB    = 0
            LocalKB    = [math]::Round($lf.Length / 1KB, 1)
            DiffKB     = "—"
            CloudFull  = ""
            LocalFull  = $lf.FullName
        }
    }
}

# === STEP 4: Display results ===
if ($results.Count -eq 0) {
    Write-Host "  No matching data files found between cloud and local." -ForegroundColor Yellow
    Write-Host "  Make sure you're pointing to the right cloud folder." -ForegroundColor Yellow
    exit 0
}

Write-Host "========================================================================" -ForegroundColor White
Write-Host "  COMPARISON RESULTS" -ForegroundColor White
Write-Host "========================================================================" -ForegroundColor White
Write-Host ""

$toCopy = @()
$toReview = @()

foreach ($r in ($results | Sort-Object Action, FileName)) {
    $color = switch ($r.Action) {
        "COPY"     { "Green" }
        "NEW"      { "Cyan" }
        "REVIEW"   { "Yellow" }
        "SKIP"     { "DarkGray" }
        "NO_CLOUD" { "DarkGray" }
        default    { "White" }
    }
    
    $icon = switch ($r.Action) {
        "COPY"     { "[>>]" }
        "NEW"      { "[++]" }
        "REVIEW"   { "[??]" }
        "SKIP"     { "[==]" }
        "NO_CLOUD" { "[--]" }
        default    { "[  ]" }
    }
    
    Write-Host "  $icon " -ForegroundColor $color -NoNewline
    Write-Host "$($r.FileName)" -ForegroundColor White -NoNewline
    Write-Host " — $($r.Reason)" -ForegroundColor $color
    Write-Host "       Cloud: $($r.CloudDate) ($($r.CloudKB) KB)  |  Local: $($r.LocalDate) ($($r.LocalKB) KB)  |  Diff: $($r.DiffKB) KB" -ForegroundColor Gray
    Write-Host "       -> $($r.LocalPath)" -ForegroundColor DarkGray
    Write-Host ""
    
    if ($r.Action -eq "COPY" -or $r.Action -eq "NEW") { $toCopy += $r }
    if ($r.Action -eq "REVIEW") { $toReview += $r }
}

Write-Host "========================================================================" -ForegroundColor White
Write-Host "  Summary: $($toCopy.Count) to COPY | $($toReview.Count) to REVIEW | $($results.Count) total" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor White
Write-Host ""

# === STEP 5: Copy files ===
if ($DryRun) {
    Write-Host "  DRY RUN mode — no files copied." -ForegroundColor Yellow
    exit 0
}

if ($toCopy.Count -eq 0) {
    Write-Host "  Nothing to copy — local files are up to date!" -ForegroundColor Green
    exit 0
}

if (-not $AutoCopy) {
    Write-Host "  Copy $($toCopy.Count) files? (Y/N): " -ForegroundColor Yellow -NoNewline
    $confirm = Read-Host
    if ($confirm -ne 'Y' -and $confirm -ne 'y') {
        Write-Host "  Cancelled." -ForegroundColor Red
        exit 0
    }
}

Write-Host ""
$copied = 0
foreach ($r in $toCopy) {
    try {
        # Create backup of existing file
        if (Test-Path $r.LocalFull) {
            $backupDir = Join-Path $BASE "Pricing_Engine\data\_backup"
            if (-not (Test-Path $backupDir)) { New-Item -Path $backupDir -ItemType Directory -Force | Out-Null }
            $backupName = "$($r.FileName).before_sync_$(Get-Date -Format 'yyyyMMdd_HHmm')"
            Copy-Item -Path $r.LocalFull -Destination (Join-Path $backupDir $backupName) -Force
            Write-Host "  Backed up: $($r.FileName)" -ForegroundColor DarkGray
        }
        
        # Ensure target directory exists
        $targetDir = Split-Path $r.LocalFull -Parent
        if (-not (Test-Path $targetDir)) { New-Item -Path $targetDir -ItemType Directory -Force | Out-Null }
        
        # Copy from cloud
        Copy-Item -Path $r.CloudFull -Destination $r.LocalFull -Force
        Write-Host "  COPIED: $($r.FileName) ($($r.CloudKB) KB)" -ForegroundColor Green
        $copied++
    }
    catch {
        Write-Host "  FAILED: $($r.FileName) — $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "  Done! $copied/$($toCopy.Count) files synced successfully." -ForegroundColor Green
Write-Host ""
