# Project: Email Automation Upgrade v3
Last updated: 2026-04-14

## THE ONLY ACTIVE PLAN
Plan HTML: `D:/OneDrive/erp/quote-mockups/email-automation-upgrade-plan.html`
State: `.planning/STATE.md`

## Completed
- ✅ S13 Rate & Send API
- ✅ S14A Dashboard v2 (FastAPI + HTML, localhost:8231)
- ✅ AI Model (XGBoost, 21 corridors, walk-forward)
- ✅ Market Intelligence badge + dynamic intro (URGENT/COMPETITIVE/STABLE)
- ✅ DuckDB 28x faster + Exp +2 day buffer
- ✅ 48h cooldown + email signature from config.xlsx
- ✅ Desktop shortcut (1-click launch)
- ✅ GitHub: b42646b, 896a1b2

## Active: v3 Upgrade (4 Phases)
1. **Phase 1: Data Foundation** — migrate cnee_master 16→25 cols, bounce handler, POL/POD enrich, ARB YAML
2. **Phase 2: Email Intelligence** — 4-step sequence, reply detect, ARB cross-origin pricing, lead scoring
3. **Phase 3: WhatsApp Channel** — Meta Business API, 100+/day template messages, PHONE column
4. **Phase 4: Analytics & Scale** — dashboard metrics, 1000 email/day + 100 WA/day, A/B test

## Key Decisions
- Local dashboard (NOT VPS webapp) — faster, Outlook COM direct
- XGBoost walk-forward (NOT simple train/test) — true OOS metrics
- arb_engine.py exists in api/pipeline/ — wire to email, not rebuild
- WhatsApp via Meta Cloud API — $0.025/conversation, Tier 1 = 1000/day
- sequence_engine.py + outlook_scanner.py already exist — enhance, not rewrite

## Data Schema Target (25 cols)
Existing 16 + New 9: PIC_TITLE, PHONE, WHATSAPP_OK, COUNTRY, ARB_ORIGINS, LEAD_SCORE, BOUNCE_COUNT, LAST_REPLY, EMAIL_STATUS, INDUSTRY

## Archived (DO NOT USE)
S14B/C/D plans superseded by v3. Old plans in plans/archive/.
