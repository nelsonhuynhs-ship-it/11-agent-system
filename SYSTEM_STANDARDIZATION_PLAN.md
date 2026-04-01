# KẾ HOẠCH CHUẨN HÓA HỆ THỐNG NELSON FREIGHT
**Ngày tạo:** 2026-04-01
**Phiên bản:** 1.0

---

## 1. HIỆN TRẠNG HỆ THỐNG

### Tổng quan
- Tổng dung lượng: 13GB (58% là 1 file backup.pst)
- Tổng file Python: 424
- Tổng file config: 271+ (phân tán nhiều nơi)
- Folder backup/archive: 8 vị trí khác nhau
- Config trùng lặp: 5 instances

### Đánh giá theo module

| Module | Điểm | Vấn đề chính |
|--------|-------|---------------|
| api/ | 9/10 | Sạch, tổ chức tốt |
| intelligence/ | 9/10 | Gọn, đúng mục đích |
| .planning/ | 9/10 | Sạch |
| ERP/ | 8/10 | Modular tốt |
| db/ | 8/10 | Gọn |
| deploy/ | 7/10 | Script phân tán |
| webapp/ | 6/10 | .next + node_modules chưa gitignore đúng |
| Pricing_Engine/ | 6/10 | File deprecated, folder rỗng |
| TelegramBot/ | 6/10 | bot_v5.py 92KB monolith, log cũ |
| .agent/ | 4/10 | gsd-local-patches trùng 2.1M |
| email_engine/ | 3/10 | 121 backup Excel, config trùng 3 nơi, backup.pst 7.6GB |
| _archive/ | 1/10 | Toàn code cũ không dùng |

---

## 2. PHASE 1 — DỌN RÁC (Tuần 1, ước tính thu hồi ~8GB)

### 2.1 Xóa file lớn không cần thiết
```
[ ] email_engine/backup.pst (7.6GB) → Move ra ổ cứng ngoài hoặc OneDrive
[ ] email_engine/backup/ → Giữ 1 file mới nhất, xóa 120 file còn lại (~40MB)
[ ] email_engine/_backup/ → Xóa (14MB)
[ ] email_engine/_archived_schedulers/ → Xóa (12K)
[ ] email_engine/_archive/ → Xóa (44K)
```

### 2.2 Xóa folder archive/legacy
```
[ ] _archive/erp_versions/ (9.3M) → Xóa, đã có trong git history
[ ] _archive/erp_legacy/ (404K) → Xóa
[ ] _archive/pre_phase6_snapshot/ (1.3M) → Xóa
[ ] _archive/streamlit_app/ (780K) → Xóa
[ ] _archive/stale_root/ (96K) → Xóa
```

### 2.3 Xóa file trùng lặp
```
[ ] .agent/gsd-local-patches/ (2.1M) → Xóa, trùng với get-shit-done/
[ ] .agent/backup/ (50+ file timestamp) → Xóa, dùng git history
[ ] email_engine/data/config.xlsx → Xóa, giữ email_engine/config/config.xlsx
[ ] TelegramBot/config.py.local_backup → Xóa
```

### 2.4 Xóa folder rỗng & file deprecated
```
[ ] Pricing_Engine/Backup_parquet/ → Xóa (rỗng)
[ ] Pricing_Engine/scripts/master_loader_v2.py → Xóa (DEPRECATED)
[ ] Pricing_Engine/scripts/refresh_erp_from_parquet_BACKUP_pre_v13.py → Xóa
[ ] api/_archive/_DEPRECATED_server.py → Xóa
[ ] TelegramBot/_archive/bot.py → Xóa
```

### 2.5 Dọn log cũ
```
[ ] TelegramBot/logs/bot.log, bot_v4.log → Xóa
[ ] .agent/listener/listener.log → Xóa
[ ] email_engine/logs/*.log → Xóa log cũ hơn 7 ngày
```

### 2.6 Cập nhật .gitignore
```gitignore
# Build artifacts
webapp/.next/
webapp/node_modules/

# Environment
**/.env
**/.env.local
**/.env.production
!**/.env.example
!**/.env.template

# Logs
**/logs/*.log
**/logs/*.csv
**/*.log

# Backups (dùng git history thay vì backup thủ công)
**/_backup/
**/_archive/
**/Backup_parquet/

# Large data
*.pst
*.pst.bak

# Python
**/__pycache__/
*.pyc

# External skills (dùng submodule)
claudekit-skills/
```

---

## 3. PHASE 2 — CHUẨN HÓA CẤU TRÚC (Tuần 2)

### 3.1 Cấu trúc folder đề xuất

```
Engine_test/                          # Root
├── api/                              # FastAPI Backend (GIỮ NGUYÊN - đã tốt)
│   ├── routers/
│   ├── services/
│   ├── middleware/
│   ├── workers/
│   ├── database/
│   └── config.py
│
├── webapp/                           # Next.js Frontend (GIỮ NGUYÊN)
│   ├── src/
│   ├── public/
│   └── package.json
│
├── TelegramBot/                      # Chatbot (CẦN REFACTOR)
│   ├── core/                         # Bot core logic (tách từ bot_v5.py)
│   │   ├── bot.py                    # Main bot entry
│   │   ├── handlers/                 # Command handlers
│   │   ├── ai/                       # AI/Gemini integration
│   │   └── memory/                   # Oracle memory
│   ├── features/                     # Feature modules
│   │   ├── pricing/
│   │   ├── sales/
│   │   └── analytics/
│   ├── config.py
│   └── .env
│
├── email_engine/                     # Email System (CẦN TỔ CHỨC LẠI)
│   ├── core/                         # Core processing
│   ├── config/                       # CHỈ 1 NƠI config
│   │   └── config.xlsx
│   ├── templates/                    # Email templates
│   ├── data/                         # Runtime data (KHÔNG config)
│   ├── logs/                         # Logs (auto-rotate 7 ngày)
│   └── .env
│
├── ERP/                              # ERP System (GIỮ NGUYÊN - đã tốt)
│   ├── core/
│   ├── crm/
│   ├── intelligence/
│   ├── jobs/
│   ├── quotes/
│   ├── carrier_rules/
│   └── vba/
│
├── Pricing_Engine/                   # Pricing (DỌN DẸP)
│   ├── importers/                    # rate_importer, puc_importer
│   ├── monitors/                     # rate_monitor, parquet_auditor
│   ├── data/                         # Parquet files
│   ├── config/                       # Mapping files
│   └── scripts/                      # Utility scripts (chỉ active)
│
├── intelligence/                     # Analytics (GIỮ NGUYÊN)
├── db/                               # Database utils (GIỮ NGUYÊN)
│
├── deploy/                           # Deployment (GOM VỀ 1 NƠI)
│   ├── deploy_vps.bat                # 1-click deploy PC
│   ├── deploy.sh                     # VPS deploy script (copy trên VPS)
│   ├── .env.template
│   └── setup/                        # One-time setup scripts
│       ├── setup_vps_full.sh
│       └── setup_github_key.sh
│
├── tests/                            # Tests (MỞ RỘNG)
│   ├── api/
│   ├── email_engine/
│   ├── pricing/
│   └── conftest.py
│
├── .claude/                          # Claude Code Skills
│   ├── skills/                       # 44 ClaudeKit skills + custom skills
│   └── commands/                     # Git + skill commands
│
├── .agent/                           # Agent Framework (DỌN DẸP)
│   ├── handoff.md
│   ├── agents/
│   ├── memory/
│   └── get-shit-done/                # GSD framework (CHỈ 1 BẢN)
│
├── .planning/                        # Project docs (GIỮ NGUYÊN)
├── CLAUDE.md                         # AI instructions
├── .gitignore                        # Cập nhật mới
└── requirements.txt                  # Python deps tập trung
```

### 3.2 Config tập trung

**Nguyên tắc:** Mỗi module CHỈ có 1 file config, 1 file .env

| Module | Config | .env |
|--------|--------|------|
| api/ | api/config.py | api/.env |
| webapp/ | webapp/next.config.ts | webapp/.env.local |
| TelegramBot/ | TelegramBot/config.py | TelegramBot/.env |
| email_engine/ | email_engine/config/config.xlsx | email_engine/.env |
| deploy/ | deploy/.env.template | (template only) |

### 3.3 Logging chuẩn hóa

Tất cả module dùng chung format:
```python
# Mỗi module tạo logger riêng
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    f"logs/{module_name}.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=3           # Giữ max 3 file
)
```

---

## 4. PHASE 3 — REFACTOR CODE (Tuần 3-4)

### 4.1 TelegramBot — Tách bot_v5.py (92KB monolith)

**Hiện tại:** 1 file 92KB chứa mọi thứ
**Mục tiêu:** Tách thành modules

```
bot_v5.py (92KB) → Tách thành:
├── core/bot.py              # Main bot, start/stop, middleware
├── core/handlers/
│   ├── command_handler.py   # /start, /help, /menu commands
│   ├── message_handler.py   # Text message routing
│   └── callback_handler.py  # Inline button callbacks
├── core/ai/
│   ├── gemini_client.py     # Gemini API wrapper
│   └── context_manager.py   # Conversation context, Oracle
├── features/
│   ├── pricing.py           # Rate lookup, price check
│   ├── sales.py             # Sales intelligence
│   ├── risk.py              # Risk analysis
│   └── analytics.py         # Usage analytics
└── utils/
    ├── formatters.py        # Message formatting
    └── validators.py        # Input validation
```

### 4.2 email_engine — Gom config, xóa backup

```
Việc cần làm:
[ ] Xóa backup.pst → chuyển sang OneDrive/external
[ ] Xóa 120/121 file backup Excel
[ ] Gom config về 1 nơi: email_engine/config/
[ ] Xóa _backup/, _archive/, _archived_schedulers/
[ ] Thêm log rotation cho tất cả log files
```

### 4.3 Pricing_Engine — Dọn deprecated

```
[ ] Xóa master_loader_v2.py (DEPRECATED)
[ ] Xóa refresh_erp_from_parquet_BACKUP_pre_v13.py
[ ] Xóa Backup_parquet/ (rỗng)
[ ] Kiểm tra OCR_Input/, OCR_Engine/ — xóa nếu không dùng
```

### 4.4 claudekit-skills — Chuyển sang submodule

```bash
# Xóa folder embedded
rm -rf claudekit-skills/

# Thêm như git submodule
git submodule add https://github.com/mrgoonie/claudekit-skills.git .external/claudekit-skills

# Skills đã copy vào .claude/skills/ nên không ảnh hưởng
```

---

## 5. PHASE 4 — HẠ TẦNG & AUTOMATION (Tuần 5-6)

### 5.1 Deploy pipeline chuẩn

```
PC Home: git push → VPS: auto pull + build + restart

Đã hoàn thành:
✅ SSH key không passphrase
✅ deploy.sh trên VPS
✅ deploy_vps.bat trên PC

Cần thêm:
[ ] GitHub Actions CI/CD (auto deploy on push to main)
[ ] Health check endpoint cho mỗi service
[ ] Slack/Telegram notification khi deploy xong
```

### 5.2 Backup strategy

```
Hiện tại: Backup thủ công, file nằm rải rác
Đề xuất:

1. Code: Git là backup duy nhất (không backup thủ công)
2. Data (parquet): Daily backup script → sync to cloud
3. Config (.env): Template trong repo, giá trị thật trên VPS only
4. Email data: Weekly export, giữ max 30 ngày
5. Logs: Auto-rotate 10MB, giữ max 3 files
```

### 5.3 Monitoring & Health checks

```python
# Thêm vào mỗi service
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "nelson-api",
        "version": "1.13.0",
        "timestamp": datetime.now().isoformat()
    }
```

### 5.4 Testing framework

```
[ ] pytest cho API endpoints
[ ] Integration test cho email_engine SMTP
[ ] E2E test cho webapp (Playwright)
[ ] Chạy tests trước mỗi deploy
```

---

## 6. TỔNG KẾT & TIMELINE

| Phase | Thời gian | Công việc chính | Kết quả |
|-------|-----------|-----------------|---------|
| Phase 1 | Tuần 1 | Dọn rác, xóa backup, cập nhật .gitignore | Thu hồi ~8GB, repo sạch |
| Phase 2 | Tuần 2 | Chuẩn hóa folder, gom config, logging | Cấu trúc rõ ràng |
| Phase 3 | Tuần 3-4 | Refactor bot_v5.py, email_engine, Pricing | Code modular, dễ maintain |
| Phase 4 | Tuần 5-6 | CI/CD, health checks, testing, monitoring | Hạ tầng production-ready |

### Ước tính cải thiện

| Metric | Trước | Sau |
|--------|-------|-----|
| Dung lượng repo | 13GB | ~3GB |
| File backup/rác | 200+ | 0 |
| Config locations | 10+ nơi | 5 nơi (1/module) |
| Deploy time | Thủ công 10 phút | 1-click 2 phút |
| Test coverage | ~0% | 60%+ |
| Code clarity | Nhiều file không rõ vai trò | Mỗi file có mục đích rõ |
