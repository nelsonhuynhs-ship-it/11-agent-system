---
name: panjiva-data-pull
description: Weekly Panjiva data extraction + clean pipeline for Nelson Freight email prospecting
version: 1.0.0
tags: [chrome, automation, data, panjiva, email]
---

# Panjiva Data Pull + Clean Pipeline

Weekly workflow: Chrome pulls fresh data from Panjiva → Python pipeline cleans + merges → cnee_master_v2 updated.

## 5 Chrome Skills

### Skill 1: Panjiva Weekly Fresh Pull
**Trigger:** Weekly Sunday morning (supervised, Chrome open)
**Goal:** Download new shipment data for each POD group

#### Steps:
1. Open Chrome tab → navigate `panjiva.com`
2. Login if needed (Nelson's account)
3. Go to **US Imports** search
4. For EACH of 6 POD groups, run a search:

| Group | Filter: Shipment Destination | Filter: Origin |
|-------|------------------------------|----------------|
| WC-DIRECT | Los Angeles, Long Beach, Oakland | Vietnam |
| EC-NORTH | New York/Newark, Baltimore, Norfolk | Vietnam |
| EC-SOUTH | Savannah, Charleston, Jacksonville | Vietnam |
| GULF | Houston, Mobile, New Orleans | Vietnam |
| CANADA | Vancouver, Montreal, Halifax | Vietnam |
| MALAYSIA | (any US port) | Malaysia (Tanjung Pelepas) |

5. Date range: **Last 7 days** (new data only)
6. Tick export fields (34 fields):
   - Shipment: Arrival Date, Bill of Lading, Matching Fields, Shipment Origin, Shipment Destination, Place of Receipt, Carrier (10 fields)
   - Container: Container Count (1 field)
   - Consignee: Name, Address, City, State, Postal, Country, Full Address, Email 1/2/3, Phone 1/2/3, Website, Profile, Trade Roles (14 fields)
   - Shipper: Name, Full Address, Email 1/2/3, Phone, Website (5 fields)
   - Vessel: Name, IMO (2 fields)
   - Tags: Matching Fields, Goods Shipped (2 fields)
7. Export → Excel
8. Save as: `panjiva_weekly_[group]_[YYYY-MM-DD].xlsx`
9. **Checkpoint** after every 2 groups → confirm continue

#### Post-download (automated by Claude Code):
```bash
cd Engine_test
python -m email_engine.ingest.build_master
```
Pipeline auto-detects new files → clean → merge → update cnee_master_v2.

### Skill 2: ImportYeti New Importer Discovery
**Trigger:** Weekly / on-demand
**URL:** importyeti.com (FREE, no login)

#### Steps:
1. Navigate `importyeti.com`
2. Search: `[product keyword]` (furniture, flooring, candle, plastic, rubber)
3. Filter: Country of Origin = Vietnam
4. Sort: Shipment count DESC
5. For each company in top 50:
   - Extract: Company name, shipment count, top suppliers
   - Check if already in cnee_master_v2 (by company name fuzzy match)
   - If NEW → add to prospect list
6. Save results → `importyeti_[product]_[date].csv`

### Skill 3: Apollo.io PIC Enrichment
**Trigger:** After pipeline clean, for NEED_ENRICHMENT prospects
**URL:** apollo.io (FREE 10K credits/month)

#### Steps:
1. Navigate `apollo.io` → People Search
2. For each company from cnee_master_v2 with missing PIC/email:
   - Search company name
   - Filter role: logistics, import, supply chain, purchasing
   - Extract: Contact name, title, verified email, LinkedIn
3. Batch: 20 companies/session → checkpoint
4. Update cnee_master_v2 with enriched PIC data

### Skill 4: VN Shipper MST Lookup
**Trigger:** After shipper_master.xlsx created
**URL:** masothue.com (FREE)

#### Steps:
1. Navigate `masothue.com`
2. Search: Shipper company name (Vietnamese)
3. Extract: MST (Mã Số Thuế), address, industry, representative
4. Cross-check Softek CRM (OData API) → mark HANDLED_BY
5. Batch: 20 shippers/session

### Skill 5: Competitor Weekly Monitor
**Trigger:** Weekly
**Source:** Panjiva search by NVOCC name

#### Steps:
1. Search Panjiva for each top competitor:
   - Castlegate (14%), Flexport (8%), De Well (7%), KLN (6%), DSV (6%)
2. Compare: shipment count this week vs last week
3. Detect: new CNEE (gained client), lost CNEE
4. Alert via Telegram if competitor loses client >10 TEU

## 8 Panjiva Email Corruption Patterns (Auto-Clean)

The pipeline (`email_cleaner.py`) auto-fixes these patterns:

| # | Pattern | Cases | Fix |
|---|---------|-------|-----|
| 1 | `em` prefix | 1,104 | Strip `em` (whitelist: email, emma, emily...) |
| 2 | `te` prefix | 139 | Strip `te` (whitelist: team, tech, tel...) |
| 3 | Multi-email in 1 field | 1,039 | Split by `, / ; \n` |
| 4 | `email:/mailto:` prefix | 17 | Strip label prefix |
| 5 | `Name <email>` format | 10 | Extract from angle brackets |
| 6 | Phone mixed in | 28 | Extract email after separator |
| 7 | `me` prefix | 10 | Strip `me` (whitelist: mega, mel...) |
| 8 | Compound (`teemail:`) | 76 | Multi-pass strip |

## Weekly Workflow Calendar

| Day | Task | Tool |
|-----|------|------|
| Sun 9AM | Panjiva pull (6 groups) | Chrome Skill 1 |
| Sun auto | Pipeline clean + merge | Claude Code |
| Mon | Apollo enrich (20 prospects) | Chrome Skill 3 |
| Tue-Thu | Send 500 emails/day | COM Outlook batch |
| Fri | Review metrics + kill weak angles | Dashboard |
| Sat | Competitor monitor | Chrome Skill 5 |

## Files

| File | Purpose |
|------|---------|
| `email_engine/ingest/collect_all_sources.py` | Collect 43+ files from 3 sources |
| `email_engine/ingest/email_cleaner.py` | 8-pattern email corruption cleaner |
| `email_engine/ingest/build_master.py` | Split + Cross-ref + Tier assignment |
| `email_engine/ingest/batch_send_outlook.py` | COM Outlook batch sender |
