# REQUIREMENTS — v1.1 Smart Ops & Price Intelligence

## v1.1 Requirements

### SHIP — Shipment Intelligence
- [ ] **SHIP-01**: System continuously monitors Outlook for shipment events (BOOKING → PAYMENT lifecycle) and auto-detects which shipments need Nelson's attention
- [ ] **SHIP-02**: System identifies risk events (change vessel, delay, amendment) and creates prioritized task list with action recommendations
- [ ] **SHIP-03**: System tracks missing stages per shipment and alerts when SLA is exceeded (e.g. no ATD 3 days after ETD)
- [ ] **SHIP-04**: Task Scheduler runs event catcher every 15-30 min, building real-time shipment state in SQLite

### MENTEE — Mentee Sales Coaching
- [ ] **MENTEE-01**: System detects when mentee is handling a customer conversation and flags if coaching/escalation is needed
- [ ] **MENTEE-02**: System identifies mentee response patterns (slow reply, missing CC, incomplete info) and generates coaching alerts
- [ ] **MENTEE-03**: System provides Nelson with mentee performance scorecard (emails handled, risk events, customer satisfaction signals)

### CAMPAIGN — Campaign Email Tracking
- [ ] **CAMPAIGN-01**: System tracks outreach campaigns (NELSON WEEK X) → customer replies → follow-up actions in a unified timeline
- [ ] **CAMPAIGN-02**: System integrates with existing send_email.py and read_email1.py to capture campaign lifecycle events into SQLite
- [ ] **CAMPAIGN-03**: System generates campaign performance metrics (sent, opened/replied, HOT/WARM/COLD conversion rates)

### PRICE — Price Intelligence Alerts
- [ ] **PRICE-01**: System reads Cleaned_Master_History.parquet from PricingSystem Engine and detects rate changes by route/carrier
- [ ] **PRICE-02**: System cross-references: "Customer A was sent rate X on date Y → today's rate is lower" and triggers re-engagement alert
- [ ] **PRICE-03**: System generates daily "Price Opportunity" list: customers who received quotes 3-7 days ago where today's rate is better
- [ ] **PRICE-04**: Alert includes: customer name, original rate sent, new rate, savings %, route, carrier — ready for Nelson to act

### INFRA — Pipeline Hardening
- [ ] **INFRA-01**: Create requirements.txt with pinned dependencies
- [ ] **INFRA-02**: Enable SQLite WAL mode for concurrent access safety
- [ ] **INFRA-03**: Add structured error handling with retry logic for Outlook COM operations

## Future Requirements (v1.2+)
- Web dashboard replacing Excel briefings
- AI auto-draft replies for HOT/WARM leads
- Customer CRM with full interaction history
- Chatbot integration (Telegram bot for queries)

## Out of Scope
- Web app UI (existing webapp in PricingSystem handles this)
- Database migration to PostgreSQL (SQLite sufficient for current scale)
- Multi-user authentication (single-user Nelson system)

## Traceability
| REQ-ID | Phase |
|--------|-------|
| SHIP-01..04 | Phase 1 |
| MENTEE-01..03 | Phase 2 |
| CAMPAIGN-01..03 | Phase 2 |
| PRICE-01..04 | Phase 3 |
| INFRA-01..03 | Phase 1 |
