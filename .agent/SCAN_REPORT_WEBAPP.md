# 🔍 SCAN REPORT — Nelson Freight WebApp Stack
> **Scan Date:** 2026-03-23 06:46 +07:00  
> **Root:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\`  
> **Scanned by:** CTO Agent

---

## PHẦN 1 — FASTAPI BACKEND SCAN

### 1.1 — Router Files (12 files)

| # | File | Prefix | Tag |
|---|---|---|---|
| 1 | `rate_router.py` | `/api/rates` | Rates |
| 2 | `quote_router.py` | `/api/quotes` | Quotes |
| 3 | `shipment_router.py` | `/api` | Shipments |
| 4 | `dashboard_router.py` | `/api` | Dashboard |
| 5 | `intelligence_router.py` | `/api/intelligence` | Intelligence |
| 6 | `email_router.py` | `/api/email-events` | Email Events |
| 7 | `auth_router.py` | `/api/auth` | Auth |
| 8 | `worker_router.py` | `/api/workers` | Workers |
| 9 | `erp_router.py` | `/api/erp` | ERP |
| 10 | `health_router.py` | `/api/health` | Health |
| 11 | `hpl_router.py` | `/api/hpl` | Hapag-Lloyd |
| 12 | `__init__.py` | — | — |

### 1.2 — Full Endpoint Map (40+ endpoints)

#### rate_router.py — `/api/rates`
| Method | Path | Description |
|---|---|---|
| GET | `/api/rates` | Query rates from Parquet (POL/POD/place/carrier/container/soc) |
| GET | `/api/rates/carriers` | List carriers with rate counts |
| GET | `/api/rates/stats` | Overall pricing stats |
| GET | `/api/rates/breakdown` | Full cost breakdown per carrier |
| GET | `/api/rates/regions` | Region summary (WC/EC/GULF/IPI) |
| GET | `/api/rates/compare` | Compare carriers — all containers |
| GET | `/api/rates/matrix` | Carrier × Container comparison matrix |
| GET | `/api/rates/best` | Best (cheapest) carrier per container |

#### quote_router.py — `/api/quotes`
| Method | Path | Description |
|---|---|---|
| GET | `/api/quotes` | List all quotes |
| POST | `/api/quotes` | Create multi-carrier/container quote |
| GET | `/api/quotes/intelligence` | Intelligence dashboard |
| GET | `/api/quotes/{id}` | Get single quote |
| PUT | `/api/quotes/{id}` | Update quote |
| PATCH | `/api/quotes/{id}/status` | Change status |
| POST | `/api/quotes/{id}/convert` | Convert → shipment |
| POST | `/api/quotes/{id}/requote` | Re-quote with updated rates |
| GET | `/api/quotes/{id}/versions` | Quote version history |

#### shipment_router.py — `/api`
| Method | Path | Description |
|---|---|---|
| GET | `/api/shipments` | All tracked shipments |
| GET | `/api/shipments/{id}` | Shipment by ID |
| GET | `/api/carrier/freetime` | DEM/DET freetime rules |

#### dashboard_router.py — `/api`
| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/charts` | Pre-computed charts (revenue, carrier profit, 4C, regions) |
| GET | `/api/customers` | All customers with shipment stats |
| GET | `/api/team` | Team members |
| GET | `/api/kpi` | KPI summary |
| GET | `/api/datasets/status` | Dataset row counts |
| GET | `/api/datasets/email` | Email dataset query |
| GET | `/api/status` | System health check |

#### intelligence_router.py — `/api/intelligence`
| Method | Path | Description |
|---|---|---|
| GET | `/api/intelligence/memory` | Memory layer status |
| GET | `/api/intelligence/carriers` | Carrier reliability ranking |
| GET | `/api/intelligence/4c` | 4C report |
| GET | `/api/intelligence/opportunities` | Business opportunities |
| GET | `/api/intelligence/market` | Market memory trends |
| GET | `/api/intelligence/news` | Logistics news |
| GET | `/api/intelligence/churn` | Customer churn risk |

#### email_router.py — `/api/email-events`
| Method | Path | Description |
|---|---|---|
| POST | `/api/email-events/sync` | Trigger email sync |
| GET | `/api/email-events/status` | Sync status |
| GET | `/api/email-events/alerts` | Trouble alerts |
| POST | `/api/email-events/scan` | Trigger Outlook scan |
| GET | `/api/email-events/timeline/{id}` | Email timeline per shipment |

#### erp_router.py — `/api/erp`
| Method | Path | Description |
|---|---|---|
| GET | `/api/erp/rates-matrix` | Rate matrix for Excel ERP |
| POST | `/api/erp/sync-quote` | Sync quote from Excel |
| GET | `/api/erp/job-status` | Job/shipment status for Excel |
| GET | `/api/erp/cost-breakdown` | Detailed cost breakdown |
| POST | `/api/erp/import-rates` | Semi-automated rate import |

#### hpl_router.py — `/api/hpl`
| Method | Path | Description |
|---|---|---|
| GET | `/api/hpl/spot` | HPL spot rate |
| GET | `/api/hpl/spot/all` | All container spot rates |
| POST | `/api/hpl/spot/refresh` | Refresh spot cache |
| GET | `/api/hpl/track/{identifier}` | Track container/job |
| POST | `/api/hpl/track/add` | Add containers to job |
| POST | `/api/hpl/webhook/events` | DCSA T&T webhook receiver |
| GET | `/api/hpl/status` | HPL integration health |

#### health_router.py — `/api/health`
| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Quick liveness |
| GET | `/api/health/ready` | Readiness (all deps) |
| GET | `/api/health/deep` | Full diagnostic |

#### auth_router.py — `/api/auth`
| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/me` | Current user info |
| GET | `/api/auth/status` | Auth system status |

#### worker_router.py — `/api/workers`
| Method | Path | Description |
|---|---|---|
| GET | `/api/workers` | All worker status |
| POST | `/api/workers/email/scan` | Trigger email scan |
| POST | `/api/workers/evaluator/run` | Trigger evaluation |
| POST | `/api/workers/intelligence/recalculate` | Trigger intelligence |
| GET | `/api/workers/alerts` | Alert history |

#### app.py (Entry Point + Direct Endpoints)
| Method | Path | Description |
|---|---|---|
| GET | `/` | Root info |
| GET | `/api/events` | Event bus recent events |
| GET | `/api/config` | System config |

### 1.3 — Entry Point
- **File:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\api\app.py`  
- **Version:** 2.3.0  
- **Run command:** `uvicorn app:app --reload --port 8000`  
- **Default port in code:** `8000` (line 8 in app.py)

### 1.4 — Port Config
- `app.py` docstring says `--port 8000`
- `CORS_ORIGINS` in config.py: `localhost:3000`, `localhost:3001`
- **⚠ WEBAPP api.ts hardcodes:** `http://14.225.207.145:8100`
- **Kết luận:** VPS deploy dùng port **8100**, code mặc định **8000**

### 1.5 — Requirements
❌ **KHÔNG TÌM THẤY `requirements.txt`** trong `api/` folder

---

## PHẦN 2 — WEBAPP NEXT.JS SCAN

### 2.1 — Pages (7 pages, KHÔNG có Reports page)

| Page | File Path | Fetch API? | URL Fetched | Status |
|---|---|---|---|---|
| **Dashboard** | `src/app/dashboard/page.tsx` | ✅ YES | `${API_URL}/api/dashboard/charts` | ✅ LIVE — fetches 4C, revenue, carriers, regions |
| **Pricing** | `src/app/dashboard/pricing/page.tsx` | ✅ YES | `/api/rates/matrix` + `/api/rates/regions` | ✅ LIVE — full matrix search |
| **Shipments** | `src/app/dashboard/shipments/page.tsx` | ✅ YES | `/api/shipments` + `/api/customers` + `/api/dashboard/charts` + `/api/carrier/freetime` | ✅ LIVE — 10 intelligence features |
| **Customers** | `src/app/dashboard/customers/page.tsx` | ✅ YES | `/api/customers` | ✅ LIVE |
| **Quotes** | `src/app/dashboard/quotes/page.tsx` | ✅ YES | `/api/quotes` + `/api/quotes/intelligence` + `/api/rates/best` + `/api/customers` | ✅ LIVE — builder + intelligence |
| **Team** | `src/app/dashboard/team/page.tsx` | ✅ YES | `/api/team` | ✅ LIVE |
| **AI Copilot** | `src/app/dashboard/ai/page.tsx` | ✅ YES | `/api/rates` + `/api/shipments` + `/api/customers` + `/api/team` | ✅ LIVE — local tool-based AI |

> **Kết luận:** TẤT CẢ 7 pages đều fetch LIVE data từ API. **KHÔNG có mock data.** Nếu API offline → hiện "Waiting for data..." hoặc empty state.

### 2.2 — Missing Pages (so với 8 pages yêu cầu)
- ❌ **Reports** — CHƯA CÓ page
- ✅ 7/8 pages exist

### 2.3 — .env.local
❌ **KHÔNG TÌM THẤY `.env.local`** trong `webapp/`

### 2.4 — API Wrapper
✅ `src/lib/api.ts` — Có fetch wrapper chung:
```typescript
export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://14.225.207.145:8100';
```
- Wrapper `fetchAPI<T>()` xử lý error + JSON parse
- Nhưng chỉ export `api` object cho `/agent/*` endpoints (CTO Agent cũ)
- **Các page không dùng `api` object** — gọi `fetch(`${API_URL}/api/...`)` trực tiếp

---

## PHẦN 3 — DATA FILES SCAN

### 3.1 — Parquet
- **Path:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\Pricing_Engine\data\Cleaned_Master_History.parquet`
- **Rows:** 10,237,866 (10.2M)
- **Columns (16):**

| Column | Dtype | Description |
|---|---|---|
| POL | object | Port of Loading |
| POD | object | Port of Discharge |
| Place | object | Place of Delivery |
| Carrier | object | Carrier name |
| Commodity | object | Commodity type |
| Contract | object | Contract number |
| **Eff** | **datetime64** | Effective date |
| **Exp** | **datetime64** | Expiry date |
| Note | object | SOC/COC/DIRECT etc |
| Group Rate | object | Group rate ref |
| Charge_Name | object | Charge component |
| Container_Type | object | 20GP/40HQ etc |
| Amount | float64 | USD amount |
| Source_File | object | Import source |
| Rate_Type | object | FAK/SCFI/FIX |
| Group_Code | object | MR code |

- **Date Range:**
  - `Eff`: 1900-01-09 → 2026-03-23 (có junk dates, cần filter)
  - `Exp`: 1970-01-01 → 2026-04-10
- **Filter 30 days column:** `Eff` (effective date)
- **Backup files:** 4 backups in `Pricing_Engine/data/`

### 3.2 — SQLite Databases

| DB | Path | Tables |
|---|---|---|
| `freight_bot.db` | `TelegramBot/data/freight_bot.db` | KPI + Memory tables (documented in GEMINI.md) |
| `shipments.db` | `email_engine/logs/shipments.db` | Shipment-related (from email engine) |

> ⚠ Không inspect trực tiếp được do PowerShell quoting issue — **cần Sếp confirm tables nếu cần chi tiết**

---

## PHẦN 4 — VPS CONNECTION CHECK

| Service | URL | Port | Status |
|---|---|---|---|
| **FastAPI** | `http://14.225.207.145:8100/api/health` | 8100 | 🔴 **OFFLINE** — Unable to connect |
| **WebApp** | `http://14.225.207.145:3002` | 3002 | 🟢 **ONLINE** — HTTP 200 |

- ❌ **KHÔNG tìm thấy deploy script** trong `Engine_test/`
- Để deploy FastAPI → cần SSH vào VPS + chạy `uvicorn app:app --port 8100`

---

## PHẦN 5 — OUTPUT

### 5.1 — GAP ANALYSIS (Endpoints vs WebApp Pages)

#### ✅ ENDPOINTS ĐÃ CÓ ĐẦY ĐỦ CHO WEBAPP

| WebApp Page | API Endpoint(s) Required | Status |
|---|---|---|
| Dashboard | `/api/dashboard/charts` | ✅ EXISTS (`dashboard_router.py`) |
| Pricing | `/api/rates/matrix`, `/api/rates/regions` | ✅ EXISTS (`rate_router.py`) |
| Shipments | `/api/shipments`, `/api/carrier/freetime` | ✅ EXISTS (`shipment_router.py`) |
| Customers | `/api/customers` | ✅ EXISTS (`dashboard_router.py`) |
| Quotes | `/api/quotes`, `/api/quotes/intelligence`, `/api/rates/best` | ✅ EXISTS |
| Team | `/api/team` | ✅ EXISTS (`dashboard_router.py`) |
| AI Copilot | `/api/rates`, `/api/shipments`, `/api/customers`, `/api/team` | ✅ EXISTS |
| **Reports** | **CHƯA CÓ ENDPOINT + CHƯA CÓ PAGE** | ❌ MISSING |

#### ⚠ ENDPOINTS THIẾU CHO TƯƠNG LAI

```
MISSING FOR REPORTS PAGE:
- GET /api/reports/weekly → weekly KPI summary (cần build từ shipment + quote data)  
- GET /api/reports/monthly → monthly P&L
- GET /api/reports/carrier-performance → carrier scoring + reliability

MISSING FOR WEBAPP IMPROVEMENT:
- POST /api/quotes/{id}/email → gửi quote qua email
- GET /api/intelligence/summary → tổng hợp 4C + opportunities cho dashboard
```

### 5.2 — WEBAPP PAGES STATUS

#### ✅ PAGES READY TO CONNECT (đã connect rồi!)
```
✅ Dashboard        → fetches /api/dashboard/charts ← LIVE
✅ Pricing/Rates    → fetches /api/rates/matrix + /api/rates/regions ← LIVE  
✅ Shipments        → fetches /api/shipments + /api/carrier/freetime ← LIVE
✅ Customers        → fetches /api/customers ← LIVE
✅ Quotes           → fetches /api/quotes + /api/quotes/intelligence ← LIVE
✅ Team             → fetches /api/team ← LIVE
✅ AI Copilot       → fetches /api/rates + /api/shipments + /api/customers ← LIVE
```

#### ❌ PAGES CẦN BUILD
```
❌ Reports          → CHƯA CÓ page.tsx + CHƯA CÓ endpoint
```

#### ⚠ VẤN ĐỀ CHÍNH: FastAPI PORT 8100 TRÊN VPS ĐANG OFFLINE

Tất cả 7 pages đều gọi `http://14.225.207.145:8100` → tất cả sẽ show empty state vì API chết.

### 5.3 — .ENV.LOCAL HIỆN TẠI vs CẦN SỬA

```env
# HIỆN TẠI:
# KHÔNG CÓ FILE .env.local
# api.ts hardcodes: NEXT_PUBLIC_API_URL fallback = 'http://14.225.207.145:8100'

# NGHĨA LÀ: WebApp tự động dùng VPS API URL mà không cần .env.local
# KHI NÀO CẦN .env.local?
#   - Khi dev local: NEXT_PUBLIC_API_URL=http://localhost:8000
#   - Khi đổi VPS IP/port

# NẾU CẦN TẠO:
# File: D:\NELSON\2. Areas\PricingSystem\Engine_test\webapp\.env.local
NEXT_PUBLIC_API_URL=http://14.225.207.145:8100
```

### 5.4 — PARQUET QUERY TEMPLATE

```python
# Template filter 30 ngày — dùng cho mọi endpoint
import pandas as pd
from datetime import datetime, timedelta

df = pd.read_parquet(r"D:\NELSON\2. Areas\PricingSystem\Engine_test\Pricing_Engine\data\Cleaned_Master_History.parquet")
cutoff = datetime.now() - timedelta(days=30)
df_recent = df[df['Eff'] >= cutoff]

# Filter thêm chỉ Total Ocean Freight (loại surcharge rows)
df_totals = df_recent[df_recent['Charge_Name'].str.contains('Total Ocean Freight', na=False)]

# Example: HPH → Denver, 40HQ
result = df_totals[
    (df_totals['POL'].str.upper() == 'HPH') &
    (df_totals['Place'].str.contains('DENVER', case=False, na=False)) &
    (df_totals['Container_Type'] == '40HQ')
].sort_values('Amount')

print(f"Found {len(result)} rates")
print(result[['Carrier', 'POD', 'Place', 'Amount', 'Eff', 'Exp', 'Note']].head(10))
```

### 5.5 — SPRINT PLAN (Post-Scan)

| Priority | Task | Why | Effort |
|---|---|---|---|
| 🔴 **P0** | Deploy FastAPI trên VPS port 8100 | WebApp 7/7 pages đang gọi nhưng API offline → all pages empty | 30min |
| 🔴 **P0** | Thêm CORS `http://14.225.207.145:3002` vào config.py | WebApp port 3002 ONLINE nhưng chưa có trong CORS origins | 5min |
| 🟡 **P1** | Tạo `requirements.txt` cho api/ | Deploy dependency management | 15min |
| 🟡 **P1** | Tạo `.env.local` cho dev local | Dev workflow | 5min |
| 🟢 **P2** | Build Reports page (`/dashboard/reports`) | 8th page — weekly/monthly KPI | 2-3h |
| 🟢 **P2** | Build `/api/reports/*` endpoints | Data cho Reports page | 2-3h |
| 🟢 **P3** | Clean Parquet junk dates (Eff < 2024) | Data quality — 1900/1970 dates | 30min |
| 🟢 **P3** | Migrate `api.ts` agent endpoints → match actual routers | api.ts export `api` object chỉ có `/agent/*` routes — outdated | 1h |

#### Build Order (khuyến nghị):
1. ✅ **Deploy FastAPI on VPS** (P0) → ngay bây giờ
2. ✅ **Fix CORS** (P0) → 5 phút
3. ✅ **Test all 7 pages** → verify data show đúng
4. 📋 **Build Reports page + endpoints** (P2) → sprint kế tiếp
5. 🧹 **Clean Parquet data** (P3) → background task

---

## APPENDIX — File Tree

```
api/
├── app.py                  # Entry point v2.3.0
├── config.py               # Centralized config
├── data_access.py          # DAL (Parquet + JSON + SQLite)
├── event_bus.py            # Event system
├── quote_store.py          # Quote CRUD
├── quote_intelligence.py   # Quote analytics
├── email_event_engine.py   # Email→Shipment sync
├── email_scanner.py        # Outlook scanner
├── erp_api_bridge.py       # Excel VBA bridge
├── data/                   # quotes.json, events.jsonl
├── database/               # PostgreSQL DAL + migrations
├── middleware/              # CORS, rate limit, error handler, logging
├── routers/                # 12 router files (mapped above)
│   ├── rate_router.py      # 8 endpoints
│   ├── quote_router.py     # 9 endpoints
│   ├── shipment_router.py  # 3 endpoints
│   ├── dashboard_router.py # 7 endpoints
│   ├── intelligence_router.py # 7 endpoints
│   ├── email_router.py     # 5 endpoints
│   ├── auth_router.py      # 2 endpoints
│   ├── worker_router.py    # 5 endpoints
│   ├── erp_router.py       # 5 endpoints
│   ├── health_router.py    # 3 endpoints
│   ├── hpl_router.py       # 7 endpoints
│   └── __init__.py
├── workers/                # Background workers
├── services/               # Notification service
└── _archive/               # Deprecated files

webapp/src/
├── app/
│   ├── page.tsx            # Root redirect
│   ├── layout.tsx          # Root layout
│   ├── globals.css         # Design system
│   └── dashboard/
│       ├── layout.tsx      # Sidebar + Topbar
│       ├── page.tsx        # Dashboard (4C + charts)
│       ├── pricing/page.tsx    # Rate Explorer
│       ├── shipments/page.tsx  # Control Tower (730 lines!)
│       ├── customers/page.tsx  # Customer Intelligence
│       ├── quotes/page.tsx     # Quote Builder (1026 lines!)
│       ├── team/page.tsx       # Team Performance
│       └── ai/page.tsx         # AI Copilot
├── components/layout/
│   ├── Sidebar.tsx
│   └── Topbar.tsx
└── lib/
    └── api.ts              # API client wrapper
```
