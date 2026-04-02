---
name: webapp-scalable
description: >
  Build và maintain WebApp dashboard cho 1,000 users. TRIGGER khi: thiết kế
  hoặc build WebApp, setup database PostgreSQL/Supabase, cần API design,
  auth system, hoặc deployment. Stack: FastAPI + Next.js + Supabase.
---

# WebApp Scalable Skill

> **Target:** Private dashboard → Multi-user platform (1,000 users)
> **Stack:** FastAPI (backend) · Next.js 14 (frontend) · Supabase (DB + Auth)
> **Deploy:** Railway/Render (API) · Vercel (frontend)

---

## 🏗️ Sub-Skill: architecture — Kiến trúc hệ thống

### System Design
```
┌─────────────────────────────────────┐
│        SUPABASE                     │
│  PostgreSQL + Auth + Realtime       │
│  • freight_rates (giá hãng tàu)     │
│  • quotes, jobs, customers (ERP)    │
│  • kpi_metrics (KPI tracking)       │
│  • user_accounts, role_assignments  │
└──────────────────────────────────────┘
         │                │
         ▼                ▼
  ┌─────────────┐  ┌──────────────┐
  │ FastAPI     │  │ Next.js 14   │
  │ (Backend)   │  │ (Frontend)   │
  │ Python      │  │ App Router   │
  │ Railway     │  │ Vercel       │
  └─────────────┘  └──────────────┘
         │                │
         └────────────────┘
              ◄──────────►
           (REST API + Realtime)
```

### Role hierarchy (1,000 users)
```
admin  (Sếp Nelson)    → Full access: pricing, quotes, jobs, reports, user mgmt
sales  (Nhân viên)     → Quotation, own CRM, assigned customers
viewer (Khách VIP)     → Rate inquiry, own shipment tracking
```

---

## ⚙️ Sub-Skill: api-design — FastAPI Backend

### Project structure
```
backend/
├── main.py              ← FastAPI app entry
├── routers/
│   ├── rates.py         ← GET /rates?pol=HPH&place=Denver
│   ├── quotes.py        ← CRUD /quotes
│   ├── jobs.py          ← CRUD /jobs
│   ├── customers.py     ← GET/PUT /customers
│   └── kpi.py           ← GET /kpi/monthly
├── services/
│   ├── rate_service.py  ← Query logic (replaces query_engine.py)
│   ├── markup_service.py← Markup calculation
│   └── kpi_service.py   ← KPI calculations
├── models/
│   └── schemas.py       ← Pydantic schemas
└── db/
    └── supabase_client.py← Supabase connection
```

### Core endpoints
```python
# Rates
GET  /api/rates?pol={pol}&place={place}&carrier={carrier}
GET  /api/rates/carriers     → list active carriers
GET  /api/rates/freetime/{carrier}

# Quotes
GET  /api/quotes?customer={code}&status={status}
POST /api/quotes             → create quote
PUT  /api/quotes/{id}/win    → mark as won → create job

# Dashboard
GET  /api/kpi/monthly?month={YYYY-MM}
GET  /api/kpi/pipeline
GET  /api/reports/weekly

# Admin
GET  /api/users
POST /api/users/{id}/role
```

---

## 🎨 Sub-Skill: dashboard-ui — Next.js Frontend

### Pages
```
app/
├── page.tsx             ← Landing / Login
├── dashboard/
│   ├── page.tsx         ← KPI overview (charts, metrics)
│   ├── rates/page.tsx   ← Rate lookup (replace bot /quote)
│   ├── quotes/page.tsx  ← Quote management
│   ├── jobs/page.tsx    ← Active jobs
│   └── customers/page.tsx← CRM
├── admin/
│   ├── users/page.tsx   ← User management (admin only)
│   └── settings/page.tsx← System settings
└── api/                 ← Next.js API routes (proxy to FastAPI)
```

### Key components
```
RateTable       → Sortable table với real-time updates
QuoteBuilder    → Form tạo báo giá (replaces ERP cho remote)
KPIChart        → Revenue/booking trend (Recharts)
PipelineFunnel  → Lead→Quote→Job→Shipment funnel
CustomerCard    → Customer profile + win rate
```

---

## 🔐 Sub-Skill: auth-system — Supabase Auth

### Setup
```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

### Role-based access (Row Level Security)
```sql
-- Supabase RLS: chỉ admin thấy tất cả quotes
CREATE POLICY "admin_all" ON quotes FOR ALL
  USING (auth.jwt() ->> 'role' = 'admin');

-- Sales chỉ thấy quotes của mình
CREATE POLICY "sales_own" ON quotes FOR SELECT
  USING (auth.uid() = created_by AND auth.jwt() ->> 'role' = 'sales');
```

---

## 🚀 Sub-Skill: deployment — Deploy Guide

### Environment variables
```env
# Backend (.env)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # Service role key (backend only)
GEMINI_API_KEY=AIza...        # For AI analysis

# Frontend (.env.local)
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...  # Anon key (public)
NEXT_PUBLIC_API_URL=https://your-api.railway.app
```

### Deploy steps
```
1. Supabase: Create project → Run migrations → Enable RLS
2. Backend:  Railway/Render → Connect GitHub → Set env vars
3. Frontend: Vercel → Connect GitHub → Set env vars → Deploy
4. Test:     Login → Rate query → Quote creation → KPI dashboard
```

### Performance targets
```
Rate query:       < 200ms (PostgreSQL index on pol+place)
Dashboard load:   < 2s (SSR + Supabase Realtime)
Concurrent users: 1,000 (Supabase scales automatically)
Uptime:           > 99.5% (managed infrastructure)
```

---

## 🗺️ Sprint 13-14 Implementation Order

```
Week 1: Supabase setup + data migration (Parquet → PostgreSQL)
Week 2: FastAPI backend (rates, quotes, jobs endpoints)
Week 3: Next.js frontend (auth + rate lookup + quote builder)
Week 4: KPI dashboard + reports + testing
Week 5: Multi-user (role-based access + user management)
Week 6: Polish + performance + deploy production
```

---

## 🔗 References
- **PostgreSQL schema:** xem skill `data-pipeline` → sub-skill `db-migration`
- **Supabase docs:** https://supabase.com/docs
- **Next.js docs:** https://nextjs.org/docs (App Router)
- **FastAPI docs:** https://fastapi.tiangolo.com
