# Rate Pipeline Contract

**Last updated:** 2026-04-11 | **Owners:** Nelson, pricing team
**Related plan:** `plans/260411-2019-rate-pipeline-reorg/`

Single source of truth for the rate import pipeline: who writes which
folder, which cron jobs run when, and which Python paths are canonical.

## TL;DR for new contributors

1. All pricing data lives under **`D:/OneDrive/NelsonData/pricing/`**. Never
   put rate data in the repo.
2. Always import paths from **`shared.paths`**. Never hardcode.
3. `rate_importer.py` is the only writer for `incoming/` and `processed/`.
4. `CARRIER_RATE_MAPPING.json` is edited **only** on OneDrive — the repo copy
   was deleted on 2026-04-11.

## Folder contract

| Folder | Path | Writer | Reader | Lifecycle |
|---|---|---|---|---|
| rate-tables | `{pricing}/rate-tables/` | Nelson (manual) + Harry (email) | `rate_importer` | Persistent reference rates (PUC, Fixed Rate, HPL SCFI templates) |
| incoming | `{pricing}/incoming/` | `rate_importer.scan_pricing_emails` | `rate_importer.classify_and_import` | Ephemeral — drained after each import via `safe_move` + `drain_drift` |
| processed | `{pricing}/processed/` | `rate_importer.safe_move` (post-import) | Audit only | Persistent archive of imported files |
| mapping | `{pricing}/mapping/` | Human edit only | All scripts via `shared.paths.CARRIER_RATE_MAPPING` | Versioned, canonical |
| knowledge | `{pricing}/knowledge/` | `rate_importer.extract_knowledge` (JSON email archive) | Manual lookup + future catalyst-crawler | Persistent |
| _backup | `{pricing}/_backup/` | `rate_importer` (parquet pre-write backup) | Rollback only | Auto-rotated — keeps last 1 |
| forecast | `{pricing}/forecast/` | `run_forecast.py` 6-agent stack | ERP + WebApp + Bot | Persistent |

**Invariant:** `incoming/` and `processed/` must have **zero overlap** at any
time. The `download_attachments` step checks `processed/` before saving to
`incoming/`; `safe_move` retries on `PermissionError`; `drain_drift` is the
safety-net cleanup. Any drift is a bug — file a plan phase.

## Canonical path table — `shared/paths.py`

Every module that needs a pricing path **must** import from here. Any grep
for hardcoded paths outside `shared/paths.py` is a violation.

```python
from shared import paths as sp

sp.DATA_DIR                 # D:/OneDrive/NelsonData
sp.PRICING_DATA             # .../pricing
sp.PARQUET_FILE             # .../pricing/Cleaned_Master_History.parquet
sp.RATE_TABLES_DIR          # .../pricing/rate-tables
sp.MAPPING_DIR              # .../pricing/mapping
sp.CARRIER_RATE_MAPPING     # .../pricing/mapping/CARRIER_RATE_MAPPING.json
sp.CARRIER_RULES            # .../pricing/carrier_rules.json
sp.EMAIL_DATA               # .../email
sp.PORT_MAP                 # .../email/Port_Code_Mapping_Final.xlsx
sp.CODE_DIR                 # repo root
```

From `rate_importer.py` you can also use the module-level exports:

```python
from Pricing_Engine.rate_importer import (
    INCOMING_DIR, PROCESSED_DIR, KNOWLEDGE_DIR,
    PARQUET_FILE, RATE_TABLES_DIR,
    drain_drift, safe_move,
)
```

## Task scheduler inventory

All cron-like jobs touching pricing. If you add a new one, update this table
**and** `memory/project-task-scheduler.md`.

| Job | Schedule | Script | Writer | Effect |
|---|---|---|---|---|
| **rate-import** | Manual / GoClaw cron (Mon-Fri 9am preferred) | `tools/goclaw/bat/rate-import.bat` → `Pricing_Engine/rate_importer.py` | parquet + incoming→processed | Scans Outlook, dedups against processed, imports new rates, drains drift |
| **rate-import --drain** | On-demand | `python rate_importer.py --drain` | deletes drift from incoming | Emergency cleanup if drift accumulates |
| **parquet-build** | Sunday 6am | `tools/goclaw/bat/parquet-build.bat` → `email_engine/core/data_collector.py` | Rebuild email parquet (NOT rate parquet) | Orthogonal to rate pipeline |
| **query-rate** | On-demand | `tools/goclaw/bat/query-rate.bat` | read-only | CLI query wrapper |
| **rate-alert** | On-demand | `tools/goclaw/bat/rate-alert.bat` | read-only | Surcharge change alerts from parquet |
| **erp-refresh** | On-demand (ERP ribbon button) | `ERP/core/refresh.py` or `refresh-v14.py` | writes ERP_Master_v14.xlsm | Parquet → xlsm |

## `rate_importer` CLI reference

```bash
# Full import: scan Outlook → classify → import → update parquet → refresh ERP
python Pricing_Engine/rate_importer.py --days 3

# Filter by type
python Pricing_Engine/rate_importer.py --days 7 --type FAK

# Import files already staged in incoming/ (skip Outlook scan)
python Pricing_Engine/rate_importer.py --import-pending

# Just list pending emails, don't download
python Pricing_Engine/rate_importer.py --days 3 --scan-only

# Emergency: delete incoming files that are already in processed
python Pricing_Engine/rate_importer.py --drain
```

## What changed 2026-04-11

Summary of the four-phase reorg (`plans/260411-2019-rate-pipeline-reorg/`):

1. **P1** — drained 3 FAK duplicates from `incoming/` (all had identical
   siblings in `processed/`); backup at
   `{pricing}/_backup/pre-reorg-260411-2054/`
2. **P2** — `rate_importer.py` now:
   - Skips download when target name already exists in `processed/` (bug fix)
   - Uses `safe_move` with 3× retry on `PermissionError` (gc between attempts)
   - Exposes `drain_drift()` and `--drain` CLI flag
   - Auto-drains before every `--import-pending` / full import
3. **P3** — `master_loader_v2.py` now imports `MAPPING_DIR` from
   `shared.paths`. Repo `Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json`
   deleted; a README stub points to OneDrive
4. **P4** — this document

## Regression coverage

Any change to `rate_importer.py` must keep these tests green:

```bash
# Unit (no Excel)
python -m pytest tests/unit/test_rate_importer_drift.py -v
# 7 tests: drain_drift + safe_move

# Integration (requires Excel + OneDrive)
scripts\run-erp-tests.bat
# 11 tests passing + 3 skipped
```

## Known-good state

| Metric | Value (2026-04-11 21:00) |
|---|---|
| Parquet size | 11.2 MB |
| Parquet rows | ~6.75M historical |
| `incoming/` files | 1 (SCFI N41, pending import) |
| `processed/` files | 5 (FAK 08/09/10 APR, SCFI N40, Fixed Rate 21) |
| `mapping/` files | 6 (1 JSON + 1 history CSV + 4 validation CSVs) |
| `_backup/` entries | 1 pre-reorg snapshot + 1 rotating parquet backup |

## Non-goals (YAGNI — deferred)

- Knowledge folder pruning (372 JSONs) — no complaint yet
- PUC logic consolidation across `rate_importer` + `master_loader_v2` +
  `pipeline_rules.json` — too risky without test coverage, revisit after
  Task A P2 (Python extraction from VBA) gives us unit test substrate
- `Cleaned_Master_History_slim.parquet` audit — unclear if still referenced
- `nmi_config.json` cleanup — only 1 reference in `rate_monitor.py`, not
  blocking anything

## Open issues

1. Is `Pricing_Engine/scripts/master_loader_v2.py` still authoritative, or
   has `rate_importer.classify_and_import` absorbed its role? Two PUC logic
   paths is a landmine.
2. `data_collector.py` writes `email_engine` parquet — confirm that NEVER
   collides with rate pipeline.
3. Should `rate-import.bat` be on a real cron (daily 8am) instead of manual?
   — waiting on Nelson decision.
