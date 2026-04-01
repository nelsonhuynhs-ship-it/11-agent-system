# ROADMAP — Phased Milestones

> Last updated: 2026-03-30

## Current Milestone: Sprint 12 — Bot + Data Skills + GSD Adoption

### Phase 1: GSD Foundation ✅ COMPLETE
- [x] Install GSD framework (v1.30.0)
- [x] Map codebase (7 docs)
- [x] Create formal planning artifacts (PROJECT, REQUIREMENTS, ROADMAP, STATE)
- [x] Document atomic commit + milestone conventions

### Phase 2: Security & Auth
- [ ] Complete JWT middleware for all API routes
- [ ] Add API rate limiting
- [ ] Verify GSD prompt guard hooks active

### Phase 3: Intelligence Wiring
- [ ] Wire `anomaly_detector.py` → Telegram bot alerts
- [ ] Market Benchmark real data → WebApp dashboard
- [ ] Carrier Scorecard engine implementation

### Phase 4: Bot Enhancements
- [ ] Sales Report command in bot_v5
- [ ] Mentee error monitoring via bot
- [ ] Bot command documentation update

---

## Next Milestone: Sprint 13-14 — WebApp MVP + Database Migration

### Phase 5: Database Migration
- [ ] PostgreSQL/Supabase setup
- [ ] Migrate Parquet → PostgreSQL
- [ ] Migrate SQLite KPI → PostgreSQL
- [ ] Update DAL (`data_access.py`) for PostgreSQL

### Phase 6: WebApp Full Deploy
- [ ] Complete all 8 dashboard pages
- [ ] Deploy Next.js + FastAPI on VPS
- [ ] Multi-user auth (10-100 users)
- [ ] SSR optimization for performance

### Phase 7: CI/CD Pipeline
- [ ] GitHub Actions: lint + test on PR
- [ ] Auto-deploy to VPS on merge to main
- [ ] Test coverage gate (50%+)

---

## Future Milestones: Sprint 15-16 — Scale

### Phase 8: Multi-tenant Architecture
- [ ] User role management (admin, operator, viewer)
- [ ] Data isolation per organization
- [ ] 100 → 1,000 user scaling

### Phase 9: Advanced Intelligence
- [ ] Predictive pricing model
- [ ] Automated email parsing + quote generation
- [ ] WhatsApp Bot integration

---

## Milestone Numbering
- Phases 1-4 = Sprint 12 (current)
- Phases 5-7 = Sprint 13-14
- Phases 8-9 = Sprint 15-16
- New phases append sequentially
