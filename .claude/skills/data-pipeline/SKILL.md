---
name: data-pipeline
description: >
  Quản lý toàn bộ data layer của hệ thống Nelson — Parquet, SQLite, và migration
  path lên PostgreSQL/Supabase. TRIGGER khi: cần update data, import carrier rates,
  query Parquet, quản lý SQLite KPI, hoặc planning database migration.
---

# Data Pipeline Skill

> **Single Truth Source:** Parquet = nguồn gốc giá | ERP = nguồn chốt Quote/Job
> **KHÔNG tạo** file trung gian `MasterFullPricing.xlsx` trôi nổi

---

## 📁 Sub-Skill: parquet-ops — Parquet Operations

### File quan trọng
```
D:\NELSON\2. Areas\PricingSystem\Engine_test\
├── Pricing_Engine\data\Cleaned_Master_History.parquet  ← 19,700 rates
├── Pricing_Engine\data\carrier_rules.json              ← 13 carrier rules
└── TelegramBot\query_engine.py                         ← Query interface
```

### Query pattern (via query_engine.py)
```python
from query_engine import FreightQueryEngine
engine = FreightQueryEngine(parquet_path)

# Basic query
results = engine.query_rates(pol="HPH", place="Denver", carrier=None)

# Filtered query
results = engine.query_rates(pol="HPH", place="Atlanta", soc_only=True)
```

### Update Parquet (khi nhận file mới từ hãng tàu)
1. Nhận Excel từ carrier → chạy Pricing Engine cleaning script
2. Merge vào Cleaned_Master_History.parquet
3. Verify: `len(df)` tăng lên, carrier mới xuất hiện
4. Restart bot để reload (bot load Parquet khi start)

### Data schema quan trọng (Parquet columns)
```
POL, POD, Place, Carrier, ContType, Base20GP, Base40HQ,
TransitDays, FreeTime, SOC, ExpDate, Surcharges...
```

---

## 🗄️ Sub-Skill: sqlite-kpi — SQLite Operations

### Database: `freight_bot.db`
```
D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot\data\freight_bot.db
```

### Tables
| Table | Dữ liệu | Module |
|-------|---------|--------|
| `kpi_monthly` | KPI targets + actuals theo tháng | `kpi_store.py` |
| `leads_log` | Lead count history | `kpi_store.py` |
| `forecast_cache` | EOM forecast calculations | `kpi_store.py` |

### Common operations
```python
from kpi_store import KPIStore
kpi = KPIStore(db_path)

# Read current KPI
current = kpi.get_current_month()

# Update KPI
kpi.update_kpi(quotes=15, bookings=8, revenue=45000)

# Set targets
kpi.set_monthly_target(revenue=60000, bookings=12)
```

---

## 🔄 Sub-Skill: data-quality — Data Quality & Maintenance

### Validation checklist trước khi merge Parquet
- [ ] ExpDate không expired (>= today)
- [ ] POL/POD/Place names standardized (không typo)
- [ ] ContType chỉ là: 20GP / 40GP / 40HQ / 45HC / 40RF
- [ ] Base price > 0 (không có giá âm)
- [ ] Carrier name trong danh sách 13 carrier approved

### Dedup logic
```python
# Key để dedup: POL + POD + Place + Carrier + ContType + ExpDate
# Nếu duplicate → giữ record mới nhất (max ExpDate)
```

### Carrier name standardization
```
CMA, ONE, MSK, YML, ZIM, OOCL, WHL, HMM, PIL, TSL, ESL, MCK, APL
```

---

## 🚀 Sub-Skill: db-migration — Lộ trình Migration lên PostgreSQL

### Tại sao cần migrate (Sprint 13-14)
| Vấn đề hiện tại | Giải pháp |
|-----------------|-----------|
| Parquet = flat file, không multi-user | PostgreSQL table `freight_rates` |
| SQLite = single-process lock | PostgreSQL tables `kpi`, `quotes`, `jobs` |
| ERP Excel = không accessible via API | Supabase sync layer + REST API |

### Database Schema đề xuất (PostgreSQL)
```sql
-- Rates table (thay Parquet)
CREATE TABLE freight_rates (
    id SERIAL PRIMARY KEY,
    pol VARCHAR(10), pod VARCHAR(10), place VARCHAR(100),
    carrier VARCHAR(20), cont_type VARCHAR(10),
    base_20gp DECIMAL(10,2), base_40hq DECIMAL(10,2),
    transit_days INT, free_time INT, is_soc BOOLEAN,
    exp_date DATE, created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quotes table (từ ERP Quotes sheet)
CREATE TABLE quotes (
    id VARCHAR(20) PRIMARY KEY,
    customer VARCHAR(50), pol VARCHAR(10), place VARCHAR(100),
    carrier VARCHAR(20), selling_20gp DECIMAL(10,2),
    selling_40hq DECIMAL(10,2), status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Jobs table (từ ERP Active Jobs)
CREATE TABLE jobs (
    id VARCHAR(20) PRIMARY KEY,
    quote_id VARCHAR(20) REFERENCES quotes(id),
    revenue DECIMAL(10,2), cost DECIMAL(10,2),
    profit DECIMAL(10,2), status VARCHAR(20),
    etd DATE, eta DATE
);

-- Customers (CRM)
CREATE TABLE customers (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100), preferred_lanes TEXT[],
    commodity TEXT[], behavior_tag VARCHAR(50),
    win_rate DECIMAL(5,2)
);
```

### Migration path (thực hiện Sprint 13-14)
1. Setup Supabase project (free tier → production)
2. Create tables từ schema trên
3. ETL: Export Parquet → CSV → Import PostgreSQL
4. ETL: Export SQLite → Import PostgreSQL
5. Update bot: replace Parquet reader với pg adapter
6. Update ERP: Python → Supabase sync sau mỗi refresh

---

## 💾 Sub-Skill: backup-restore — Backup Strategy

### Backup schedule
```
Daily:   SQLite freight_bot.db → copy to /backup/db/
Weekly:  Parquet → copy to /backup/parquet/
Monthly: ERP_Master.xlsm → copy to /backup/erp/
```

### Restore steps
```
1. Stop bot
2. Copy backup file đến vị trí gốc
3. Verify file không corrupt (open + check row count)
4. Restart bot + test /quote command
```

---

## 🔗 References
- **Parquet path:** `Pricing_Engine/data/Cleaned_Master_History.parquet`
- **SQLite path:** `TelegramBot/data/freight_bot.db`
- **Query module:** `TelegramBot/query_engine.py`
- **Migration planning:** `memory/01_system_architecture.md` → Section 2
