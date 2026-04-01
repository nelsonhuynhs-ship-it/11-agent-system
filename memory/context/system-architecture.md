# System Architecture — Nelson Freight Platform
Last updated: 2026-04-01

## Infrastructure
- **VPS:** 14.225.207.145
  - nelson-api: port 8100 (FastAPI)
  - nelson-webapp3003: port 3003 (Next.js)
  - TraSuaPOS Docker: port 3000+3001 (NEVER TOUCH)
  - Cloudflare Tunnel → HTTPS public URL
- **PC Home:** Development machine (Cowork + Claude)
- **Laptop VP:** Telegram bot runtime only

## Backend (FastAPI port 8100)
- 15 routers, DAL pattern via `data_access.py`
- DuckDB engine: `db/duckdb_engine.py`
- Key routers:
  - `email_rate_router.py` — Rate & Send (Sprint 13+14)
  - `intelligence/anomaly_detector.py` — SENTINEL
  - `/api/reports/monthly` — pending VPS deploy

## Frontend (Next.js port 3003)
- 9 pages + login
- Pages: Overview, Pricing, Shipments, Customers, Quotes, Team, Rate&Send, Reports, AI Assistant
- Rate & Send: `webapp/src/app/dashboard/rate-send/page.tsx` (1,064 lines)

## Data Layer
- Parquet: `Pricing_Engine/data/Cleaned_Master_History.parquet` (~6.6M rows)
- CNEE Master: `email_engine/data/cnee_master.xlsx` (5,316 rows)
- Email Log: `email_engine/logs/email_log.csv` (585 rows)
- Customer Rules: `email_engine/data/customer_rules.json`
- Port Map: `email_engine/data/Port_Code_Mapping_Final.xlsx`
- Config: `email_engine/data/config.xlsx` (subjects, templates, signature)

## Email System
- SMTP: smtp.office365.com:587
- From: nelson@pudongprime.vn
- Mentee emails: johnny, jennie, blue, lina, otis, jun @pudongprime.vn
- Log: `email_engine/logs/email_log.csv`

## Telegram Bot (v5)
- Runs on Laptop VP only
- NOT running on local PC
- `.env`: BOT_TOKEN + GEMINI_API_KEY
- N.E.L.S.O.N: ORACLE + SENTINEL modules

## Deploy Flow
```
PC Home: git push → SSH to VPS → git pull → cp files → npm build → systemctl restart
Script: deploy/auto_deploy.bat
SSH key: C:\Users\ADMIN\.ssh\id_nelson_vps
```

## Rules
1. Never use C:\tmp — always C:\Users\ADMIN\Documents\2. Areas\
2. Backup before any edit
3. Parquet: ALWAYS last 30 days filter (fallback 60d→90d nếu empty)
4. API: DuckDB via FreightDB only
5. NEVER touch ports 3000/3001
6. Email: Office 365 SMTP only (no Outlook COM)
