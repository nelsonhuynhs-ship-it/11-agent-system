# 🔍 Nelson Freight System Audit — 2026-04-21

**Run date:** 2026-04-21 16:22
**Duration:** ~10 min
**Scope:** Architecture + file storage + email/scanner runtime + task scheduler

---

## 📊 Tóm tắt 1 dòng

Architecture **9.2/10** (rất tốt), scanner task **chạy đều và SUCCESS** (không silent-fail như em nghĩ trước), nhưng **shipment_brain sub-job dường như không process events mới từ 13/04**. File storage 2 tier rõ ràng: OneDrive = master data, local = runtime state.

---

## 1️⃣ Architecture Health (skill nelson-system-audit)

| Layer | Score | Findings |
|-------|-------|----------|
| Data Layer | 8.5/10 | 🔴 No `data_access.py` DAL — modules access data directly |
| API Layer | 10/10 | ✅ Clean |
| Service Layer | 9.5/10 | 🟢 Target router structure partial (11 files missing theo blueprint) |
| Client Isolation | 10/10 | ✅ Clean |
| Event System | 10/10 | ✅ Clean |
| Security | 7/10 | 🔴 No auth system | 🟡 No RBAC |
| **Total** | **9.2/10** | **Conforms to blueprint** |

**Drift:** 0 violations
**Tech debt:** 0 (nhưng skill scan tự động — không bắt được VBA dead code đã biết)

---

## 2️⃣ File Storage Map (where everything lives)

### OneDrive = MASTER DATA (sync cross-machine)

```
D:/OneDrive/NelsonData/
├── erp/                              ← ERP xlsm + VBA source
│   ├── ERP_Master_v14.xlsm           2.14 MB, LIVE
│   ├── ERP_Master_v14.backup_*       5 backups (rotation)
│   ├── erp-v14-*.bas                 5 VBA modules (canonical source)
│   ├── CustomUI_v14.xml              Ribbon XML
│   ├── Jobs_Master.xlsx              Legacy
│   ├── Quote_History.xlsx            Legacy
│   └── refresh_*.txt                 VBA click logs + chain logs
│
├── email/                            ← Email MASTER data
│   ├── cnee_master_v2_final.xlsx     ⭐ MASTER 22,230 CNEE (26 cols)
│   ├── cnee_master.xlsx              (legacy v1)
│   ├── cnee_master_v2.xlsx           (legacy v2)
│   ├── customer_rules.json           ⭐ Customer sort rules
│   ├── customer_rules_v2.json        (legacy)
│   ├── rules.json / rules.yaml       Legacy rules
│   ├── shipment_patterns.yaml        ⭐ Regex patterns
│   ├── shipper_master.xlsx           Shipper list
│   ├── contact_master.xlsx           Contact list
│   ├── Port_Code_Mapping_Final.xlsx  Port codes
│   ├── competitor_blacklist.json     49 domains + 98 keywords
│   ├── replacement_leads.xlsx        Replacement CNEE
│   ├── campaign_runs/                Email send history
│   └── panjiva/                      Panjiva intel
│
├── pricing/                          ← Pricing data
│   ├── Cleaned_Master_History.parquet   ⭐ 6.6M rows
│   ├── Cleaned_Master_History_slim.parquet
│   ├── carrier_rules/                13 carrier configs
│   ├── forecast/ · incoming/ · knowledge/ · mapping/
│   ├── market-reports/ · processed/
│   └── _backup/
│
├── bot/                              ← Telegram bot
│   └── carrier_tips.json
│
├── assets/                           ← Static
└── Data Loc/                         ← Misc
```

### Local = RUNTIME STATE (PC Home only)

```
D:/NELSON/2. Areas/Engine_test/email_engine/data/
├── shipment_state.json               🟡 72 bytes, last-mod 13/04 (8 NGÀY STALE)
├── milestone_state.jsonl             🟡 0 bytes, last-mod 20/04 (empty)
├── shipment_brain.duckdb             ✅ 268 KB, last-mod 18/04 (3 ngày stale)
├── outlook_queue.db (+ wal/shm)      SQLite outlook MAPI cache
├── intel.db (+ wal/shm)              Intelligence cache
├── competitor_blacklist.json         Mirror từ OneDrive
├── excluded_customers.json           Local only
├── send_time_rules.json              Timing rules
├── shipper_master.xlsx               Mirror
├── cnee_master*.xlsx                 Mirror (dev copies)
└── Port_Code_Mapping_Final.xlsx      Mirror
```

---

## 3️⃣ Email Engine Inventory

### Scanner Layer (6 files)
| File | Purpose |
|------|---------|
| `scanner/inbox_scanner.py` | APScheduler in-process, 30min loop, classifier dispatch |
| `scanner/classifier.py` | Bounce / auto-reply / real mail classification |
| `scanner/handlers.py` | Per-class handlers (bounce, reply, real) |
| `scanner/daily_report.py` | 21:00 daily summary |
| `scanner/telegram.py` | Telegram send helper |
| `scanner/__init__.py` | Package init |

### Core Layer (47 modules — quá nhiều!)
**Shipment Intelligence:**
- `shipment_brain.py` ⭐ 11-stage lifecycle detection
- `cnee_memory.py` · `cnee_milestone.py` ⭐ ATD auto-compose
- `smart_compose.py` · `brief_synthesizer.py` · `nelson_briefing.py` · `ops_briefing.py`

**Email processing:**
- `outlook_scanner.py` ⭐ **Main scheduled script** (6 sub-jobs)
- `email_engine.py` · `email_parser.py` · `process_reply.py` · `pst_importer.py`

**Customer/rules:**
- `nelson_customer_sort.py` · `lead_scorer.py` · `follow_up_engine.py`

**Verification:**
- `email_verifier.py` · `email_bulk_verifier.py` · `bounce_handler.py` · `bounce_knowledge.py`

**LLM integrations:**
- `llm_client.py` · `llm_extract_reply.py` · `query_parser.py` · `auto_rate_builder.py`

**Dashboard/data:**
- `data_collector.py` · `data_migrator.py` · `generate_dashboard.py`
- `knowledge_ingest.py` · `rate_parquet_updater.py` · `arb_pricing.py`

**Utilities:**
- `main.py` · `notify.py` · `llm_client.py`

**🟡 Quan sát:** 47 modules trong 1 folder `core/` — vượt rule "<200 LOC/file" và "<10 module/namespace". Đáng cân nhắc refactor grouping thành `shipment/`, `customer/`, `verify/`, `llm/`.

### Web Server Layer
| File | Purpose |
|------|---------|
| `web_server.py` | FastAPI dashboard port 8100 |
| `intel/writeback.py` | Intel state writeback |

---

## 4️⃣ Task Scheduler Windows — Nelson-related

| TaskName | State | Last Run | Next Run | Result | Script |
|----------|-------|----------|----------|--------|--------|
| **NelsonUnifiedScanner** | Ready | **21/04 16:00** | 21/04 16:30 | **0 (SUCCESS)** | `email_engine/core/outlook_scanner.py` |
| NelsonCNEEMilestoneETA7 | Ready | (daily 08:00) | next 08:00 | - | `cnee_milestone eta-reminder` |

**NelsonUnifiedScanner triggers:** 20 lần/ngày (mỗi 30 phút từ 08:00→17:30, daily repeat)
**Sub-jobs trong outlook_scanner.py:**
1. `mentee` → `run_mentee_classification()`
2. `pricing` → `run_pricing_import()`
3. `shipment_brain` → `run_shipment_brain()` ⭐
4. `knowledge_ingest` → `run_knowledge_ingest()`
5. `nelson_customer_sort` → `run_nelson_customer_sort()`
6. `reply_processing` → `run_reply_processing()` (inbox_scanner.run_scan)

---

## 5️⃣ 🚨 ANOMALIES phát hiện

| # | Vấn đề | Severity | Bằng chứng |
|---|--------|----------|-----------|
| 1 | `shipment_state.json` **stale 8 ngày** (cuối 13/04) | 🔴 HIGH | 72 bytes, `{"shipments":{}}` |
| 2 | `milestone_state.jsonl` **empty** (CNEE milestone feature shipped 20/04 nhưng chưa fire) | 🟡 MED | 0 bytes |
| 3 | `shipment_brain.log` + `email_engine.log` **0 bytes** từ 02/04 | 🟡 MED | Logger chưa init hoặc pythonw.exe suppress |
| 4 | Task scheduler LastResult=0 **NHƯNG** sub-job shipment_brain không update state | 🔴 HIGH | Ngụ ý `run_shipment_brain()` return "skip" hoặc fail silently |
| 5 | Duplicate files trong `email_engine/data/` **mirror** OneDrive | 🟢 LOW | cnee_master.xlsx, shipper_master.xlsx trùng 2 nơi — có thể Nelson đang dev dùng local |
| 6 | Legacy v1 files chưa xóa (`cnee_master.xlsx` v1, `customer_rules.json` v1) trong OneDrive | 🟢 LOW | Gây nhầm lẫn nguồn nào là master |
| 7 | 47 modules trong `core/` chưa group | 🟢 LOW | YAGNI/KISS violation — đáng group theo domain |
| 8 | No DAL — audit báo data access direct | 🟢 LOW | Business logic scatter; future hardening |

---

## 6️⃣ Root Cause: Tại sao shipment_brain không update state?

**Hypothesis ranked theo khả năng:**

1. **Scanner CHẠY nhưng không có mail mới cần process** — each run processed all old mail, nothing new since 13/04 vì pattern detection cần exact keyword match và recent Inbox có thể đã mark PROCESSED_FLAG
2. **`run_shipment_brain()` fail silently** — exception swallowed ở line 149-158 outlook_scanner.py (catch broad Exception, chỉ log.error)
3. **Windows schedule trigger 20 lần/ngày nhưng chỉ 1 trigger active** — em thấy triggers chồng lấn, có thể 1 số không fire
4. **Outlook MAPI connection expire sau session Excel đóng** — scanner cần Outlook process running
5. **Logger path sai hoặc permission** — pythonw.exe chạy với user khác nên file log không write được

**Next debug step (mandatory trước khi cook InvoiceLog):**
```bash
# Chạy manual xem exception gì
cd "D:/NELSON/2. Areas/Engine_test/email_engine"
PYTHONIOENCODING=utf-8 python core/outlook_scanner.py --job shipment_brain --dry-run
```

---

## 7️⃣ Khuyến nghị (priority order)

### 🔴 NGAY — trước mọi việc khác
1. **Debug shipment_brain sub-job** (30 phút) — tìm tại sao state.json không update
2. **Verify Outlook process đang chạy** khi scanner trigger — `pythonw.exe` cần COM Outlook alive

### 🟡 TRONG TUẦN
3. **Enforce logging** — thay `pythonw.exe` bằng `python.exe` với `--redirect-output` để log file update
4. **Cleanup duplicate files:** quyết định 1 nơi duy nhất — nếu dev dùng local, add `.gitignore` + docs ghi rõ
5. **Archive legacy files trong OneDrive:** `cnee_master.xlsx` v1, `customer_rules.json` v1 → `_archive/`
6. **Build InvoiceLog đơn giản** (theo design 4 event — không phức tạp)

### 🟢 TƯƠNG LAI
7. Group `email_engine/core/` 47 modules thành subfolders theo domain
8. Thêm DAL `data_access.py` cho data access unified
9. Implement auth + RBAC cho FastAPI (nếu multi-user sau này)

---

## 8️⃣ Files/paths canonical (dùng trong code về sau)

```python
# MASTER data — OneDrive
ERP_XLSM         = "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"
CNEE_MASTER      = "D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx"
PARQUET_MASTER   = "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"
CUSTOMER_RULES   = "D:/OneDrive/NelsonData/email/customer_rules.json"
SHIPMENT_PATTERNS = "D:/OneDrive/NelsonData/email/shipment_patterns.yaml"

# RUNTIME state — local PC Home
SHIPMENT_STATE   = "email_engine/data/shipment_state.json"
MILESTONE_STATE  = "email_engine/data/milestone_state.jsonl"
SHIPMENT_DB      = "email_engine/data/shipment_brain.duckdb"
OUTLOOK_QUEUE    = "email_engine/data/outlook_queue.db"
INTEL_DB         = "email_engine/data/intel.db"

# Path resolver — tất cả code mới DÙNG
from shared.paths import PARQUET_FILE, CNEE_MASTER, MACHINE
```
