# Setup PC Home — FreightBrian Clone

**Mục tiêu:** PC Home có setup identical với Laptop VP. Ban đầu Task Scheduler OFF (Laptop vẫn chạy). Khi Nelson chuyển về làm PC Home full-time → disable Laptop task, enable PC Home task.

**Thời gian:** ~20-30 phút (gồm sync OneDrive).

---

## ✅ Prerequisites Checklist

Trên PC Home kiểm tra trước:

```powershell
git --version          # ≥ 2.40
python --version       # Python 3.11 (anaconda recommended)
ssh -T git@github.com  # "Hi nelsonhuynhs-ship-it!"
```

Nếu SSH chưa config:
```powershell
ssh-keygen -t ed25519 -C "pchome@nelson" -f $env:USERPROFILE\.ssh\id_pchome
Get-Content $env:USERPROFILE\.ssh\id_pchome.pub
# Copy output → GitHub Settings → SSH Keys → New SSH key
```

---

## 🚀 Setup Steps

### Step 1 — Clone repo

```powershell
cd "D:/NELSON/2. Areas"
git clone git@github.com:nelsonhuynhs-ship-it/FrieghtBrian.git Engine_test
cd Engine_test
git log --oneline -3
# Verify thấy: "chore(plans): archive completed + cleanup orphan files"
```

### Step 2 — Install Python dependencies

```powershell
pip install pandas openpyxl fastapi uvicorn filelock holidays rapidfuzz pywin32 python-dateutil pydantic xlrd duckdb apscheduler requests python-dotenv
```

### Step 3 — Copy secrets từ Laptop VP

**2 file `.env` KHÔNG có trên GitHub:**
- `email_engine/.env` — SMTP Office 365 config
- `api/.env` — JWT secrets

**Cách copy nhanh:**
1. Trên Laptop: zip 2 file trên
2. Upload lên OneDrive/email cá nhân
3. Download ở PC Home → unzip vào đúng path

Hoặc share via AirDrop/USB 1 lần.

### Step 4 — Setup Windows env vars

```powershell
# Chạy với admin (Machine scope):
setx BOT_TOKEN "8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys" /M
setx ADMIN_CHAT_ID "5398948978" /M
# Restart terminal để load env mới
```

### Step 5 — Verify OneDrive sync

```powershell
Get-Item "D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx"
# Size ~16MB → OK
Get-Item "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"
# Size ~1-2GB → OK
```

Nếu OneDrive chưa sync: mở OneDrive app → sign-in → chờ 10-30 phút pull full folder `NelsonData`.

### Step 6 — Test web_server

```powershell
cd "D:/NELSON/2. Areas/Engine_test/email_engine"
python web_server.py
# Open browser: http://localhost:8100/api/send-stats
# Expect: {"total":22842,"unsent":18440,...}
```

Nếu OK → Ctrl+C kill. Chuyển sang pythonw hidden (Step 7).

### Step 7 — Create Desktop shortcut

Copy shortcut template từ Laptop:
- Target: `D:\NELSON\2. Areas\Engine_test\email_engine\start-dashboard-v4.bat`
- Working dir: `D:\NELSON\2. Areas\Engine_test\email_engine`
- Icon: tùy chọn

Test double-click → CMD mở title "NELSON EMAIL DASHBOARD v6" + browser auto mở `email-dashboard-v6.html`.

### Step 8 — Task Scheduler (KHÔNG register đến khi switch)

**Mặc định OFF:** Vì Laptop đang chạy `NelsonEmailRotation` 8AM daily.

**Khi Nelson sẵn sàng switch sang PC Home:**

```powershell
# Ở LAPTOP: disable task (không xóa)
schtasks /Change /TN "NelsonEmailRotation" /DISABLE

# Ở PC HOME: register task mới
schtasks /Create /TN "NelsonEmailRotation" `
  /TR "D:\NELSON\2. Areas\Engine_test\scripts\daily-rotation-trigger.bat" `
  /SC DAILY /ST 08:00 /RU Nelson
```

Verify: `schtasks /Query /TN "NelsonEmailRotation"`.

### Step 9 — Set Machine env var để shared.paths detect

```powershell
# PC Home identify itself to shared/paths.py
setx NELSON_MACHINE "pc-home" /M
```

Check `shared/paths.py:MACHINE` resolve đúng khi Python start.

---

## 🔐 Critical — Outlook COM config

Email gửi **qua Outlook COM** (không phải SMTP admin):
- Outlook Desktop app phải đã install + signed in với `nelson@pudongprime.vn`
- Click "Stay signed in" để Outlook không prompt khi worker gọi
- Test gửi 1 email manual trong Outlook trước khi chạy worker

Worker `outlook_queue_worker.py` dùng `win32com.client.Dispatch("Outlook.Application")` → requires Outlook running.

---

## ⚠ Avoid duplicate send

**Chỉ 1 máy chạy Task Scheduler tại 1 thời điểm.**

**State tracking:**
- Laptop đang primary → PC Home task DISABLED
- Khi switch → PC Home primary → Laptop task DISABLED

**Rule:** Trước khi enable PC Home task, verify Laptop đã disable:
```powershell
# SSH hoặc remote vào Laptop:
schtasks /Query /TN "NelsonEmailRotation" | Select-String "State"
# Expect: "State: Disabled"
```

---

## 📋 Verification Checklist (sau khi xong 9 steps)

- [ ] `git log` cho thấy commit mới nhất giống Laptop
- [ ] `python web_server.py` chạy không lỗi
- [ ] `curl http://localhost:8100/api/send-stats` trả total=22842
- [ ] Desktop shortcut mở browser + CMD
- [ ] `ls D:/OneDrive/NelsonData/email/` thấy đầy đủ file
- [ ] Task Scheduler PC Home DISABLED (Laptop vẫn chạy)
- [ ] BOT_TOKEN + ADMIN_CHAT_ID env vars set
- [ ] Outlook Desktop đã sign-in

---

## 🔄 Daily sync workflow (cả 2 máy)

**Trên máy đang dev (thay đổi code):**
```powershell
git add <files>
git commit -m "feat: ..."
git push origin main
```

**Trên máy kia (pull latest):**
```powershell
cd "D:/NELSON/2. Areas/Engine_test"
git pull origin main
# Restart web_server để load code mới
```

**Data (xlsx/parquet):** OneDrive tự sync — không cần làm gì.

---

## 🆘 Troubleshooting

| Issue | Fix |
|---|---|
| `git clone` permission denied | Check SSH key added to GitHub |
| `ImportError: No module X` | `pip install <X>` — check step 2 list |
| `FileNotFoundError: contact_unified_v6.xlsx` | Wait OneDrive sync finished |
| Port 8100 already in use | `Get-Process pythonw \| Stop-Process` |
| Task Scheduler "Access denied" | Run powershell as Administrator |
| Outlook COM "Class not registered" | Open Outlook Desktop + sign-in first |

---

## 🎯 Khi Nelson chính thức chuyển sang PC Home

1. Ở Laptop VP: disable task scheduler, đóng dashboard
2. Ở PC Home: enable task scheduler, start dashboard
3. Verify 1 ngày: 8AM next day → PC Home chạy 700 email batch → check Telegram ping
4. Nếu OK 3 ngày liên tiếp → Laptop chỉ dùng monitor read-only (pull code, không push)
