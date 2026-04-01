# PROJECT — Email Intelligence Engine

## Core Value
Automate Nelson's email intelligence workflow: classify, analyze risk, track shipments, coach mentees, and leverage pricing data — so Nelson focuses on decisions, not reading emails.

## Current Milestone: v1.1 Smart Ops & Price Intelligence

**Goal:** Transform the data pipeline into an active intelligence system — real-time shipment monitoring, mentee coaching triggers, campaign tracking, and price-aware re-engagement alerts.

**Target features:**
- Continuous shipment event monitoring with risk/task detection
- Mentee coaching triggers (when mentees handle customers)
- Campaign email tracking (outreach → reply → follow-up)
- Price intelligence alerts (Parquet rate data → re-engagement)
- Integration with PricingSystem Engine parquet data

## What Shipped (v1.0 — Data Pipeline Foundation)
- Outlook inbox routing (main.py, 30-min cycle)
- Sales pipeline (scan → classify → send campaigns)
- Intelligence pipeline (.msg → SQLite → 5-sheet briefing)
- PST importer (5,475 historical emails)
- Shipment brain with Telegram alerts
- Codebase mapped (7 GSD documents)

## Architecture
- Python 3.12, Windows, Outlook COM
- SQLite (logs/shipments.db) — 6 tables, 6,163 email_events
- Excel outputs, Parquet exports, Telegram bot
- PricingSystem parquet at `D:\NELSON\2. Areas\PricingSystem\Engine_test\Pricing_Engine\data\Cleaned_Master_History.parquet`

---
*Last updated: 2026-03-20*
