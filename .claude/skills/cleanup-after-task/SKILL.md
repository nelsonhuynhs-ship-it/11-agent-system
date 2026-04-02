---
name: cleanup-after-task
description: Dọn dẹp file tạm (inspect, patch, syntax check scripts) sau khi hoàn tất mỗi task. TRIGGER ngay sau khi bot chạy thành công hoặc khi Sếp xác nhận task done. Áp dụng cho bất kỳ file nào được tạo tạm thời để debug, inspect, hoặc patch.
---

# Cleanup After Task — Quy trình Dọn dẹp File Tạm

> **Áp dụng:** Cuối mỗi task có tạo file tạm để debug, patch, hoặc inspect hệ thống.

## Danh sách file cần xóa

**Xóa bất kỳ file nào khớp pattern sau:**

| Pattern | Ví dụ |
|---------|-------|
| `C:\Temp\inspect_*.py` | inspect_erp.py, inspect_jobs.py |
| `C:\Temp\patch_*.py` | patch_bot.py, patch_sprint8_bot.py |
| `C:\Temp\syntax_check*.py` | syntax_check.py |
| `C:\Temp\check_*.py` | check_db.py |
| `/tmp/*.py` (nếu Linux/WSL) | temp_script.py |
| Bất kỳ file nào trong `C:\Temp\` tạo trong session này | — |

## Step 1: Xác định file cần xóa

Trước khi xóa, list ra để xác nhận:

```powershell
Get-ChildItem C:\Temp\*.py | Select-Object Name, LastWriteTime
```

## Step 2: Xóa file tạm

// turbo
```powershell
Get-ChildItem C:\Temp\*.py | Remove-Item -Force
Write-Host "Cleaned up temp files in C:\Temp"
```

## Step 3: Xác nhận sạch

// turbo
```powershell
$remaining = Get-ChildItem C:\Temp\*.py -ErrorAction SilentlyContinue
if ($remaining) { Write-Host "Remaining: $($remaining.Name)" } else { Write-Host "C:\Temp is clean." }
```

## Quy tắc KHÔNG xóa

- ❌ KHÔNG xóa file trong `D:\NELSON\` (production files)
- ❌ KHÔNG xóa file trong `.agent\memory\`, `.agent\workflows\`, `.agent\skills\`
- ❌ KHÔNG xóa file mà Sếp đặt tên cụ thể (không phải auto-generated)
- ✅ Chỉ xóa file trong `C:\Temp\` hoặc `/tmp/` được tạo trong session hiện tại

## Ghi chú cho AI

- Tạo file tạm **luôn** vào `C:\Temp\` hoặc `/tmp/` — không bao giờ vào thư mục production
- Khi task xong, chạy workflow này như bước cuối cùng trước khi báo cáo kết quả
- Thông báo ngắn gọn: "🧹 Đã xóa X file tạm sau task."
