# Master v7 Schema Reference (contact_unified_v7.xlsx)

**Last updated:** 2026-04-23  
**File:** `D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx`  
**Rows:** 22,854 CNEE + 2,338 SHIPPER  
**Columns:** 62 (v6: 41 core + v7: 21 new firmographic/multi-origin)  
**Primary key:** EMAIL (unique, non-NULL)

---

## Column Index (62 columns)

### Group 1: Contact Identity (v6 preserved, 15 cols)

Essential contact information, manually maintained or imported.

| # | Column | Type | Nullable | Locked | Description |
|---|--------|------|----------|--------|-------------|
| 1 | EMAIL | string | N | ✅ | Primary key; email address. Immutable. |
| 2 | FIRST_NAME | string | Y | — | First name of contact |
| 3 | LAST_NAME | string | Y | — | Last name of contact |
| 4 | COMPANY | string | Y | — | Company / organization name |
| 5 | JOB_TITLE | string | Y | — | Job title at company (e.g., "Purchasing Manager") |
| 6 | PHONE | string | Y | — | Phone number (international format optional) |
| 7 | CITY | string | Y | — | City of company HQ |
| 8 | STATE | string | Y | — | State / province |
| 9 | COUNTRY | string | Y | — | Country code (2-letter ISO) |
| 10 | POSTAL_CODE | string | Y | — | ZIP / postal code |
| 11 | WEBSITE | string | Y | — | Company website URL |
| 12 | LINKEDIN | string | Y | — | LinkedIn profile URL |
| 13 | TIMEZONE | string | Y | — | IANA timezone (e.g., "America/Los_Angeles") for smart send window |
| 14 | COMMODITY_CATEGORY | string | Y | — | Commodity type: FURNITURE, FLOORING, CANDLE, etc. (18 categories) |
| 15 | DESTINATION_REGION | string | Y | — | US destination: West Coast, East Coast, Midwest, Gulf Coast, Canada |

---

### Group 2: System Lock Columns (v6 preserved, 9 cols)

**NEVER edit manually.** Updated by system jobs (rotation_engine, scan-sent, bounce harvest).

| # | Column | Type | Nullable | Lock rule | Description |
|---|--------|------|----------|-----------|-------------|
| 16 | EMAIL_STATUS | enum | Y | ✅ Always | ACTIVE / INACTIVE / EXCLUDED / SUPPRESSED / BOUNCED / DEAD / HARD_BOUNCE. Rotation engine checks before queue. |
| 17 | SEND_COUNT_EMAIL | int | Y | ✅ Always | Cumulative email sends (lifetime). Incremented by web_server.py. |
| 18 | SEND_COUNT_WA | int | Y | ✅ Always | WhatsApp sends (v6+ feature, deferred Phase 5). |
| 19 | SEND_COUNT_LI | int | Y | ✅ Always | LinkedIn sends (deferred Phase 6). |
| 20 | LAST_SENT_EMAIL | date | Y | ✅ Always | YYYY-MM-DD of last email. ISO 8601 format. NULL = never sent. |
| 21 | LAST_SENT_WA | date | Y | ✅ Always | YYYY-MM-DD of last WhatsApp. |
| 22 | LAST_SENT_LI | date | Y | ✅ Always | YYYY-MM-DD of last LinkedIn. |
| 23 | REPLY_STATUS | enum | Y | ✅ Always | NONE / OOO / LEFT / BOUNCED. Set by scan-sent-outlook.py. |
| 24 | TIER | enum | Y | ✅ if CUSTOMER/VIP | PROSPECT / CUSTOMER / VIP. Locked if value is CUSTOMER or VIP (Nelson-assigned). Editable if PROSPECT. |

---

### Group 3: Firmographic Data (v7 NEW, 12 cols)

Company metadata from Panjiva buyer-level files. **Read-only.** Updated quarterly via migration.

| # | Column | Type | Nullable | Source | Description |
|---|--------|------|----------|--------|-------------|
| 25 | REVENUE_USD | float | Y | Panjiva | Annual revenue in USD (estimated from customs data). Use for HOT/WARM/COLD segmentation. May be NULL (not available for all companies). |
| 26 | EMPLOYEES | int | Y | Panjiva | Total headcount (from business database or estimate). May inflate for VN companies. |
| 27 | TOTAL_SHIPMENTS_ALL | int | Y | Panjiva | Lifetime shipment count across ALL product categories (more reliable than revenue for company size). |
| 28 | MATCHED_SHIPMENTS | int | Y | Migration | Count of TOTAL_SHIPMENTS_ALL matched to this row's ORIGIN_COUNTRY (for multi-origin companies). |
| 29 | PARENT_COMPANY | string | Y | Panjiva | Parent company name if subsidiary. NULL if independent. |
| 30 | DUNS | string | Y | Panjiva | Dun & Bradstreet number (B2B credit reference). |
| 31 | TOP_SUPPLIERS | string | Y | Panjiva | JSON array: [{"name": "Supplier A", "shipments": 45}, ...]. Identifies if trade house (many suppliers) vs. single-source. |
| 32 | TOP_PRODUCTS | string | Y | Panjiva | JSON array: [{"hs_code": "6203", "name": "Jackets", "shipments": 23}, ...]. Product mix indicator. |
| 33 | LAST_SHIPMENT_DATE | date | Y | Panjiva | ISO 8601 date of most recent shipment. Recency signal (active company = recent shipment). |
| 34 | ROUTE_DESC | string | Y | Panjiva | Most common route (e.g., "VN→USLAX", "MY→USHOU"). |
| 35 | PANJIVA_URL | string | Y | Panjiva | Link to company's Panjiva profile (for Nelson manual research). |
| 36 | CITY_PANJIVA | string | Y | Panjiva | City of company HQ (from Panjiva; may differ from CITY col if updated). |

---

### Group 4: Decision Maker (v7 NEW, 2 cols)

Contact information from Panjiva Contact Info sheet (shipment-level files). **Read-only.** ~22% email coverage.

| # | Column | Type | Nullable | Source | Description |
|---|--------|------|----------|--------|-------------|
| 37 | PIC_NAME | string | Y | Panjiva Contact Info | Person In Charge name (shipper on customs doc). May be role title if personal name not on form. |
| 38 | PIC_POSITION | string | Y | Panjiva Contact Info | Position / title at company (e.g., "Purchasing Manager", "Imports Coordinator", "Director Ops"). Position classifier used for bounce harvest (LEFT reply replacement extractor). |

---

### Group 5: Multi-Origin Tracking (v7 NEW, 4 cols)

Track companies sourcing from multiple countries. **Computed at migration time.** Read-only.

| # | Column | Type | Nullable | Computed by | Description |
|---|--------|------|----------|-------------|-------------|
| 39 | ORIGIN_COUNTRY | string | Y | v6 original | Primary origin country (VN, MY, TH, CN, KH, BD, IN, PH, ID). Base for ARB routing. |
| 40 | POL_LIST | string | Y | Migration | Comma-separated distinct ports of loading for this CNEE (e.g., "HCM,HPH,PKG,BKK"). Extracted from shipment routes in Panjiva. |
| 41 | ORIGIN_COUNTRIES | string | Y | Migration | Comma-separated unique origin countries detected in shipment routes (e.g., "VN,MY,TH"). Shows if company is multi-origin. |
| 42 | MULTI_ORIGIN | bool | Y | Migration | True if len(ORIGIN_COUNTRIES) > 1, else False. Flag for UI to suggest multi-lane rates. |
| 43 | PRIMARY_POL | string | Y | Migration | Most frequent POL for this company (statistical mode from shipment routes). Use as default if ORIGIN_COUNTRY routing is ambiguous. |

---

### Group 6: Tier Scoring (v7 NEW, 1 col)

Auto-computed prospect ranking. **Read-only.** Recomputed quarterly at migration.

| # | Column | Type | Nullable | Algorithm | Description |
|---|--------|------|----------|-----------|-------------|
| 44 | TIER_AUTO_SCORE | enum | Y | TIER_AUTO_SCORE function | **HOT** = high revenue (>$1M) + frequent shipments (>20/yr) + recent activity (<90d) + not yet sent / low send count. **WARM** = mid revenue ($100K–$1M) or moderate frequency (5–20/yr). **COLD** = low revenue (<$100K) or sparse activity (<5/yr) or high send count already. Used for segmentation in rotation engine (optional: send HOT first in daily plan). |

---

## Lock Rules

### Always Locked (cannot edit via API/UI)

1. EMAIL — primary key, immutable
2. EMAIL_STATUS — system-updated only
3. SEND_COUNT_* — incremented by send events
4. LAST_SENT_* — updated by send events
5. REPLY_STATUS — updated by auto-reply scanner
6. Firmographic cols (25–36) — Panjiva read-only
7. Decision maker cols (37–38) — Panjiva Contact Info read-only
8. Multi-origin cols (40–43) — computed at migration
9. TIER_AUTO_SCORE (44) — computed quarterly

### Conditionally Locked

- **TIER** — Locked if value is "CUSTOMER" or "VIP" (Nelson-assigned priority). Editable if "PROSPECT" (can override to CUSTOMER if Nelson closes deal).

### Editable

- Contact Identity (2–14): FIRST_NAME, LAST_NAME, COMPANY, JOB_TITLE, PHONE, CITY, STATE, COUNTRY, POSTAL_CODE, WEBSITE, LINKEDIN, TIMEZONE, COMMODITY_CATEGORY
- DESTINATION_REGION (15)
- TIER (if currently "PROSPECT")
- Any custom fields added by Nelson

---

## Import/Update Rules

### Never NULL

- EMAIL ← validation: all rows must have valid email address

### Can be NULL

- Most columns (open for future enrichment)
- Firmographic fields (20% of Panjiva records have incomplete data)
- Decision maker fields (22% coverage from Contact Info sheet)

### Special handling

**TIER = CUSTOMER/VIP:** Prevent accidental overwrite via API. Contact Nelson if need to change priority tier.

**MULTI_ORIGIN = true:** Dashboard UI should auto-generate rate quote suggestions for multiple POLs (not just primary).

**POL_LIST empty:** Company has no shipment history in Panjiva. Use ORIGIN_COUNTRY as sole POL.

---

## Data Dictionary Example (5 rows)

### Row: alice@widgetcorp.com (v6 original, enriched v7)

| Column | Value | Notes |
|--------|-------|-------|
| EMAIL | alice@widgetcorp.com | — |
| COMPANY | Widget Corp | — |
| COMMODITY_CATEGORY | FURNITURE | — |
| EMAIL_STATUS | ACTIVE | System-locked |
| SEND_COUNT_EMAIL | 12 | System-locked |
| REVENUE_USD | 4500000 | From Panjiva (enriched v7) |
| TIER_AUTO_SCORE | HOT | revenue > $1M + active shipments |
| ORIGIN_COUNTRY | VN | v6 original |
| POL_LIST | HCM,HPH | Multiple shipment ports detected |
| MULTI_ORIGIN | false | Only Vietnam sourcing |
| TIER | CUSTOMER | Locked (Nelson-assigned) |

### Row: bob@newbuyer.com (v7 new from Contact Info)

| Column | Value | Notes |
|--------|-------|-------|
| EMAIL | bob@newbuyer.com | New in v7 (Panjiva Contact Info sheet) |
| COMPANY | New Buyer Inc | — |
| PIC_NAME | Bob Smith | From Contact Info sheet |
| PIC_POSITION | Purchasing Manager | Position classifier |
| COMMODITY_CATEGORY | CANDLE | Inferred from shipment HS codes |
| EMAIL_STATUS | ACTIVE | Default for new rows |
| SEND_COUNT_EMAIL | 0 | New row (never sent) |
| REVENUE_USD | 850000 | Panjiva estimate |
| TIER_AUTO_SCORE | WARM | mid-revenue + moderate frequency |
| ORIGIN_COUNTRIES | VN,MY | Sources from both countries |
| MULTI_ORIGIN | true | Flag for multi-lane rates |
| POL_LIST | HCM,PKG | Primary POL: HCM (Vietnam) |
| PRIMARY_POL | HCM | Statistical mode from routes |
| TIER | PROSPECT | Editable (not yet customer) |

---

## Schema Evolution (Version History)

| Version | Date | Changes |
|---------|------|---------|
| v7 | 2026-04-23 | Added 21 cols: firmographic (REVENUE_USD, EMPLOYEES, TOP_SUPPLIERS, TOP_PRODUCTS, DUNS, PANJIVA_URL, CITY_PANJIVA, LAST_SHIPMENT_DATE, ROUTE_DESC, MATCHED_SHIPMENTS, PARENT_COMPANY), decision maker (PIC_NAME, PIC_POSITION), multi-origin tracking (POL_LIST, ORIGIN_COUNTRIES, MULTI_ORIGIN, PRIMARY_POL), tier scoring (TIER_AUTO_SCORE). All v6 41 cols preserved 100%. |
| v6 | 2026-04-22 | Split CNEE/SHIPPER, 2-sheet architecture, 41 cols, 22,230 CNEE rows. |
| v5 | 2026-04-01 | Single-sheet legacy (cnee_master_v2_final.xlsx). Fallback only. |

---

## Validation Checklist (Post-Migration)

Before considering v7 migration complete:

- [ ] All 62 columns present in header row
- [ ] EMAIL column has 0 NULL values (all 22,854 rows)
- [ ] SEND_COUNT_EMAIL, LAST_SENT_EMAIL, REPLY_STATUS, EMAIL_STATUS, TIER match v6 for existing rows (5-col LOCK preserved)
- [ ] New rows have EMAIL_STATUS = ACTIVE, SEND_COUNT_EMAIL = 0, TIER = PROSPECT (defaults)
- [ ] REVENUE_USD contains numeric values or blank (no error strings)
- [ ] TIER_AUTO_SCORE contains "HOT", "WARM", "COLD", or blank (no errors)
- [ ] POL_LIST format is comma-separated (e.g., "VN", "VN,MY,TH") or blank
- [ ] MULTI_ORIGIN is boolean (true/false) or blank
- [ ] PANJIVA_URL contains only valid URLs or blank
- [ ] Row count CNEE ≥ 22,800; SHIPPER ≥ 2,300

---

## Related Documentation

- [DATA_FLOW.md — Layer 4 schema](./DATA_FLOW.md#cnee-contact-schema-v7-layer-4-contract-with-layer-5) — v7 contract details
- [PANJIVA_EXPORT_GUIDE.md](./PANJIVA_EXPORT_GUIDE.md) — How to download + export Panjiva files
- [EMAIL_DASHBOARD_V7.md](./EMAIL_DASHBOARD_V7.md) — Master v7 platform overview
- [SYSTEM_STANDARDS.md Section 1](./SYSTEM_STANDARDS.md#section-1--canonical-file-paths) — v7 file paths

---

**Last Updated:** 2026-04-23 by Nelson Huynh  
**Maintainer:** Nelson Huynh  
**Review cadence:** After quarterly Panjiva refresh, or when schema adds new columns
