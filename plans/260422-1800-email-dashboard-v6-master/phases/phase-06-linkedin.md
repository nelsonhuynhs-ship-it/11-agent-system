# Phase 6 — LinkedIn Integration

**Status:** DEFERRED (until WhatsApp stable 1 tháng)
**Effort:** 8h
**Cost:** ~$350/month (Sales Nav $99 + Expandi $100 + enrichment $150)
**Depends on:** Phase 5B stable

## Overview

Hybrid strategy: Sales Navigator (official, 0% ban risk) + Expandi cloud automation (3-5% risk, safe limits). Enrich email/phone → LinkedIn URL for B2B decision makers.

**Why DEFERRED:** Focus WhatsApp first. LinkedIn adds complexity + cost. Launch only after WA ROI confirmed.

## Files to create (when activated)

- `email_engine/core/li_enricher.py` — Lix API wrapper
- `email_engine/core/li_outreach.py` — Expandi webhook integration
- `email_engine/api/routes/li_router.py` — 5 endpoints
- Tab 7 LinkedIn UI

## Workflow

```
STEP 1 Enrichment (Lix API, ~$0.05/lookup)
       ├─ Pool: TIER=HOT + has_email
       ├─ Target: 2,000-5,000 contacts
       └─ Output: fill LINKEDIN_URL, POSITION, LI_MATCH_SCORE

STEP 2 Outreach (Expandi, safe limits)
       ├─ Daily: 20 connection requests
       ├─ Sequence:
       │   Day 0: Connect + note 200 char
       │   Day 3: Follow-up message
       │   Day 7: InMail pitch
       └─ Reply rate target: 12%

STEP 3 Inbox unified
       └─ LinkedIn replies → REPLY_STATUS update in master
```

## Safety rules

- NO browser extensions (23-40% ban risk 2026)
- Connection limit: 20/day, 100/week
- Message personalization required
- Account warm-up 2 weeks before automation
- Monitor acceptance rate → drop if < 15%

## Open questions (pre-activation)

- Nelson có sẵn Sales Nav account cá nhân?
- Budget $350/tháng OK hay tập trung WA?
- Expandi vs La Growth Machine vs HeyReach — chọn nào?

## Decision gate

Activate Phase 6 only if:
- Phase 5B WhatsApp running 1 tháng
- WA generated ≥ 1 HĐ ký
- Nelson confirm budget $350/tháng bearable
