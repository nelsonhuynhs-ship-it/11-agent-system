# REQUIREMENTS — Current Milestone (Sprint 12+)

> Last updated: 2026-03-30 | Milestone: Sprint 12 → GSD Adoption

## Scope

### V1 — This Milestone (Sprint 12)
1. **GSD Integration** — Install and adopt GSD framework ✅ Done
2. **Codebase Mapping** — 7 standardized docs ✅ Done
3. **Bot Anomaly Alerts** — Wire `anomaly_detector.py` → Telegram alerts
4. **Market Benchmark** — Real data wiring for WebApp dashboard
5. **JWT Middleware** — Route protection for all API endpoints
6. **Carrier Scorecard** — Scoring engine for carrier performance

### V2 — Next Milestone (Sprint 13-14)
1. **WebApp MVP Full Deploy** — FastAPI + Next.js on VPS with HTTPS
2. **PostgreSQL Migration** — Move from Parquet + SQLite to Supabase
3. **Multi-user Auth** — Support 10-100 users
4. **CI/CD Pipeline** — GitHub Actions for test + deploy

### Out of Scope
- Mobile app (future)
- Multi-tenant architecture (Sprint 15-16)
- 1,000+ user scaling (Sprint 15-16)
- WhatsApp Bot integration (backlog)

## Non-Functional Requirements
- **Performance:** API response < 500ms for rate queries
- **Data Freshness:** Parquet updated within 24h of new carrier rates
- **Availability:** VPS uptime > 99% (Cloudflare Tunnel)
- **Security:** JWT auth on all API routes, prompt injection guard

## Constraints
- **Budget:** Free-tier AI (Gemini RPM=5, RPD=20)
- **Team:** Solo developer + AI agents
- **Data:** Carrier rates arrive as PDF/Excel (manual import)
- **ERP:** Must maintain Excel/VBA compatibility (user workflow)
