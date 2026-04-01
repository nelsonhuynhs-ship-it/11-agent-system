# PROJECT — Nelson Freight Intelligence Platform

> Last updated: 2026-03-30

## Vision
Build a comprehensive freight intelligence platform that transforms Nelson Freight from a traditional NVOCC freight forwarder into an AI-powered logistics operation — managing pricing, quoting, CRM, and market intelligence through automated systems.

## Business Context
- **Company:** Nelson Freight — NVOCC Vietnam → USA/Canada
- **Owner:** Nelson (Sếp)
- **Core Route:** HPH/HCM → US ports (USTIW, USLAX, etc.) → inland cities
- **Active Carriers:** 13 (CMA, ONE, MSK, YML, ZIM, OOCL, WHL, HMM, PIL, TSL, ESL, MCK, APL)
- **Key Customers:** HML (stone/slabs), SIRI (office nails), PANDA

## System Components
1. **Pricing Engine** — Parquet-based rate storage (19,700+ rates), OCR import pipeline
2. **ERP** — Excel/VBA hybrid for quotes, jobs, CRM, intelligence
3. **Telegram Bot v5** — AI-powered freight assistant (30+ modules)
4. **FastAPI Backend** — 12-router REST API with DuckDB DAL
5. **Next.js WebApp** — Dashboard for analytics and management
6. **Intelligence Engine** — Anomaly detection, rate prediction, email intel
7. **Email Engine** — Outlook integration for market intelligence

## Tech Stack
- **Backend:** Python 3.x, FastAPI, DuckDB, Parquet, SQLite
- **Frontend:** Next.js 16, React 19, TailwindCSS 4, Recharts
- **AI:** Google Gemini (2.5 Flash + 3.1 Lite)
- **Bot:** python-telegram-bot 22.6
- **ERP:** Excel .xlsm + VBA macros
- **Deploy:** VPS (14.225.207.145), Cloudflare Tunnel, systemd

## History
| Milestone | Status | Date |
|-----------|--------|------|
| Sprint 1-9 | ✅ Core system built | Pre-2026-03 |
| Sprint 10b | ✅ KPI Intelligence + Bot Reorganization | 2026-03 |
| Sprint 11 | ✅ ERP Refactor + Architecture Audit | 2026-03 |
| Sprint 12 | 🔄 Bot + Data Skills | NOW |
| GSD Adoption | ✅ Installed + Mapped | 2026-03-30 |
