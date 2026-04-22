# Email Automation Upgrade v3 — Master Plan (ARCHIVED)
**Date:** 2026-04-14 | **Status:** ✅ DONE — archived 2026-04-15
**Visual:** `D:/OneDrive/erp/quote-mockups/email-automation-upgrade-plan.html`

> All 4 phases shipped. See commits: f517a5d, bb4264e, 2fab8d3, 5062f57, c4d95bc.

## Phase 1: Data Foundation ✅ DONE (commit f517a5d)
- [x] Migrate cnee_master.xlsx 16→26 columns (data_migrator.py)
- [x] Auto-fill POL defaults for 3,256 missing rows
- [x] Auto-fill DESTINATION for 2,492 missing rows
- [x] Bounce handler: scan Outlook NDR → mark INVALID (bounce_handler.py)
- [x] Email syntax + MX verify before send (email_verifier.py)
- [x] Import ARB YAML (HPL/CMA/ONE/YML × China/Thai/Cambodia/Malaysia) — arb_rates.yaml
- [x] Wire arb_engine.py into auto_rate_builder.py
- [x] /api/data-health + /api/arb-rates endpoints

## Phase 2: Email Intelligence ✅ DONE (commit bb4264e)
- [x] sequence_runner.py: 4-step (Day 0→3→7→14) + auto-advance
- [x] Reply detection via reply_detector.py → HOT LEAD
- [x] Auto-stop sequence when reply detected
- [x] ARB cross-origin rates in email rate table
- [x] Lead scoring 0–100 (lead_scorer.py): reply +30, shipment +20, bounce −20
- [x] 5 endpoints: /api/sequence/due, /send, /replies/scan, /leads/hot, /priority

## Phase 3: WhatsApp Channel ✅ DONE (commit bb4264e)
- [x] Meta Cloud API via whatsapp_sender.py
- [x] Template messages (rate_update, follow_up, market_alert)
- [x] whatsapp_sender.py + whatsapp_webhook.py
- [x] PHONE → WHATSAPP_OK flag
- [x] Webhook for reply detection + STOP opt-out
- [x] 5 endpoints: /api/whatsapp/status, /send, /webhook (GET+POST), /log

## Phase 4: Analytics & Scale ✅ DONE (commit 2fab8d3)
- [x] Analytics Dashboard: 4 KPI cards, timeline chart, campaign table
- [x] /api/analytics/overview + /campaign-stats + /timeline
- [x] Data Quality widget + Hot Leads panel + Follow-up Queue
- [x] Bulk email verifier with dashboard integration (commit 5062f57)

## Superseded
Old S14B/C/D plans replaced by this v3 plan → now all DONE.

## Open follow-ups (not in original plan)
- [ ] Meta Business approval + real API creds in .env (Phase 3 runtime)
- [ ] A/B test subject lines (2 variants) — deferred
- [ ] AI model accuracy iteration (ck:loop) — deferred
- [ ] Panjiva weekly auto-enrich cron — deferred
