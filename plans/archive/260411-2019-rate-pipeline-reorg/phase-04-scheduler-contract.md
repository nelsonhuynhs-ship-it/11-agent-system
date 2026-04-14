# Phase 4 — Document scheduler + folder contract

**Priority:** LOW (documentation, no code) | **Status:** PENDING
**Effort:** 30 min | **Files touched:** `docs/rate-pipeline-contract.md`, memory update

## Context

Currently task scheduler knowledge is split across:
- `tools/goclaw/bat/` (4 .bat wrappers)
- Memory `project-task-scheduler.md` (partial)
- Memory `project-auto-campaign-flow.md`
- GoClaw cron config

No single doc lists: which job runs when, what it touches, who owns it. Onboarding Johnny/Jennie to this area = reading 5 memory files.

## Actions

### 4.1 Create `docs/rate-pipeline-contract.md`
Single page covering:

**Folder contract** — each OneDrive folder's responsibility + who writes:
| Folder | Writer | Reader | Lifecycle |
|---|---|---|---|
| `rate-tables/` | Nelson manual / Harry email | rate_importer | Persistent reference |
| `incoming/` | rate_importer (scan_pricing_emails) | rate_importer (classify_and_import) | Ephemeral — drained after import |
| `processed/` | rate_importer (safe_move) | Audit only | Persistent archive |
| `mapping/` | Human edit only | All scripts via `shared.paths.CARRIER_RATE_MAPPING` | Versioned |
| `knowledge/` | rate_importer (email archive) | Manual lookup | Persistent, optional pruning |
| `_backup/` | rate_importer (auto before write) | Rollback only | Auto-rotated |

**Task scheduler inventory** — all cron-like jobs touching pricing:
| Job | Schedule | Script | Effect |
|---|---|---|---|
| rate-import | (manual / GoClaw cron) | `tools/goclaw/bat/rate-import.bat` → `Pricing_Engine/rate_importer.py` | Scan Outlook → incoming → parquet |
| parquet-build | Sunday 6am | `tools/goclaw/bat/parquet-build.bat` → `email_engine/core/data_collector.py` | Rebuild email parquet |
| query-rate | On-demand | `tools/goclaw/bat/query-rate.bat` | CLI query wrapper |
| rate-alert | On-demand | `tools/goclaw/bat/rate-alert.bat` | Surcharge change alerts |
| erp-refresh | On-demand (from ERP ribbon) | `refresh-v14.py` | Parquet → xlsm |

**Single-source path table** — every file path that code references:
```python
# shared/paths.py exports (canonical)
ONEDRIVE_PRICING            # D:/OneDrive/NelsonData/pricing
PARQUET_FILE                # ONEDRIVE_PRICING / Cleaned_Master_History.parquet
INCOMING_DIR                # ONEDRIVE_PRICING / incoming
PROCESSED_DIR               # ONEDRIVE_PRICING / processed
RATE_TABLES_DIR             # ONEDRIVE_PRICING / rate-tables
MAPPING_DIR                 # ONEDRIVE_PRICING / mapping  (added in P3)
CARRIER_RATE_MAPPING        # MAPPING_DIR / CARRIER_RATE_MAPPING.json  (added in P3)
KNOWLEDGE_DIR               # ONEDRIVE_PRICING / knowledge
ERP_XLSM                    # ONEDRIVE_NELSON / erp / ERP_Master_v14.xlsm
```

Any script importing via other means is a violation.

### 4.2 Update memory
Update `memory/project-task-scheduler.md` (if it exists) or create pointer:
```markdown
Canonical scheduler inventory lives at docs/rate-pipeline-contract.md.
Memory stays for transient state (last run, known issues).
```

### 4.3 Add CI-style check (optional)
Tiny script `scripts/verify-pipeline-contract.py` that:
- Greps for hardcoded `"Cleaned_Master_History"` strings outside `shared/paths.py` → warn
- Greps for `"Mapping/CARRIER_RATE_MAPPING"` → warn
- Prints violations + exit 1

Hook into pre-commit later. For now, manual run in P4.

## Success criteria
- [ ] `docs/rate-pipeline-contract.md` exists, ≤200 lines, covers all 3 tables
- [ ] Folder contract matches current reality (no aspirational entries)
- [ ] Memory file updated or pointer added
- [ ] Grep for hardcoded parquet paths returns ONLY `shared/paths.py`

## Risk
- NONE — documentation only
- No runtime changes

## Next
After P1-P4 complete, consider stretch goals:
- **P5 (optional):** ML forecast auto-retrain trigger (see `plan.md` — Nelson asked 2026-04-11 about count-based retrain)
- **P6 (optional):** PUC logic consolidation — requires test coverage from Task A P2
