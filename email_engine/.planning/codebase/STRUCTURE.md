# STRUCTURE — Directory Layout

```
D:\NELSON\email_engine\
├── .agent\               # Antigravity agent config (skills, workflows)
├── .planning\            # GSD planning documents
│   └── codebase\         # This mapping
├── _archive\             # Deprecated scripts
├── _backup\              # Full backup (2026-03-20)
│   └── backup_20260320\  # Snapshot of all files pre-refactor
├── assets\               # Static assets (outlook_dataset.json)
├── backup\               # Backup-related files
│
├── core\                 # ★ MAIN CODE — 18 Python modules
│   ├── main.py           # (24KB) Outlook routing engine
│   ├── email_parser.py   # (13KB) EmailClassifier — classify + parse
│   ├── data_collector.py # (28KB) DataCollector — .msg → SQLite
│   ├── pst_importer.py   # (26KB) PST import via Outlook COM
│   ├── nelson_briefing.py# (10KB) Daily Excel dashboard
│   ├── reply_analyzer.py # (3KB)  Panjiva cross-reference
│   ├── shipment_brain.py # (22KB) Real-time Outlook + Telegram alerts
│   ├── read_email1.py    # (28KB) Bounce scan + reply classification
│   ├── process_reply.py  # (30KB) Reply processing + customer_final
│   ├── send_email.py     # (33KB) Campaign email sender
│   ├── email_engine.py   # (7KB)  Legacy email sender
│   ├── follow_up_engine.py# (14KB) Follow-up alert engine
│   ├── sequence_engine.py # (26KB) 3-email drip sequences
│   ├── generate_dashboard.py# (19KB) email_master.xlsx generator
│   ├── ops_briefing.py   # (6KB)  Ops briefing
│   ├── replacement_outreach.py# (7KB) Replacement lead outreach
│   ├── scan_outlook_folders.py# (23KB) Folder scanner utility
│   └── notify.py         # (2KB)  Windows toast notifications
│
├── data\                 # ★ CONFIGURATION + DATA FILES
│   ├── rules.json        # Team structure, CC rules
│   ├── rules.yaml        # Shipment lifecycle rules
│   ├── shipment_patterns.yaml  # Shipment regex patterns
│   ├── customer_rules.json     # Customer routing rules
│   ├── config.xlsx       # Runtime config
│   ├── cnee_master.xlsx  # Panjiva consignee data
│   ├── contact_master.xlsx     # Contact database
│   ├── customer_final.xlsx     # Classified customer replies
│   ├── shipper_master.xlsx     # Shipper database
│   └── replacement_leads.xlsx  # Replacement lead list
│
├── data_panjiva\         # Raw Panjiva import data
├── ingest\               # ★ DATA INGESTION
│   ├── combine_all.py    # (29KB) Merge Panjiva files → master
│   ├── clean_data.py     # (5KB)  Data cleaning
│   ├── clean_log.py      # (2KB)  Log cleaning
│   ├── merge.py          # (4KB)  Merge helper
│   └── normalize.py      # (11KB) Data normalization
│
├── logs\                 # ★ OUTPUT + LOGS
│   ├── shipments.db      # SQLite database (3.7MB)
│   ├── email_master.xlsx # Generated dashboard
│   ├── nelson_briefing_*.xlsx  # Daily briefings
│   ├── *.csv             # Various logs
│   ├── *.log             # Application logs
│   └── parquet\          # Parquet exports
│
├── outlook\              # ★ EMAIL STAGING
│   ├── CNEE\             # Consignee customer folders
│   ├── SHIPPER\          # Shipper folders
│   ├── AGENT\            # Agent folders
│   ├── INTERNAL\         # Internal folders
│   ├── TEAM_SUNNY\       # Team member subfolders
│   ├── NELSON\           # Nelson's folder
│   ├── _processed\       # Processed .msg files (auto-delete 7d)
│   └── _unmatched\       # Unmatched .msg files
│
├── run_all.py            # ★ ORCHESTRATOR — 13-option pipeline menu
├── test_pipeline.py      # End-to-end test script
├── setup_task_scheduler.ps1  # Windows Task Scheduler registration
├── setup_brain_scheduler.ps1 # Brain service scheduler
├── backup.pst            # Outlook PST export (7.5GB)
├── SOP.md                # Standard operating procedure
└── README.md             # Project documentation
```

## Key Locations
- **Entry point:** `run_all.py` (interactive) or individual `core/*.py` scripts
- **Config:** `data/rules.json` + `data/rules.yaml`
- **Database:** `logs/shipments.db`
- **Outputs:** `logs/` directory
- **Email staging:** `outlook/` subdirectories
