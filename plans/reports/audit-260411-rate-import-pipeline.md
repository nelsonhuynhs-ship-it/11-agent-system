# Rate Import Pipeline Audit

## Current Flow

```
OUTLOOK EMAILS (pricing@pudongprime.vn)
        ↓
  [rate_importer.py scans]
        ↓
OneDrive/NelsonData/pricing/incoming/ (staging)
        ↓
  [classify_and_import + master_loader_v2.py]
        ↓
OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet (11.2 MB, master)
        ↓
  [refresh_erp_from_parquet.py]
        ↓
ERP/ERP_Master.xlsm (Dashboard + BasicCost_Lookup sheets)
```

**File Types:** FAK, SCFI, FIX classified by email subject patterns.

---

## File Inventory

### Rate Importer Script
- **Path:** Pricing_Engine/rate_importer.py
- **Entry Points:** run_full_import(days=N), scan_pricing_emails(), classify_and_import()
- **Classification:** Subject regex patterns lines 87-102
- **Source:** Outlook from pricing@pudongprime.vn
- **Destinations:** INCOMING_DIR, PROCESSED_DIR, KNOWLEDGE_DIR (JSON email archive)
- **Dependencies:** shared/paths.py, master_loader_v2.py, PUC_SOC.xlsx

### OneDrive Pricing Folder
Base: D:/OneDrive/NelsonData/pricing/

| Folder | Count | Purpose |
|--------|-------|---------|
| rate-tables/ | 3 | PUC MAR 2026.xlsx, Fixed Rate Summary, HPL SCFI CONTRACT |
| incoming/ | 4 | Downloaded FAK/SCFI files awaiting import |
| processed/ | 5 | Archive of imported files |
| mapping/ | 6 | CARRIER_RATE_MAPPING.json + V4_FINAL_CHECK_*.csv |
| knowledge/ | 372+ | Email archive JSON (operational logs) |
| _backup/ | 1 | Timestamped Parquet backups |
| ROOT | 2 | Cleaned_Master_History.parquet (11.2 MB ACTIVE), _slim (785 KB) |

### Carrier Rules
**ERP/carrier_rules/**
- booking_rules.json: Booking email template
- weight_rules/: 9 carrier surcharge rules (COSCO, EMC, HMM, HPL, MSC, MSK, ONE, YML, ZIM)
- builder.py: Rule engine

**Pricing_Engine/config/**
- pipeline_rules.json: Master config for master_loader_v2 (PUC, container norm, commodity, ONE group codes)
- nmi_config.json: (purpose unclear)

### Mapping Files
- CARRIER_RATE_MAPPING.json: Master column map (Pricing_Engine/Mapping + OneDrive/mapping)
- MASTER_MAPPING_HISTORY.csv: Mapping audit trail
- V4_FINAL_CHECK_*.csv: Validation checksums (FAK, FIX, SCFI)
- Port_Code_Mapping_Final.xlsx: OneDrive/email/

### Task Scheduler (tools/goclaw/bat/)
- rate-import.bat → Pricing_Engine/rate_importer.py (manual or on-demand)
- parquet-build.bat → email_engine/core/data_collector.py (Sunday 6am)
- query-rate.bat, rate-alert.bat (on-demand)

### Parquet Master
| File | Location | Size | Status |
|------|----------|------|--------|
| Cleaned_Master_History.parquet | OneDrive/pricing/ | 11.2 MB | ACTIVE |
| Cleaned_Master_History.parquet | Pricing_Engine/data/ | N/A | MISSING |
| Cleaned_Master_History_slim.parquet | OneDrive/pricing/ | 785 KB | Archive |
| Cleaned_Master_History_BACKUP_*.parquet | OneDrive/pricing/_backup/ | 11.2 MB | Auto backups |

**FINDING:** Parquet is always on OneDrive. shared/paths.py resolves sp.PARQUET_FILE → OneDrive. Repo copy never created.

---

## Scattered/Duplicate Files

| Issue | Files | Action |
|-------|-------|--------|
| Parquet in repo? | Pricing_Engine/data/Cleaned_Master_History.parquet | NOT FOUND — never synced to repo |
| Mapping duplication | Pricing_Engine/Mapping/ vs OneDrive/mapping/ | VERIFY if synced — Git has copy |
| Backup in repo | email_engine/_backup/backup_20260320/Port_Code_Mapping_Final.xlsx | DELETE — dead backup |
| Knowledge folder | OneDrive/pricing/knowledge/ (372 JSON) | KEEP — operational email archive |
| Config scatter | Pricing_Engine/config/ vs email_engine/config/ | OK — separate systems |

---

## Proposed Clean Structure

```
OneDrive/NelsonData/pricing/
├── Cleaned_Master_History.parquet        [MASTER — 11.2 MB]
├── _backup/
│   └── Cleaned_Master_History_BACKUP_*.parquet
├── rate-tables/                          [Carrier rate files]
├── incoming/                             [Downloaded emails awaiting import]
├── processed/                            [Archive after import]
├── mapping/                              [CANONICAL: CARRIER_RATE_MAPPING.json, V4_FINAL_CHECK_*.csv]
└── knowledge/                            [Email archive]

Pricing_Engine/ (repo)
├── rate_importer.py
├── scripts/master_loader_v2.py           [FAK/SCFI/FIX → parquet]
├── scripts/refresh_erp_from_parquet.py   [parquet → ERP]
├── config/pipeline_rules.json            [Master rules — KEEP SYNCED with OneDrive]
└── Mapping/CARRIER_RATE_MAPPING.json     [DELETE or backup only]

ERP/
├── carrier_rules/booking_rules.json
├── carrier_rules/weight_rules/           [Per-carrier rules]
└── core/refresh.py                       [Reads sp.PARQUET_FILE]
```

---

## Reorganization Actions

1. **Verify Mapping Sync:** Is Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json hand-edited or auto-synced? Establish single owner (OneDrive).

2. **Delete Dead Backup:** email_engine/_backup/backup_20260320/Port_Code_Mapping_Final.xlsx

3. **Clarify nmi_config.json:** Is it used by any script? If not, delete.

4. **Formalize Parquet Master:** Add comment in shared/paths.py — PARQUET_FILE must be on OneDrive, never local.

5. **Enforce Rate Table Naming:** Standardize rate-tables/ folder naming for auto-detection.

6. **Verify Knowledge Archive Cleanup:** Optional: prune files >90 days old.

7. **Document Task Scheduler:** List which .bat files run on which schedule.

---

## Unresolved Questions

1. **PUC Logic:** rate_importer.py hardcodes PUC stripping for CMA/ONE/YML. Is this the source of truth, or master_loader_v2.py?
2. **Slim Parquet:** What is Cleaned_Master_History_slim.parquet for? Is it kept current?
3. **Knowledge Pruning:** Should knowledge/ folder auto-archive files >N days old?
4. **Mapping Ownership:** Is Pricing_Engine/Mapping/ the source or OneDrive/mapping/? Prevent divergence.
5. **NMI Config:** Is nmi_config.json referenced anywhere? If dead, remove.
6. **VPS Sync:** Does shared/paths.py correctly resolve /opt/nelson/data on VPS? Test in production.
