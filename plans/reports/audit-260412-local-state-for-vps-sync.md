# LOCAL STATE AUDIT — 2026-04-12
> For VPS Claude to understand what exists on Nelson's local PC (PC Home)
> and what needs rclone/scp sync.

## 1. Git State

### Branch: claude/dazzling-engelbart (4 commits ahead of main)
```
17cea66 docs(plans): add rate pipeline reorg + ERP workflow upgrade plans
93f79ef test(erp): add ERP auto-test infrastructure
c029a4a feat(pricing): add forecast retrain + market report modules
1b771f9 feat(erp): update refresh.py, rate_importer, master_loader + add ERP docs
--- VPS commits below (already on main) ---
ec9eb68 feat(pricing): update CARRIER_RATE_MAPPING with SCFI new columns
669a96c feat(pipeline): add email templates, policy guard, panjiva import, queue manager
d05accc feat(pipeline): add automation pipeline — blacklist, email cleaner, DuckDB pricing, ARB
5665376 fix(security): replace token-in-URL with http.extraheader in goclaw-sync
```

### What local commits contain:
| Commit | Content |
|--------|---------|
| 1b771f9 | ERP refresh.py charge_mapping update, rate_importer SCFI support, master_loader improvements, ERP README docs, .claude/ added to .gitignore |
| c029a4a | Pricing_Engine/forecast_retrain/ (ML retrain pipeline), Pricing_Engine/market_report/ (4C report system, 14 files) |
| 93f79ef | pytest.ini + tests/ (4 unit + 4 integration tests for ERP, rate import, forecast, market report) |
| 17cea66 | Plans: rate-pipeline-reorg (5 phases), erp-workflow-upgrade (6 phases), 5 session reports, 4 docs, 4 helper scripts |

## 2. OneDrive Data Files (D:\OneDrive\NelsonData\)

### Parquet (NEEDS SYNC TO VPS)
| File | Size | Updated | VPS Path |
|------|------|---------|----------|
| `pricing/Cleaned_Master_History.parquet` | **12 MB** | 2026-04-10 | `/opt/nelson/data/pricing/` |
| `pricing/Cleaned_Master_History_slim.parquet` | 767 KB | 2026-04-04 | `/opt/nelson/data/pricing/` |
| `pricing/forecast/_cleaned_weekly.parquet` | — | — | `/opt/nelson/data/pricing/forecast/` |

### Rate Tables (incoming Excel from carriers)
| Dir | Content |
|-----|---------|
| `pricing/rate-tables/incoming/` | Empty (all processed) |
| `pricing/rate-tables/processed/` | Empty (archived or moved) |

### Mapping
| File | Purpose |
|------|---------|
| `pricing/mapping/CARRIER_RATE_MAPPING.json` | Master column definitions for FAK/FIX/SCFI (already pushed to GitHub ec9eb68) |
| `pricing/mapping/MASTER_MAPPING_HISTORY.csv` | Historical mapping audit trail |
| `pricing/mapping/V4_FINAL_CHECK_*.csv` | 4 validation files for FAK/FIX/SCFI column checks |

### ERP (D:\OneDrive\NelsonData\erp\)
| File | Purpose | Sync? |
|------|---------|-------|
| `ERP_Master_v14.xlsm` | Production ERP workbook | NO (local-only, Outlook COM) |
| `CustomUI_v14.xml` | Ribbon definition (2 tabs, 7 groups, 50 controls) | NO |
| `erp-v14-ribbon-callbacks.bas` | 71KB VBA, 50 callbacks | NO |
| `refresh-v14.py` | Parquet → ERP sheets | In repo already |
| `CostBreakdown.bas` | VBA cost breakdown + HDL rules | NO |
| `customui_utils.py` | Ribbon XML injector | In repo already |
| `erp-v14-preset-dryreefer.bas` | Preset module for Dry/Reefer | NO |
| `erp-v14-quick-wins.bas` | Quick win patches | NO |
| `market_history.json` | Historical market data cache | Sync if needed |

### Email Data (D:\OneDrive\NelsonData\email\)
| File | Records | Purpose |
|------|---------|---------|
| `cnee_master_v2_final.xlsx` | 28,169 prospects | Master CNEE database (6 tiers, 23 campaigns) |
| `cnee_master.xlsx` | 5,316 | Legacy CNEE (still used by some scripts) |
| `customer_rules.json` | — | Nelson's direct customers + mentee rules |
| `config.xlsx` | — | Email engine configuration |
| `panjiva/` | — | Panjiva import data directory |
| `campaign_runs/` | — | Campaign execution logs |

## 3. Code Modules on Local (in repo, needs push)

### New modules not yet on VPS:
| Module | Path | Purpose |
|--------|------|---------|
| Forecast Retrain | `Pricing_Engine/forecast_retrain/` | ML model retrain pipeline (2 files) |
| Market Report 4C | `Pricing_Engine/market_report/` | Weekly market report generator (12 files) |
| Test Suite | `tests/` | 8 pytest tests (unit + integration) |
| Helper Scripts | `scripts/` | 4 bat/py scripts for ERP operations |

### Key code changes:
| File | What changed |
|------|-------------|
| `ERP/core/refresh.py` | charge_mapping updated for SCFI, normalize logic improved |
| `Pricing_Engine/rate_importer.py` | SCFI 2 new columns (Contract, MR Code) support |
| `Pricing_Engine/scripts/master_loader_v2.py` | Loader improvements |
| `.gitignore` | Added `.claude/` to ignore list |

## 4. Data Flow: When to use what

| Scenario | Data Source | Why |
|----------|-------------|-----|
| Outlook COM send email | **Local** parquet + master | Outlook runs on local PC |
| WebApp query rates | **VPS** parquet via DuckDB | WebApp runs on VPS |
| GoClaw agents (reporter, auto-reply) | **VPS** parquet via DuckDB | Agents run on VPS |
| Import new rates from carrier | **Local** → parse → update parquet → sync to VPS | Rate files arrive via email locally |

## 5. Sync Actions Needed

### Priority 1: Push git commits
```bash
# On local PC:
cd Engine_test/.claude/worktrees/dazzling-engelbart
git push origin claude/dazzling-engelbart
# Then create PR and merge to main
# VPS: git pull origin main
```

### Priority 2: Sync Parquet to VPS
```bash
# rclone (if configured):
rclone copy "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet" nelson-vps:/opt/nelson/data/pricing/

# Or scp:
scp "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet" nelson@14.225.207.145:/opt/nelson/data/pricing/
```

### Priority 3: Sync CNEE master
```bash
scp "D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx" nelson@14.225.207.145:/opt/nelson/data/email/
```

### Priority 4: Check rclone config
```bash
rclone listremotes  # Should show nelson-vps: or similar
rclone config show nelson-vps
```

## 6. GoClaw Status (Local PC Home)

### Current (from UI screenshot 2026-04-12):
- **Version:** v3.3.0 (upgraded from pinned-260410)
- **12 agents** active (7 original + 5 new platform/squad)
- **5 teams:** PLATFORM-TEAM, TRASUA-DEV, FREIGHT-DEV, TRASUA-OPS, FREIGHT-OPS
- **6 cron jobs** configured

### Agents:
| Agent | Key | Role |
|-------|-----|------|
| PLATFORM-QA | platform-qa | Code review + test (read-only) |
| PLATFORM-DEVOPS | platform-devops | Docker, CI/CD, VPS |
| PLATFORM-BACKEND | platform-backend | FastAPI, DuckDB, PostgreSQL |
| PLATFORM-FRONTEND | platform-frontend | Next.js, React, Tailwind |
| PLATFORM-LEAD | platform-lead | Orchestrator, task decomposition |
| SQUAD-FREIGHT | squad-freight | FreightBrian product owner |
| SQUAD-TRASUA | squad-trasua | TraSuaPOS product owner |
| + 5 more | — | trasua-dev-lead, freight-dev-lead, reporters, marketer |

## 7. .claude/ Infrastructure (Local Only, NOT in git)

Backed up to: `D:\NELSON\2. Areas\_backup\claude-config-260412/` (22 MB)
Contains: 565 skills, 82 hooks, 21 agents, 10 scripts, rules, schemas
These are Claude Code CLI configurations — local only, not needed on VPS.
