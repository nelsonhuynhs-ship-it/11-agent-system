# STACK — Technology Stack

## Language & Runtime
- **Python 3.12** (CPython, Windows)
- No virtual environment management file found (system Python)

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `win32com.client` (pywin32) | — | Outlook COM automation (read inbox, move items, save .msg) |
| `pandas` | — | DataFrames for Excel I/O, CSV processing, Parquet export |
| `openpyxl` | — | Excel .xlsx read/write + formatting |
| `extract-msg` | — | Parse .msg files offline (without Outlook COM) |
| `pyarrow` | — | Parquet file export |
| `httpx` | — | HTTP client (Telegram Bot API) |
| `pyyaml` | — | YAML config parsing (`rules.yaml`, `shipment_patterns.yaml`) |
| `requests` | — | HTTP client (Claude API calls in `pst_importer.py`) |

## Standard Library (heavy use)
`sqlite3`, `json`, `re`, `csv`, `logging`, `logging.handlers`, `shutil`, `uuid`, `argparse`, `pathlib`, `datetime`

## Data Storage
- **SQLite** → `logs/shipments.db` (6 tables: `email_events`, `shipments`, `sales_replies`, `nelson_alerts`, `customers`, `email_maybe_review`)
- **Excel .xlsx** → `data/*.xlsx` (master files: cnee, shipper, contacts, config)
- **CSV** → `logs/*.csv` (email_log, bounce_log, cmd_send_history, followup_alerts, tier_history, email_knowledge)
- **Parquet** → `logs/parquet/*.parquet` (weekly AI/ML export)
- **YAML/JSON** → `data/rules.json`, `data/rules.yaml`, `data/shipment_patterns.yaml`, `data/customer_rules.json`

## Configuration
- `data/rules.json` — Team structure, member info, folders, required CC
- `data/rules.yaml` — Shipment lifecycle rules, stage definitions
- `data/shipment_patterns.yaml` — Regex patterns for shipment parsing
- `data/customer_rules.json` — Customer routing rules
- `data/config.xlsx` — Runtime config (email subjects, templates)

## Scheduling
- **Windows Task Scheduler** via `setup_task_scheduler.ps1`
- 4 tasks: main.py (30min), data_collector.py (60min), nelson_briefing.py (daily 07:45), parquet export (weekly)

## Build / Package
- No `requirements.txt`, `pyproject.toml`, or `setup.py` found
- Dependencies installed globally via pip
