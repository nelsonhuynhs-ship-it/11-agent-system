# ROADMAP — v1.1 Smart Ops & Price Intelligence

## Overview
**3 phases** | **17 requirements** | All covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Shipment Brain + Infra | Real-time shipment monitoring + pipeline hardening | SHIP-01..04, INFRA-01..03 | 7 |
| 2 | Mentee Coach + Campaigns | Mentee coaching triggers + campaign tracking | MENTEE-01..03, CAMPAIGN-01..03 | 6 |
| 3 | Price Intelligence | Rate change detection + re-engagement alerts | PRICE-01..04 | 4 |

---

## Phase 1: Shipment Brain + Infrastructure Hardening

**Goal:** Transform shipment_brain.py into a continuous event catcher with SLA tracking, and harden the pipeline for production reliability.

**Requirements:** SHIP-01, SHIP-02, SHIP-03, SHIP-04, INFRA-01, INFRA-02, INFRA-03

**Success Criteria:**
1. Task Scheduler runs shipment monitor every 15-30 min and catches all lifecycle events
2. Risk events (change vessel, delay, amendment) create prioritized task list in SQLite
3. Missing stage alerts fire when SLA is exceeded (configurable hours per stage)
4. Nelson can see "What needs my attention right now?" from briefing
5. SQLite uses WAL mode, concurrent writes don't fail
6. requirements.txt exists with pinned versions
7. Outlook COM operations retry 3x on failure

---

## Phase 2: Mentee Coaching + Campaign Tracking

**Goal:** Detect when mentees need coaching and unify campaign email tracking into the intelligence pipeline.

**Requirements:** MENTEE-01, MENTEE-02, MENTEE-03, CAMPAIGN-01, CAMPAIGN-02, CAMPAIGN-03

**Success Criteria:**
1. System detects mentee-customer conversations and flags coaching opportunities
2. Slow reply / missing CC / incomplete info patterns generate alerts
3. Weekly mentee scorecard shows emails, risks, and coaching needs
4. Campaign lifecycle (send → reply → follow-up) tracked in SQLite
5. Campaign performance metrics (sent, replied, conversion) available in briefing
6. Existing send_email.py and read_email1.py events flow into unified DB

---

## Phase 3: Price Intelligence Alerts

**Goal:** Connect PricingSystem parquet data to email campaigns — alert when better rates available for previously-quoted customers.

**Requirements:** PRICE-01, PRICE-02, PRICE-03, PRICE-04

**Success Criteria:**
1. System reads Cleaned_Master_History.parquet and detects rate changes by route/carrier
2. Cross-reference works: "Customer A got rate $X on day Y, today rate is $Z (lower)"
3. Daily "Price Opportunity" list generated with customer, old rate, new rate, savings %
4. Alert integrates into nelson_briefing.xlsx as new sheet or into Telegram
