# ARCHITECTURE — System Design

## System Overview
A **multi-pipeline email intelligence system** for Nelson (freight forwarding manager at Pudong Prime). Processes Outlook emails via 3 distinct pipelines: Team Routing, Sales Outreach, and Data Intelligence.

## Architecture Pattern
**Pipeline / ETL architecture** — no web server, no REST API. Each pipeline is a standalone Python script orchestrated by `run_all.py` (CLI menu) and Windows Task Scheduler.

```
Outlook → main.py (routing + .msg save) → outlook/ disk
                                              ↓
                        data_collector.py (parse .msg → SQLite)
                                              ↓
                        nelson_briefing.py (SQLite → Excel dashboard)
                        
Outlook ← send_email.py ← process_reply.py ← read_email1.py (scan bounce)
                                              ↓
                        generate_dashboard.py (Excel report)
```

## Data Flow Layers

### Layer 1: Email Routing (`core/main.py`)
- Scans Outlook inbox every 30 min
- **Two-tier routing:** Tier 1 matches sender email → move to member folder; Tier 2 matches recipient email
- Saves `.msg` copies to `outlook/TEAM_SUNNY/{member}/` via `save_msg_local()`
- Rules defined in `data/rules.json`

### Layer 2: Sales Pipeline (`read_email1.py → process_reply.py → send_email.py`)
- `read_email1.py` — Scans sent items + inbox for bounces, classifies customer replies into tiers (REPLY_1, REPLY_2, REPLY_3)
- `process_reply.py` — Processes classified replies, builds `customer_final.xlsx`
- `send_email.py` — Sends campaign emails via Outlook COM
- `follow_up_engine.py` — Generates follow-up alerts
- `sequence_engine.py` — Auto-advances 3-email drip sequences

### Layer 3: Intelligence Pipeline (NEW — `email_parser.py → data_collector.py → nelson_briefing.py`)
- `email_parser.py` — `EmailClassifier` classifies emails (SHIPMENT/SALES/INTERNAL) and parses structured fields
- `data_collector.py` — Scans `.msg` files from disk → SQLite (5+ tables)
- `pst_importer.py` — Imports historical PST via Outlook COM with 3-layer filter
- `nelson_briefing.py` — Generates daily Excel briefing (5 sheets)
- `reply_analyzer.py` — Cross-references sales replies with Panjiva data

### Layer 4: Shipment Brain (`core/shipment_brain.py`)
- Real-time Outlook monitoring for shipment events
- Telegram alerts for CRITICAL/HIGH risk events
- Stage tracking against lifecycle rules

## Entry Points
| Entry Point | Trigger | Description |
|-------------|---------|-------------|
| `run_all.py` | Manual / CLI | 13-option menu orchestrating all pipelines |
| `core/main.py` | Task Scheduler (30 min) | Outlook inbox routing |
| `core/data_collector.py` | Task Scheduler (60 min) | .msg → SQLite |
| `core/nelson_briefing.py` | Task Scheduler (daily 07:45) | Excel dashboard |
| `core/shipment_brain.py` | Manual | Real-time Outlook monitoring |
| `core/pst_importer.py` | Manual | Historical PST import |

## Key Abstractions
- `EmailClassifier` (class in `email_parser.py`) — Shared classifier used by data_collector + pst_importer
- `DataCollector` (class in `data_collector.py`) — DB init, scan, upsert, export
- No shared base classes or interfaces — each module is standalone
