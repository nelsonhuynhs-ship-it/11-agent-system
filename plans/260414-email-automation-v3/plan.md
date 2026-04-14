# Email Automation Upgrade v3 — Master Plan
**Date:** 2026-04-14 | **Status:** ACTIVE — THE ONLY PLAN
**Visual:** `D:/OneDrive/erp/quote-mockups/email-automation-upgrade-plan.html`

## Phase 1: Data Foundation (Priority: HIGHEST)
- [ ] Migrate cnee_master.xlsx 16→25 columns
- [ ] Add: PIC_TITLE, PHONE, WHATSAPP_OK, COUNTRY, ARB_ORIGINS, LEAD_SCORE, BOUNCE_COUNT, LAST_REPLY, EMAIL_STATUS, INDUSTRY
- [ ] Auto-fill POL defaults for 3,256 missing rows (from Panjiva/shipment history)
- [ ] Auto-fill DESTINATION for 2,492 missing rows
- [ ] Bounce handler: scan Outlook NDR → mark INVALID
- [ ] Email syntax + MX verify before send
- [ ] Import ARB YAML (HPL/CMA/ONE/YML × China/Thai/Cambodia/Malaysia)
- [ ] Wire arb_engine.py into auto_rate_builder.py

## Phase 2: Email Intelligence (Priority: HIGH)
- [ ] Activate sequence_engine.py: 4-step (Day 0→3→7→14)
- [ ] Reply detection via outlook_scanner.py → HOT LEAD alert → Telegram
- [ ] Auto-stop sequence when reply detected
- [ ] ARB cross-origin rates in email rate table
- [ ] Lead scoring: reply=+30, open=+10, bounce=-50
- [ ] A/B test subject lines (2 variants)

## Phase 3: WhatsApp Channel (Priority: MEDIUM)
- [ ] Setup Meta Business + WhatsApp Cloud API
- [ ] Create template messages (rate_update, follow_up, market_alert)
- [ ] whatsapp_sender.py module
- [ ] Verify PHONE → WHATSAPP_OK flag
- [ ] Webhook for reply detection + opt-out
- [ ] Parallel send: Email + WhatsApp same contact

## Phase 4: Analytics & Scale (Priority: LOW)
- [ ] History tab: per-campaign open/reply/bounce rates
- [ ] AI model accuracy iteration (ck:loop)
- [ ] Panjiva weekly auto-enrich
- [ ] Target: 1000 email + 100 WhatsApp per day
