---
name: DATA_FLOW — Single Source of Truth for Schema Contracts
description: Authoritative data contracts & schema evolution across all 6 layers (parquet → DuckDB → auto_rate_builder → API → ERP/UI). Update on every schema change. Validated by scripts/validate-data-contracts.py.
version: 1.0
last_updated: 2026-04-22
maintainer: Nelson Huynh
---

# Data Flow — Nelson Freight System

**PURPOSE:** This document defines all data contracts between layers. When you encounter "sửa ERP ribbon OK nhưng parquet load sai, mapping giá sai," the root cause is **contract drift** — this file prevents that.

**RULE:** Every schema change requires:
1. Update this file (Layer X schema table)
2. Update corresponding pipeline code
3. Update affected downstream layers
4. Run `python scripts/validate-data-contracts.py`
5. Commit with reference to contract change

---

## Quick Reference: Data Pipeline

```
Layer 1: PARQUET (Pricing Master)
  ↓ [read_parquet via DuckDB]
Layer 2: DuckDB Engine (Query wrapper)
  ↓ [query_rates(), get_market_envelope(), get_carrier_list()]
Layer 3: auto_rate_builder (Rate HTML generator)
  ↓ [build_rate_table_for_customer() output dict]
Layer 4: Web Server API (FastAPI endpoints)
  ↓ [/api/v6/contacts, /api/email-rate/*, /api/arb-rates]
Layer 5: ERP Excel (ActiveJobs, Quotes, CRM sheets)
  ↓ [VBA ribbon handlers → Python jobs]
Layer 6: Email Dashboard + Rule Engine (UI + business logic)
```

---

## Layer 1 — Parquet (Pricing Master)

**Source:** `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet`  
**Size:** ~6.6M rows | **Updated by:** `Pricing_Engine/master_loader.py`  
**Last schema update:** 2026-04-22

### Schema (v1)

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| **RATE_ID** | int64 | N | Primary key (auto-increment) | 12345 |
| **POL** | string | N | Port of Loading (uppercase) | HPH, HCM, PKG, BKK, SHA, CGP, NSA, MNL, JKT |
| **POD** | string | N | Port of Discharge (USXXX or CAXXX) | USLAX, USLGB, USEWR, USMIA, CAVAN |
| **Place** | string | Y | City/Region for Parquet search | Denver, NYC, LA, Long Beach, Chicago |
| **Carrier** | string | N | Shipping line (uppercase) | HPL, MSC, OOCL, ONE, CMA, EMC |
| **Container_Type** | string | N | 20GP, 40GP, 40HC, 40HQ, 45HC, 20RF, 40RF | 40HQ |
| **Amount** | float64 | N | Ocean freight cost (USD) | 2939.00 |
| **Eff** | timestamp | N | Effective date (YYYY-MM-DD) | 2026-04-01 |
| **Exp** | timestamp | N | Expiration date (YYYY-MM-DD) | 2026-05-31 |
| **Charge_Name** | string | N | Cost component (standardized) | Total Ocean Freight, BASIC O/F |
| **Rate_Type** | string | Y | Booking type (FAK/FIX/SCFI) | FAK, SCFI, FIX |
| **Contract** | string | Y | Contract number (may include /) | S25NEA203, PSW-HPL-001 |
| **Note** | string | Y | Additional context (SOC/COC, via, scope) | SOC, DIRECT, EC (East Coast) |
| **Commodity** | string | Y | Commodity group (FAK classification) | GENERAL, HOUSEHOLD, FURNITURE |
| **Group_Rate** | string | Y | Rate tier within contract | MR, FAK GCFL, BASKET NAC |
| **Group_Code** | string | Y | Rate code (SCFI only) | PUDSCF001, PUDSCF002 |

### Charge_Name Normalization (LAW)

**All customer quotes use `Charge_Name = 'Total Ocean Freight'` only.**

| Input source | Original label | → Parquet Charge_Name |
|---|---|---|
| Panjiva FAK | `ALL IN COST` | `Total Ocean Freight` |
| Panjiva FAK raw | `BASIC O/F` | `BASIC O/F` (raw, not all-in) |
| HPL SCFI contract | `BASE O/F` | `Total Ocean Freight` (includes DLF+ISPS+EMF+COMM) |
| HPL SCFI raw | `HLCU Offer` | ❌ FORBIDDEN (must normalize) |
| FIX COC | `Base Ocean Freight` | `Total Ocean Freight` |
| FIX SOC | `TOTAL O/F` | `Total Ocean Freight` |

**Normalization pipeline:** `Pricing_Engine/charge_normalizer.py` → reads `CARRIER_RATE_MAPPING.json`

**RULE 1.1:** If Parquet contains `BASIC O/F` or `HLCU Offer` after load, loader has bugs → fail validator.

### Cleaning Pipeline

```
Incoming rates (Panjiva + contracts, YAML files)
  ↓
scripts/panjiva_clean_v2.py
  ├─ Filter expired rates
  ├─ Normalize Charge_Name → 'Total Ocean Freight'
  ├─ Type casting (Amount: str → float64)
  ├─ Column mapping (source → canonical names)
  ↓
scripts/master_loader_v2.py
  ├─ Merge with existing Cleaned_Master_History.parquet
  ├─ De-duplicate on (POL, POD, Carrier, Container_Type, Eff, Exp)
  ├─ Filter Amount > 0
  ↓
D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet
```

### Consumers (downstream layers)

| Consumer | Query type | Filters applied |
|----------|-----------|-----------------|
| DuckDB Engine | query_rates() | Exp >= today, Charge_Name='Total Ocean Freight', Amount > 900 |
| auto_rate_builder | _load_parquet() | Exp >= today (cascade 30d→60d→90d if empty) |
| ERP refresh_v14.py | read_parquet() | Eff+Exp filter, split Dry/Reefer by Container_Type |
| Email dashboard rule_engine | (indirect via auto_rate_builder) | Route + ARB surcharge context |

### Contract Changes Protocol

When modifying Parquet schema:

1. Update this Layer 1 schema table ✓
2. Update `scripts/panjiva_clean_v2.py` output (column list)
3. Update `scripts/master_loader_v2.py` dtype casting
4. Update `api/data_access.py._RATE_COLUMNS` (if adding/removing)
5. Update `db/duckdb_engine.py._date_filter()` and SELECT clauses (if filter logic changes)
6. Update `email_engine/core/auto_rate_builder.py._load_parquet()` (if columns used change)
7. Run validator: `python scripts/validate-data-contracts.py`
8. **DO NOT** deploy parquet change until ERP v14 and API all updated

---

## Layer 2 — DuckDB Engine (Query Wrapper)

**Source:** `db/duckdb_engine.py`  
**Parquet backend:** `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet`  
**Last interface update:** 2026-04-22

### FreightDB Class Interface

```python
from db.duckdb_engine import FreightDB

db = FreightDB(parquet_path="...")  # defaults to shared.paths.PARQUET_FILE
```

### Method Signatures & Output Contracts

#### 1. query_rates()

```python
def query_rates(
    pol: Optional[str] = None,        # "HPH", "HCM", etc. (optional filter)
    pod: Optional[str] = None,        # "USLAX" (LIKE substring match on POD)
    container_type: Optional[str] = None,  # "40HQ", "20GP" (optional filter)
    days: int = 30,                   # lookback window (1–3650 days)
) -> pd.DataFrame:
```

**Output schema:**

| Column | Type | Notes |
|--------|------|-------|
| POL | string | |
| POD | string | |
| Place | string | |
| Carrier | string | |
| Container_Type | string | |
| Amount | float64 | Sorted ascending (cheapest first) |
| Eff | timestamp | |
| Exp | timestamp | |
| Rate_Type | string | |
| Note | string | |
| Commodity | string | |
| Contract | string | |

**Filters applied:**
- `Eff >= (today - days)` and `(Exp IS NULL OR Exp >= today)`
- `Charge_Name = 'Total Ocean Freight'`
- `Amount > 0`

---

#### 2. get_route_median()

```python
def get_route_median(
    pol: str,                         # e.g., "HPH"
    pod: str,                         # e.g., "USLAX"
    container_type: str = "40HQ",
    days: int = 30,
) -> float:  # median USD amount or 0.0 if no data
```

---

#### 3. get_market_envelope()

```python
def get_market_envelope(
    pol: str,
    pod: str,
    container_type: str = "40HQ",
    days: int = 30,
) -> dict:
```

**Output schema:**

```python
{
    "market_low": 2850.0,      # p2.5 percentile
    "market_avg": 3200.0,      # mean
    "market_high": 3800.0,     # p97.5 percentile
    "median": 3150.0,          # median
    "data_points": 42,         # N rows for route
    "carriers": 8,             # distinct carriers
}
```

---

#### 4. get_carrier_list()

```python
def get_carrier_list(
    pol: Optional[str] = None,
    pod: Optional[str] = None,
) -> list[str]:  # sorted alphabetically
```

---

#### 5. get_rate_stats()

```python
def get_rate_stats(
    pol: str,
    pod: str,
    container_type: str = "40HQ",
    days: int = 30,
) -> dict:
```

**Output schema:**

```python
{
    "count": 42,
    "avg": 3200.0,
    "min": 2850.0,
    "max": 3800.0,
    "stddev": 220.0,
}
```

### Date Filter Logic (IMPORTANT)

```
if days >= 1 and <= 3650:
  Eff >= (today - {days} days)
else:
  days = min(max(days, 1), 3650)  # clamp to safe range
```

**Fallback cascade (in auto_rate_builder, not DuckDB itself):** 30d → 60d → 90d if empty

### Consumers (downstream layers)

| Consumer | Method called |
|----------|---------------|
| auto_rate_builder._load_parquet() | read_parquet() directly (does NOT call FreightDB) |
| api/routers/latest_rates_router.py | query_rates(), get_market_envelope() |
| api/routers/intelligence_router.py | get_rate_stats(), get_carrier_list() |

**NOTE:** DuckDB is read-only; no write operations.

---

## Layer 3 — auto_rate_builder (Rate HTML Generator)

**Source:** `email_engine/core/auto_rate_builder.py`  
**Parquet backend:** `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet`  
**Last interface update:** 2026-04-22

### build_rate_table_for_customer()

```python
def build_rate_table_for_customer(
    pol: str = "HPH",
    destinations: str = "",              # comma-separated: "USCHI,USLAX,USSAV"
    markup: float = 20,                  # minimum $USD/container
    top_per_route: int = 5,              # carriers shown per route
    arb_origin: str = None,              # optional: "shanghai", "lat_krabang", "port_klang"
) -> dict:
```

**Output schema:**

```python
{
    # HTML table (Outlook-compatible)
    "html": "<table>...</table><p>Badge</p>",
    
    # Metadata
    "routes_found": 8,                   # count of destination ports with data
    "total_rates": 40,                   # count of rate rows in HTML
    
    # Raw rates per carrier (for API consumption)
    "rates": [
        {
            "pod_code": "USLAX",
            "pod_city": "Los Angeles",
            "carrier": "HPL",
            "container_20gp": 1850.0,    # base + markup
            "container_40hq": 2939.0,
            "container_40gp": 2750.0,
            "parquet_pod": "USLGB",      # original Parquet POD value
            "parquet_place": "Long Beach",
            "contract_type": "SOC",
            "rate_type": "SCFI",
            "group_code": "PUDSCF001",   # SCFI only
        },
        ...
    ],
    
    # Route summary for logging
    "routes_detail": [
        {
            "port": "USLAX",
            "place": "Los Angeles",
            "carriers": ["HPL", "MSC", "OOCL", "ONE"],
        },
        ...
    ],
    
    # Market intelligence (optional)
    "market_context": {
        "direction": "UP",               # UP / DOWN / STABLE
        "confidence": 0.75,              # 0.0–1.0
        "template_type": "URGENT",       # URGENT / COMPETITIVE / STABLE
    },
    "arb_origin": "shanghai",            # echoed from input
}
```

### Internal Data Transformations

**Parquet → HTML pipeline:**

```
_load_parquet()
  ├─ Filter: Exp >= today
  ├─ Cascade: 30d → 60d → 90d if empty
  ├─ Group by POD → top {top_per_route} carriers by rate
  │
  ├─ For each route (POD):
  │   └─ _load_port_map() → POD → city name
  │   └─ For each carrier:
  │       ├─ Apply markup: Amount + $20 (user-supplied)
  │       └─ Populate containers (20GP, 40HQ, etc.)
  │
  ├─ [Optional] ARB integration:
  │   └─ arb_pricing.build_cross_origin_rates()
  │   └─ Apply surcharge per (arb_origin, carrier, rate_type, container)
  │
  ├─ [Optional] Market intelligence:
  │   └─ get_market_context() → AI direction (UP/DOWN/STABLE)
  │
  └─ _build_html_table(all_rows) → HTML string
```

### Parquet Column Usage

| Parquet column | Use in output |
|---|---|
| POL | passed to get_market_context() |
| POD | "pod_code" in output rates |
| Place | "pod_city" in output rates |
| Carrier | "carrier" in output rates |
| Container_Type | expand to 20GP, 40HQ, etc. |
| Amount | base for markup calculation |
| Eff, Exp | filter (cascade 30d→60d→90d) |
| Charge_Name | filter: must be 'Total Ocean Freight' |
| Rate_Type | "rate_type" in output rates |
| Contract | appended to email context (not HTML) |
| Note | "contract_type" (SOC/COC) |
| Group_Code | "group_code" in output (SCFI only) |

### ARB Surcharge Integration

When `arb_origin` is provided (e.g., "shanghai"):

1. Call `arb_pricing.load_arb_rates()`
2. For each rate row: `get_arb_surcharge(arb_origin, carrier, rate_type, container_type)` → USD
3. Replace base rates with ARB-adjusted rates
4. Display ARB badge in HTML header

**ARB keys (from rule_engine.ARB_MAPPING):**
- VN → None (no surcharge)
- MY → "port_klang"
- TH → "lat_krabang"
- CN → "shanghai" or "ningbo"
- KH → "phnom_penh"

### Consumers (downstream layers)

| Consumer | Uses which outputs |
|----------|---|
| email_engine/web_server.py | html (for email body), routes_found, total_rates |
| Email dashboard UI (rule_engine) | rates[], market_context, arb_origin |
| ERP macro QuoteHTML | html (displayed in Quote sheet) |

---

## Layer 4 — Web Server API (FastAPI)

**Source:** `email_engine/web_server.py` + `email_engine/api/routes/*.py`  
**Port:** 8100 (local PC) | **Last update:** 2026-04-22

### Contacts Router (`/api/v6/contacts`)

**Source:** `email_engine/api/routes/contacts_router.py`  
**Backed by:** DuckDB in-memory (reads from `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx`)  
**Cache TTL:** 300 seconds

#### GET /api/v6/contacts (List contacts)

```python
GET /api/v6/contacts?sheet=CNEE&sort_by=EMAIL_STATUS&limit=100

Response 200:
[
  {
    "EMAIL": "alice@company.com",
    "FIRST_NAME": "Alice",
    "COMPANY": "Widget Corp",
    "COMMODITY_CATEGORY": "FURNITURE",
    "ORIGIN_COUNTRY": "VN",
    "DESTINATION_REGION": "West Coast",
    "EMAIL_STATUS": "ACTIVE",
    "SEND_COUNT_EMAIL": 5,
    "SEND_COUNT_WA": 0,
    "SEND_COUNT_LI": 0,
    "LAST_SENT_EMAIL": "2026-04-20",
    "REPLY_STATUS": "REPLIED",
    "TIER": "PROSPECT",
    ... [39 total columns]
  },
  ...
]
```

#### GET /api/v6/contacts/{email}

```python
GET /api/v6/contacts/alice@company.com?sheet=CNEE

Response 200:
{
  "EMAIL": "alice@company.com",
  "FIRST_NAME": "Alice",
  ... [all 41 columns]
}

Response 404 if not found
```

#### PATCH /api/v6/contacts/{email}

```python
PATCH /api/v6/contacts/alice@company.com
Content-Type: application/json

{
  "COMPANY": "New Widget Inc",
  "COMMODITY_CATEGORY": "ELECTRONICS",
  "DESTINATION_REGION": "East Coast",
}

Response 200: { "message": "Updated", "row_count": 1 }
```

**LOCKED COLUMNS (cannot be patched):**
- EMAIL_STATUS, SEND_COUNT_EMAIL, SEND_COUNT_WA, SEND_COUNT_LI
- LAST_SENT_EMAIL, LAST_SENT_WA, LAST_SENT_LI
- REPLY_STATUS
- TIER (if value is "CUSTOMER" or "VIP")

---

### CNEE Contact Schema (Layer 4 contract with Layer 5)

**Source file:** `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` (sheet: CNEE)  
**Rows:** 22,230 CNEE records  
**Columns:** 41 total (including 8 system-locked)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| EMAIL | string | N | Primary key; email address |
| FIRST_NAME | string | Y | |
| LAST_NAME | string | Y | |
| COMPANY | string | Y | |
| JOB_TITLE | string | Y | |
| PHONE | string | Y | |
| CITY | string | Y | |
| STATE | string | Y | |
| COUNTRY | string | Y | |
| POSTAL_CODE | string | Y | |
| WEBSITE | string | Y | |
| LINKEDIN | string | Y | |
| COMMODITY_CATEGORY | string | Y | FURNITURE, FLOORING, CANDLE, etc. (18 categories) |
| ORIGIN_COUNTRY | string | Y | VN, MY, TH, CN, KH, BD, IN, PH, ID (from rule_engine.ARB_MAPPING keys) |
| DESTINATION_REGION | string | Y | West Coast, East Coast, Gulf Coast, Midwest, Canada, etc. |
| **EMAIL_STATUS** | string | Y | ACTIVE / INACTIVE / BOUNCED / HARD_BOUNCE | **[LOCKED]** |
| **SEND_COUNT_EMAIL** | int | Y | Cumulative sends via email | **[LOCKED]** |
| **SEND_COUNT_WA** | int | Y | WhatsApp sends (v6+ feature) | **[LOCKED]** |
| **SEND_COUNT_LI** | int | Y | LinkedIn sends (deferred) | **[LOCKED]** |
| **LAST_SENT_EMAIL** | date | Y | YYYY-MM-DD of last email | **[LOCKED]** |
| **LAST_SENT_WA** | date | Y | YYYY-MM-DD of last WA | **[LOCKED]** |
| **LAST_SENT_LI** | date | Y | YYYY-MM-DD of last LI | **[LOCKED]** |
| **REPLY_STATUS** | string | Y | REPLIED / NO_REPLY / OOO | **[LOCKED]** |
| TIER | string | Y | PROSPECT / CUSTOMER / VIP | **[LOCKED if CUSTOMER/VIP]** |
| STATE | string | Y | (duplicated?) |
| ... | string | Y | [20 more columns — custom fields per Nelson] |

**RULE 4.1:** Locked columns updated ONLY via system jobs, never user PATCH.

**RULE 4.2:** EMAIL is immutable primary key (no rename/remap).

---

### Email Rate Router (deprecated — DO NOT USE)

**Removed 2026-04-17.** These endpoints no longer exist:
- ❌ `POST /api/email-rate/send`
- ❌ `POST /api/email-rate/campaign/prospects`
- ❌ `GET /api/email-rate/preview`

Use `email_engine/web_server.py` local endpoints instead.

---

## Layer 5 — ERP Excel (v14)

**Live file:** `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm`  
**VBA modules:** `D:/OneDrive/NelsonData/erp/erp-v14-*.bas` (canonical source)  
**Python jobs:** `ERP/intelligence/*.py`  
**Last schema update:** 2026-04-21

### Active Jobs Sheet — Rate Quote Columns

**Sheet:** Active Jobs | **Headers:** Row 7  
**Rate columns (sample for mapping):**

| Col | Name | Data type | Input source | Contract info |
|-----|------|-----------|---------------|---|
| A | MONTH | text | Manual | — |
| D | CUSTOMER | text | Manual | — |
| E | POL-POD | text | Manual | e.g., "HPH-USLAX" |
| G | CARRIER | text | Quote cell or manual | "HPL", "MSC", "OOCL" |
| J | CONT | text | Quote cell | "40HQ", "20GP" |
| K | QTY | number | Quote cell | — |
| P | SELL | currency | Quote cell (markup) | |
| **Q** | **COST** | currency | Parquet lookup | **[Comment: Carrier / Contract / Service / Breakdown]** |
| W | Contract_Type | dropdown | Quote cell | "SOC" / "COC" |
| X | Profit_Margin | % | Calculated | `(SELL - COST) / SELL * 100` |

### Column Q (COST) — Comment Format (LAW)

**Cell comment (on Col Q) must contain:**

```
S/C: {Carrier} {ContractNumber}
Service: {RateType} {GroupRate} {Note}

Cost Breakdown (USD):
  O/F          ${amount}
  ISPS         ${isps}     [if applicable]
  ARB          ${arb}      [if cross-origin]
  PUC          ${puc}      [if SOC]
  COMMISSION   ${comm}     [if applicable]
  ─────────────
  TOTAL        ${cost}
```

**Example (HPL SCFI HCM→Saint Louis 40HQ):**
```
S/C: HPL S25NEA203
Service: SCFI MR PUDSCF001 EC

Cost Breakdown (USD):
  O/F          2,939
  ISPS            25
  EMF             20
  DLF          1,500
  COMMISSION      16
  ─────────────
  TOTAL        4,500
```

**RULE 5.1:** Comment format validated by `ERP/intelligence/cost_breakdown.py` before quote commit.

### Refresh Flow (Parquet → ERP)

```
Parquet (Layer 1)
  ↓ [refresh-v14.py]
  ├─ Filter: Eff + Exp valid
  ├─ Cascade: 30d → 60d → 90d if empty
  ├─ Split: Dry (20GP/40GP/40HC/45HC/40NOR) vs Reefer (20RF/40RF)
  ├─ Normalize: Charge_Name → 'Total Ocean Freight'
  ├─ Lookup: Place → City mapping
  ↓
ERP_Master_v14.xlsm sheets:
  ├─ Pricing Dry (POL/POD/Carrier/amounts for 6 container types)
  ├─ Pricing Reefer (POL/POD/Carrier/amounts for 2 reefer types)
  ├─ ChargeBreakdown (component breakdown per route)
  ├─ RateVersions (FAK/SCFI/PUC version labels)
  ├─ PUC_Lookup (SOC surcharge by Place)
```

**Script:** `D:/OneDrive/NelsonData/erp/refresh-v14.py` (NOT `ERP/core/refresh.py`)

### CRM Sheet (Customer metadata for Milestone Notify)

**Sheet:** CRM | **Headers:** Row 1

| Col | Name | Type | Notes |
|-----|------|------|-------|
| B | Customer_Name | text | Must match CUSTOMER in Active Jobs |
| H | Contact1_Email | text | Primary CNEE (semicolon list supported) |
| K | Contact2_Email | text | Secondary CNEE |
| AP | **AUTO_NOTIFY** | dropdown | **Y/N** — Enable auto CNEE drafts per customer |

**RULE 5.2:** Milestone email draft only created if `CRM.AUTO_NOTIFY = "Y"` for customer.

### Milestone Notify Columns (added 2026-04-20)

| Col | Name | Type | Updated by | Notes |
|-----|------|------|-----------|-------|
| AO | ATD_DATE | date | VBA Sync button | DD/MM/YYYY from milestone_state.jsonl |
| AP | ETA_DATE | date | Nelson manual | DD/MM/YYYY |
| AQ | NOTIFIED_ATD | dropdown | VBA after draft | Y/N — ATD email drafted |
| AR | NOTIFIED_ETA7 | dropdown | VBA after draft | Y/N — ETA-7 email drafted |

**Pipeline:** `email_engine/jobs/cnee_milestone.py` writes `milestone_state.jsonl` → Nelson clicks "Sync Milestones" button → VBA reads sidecar → updates columns AO–AR.

---

## Layer 6 — Email Dashboard + Rule Engine

**Source:** `email_engine/core/rule_engine.py` + `plans/visuals/email-dashboard-v6.html`  
**Last update:** 2026-04-22

### Rule Engine: resolve_config()

```python
def resolve_config(
    row: dict[str, Any],                # CNEE row from Layer 4
    user_markup: int = 20,              # USD markup per container (user input)
) -> dict:
```

**Input row (from CNEE contact):**
```python
{
    "EMAIL": "alice@company.com",
    "COMMODITY_CATEGORY": "FURNITURE",
    "ORIGIN_COUNTRY": "VN",
    "DESTINATION_REGION": "West Coast",
    ...
}
```

**Output config (passed to auto_rate_builder):**
```python
{
    "email": "alice@company.com",
    "pol": "HCM",                       # from ARB_MAPPING[ORIGIN_COUNTRY]
    "destinations": "USLAX,USLGB",      # default or from row
    "markup": 20,                       # user input
    "arb_origin": None,                 # None for VN (direct); "shanghai" for CN, etc.
    "subject": "Ocean Freight Update — HCM to US | Week 16 | NELSON",
    "commodity": "FURNITURE",
}
```

### ARB_MAPPING (Source of Truth for country routing)

**From rule_engine.py:**

```python
ARB_MAPPING: dict[str, dict[str, str | None]] = {
    "VN": {"pol_default": "HCM", "arb_key": None},              # direct, no surcharge
    "MY": {"pol_default": "PKG", "arb_key": "port_klang"},      # MY uses PKG, ARB to US
    "TH": {"pol_default": "BKK", "arb_key": "lat_krabang"},     # TH uses BKK, ARB to US
    "CN": {"pol_default": "SHA", "arb_key": "shanghai"},        # CN uses SHA (or NGB→ningbo)
    "KH": {"pol_default": "HCM", "arb_key": "phnom_penh"},      # KH via HCM + ARB surcharge
    "BD": {"pol_default": "CGP", "arb_key": None},              # Bangladesh (TBD)
    "IN": {"pol_default": "NSA", "arb_key": None},              # India Nhava Sheva (TBD)
    "PH": {"pol_default": "MNL", "arb_key": None},
    "ID": {"pol_default": "JKT", "arb_key": None},
}
```

**RULE 6.1:** CN ships directly from SHA/NGB — NEVER transits via VN. If ORIGIN_COUNTRY=CN, ignore any VN POL in row data; always use SHA or NGB.

**RULE 6.2:** VN origin uses HCM (default) or HPH (if overridden in row); no ARB surcharge (direct lane).

**RULE 6.3:** Cambodia (KH) routes via HCM base POL + "phnom_penh" ARB surcharge to reach US.

### Subject Template Rotation

**5 templates (anti-spam rotation):**

```python
SUBJECT_TEMPLATES = [
    "Ocean Freight Update — {pol} to {region} | Week {week} | NELSON",
    "Weekly Rate Update — {commodity} | {pol} → US",
    "{pol} to US Freight Rates — Week {week}",
    "Latest Container Rates from {pol} — {region}",
    "Shipping Quote — {pol} to US | Valid end of month",
]
```

**Region mapping (from first destination POD):**
- USLAX, USLGB, USOAK, etc. → "West Coast"
- USNYC, USEWR, USSAV, etc. → "East Coast"
- USHOU, USMSY → "Gulf Coast"
- USCHI, USDAL → "Midwest"
- CAVAN, CATOR → "Canada"

### Dashboard UI Contract (v6)

**2-sheet architecture (Layer 4 contact_unified_v6.xlsx):**

1. **CNEE sheet** (22,230 rows) — prospect contacts, 41 columns (see Layer 4)
2. **SHIPPER sheet** (TBD) — shipper/supplier lookup, similar schema

**Dashboard tabs (Phase 1 ready):**
- Contacts (CNEE list, search, import, typo detection)
- Shipment Tracker (milestone tracking, 3-panel layout)
- Email History (send log, follow-up sequences)
- [Deferred] Multi-channel (v6 Phase 2–3)

---

## Cross-Layer Mapping Table

### Rate Table Flow (Parquet → Email body)

| Step | Parquet column | DuckDB query | auto_rate_builder output | Email HTML |
|---|---|---|---|---|
| 1 | POL | input param | "pol" in config | Subject placeholder `{pol}` |
| 2 | POD | filter via LIKE | "pod_code" in rates[] | Table row (city name) |
| 3 | Amount + Charge_Name | filter='Total Ocean Freight' | "container_20gp" / "container_40hq" | Table cell (+ markup) |
| 4 | Carrier | GROUP BY | "carrier" in rates[] | Table column |
| 5 | Container_Type | expand 20GP/40HQ | separate object keys | Table header |
| 6 | Eff/Exp | CASCADE 30d→60d→90d | "routes_found" count | Email intro "X routes available" |
| 7 | Rate_Type + Contract | lookup join | "rate_type", "group_code" | Email footer note |
| 8 | Note (SOC/COC) | normalize | "contract_type" | Quote cell comment (Col W) |

### CNEE Flow (Unified v6 → API → Email)

| Step | Layer 4 (API) | Layer 6 (Rule Engine) | auto_rate_builder | Email/ERP |
|---|---|---|---|---|
| 1 | contact_unified_v6.xlsx CNEE sheet | resolve_config(row) | — | — |
| 2 | EMAIL | input row | "email" in config | To: field |
| 3 | ORIGIN_COUNTRY | ARB_MAPPING[country] | "pol", "arb_origin" | Subject, quote routes |
| 4 | DESTINATION_REGION | _pod_region() | "destinations" | Subject placeholder {region} |
| 5 | COMMODITY_CATEGORY | _resolve_subject() | "commodity" | Subject placeholder {commodity} |
| 6 | TIER | rule_engine filter | (may skip TIER=BLOCKED) | (not sent) |
| 7 | EMAIL_STATUS | locked, system-updated | — | (not sent if not ACTIVE) |
| 8 | SEND_COUNT_EMAIL | locked, incremented by web_server | — | Dashboard metric |

### ARB Surcharge Flow

| Input | Layer 3 | Layer 6 | Parquet lookup | Output |
|---|---|---|---|---|
| ORIGIN_COUNTRY=MY | "pol"="PKG" | "arb_origin"="port_klang" | — | auto_rate_builder calls arb_pricing.get_arb_surcharge("port_klang", carrier, rate_type, container) |
| ORIGIN_COUNTRY=CN, POL=NGB | — | "arb_origin"="ningbo" | — | ARB surcharge added to base rate |
| ORIGIN_COUNTRY=KH | "pol"="HCM" | "arb_origin"="phnom_penh" | — | ARB surcharge represents transit to US |
| ORIGIN_COUNTRY=VN | — | "arb_origin"=None | — | (no surcharge, direct lane) |

---

## Change Impact Matrix

**When you modify X in Layer N, check impact on Y:**

| Change | Affected Layers | Action |
|--------|-----------------|--------|
| Add column to Parquet | 1→2→3→4→5→6 | Update Layer 1 schema + all downstream queries + selector UI |
| Change Charge_Name norm logic | 1→3→4→5 | Update panjiva_clean.py + auto_rate_builder + ERP refresh script |
| Add new ARB_MAPPING country | 6→3 | Update rule_engine.py + test auto_rate_builder with new country |
| Modify Rate HTML template | 3→6 | Update auto_rate_builder._build_html_table() + email preview UI |
| Add CNEE schema column | 4→6 | Update contact_unified_v6.xlsx + API schema + dashboard filter UI |
| Lock/unlock CNEE column | 4 | Update contacts_router._LOCKED_ALWAYS + Layer 5 job writers |
| Change refresh cascade (30d→90d) | 1→2→3 | Update _date_filter() logic + auto_rate_builder + test |
| Add ERP sheet | 5 | Update refresh-v14.py + VBA ribbon + ERP SOT doc |

---

## Validation Checklist

**Before committing schema changes, run:**

```bash
python scripts/validate-data-contracts.py
```

**Validator checks:**

1. ✓ Parquet file exists and is readable
2. ✓ Parquet schema matches Layer 1 table (required columns present, types correct)
3. ✓ auto_rate_builder.build_rate_table_for_customer() callable with all outputs
4. ✓ API endpoints respond with expected output schemas
5. ✓ ERP refresh-v14.py completes without error
6. ✓ rule_engine.ARB_MAPPING has all 9 countries (VN/MY/TH/CN/KH/BD/IN/PH/ID)
7. ✓ Email template placeholders ({pol}, {region}, {commodity}, {week}) resolvable
8. ✓ CNEE contact_unified_v6.xlsx has 41 columns + 8 locked columns
9. ✓ DuckDB queries parse without SQL errors
10. ✓ No "BASIC O/F" or "HLCU Offer" charge names in active Parquet data

---

## Incident Reference Log

| Date | Layer | Issue | Root cause | Fix |
|---|---|---|---|---|
| 2026-04-17 | 1→5 | ERP Refresh All button returns URL instead of canonical path | `ThisWorkbook.FullName` returns URL when file opened from Teams/O365 | Detect URL + canonical fallback + split log |
| 2026-04-17 | 1→2 | HPL SCFI mapping used `BASE O/F` instead of `Total Ocean Freight` → under-quote $1.5K/40HQ | Charge_Name normalization skipped for HPL rates | Updated panjiva_clean.py to check CARRIER_RATE_MAPPING.json |
| 2026-04-20 | 5→6 | Milestone CNEE emails drafted but not sync'd to Active Jobs | Auto-draft written to file but VBA "Sync Milestones" button not clicked | Added milestone_state.jsonl sidecar + manual VBA button |

---

## Related Documentation

- `docs/SYSTEM_STANDARDS.md` — System-wide rules (canonical paths, charge mapping, rate type cheat sheet)
- `docs/erp-v14-source-of-truth.md` — ERP v14 live file locations and refresh flow
- `email_engine/data/arb_rates.yaml` — ARB surcharge lookup table
- `email_engine/data/Port_Code_Mapping_Final.xlsx` — POD → city name mapping
- `Pricing_Engine/charge_normalizer.py` — Charge name mapping logic
- `scripts/validate-data-contracts.py` — Validation script (TBD if not exists)

---

## Version History

| Date | Version | Changes |
|---|---|---|
| 2026-04-22 | 1.0 | Initial comprehensive baseline — all 6 layers documented, cross-layer mappings complete, ARB routing finalized |

---

**Last Updated:** 2026-04-22 by Nelson Huynh  
**Maintainer:** Nelson Huynh  
**Review cadence:** After every major feature launch, rate schema change, or CNEE model update
