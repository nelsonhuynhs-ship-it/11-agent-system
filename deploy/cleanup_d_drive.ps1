# cleanup_d_drive.ps1
# Nelson Freight - Cleanup D:\NELSON (safe version)
# Chạy theo từng PHASE - anh confirm từng bước
#
# Usage:
#   -Audit    : chỉ báo cáo, không xóa gì
#   -Phase1   : xóa Engine_test trên D: (đã có đầy đủ trên C:)
#   -Phase2   : xóa Engine, Raw, Assets, GW_Raw, LCC cũ
#   -Phase3   : xóa PricingSystem root files cũ (sau khi confirm đã có C:)
#
# KHÔNG BAO GIỜ đụng: goclaw, TraSuaPOS, OutlookData, Learn

param(
    [switch]$Audit,
    [switch]$Phase1,
    [switch]$Phase2,
    [switch]$Phase3
)

$D_PRICING  = "D:\NELSON\2. Areas\PricingSystem"
$C_PRICING  = "C:\Users\ADMIN\Documents\2. Areas\PricingSystem"
$C_ENGINE   = "$C_PRICING\Engine_test"

function Get-FolderSize($path) {
    if (-not (Test-Path $path)) { return "NOT FOUND" }
    $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    return "$([math]::Round($size/1MB, 1)) MB"
}

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Nelson D: Drive Cleanup" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# ── AUDIT MODE ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[AUDIT] D:\NELSON\2. Areas\PricingSystem breakdown:" -ForegroundColor Yellow

$folders = @("Engine_test","Engine","Data","Raw","Assets","GW_Raw","LCC")
foreach ($f in $folders) {
    $path = "$D_PRICING\$f"
    $size = Get-FolderSize $path
    $lastMod = if (Test-Path $path) {
        (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
    } else { "N/A" }
    Write-Host "  $f : $size | Last: $lastMod"
}

Write-Host ""
Write-Host "[AUDIT] D: root Excel files (check if on C:):" -ForegroundColor Yellow
Get-ChildItem "$D_PRICING" -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in ".xlsx",".xls",".csv",".pdf",".png",".jpg" } | ForEach-Object {
    $onC = Test-Path "$C_ENGINE\$($_.Name)"
    $onC2 = Test-Path "$C_ENGINE\Pricing_Engine\data\$($_.Name)"
    $status = if ($onC -or $onC2) { "✅ có trên C:" } else { "⚠️  CHỈ CÓ TRÊN D:" }
    Write-Host "  $($_.Name) | $status"
}

Write-Host ""
Write-Host "[AUDIT] Parquet size comparison:" -ForegroundColor Yellow
$dParquet = "$D_PRICING\Engine_test\Pricing_Engine\data\Cleaned_Master_History.parquet"
$cParquet = "$C_ENGINE\Pricing_Engine\data\Cleaned_Master_History.parquet"
if (Test-Path $dParquet) { Write-Host "  D: Parquet: $([math]::Round((Get-Item $dParquet).Length/1MB,1)) MB" }
if (Test-Path $cParquet) { Write-Host "  C: Parquet: $([math]::Round((Get-Item $cParquet).Length/1MB,1)) MB" }

if ($Audit) {
    Write-Host ""
    Write-Host "Audit complete. Chạy với -Phase1, -Phase2, -Phase3 để xóa." -ForegroundColor Cyan
    exit 0
}

# ── PHASE 1: Xóa Engine_test trên D: ─────────────────────────────────────────
if ($Phase1) {
    $target = "$D_PRICING\Engine_test"
    Write-Host ""
    Write-Host "[PHASE 1] Xóa D:\...\PricingSystem\Engine_test" -ForegroundColor Yellow
    Write-Host "  Size: $(Get-FolderSize $target)"
    Write-Host "  C: có: $((Get-ChildItem $C_ENGINE -Recurse -File -ErrorAction SilentlyContinue).Count) files"
    Write-Host ""
    $confirm = Read-Host "Confirm xóa? (yes/no)"
    if ($confirm -eq "yes") {
        Remove-Item $target -Recurse -Force
        Write-Host "  ✅ Đã xóa: $target" -ForegroundColor Green
    } else {
        Write-Host "  Skipped." -ForegroundColor Gray
    }
}

# ── PHASE 2: Xóa Engine, Raw, Assets, GW_Raw, LCC ────────────────────────────
if ($Phase2) {
    $targets = @("Engine","Raw","Assets","GW_Raw","LCC")
    Write-Host ""
    Write-Host "[PHASE 2] Xóa các folder cũ: Engine, Raw, Assets, GW_Raw, LCC" -ForegroundColor Yellow
    foreach ($f in $targets) {
        $path = "$D_PRICING\$f"
        if (Test-Path $path) {
            Write-Host "  $f : $(Get-FolderSize $path)"
        }
    }
    Write-Host ""
    $confirm = Read-Host "Confirm xóa tất cả? (yes/no)"
    if ($confirm -eq "yes") {
        foreach ($f in $targets) {
            $path = "$D_PRICING\$f"
            if (Test-Path $path) {
                Remove-Item $path -Recurse -Force
                Write-Host "  ✅ Đã xóa: $path" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "  Skipped." -ForegroundColor Gray
    }
}

# ── PHASE 3: Xóa root Excel/PDF files trên D:\PricingSystem ──────────────────
if ($Phase3) {
    Write-Host ""
    Write-Host "[PHASE 3] Xóa root files trên D:\PricingSystem" -ForegroundColor Yellow
    Write-Host "  CHỈ xóa nếu đã confirm có trên C:" -ForegroundColor Yellow
    $files = Get-ChildItem "$D_PRICING" -File -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        Write-Host "  - $($f.Name)"
    }
    Write-Host ""
    $confirm = Read-Host "Confirm xóa tất cả root files? (yes/no)"
    if ($confirm -eq "yes") {
        foreach ($f in $files) {
            Remove-Item $f.FullName -Force
            Write-Host "  ✅ Xóa: $($f.Name)" -ForegroundColor Green
        }
    } else {
        Write-Host "  Skipped." -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Done! Remaining D: size:"
Write-Host "  PricingSystem: $(Get-FolderSize $D_PRICING)"
Write-Host "===========================================" -ForegroundColor Cyan
