---
name: bot-v5-dev
description: >
  Phát triển và maintain Telegram Bot v5 modular system cho Nelson Freight.
  TRIGGER khi: thêm command mới cho bot, debug bot behavior, sửa module bot,
  upgrade bot version, hoặc bất kỳ việc gì liên quan đến bot_v5.py và các modules.
---

# Bot v5 Development Skill

> **Core file:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot\bot_v5.py`
> **RULE #1:** KHÔNG sửa `bot_v5.py` core khi thêm tính năng mới → Tạo module mới
> **RULE #2:** KHÔNG đọc `_ARCHIVED_bot_legacy_DONTMODIFY.py`

---

## 📦 Sub-Skill: module-map — 30 Modules của Bot System

### Core Bot (4 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `bot_v5.py` | **BOT CHÍNH** — handlers + routing | ~1,842 |
| `config.py` | Environment config + tokens | ~25 |
| `bot_menu.py` | Menu builder + keyboard layouts | ~337 |
| `rate_limiter.py` | Rate limiting middleware | ~89 |

### Pricing & Quoting (5 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `query_engine.py` | Parquet load + rate query | ~180 |
| `query_parser.py` | Natural language → structured query | ~386 |
| `quote_formatter.py` | format_quotation + _smart_note | ~174 |
| `freetime_formatter.py` | Intent detection + freetime | ~214 |
| `markup_engine.py` | Base + PUC + Markup → Selling Price | ~236 |

### ERP Integration (3 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `erp_reader.py` | ERP CRM/Quotes/Jobs (read-only) | ~465 |
| `erp_writer.py` | Convert Quote → Active Job | ~206 |
| `etl_sync.py` | ERP ↔ Bot data sync | ~140 |

### AI Brain (7 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `ai_chat.py` | Gemini AI chat mode | ~191 |
| `ai_pricing.py` | AI pricing recommendations | ~264 |
| `ai_risk_engine.py` | 4D risk scoring (weight/rate/space/payment) | ~306 |
| `ai_sales_intel.py` | Churn detection + next-order prediction | ~251 |
| `customer_intelligence.py` | 360° customer card + negotiation | ~231 |
| `nl_query_agent.py` | Vietnamese NL → structured queries | ~317 |
| `data_lake.py` | DuckDB analytics layer | ~290 |

### Intelligence Features (2 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `intelligence_features.py` | 7 intelligence bot commands | ~480 |
| `email_analytics.py` | Carrier trouble + route health engine | ~578 |

### KPI & Reporting (5 modules)
| Module | Vai trò | Dòng |
|--------|---------|------|
| `kpi_store.py` | KPI + Forecast + Pipeline (SQLite) | ~216 |
| `dashboard_builder.py` | PNG chart builder (matplotlib) | ~247 |
| `win_loss_analyzer.py` | AI analysis via Gemini | ~232 |
| `customer_profiles.py` | HML/SIRI/PANDA static profiles | ~138 |
| `rate_expiry_guardian.py` | Rate expiration monitoring | ~184 |

### Data & Config (3 files)
| File | Vai trò |
|------|---------|
| `carrier_tips.json` | Advisory notes per carrier |
| `auto_email_booking.py` | Automated email booking drafts (~297) |
| `database.py` | SQLite database layer (~214) |

---

## 🎮 Sub-Skill: command-registry — Tất cả Commands

### Pricing Commands
```
/quote [POL] [PLACE] [OPTIONS]  → Top 3 rates từ Parquet
/quote HPH ATLANTA              → Standard query
/quote HPH DENVER SOC           → Filter SOC only
/quote HPH LAX +50              → +$50 custom markup
```

### ERP/CRM Commands
```
/crm [CUSTOMER]     → Customer profile + history
/jobs               → Active jobs list
/history [CUST]     → Quote history per customer
/win [QUOTE_ID]     → Mark quote as won → create job
/savequote          → Save current quote to ERP
```

### KPI/Analytics Commands
```
/kpi                → Current month KPI progress
/forecast           → EOM revenue forecast
/pipeline           → Sales funnel breakdown
/setleads N         → Update monthly lead count
/setkpi [targets]   → Set monthly KPI targets
/report [YYYY-MM]   → PNG dashboard report
/wins               → Recent won quotes
/losses             → Recent lost quotes
/analyze [mode]     → AI win/loss analysis (4 modes)
```

### 🧠 Intelligence Commands (NEW)
```
/trouble [carrier]  → Carrier Trouble Index (#3)
/route [POL] [PLACE]→ Route Health Map (#5)
/churn              → Churn Radar — at-risk customers (#1)
/risk CUSTOMER      → 4D Risk Assessment (#3+)
/intel CUSTOMER     → 360° Customer Intelligence (#9)
/intelligence       → Feature overview dashboard
/custintel          → Customer summary ranking
```

### System Commands
```
/start      → Welcome + help
/help       → Command list
/status     → Bot system status
```


---

## 🔧 Sub-Skill: new-command — Template thêm command mới

### Bước 1: Tạo module mới (KHÔNG sửa bot_v5.py logic)
```python
# new_feature.py
def process_feature(input_data):
    """Core logic của feature mới"""
    # ... implementation
    return result
```

### Bước 2: Thêm handler vào bot_v5.py
```python
# Trong bot_v5.py — chỉ thêm handler, không sửa existing code
async def cmd_new_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from new_feature import process_feature
    result = process_feature(context.args)
    await update.message.reply_text(result)

# Đăng ký trong main():
app.add_handler(CommandHandler("newfeature", cmd_new_feature))
```

### Bước 3: Test
```
/newfeature test_input
→ Verify output format đúng template
→ Verify không break existing commands
```

---

## 🐛 Sub-Skill: debug-routing — Debug theo module

### Debug path theo triệu chứng
| Triệu chứng | Module cần xem |
|-------------|---------------|
| Giá sai / không ra kết quả | `query_engine.py` |
| Freetime hiểu nhầm thành giá | `freetime_formatter.py` |
| Format quote xấu / sai | `quote_formatter.py` |
| Markup tính sai | `markup_engine.py` |
| CRM/Jobs không load | `erp_reader.py` |
| /win không ghi ERP | `erp_writer.py` |
| /kpi /forecast sai | `kpi_store.py` |
| /report không ra PNG | `dashboard_builder.py` |
| /analyze không chạy | `win_loss_analyzer.py` |
| Customer profile sai | `customer_profiles.py` |

### Common fixes
```python
# Import error → check __init__ trong main()
# Module không load → check if module init được gọi trong main()
# Command không respond → check CommandHandler registration
```

---

## 🚀 Sub-Skill: upgrade-checklist — Deploy checklist bot mới

Trước khi restart bot:
- [ ] Tất cả imports đúng trong bot_v5.py
- [ ] Module init functions được gọi trong `main()`
- [ ] Test `/quote HPH ATLANTA` → format đúng
- [ ] Test `freetime CMA` → freetime_formatter kích hoạt
- [ ] Test `/kpi` → SQLite data đúng
- [ ] Test `/report` → PNG generate không lỗi
- [ ] Không còn hardcoded values trong bot_v5.py core

---

## 🔗 References
- **Module file paths:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot\`
- **Data paths:** xem `memory/05_active_context.md` → System Paths section
- **Carrier tips:** `carrier_tips.json` (edit directly, không cần restart bot sau khi sửa JSON)
