# Email Engine — Freight Forwarding Operations OS
> Version: 2.0 | Last updated: 2026-03-13 | Author: Nelson (Pudong Prime)

Hệ thống tự động xử lý email vận hành logistics, theo dõi vòng đời lô hàng, phân loại khách hàng, và cảnh báo qua Telegram.

---

## 🗺️ Tổng quan hệ thống

```
Outlook Inbox
     │
     ▼
[main.py]                  ← Email routing + CC compliance (chạy mỗi 30 phút)
     │  Routes to TEAM SUNNY folders
     ▼
[shipment_brain.py]        ← Scan email, extract HBL/BKG, track lifecycle, fire alerts
     │  Updates
     ▼
[shipment_state.json]      ← Persistent state: mỗi lô hàng + stage + risk history
     │  Reads for
     ▼
[ops_briefing.py]          ← Daily 08:00 Telegram summary 🔴/🟡/🟢
```

---

## 📁 Cấu trúc thư mục

```
D:\NELSON\email_engine\
│
├── 📋 CONFIG (quan trọng nhất)
│   ├── rules.json               ← Org chart: Team Sunny, routing logic
│   ├── rules.yaml               ← Lifecycle keywords (phiên bản cũ)
│   ├── customer_rules.json      ← ✅ MỚI: Khách hàng + SLA + email domain
│   └── shipment_patterns.yaml  ← ✅ MỚI: Identifier regex + lifecycle patterns
│
├── 🧠 CORE SCRIPTS
│   ├── main.py                  ← Email router + CC checker (ĐỪNG SỬA bừa)
│   ├── follow_up_engine.py      ← Follow-up alerts theo SLA
│   ├── shipment_brain.py        ← ✅ MỚI: Shipment intelligence layer
│   └── ops_briefing.py          ← ✅ MỚI: Daily Telegram briefing
│
├── 🛠️ TOOLS & UTILITIES
│   ├── scan_outlook_folders.py  ← ✅ MỚI: Export .msg files từ Outlook folders
│   ├── _parse_msg_files.py      ← Parse .msg → JSON dataset
│   └── notify.py                ← Windows toast notifications
│
├── 📊 DATA
│   ├── shipment_state.json      ← ✅ MỚI: Auto-generated, persistent state
│   ├── outlook_dataset.json     ← ✅ MỚI: 535 emails analyzed dataset
│   └── customer_final.xlsx      ← CRM data (cho follow_up_engine.py)
│
├── 📬 EMAIL EXPORTS
│   └── outlook/
│       ├── FWD/
│       │   ├── SIRI/            ← 50 .msg files
│       │   ├── HML/             ← 50 .msg files
│       │   └── PANDA GROUP|HN|BN/ ← 135 .msg files
│       ├── DIRECT/
│       │   ├── NAFOOD/          ← 50 .msg files
│       │   ├── PT FOOD/         ← 50 .msg files
│       │   ├── VINARES/         ← 100 .msg files
│       │   ├── HER HUI WOOD/    ← 50 .msg files
│       │   └── CREATIVE LIGHT/  ← 50 .msg files
│       └── backup.pst           ← Full Outlook backup (1.9 GB)
│
├── 📝 LOGS
│   ├── email_engine.log         ← main.py log
│   ├── shipment_brain.log       ← ✅ MỚI: Brain scan log
│   └── scan_folders.log         ← Folder scan log
│
└── ⚙️ SCHEDULER SETUP
    ├── setup_task_scheduler.ps1 ← Main email engine task (đã active)
    └── setup_brain_scheduler.ps1 ← ✅ MỚI: Brain + Briefing tasks (chưa chạy)
```

---

## 🔧 Requirements

### Python packages (đã có sẵn)
```
pip install pywin32 pyyaml httpx extract-msg openpyxl pandas
```

### Kiểm tra nhanh
```bash
python -c "import win32com.client, yaml, httpx, extract_msg, openpyxl; print('OK')"
```

### System Requirements
- ✅ Windows 10/11
- ✅ Microsoft Outlook (phải đang mở khi script chạy)
- ✅ Python 3.10+ (Anaconda)
- ✅ Telegram Bot Token + Chat ID

---

## 🚀 Setup từ đầu (PC mới / Home PC)

### 1. Clone / Copy source về
```
Copy toàn bộ D:\NELSON\email_engine\ → OneDrive hoặc USB
Tại PC nhà: giải nén vào cùng đường dẫn D:\NELSON\email_engine\
```

### 2. Cài Python packages
```powershell
pip install pywin32 pyyaml httpx extract-msg openpyxl pandas
```

### 3. Cấu hình Telegram
```powershell
# Chạy PowerShell as Admin, thay YOUR_TOKEN và YOUR_CHAT_ID
[System.Environment]::SetEnvironmentVariable("TELEGRAM_TOKEN", "YOUR_TOKEN", "User")
[System.Environment]::SetEnvironmentVariable("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID", "User")
```
> **Lấy Token:** Chat với `@BotFather` → `/newbot`
> **Lấy Chat ID:** Chat với `@userinfobot` → copy ID

### 4. Đăng ký Task Scheduler
```powershell
# Task chính (email routing) - đã có sẵn
PowerShell -ExecutionPolicy Bypass -File "D:\NELSON\email_engine\setup_task_scheduler.ps1"

# Task Shipment Brain + Daily Briefing - MỚI
PowerShell -ExecutionPolicy Bypass -File "D:\NELSON\email_engine\setup_brain_scheduler.ps1"
```

### 5. Test chạy thử
```powershell
# Test shipment brain (không gửi Telegram nếu chưa config)
python "D:\NELSON\email_engine\shipment_brain.py"

# Test ops briefing
python "D:\NELSON\email_engine\ops_briefing.py"
```

---

## 🗂️ Customer Classification

| Customer | Type | SLA | Outlook Folder | Ghi chú |
|----------|------|-----|----------------|---------|
| NAFOOD | DIRECT | 2h | `DIRECT/NAFOOD` | Reefer (20RF), route HCM-AUS |
| PT FOOD | DIRECT | 2h | `DIRECT/PT FOOD` | |
| VINARES | DIRECT | 2h | `DIRECT/Vinares` | HPH-Canada |
| HER HUI WOOD | DIRECT | 2h | `DIRECT/HER HUI WOOD` | |
| CREATIVE LIGHT | DIRECT | 2h | `DIRECT/CREATIVE LIGHT` | HPH-LAX |
| SIRI | FWD | 4h | `FWD/SIRI LOG` | |
| HML | FWD | 4h | `FWD/HML` | 3759 emails! |
| PANDA | FWD | 4h | `FWD/PANDA GROUP` + `PANDA HN` + `PANDA BN` | 3 offices |

---

## 🔄 Lifecycle Stages (từ real email data)

```
BOOKING_CONFIRMED → SI_SUBMITTED → DRAFT_BL_ISSUED → DRAFT_BL_CONFIRMED
→ LOADED → ATD → ETA_UPDATE → DN_SENT → INVOICE_ISSUED → PAYMENT_CONFIRMED
```

**Risk stages (parallel, không theo thứ tự):**
- `DELAY_NOTICE` → 🟡 Watch
- `CHANGE_VESSEL` → 🔴 Action Required

### Stage distribution từ 535 emails thực tế:
```
DRAFT_BL_ISSUED     205 occurrences  ← keyword: "draft b_l", "draft b/l"
DN_SENT             144              ← keyword: "dn __", "debit //"
ATD                 112              ← keyword: "atd__", "update atd"
DELAY_NOTICE        109              ← keyword: "delay notice", "rollover"
CHANGE_VESSEL        71              ← keyword: "change vessel"
INVOICE_ISSUED       45              ← keyword: "invoice"
PAYMENT_CONFIRMED    17              ← keyword: "payment received", "đã thanh toán"
```

---

## 📡 HBL Identifier Patterns (đã học từ email thực)

| Pattern | Regex | Ví dụ | Carrier |
|---------|-------|-------|---------|
| ONE/Hapag | `P[A-Z]{3}\d{7,12}` | PNYC26010385 | ONE / Hapag |
| CMA/Pelican | `PELP\d{7,12}` | PELP26030260 | CMA CGM |
| ZIM | `ZIMU(HCM\|HAI\|SGN)\d{8,}` | ZIMUHCM80610801 | ZIM |
| Evergreen | `ESLV[A-Z0-9]{5,15}` | ESLVNESAL003946 | Evergreen |
| Yang Ming | `HANG\d{8,12}` | HANG17369900 | Yang Ming |
| Hapag MAPI | `HLCU[A-Z]{3}\d{9,}` | HLCUBKK2602... | Hapag |
| BKG generic | `BKG[\s#]*([A-Z0-9]{5,12})` | BKG 14380157 | Any |
| Nafood EBKG | `EBKG\d{8,12}` | EBKG14870911 | MSC |

---

## 🚧 ROADMAP — Những gì cần làm tiếp

### 🔲 Cấp thiết (làm ngay)
- [ ] **Cấu hình Telegram** — set `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID`
- [ ] **Chạy `setup_brain_scheduler.ps1`** — đăng ký Task Scheduler
- [ ] **Test end-to-end**: gửi email test → check `shipment_state.json` → check Telegram

### 🔲 Phase 2 — SLA Monitor
File: `sla_monitor.py`
- Scan DIRECT customer folders mỗi 30 phút
- Nếu có email mới từ DIRECT customer mà sau 2h chưa có reply → Telegram alert
- Đọc `customer_rules.json` để lấy `sla_hours` theo từng khách

### 🔲 Phase 2 — CC Violation Telegram Alert
File: `main.py` → function `check_cc_compliance()`
- Thêm `send_telegram()` call khi phát hiện CC violation
- Hiện tại chỉ log WARNING, chưa gửi Telegram
- Thấy trong log: Blue và Johnny hay bị miss CC Brian

### 🔲 Phase 3 — Enrich shipment_state.json
- Kết nối với `Jobs_Master.xlsx` để link shipment IDs → actual job records
- Thêm field: `job_number`, `etd_actual`, `vessel_name`, `pod`
- Checkout: `ERP\scripts\refresh_erp_data.py`

### 🔲 Phase 4 — Web Dashboard (Optional)
- Simple Flask/FastAPI dashboard hiển thị `shipment_state.json`
- Bảng lô hàng theo stage, filter by customer, risk highlight

---

## ⚠️ Rules & Warnings

> **ĐỪNG SỬA** `main.py` và `QuoteJobWorkflow.bas` trực tiếp
> → Đọc `/erp-code-rules` workflow trước

> **backup.pst** (1.9 GB) — KHÔNG upload lên OneDrive (quá lớn, chậm)
> → Chỉ sync source code `.py`, `.json`, `.yaml`, `.md` files

> **shipment_state.json** — File này tự grow theo thời gian
> → Nên backup định kỳ, không xóa (là source of truth cho toàn bộ lô hàng)

---

## 📞 Contacts (từ email data)

| Email | Người | Role |
|-------|-------|------|
| isabel@pudongprime.vn | Isabel Vo | Ops team (CS/Doc) |
| accounting4@pudongprime.vn | Crystal Huyen | Kế toán chính |
| nelson@pudongprime.vn | Nelson | Manager |
| zoe.nguyen@panda4u.com | Zoe Nguyen | PANDA contact |

---

## 🔗 Related Systems

| System | Location | Script |
|--------|----------|--------|
| Pricing Engine | `D:\NELSON\2. Areas\PricingSystem\Engine_test\` | `run_all.py` |
| ERP (Excel) | `D:\NELSON\2. Areas\ERP\` | `refresh_erp_data.py` |
| CRM | `D:\NELSON\2. Areas\CRM\scripts\` | 7 scripts |
| Email Engine | `D:\NELSON\email_engine\` | `main.py` |