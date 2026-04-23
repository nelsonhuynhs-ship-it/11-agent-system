# Panjiva Export Guide — Contact Import Strategy

**Last updated:** 2026-04-23  
**Purpose:** Step-by-step guide for exporting Panjiva buyer + shipment data, preparing for v7 contact migration  
**Frequency:** Quarterly (recommend: every 90 days)  
**Owner:** Nelson Huynh

---

## Overview

Panjiva provides 2 export types that work together:

| Type | Best for | Email coverage | Key data |
|------|----------|---|---|
| **Buyer-level exports** | Company firmographic, supplier networks | 1–2% | Revenue, employees, parent company, top suppliers |
| **Shipment-level exports** | Decision makers, route patterns, activity | 22% | Contact Info sheet with shipper name + PIC email + position |

**Strategy:** Download BOTH types per commodity × country combination, then merge via `migrate-to-unified-v7.py`.

---

## Export Type 1: Buyer-Level Files

**Use:** Firmographic enrichment (revenue, employees, HQ info)

### How to Export

1. **Log in:** panjiva.com → click "Import Data" → Select "Buyer-Level" report
2. **Filter by commodity + country:**
   - Commodity: FLOORING, FURNITURE, CANDLE, etc.
   - Import country: VN, MY, TH, CN, KH, etc.
   - Time range: Last 12 months (default)
   - Min shipments: 2 (filters noise)
   - Size: > $50K (optional, catch midsize companies)
3. **Select fields:** Ensure these columns are checked:
   - Company name, Address, City, State, Postal Code, Country
   - Phone, Website, Email (if available)
   - Revenue (USD), Employees
   - DUNS number
   - Top suppliers (partner list)
   - Top HS codes / commodities shipped
   - Panjiva company URL
   - Last shipment date
4. **Export format:** ✅ **Excel (.xlsx)** recommended (CSV lacks cell formatting)
5. **Save to:** `D:/OneDrive/NelsonData/email/panjiva/Panjiva-FLOORING-VN-buyer-202604.xlsx`

**Naming convention:** `Panjiva-{COMMODITY}-{COUNTRY}-buyer-{YYYYMM}.xlsx`

### Data quality notes

- **Email coverage:** 1–2% (most buyer-level exports have missing email; contact Info sheet is better)
- **Company name variation:** May not match exact v6 names (Panjiva may have alternate legal names)
- **Revenue range:** Often blank or estimated (use as HOT/WARM/COLD signal, not absolute truth)
- **Typical size:** 1000–5000 rows per commodity × country

---

## Export Type 2: Shipment-Level Files

**Use:** Decision maker discovery (PIC name + position) + route/activity patterns

### How to Export

1. **Log in:** panjiva.com → "Import Data" → Select "Shipment-Level" report
2. **Filter by commodity + country:**
   - Commodity: same as buyer-level (FLOORING, FURNITURE, etc.)
   - Export country: same (VN, MY, TH, CN, KH, etc.)
   - Time range: Last 12 months
3. **This export has 3 sheets automatically:**
   - **Info** — Summary of unique buyers in this dataset
   - **US Imports Shipments** — Line-by-line shipment data (large)
   - **Contact Info** ← **THIS IS THE GOLD** (22% email, decision makers with position)
4. **Select fields on Contact Info sheet:**
   - Buyer company name, Buyer contact (shipper)
   - Contact position / title
   - Contact email ← **Primary source for new CNEE**
   - Supplier company name
   - Product category, HS code
5. **Export format:** ✅ **Excel (.xlsx)**
6. **Save to:** `D:/OneDrive/NelsonData/email/panjiva/Panjiva-FLOORING-VN-shipment-202604.xlsx`

**Naming convention:** `Panjiva-{COMMODITY}-{COUNTRY}-shipment-{YYYYMM}.xlsx`

### Contact Info sheet (decision makers)

**Columns of interest:**

| Column | Notes |
|--------|-------|
| Buyer Company Name | Importer name |
| Buyer Contact (Shipper name) | Person who signed customs docs |
| Contact Position / Title | "Purchasing Manager", "Imports Coordinator", "Director", etc. |
| Contact Email | Email address of shipper/PIC ← **primary key for new CNEE** |
| Supplier Company | Exporter name |
| HS Code | Product classification |
| Shipment Date | When goods shipped (recency signal) |

**Email coverage here:** ~22% (much better than buyer-level 1–2%)

**Quality check:** Position field usually has real job titles (not blank like buyer-level). Use to differentiate new prospects (decision makers) vs. old buyerless rows.

---

## Pre-Migration Checklist

Before running `migrate-to-unified-v7.py`:

- [ ] Downloaded buyer-level files for ALL active commodities (FLOORING, FURNITURE, CANDLE, etc.)
- [ ] Downloaded shipment-level files (same commodities) — minimum 1 per quarter
- [ ] Saved files to `D:/OneDrive/NelsonData/email/panjiva/`
- [ ] Verified file naming matches pattern: `Panjiva-{COMMODITY}-{COUNTRY}-{TYPE}-{YYYYMM}.xlsx`
- [ ] Checked Contact Info sheet in shipment files has ≥100 rows with email (else skip that file)
- [ ] Copied old v6 master to backup (migration script auto-backups, but manual backup is safer)
- [ ] Cleared any legacy CSVs or old .xlsx versions from panjiva/ folder

---

## Running the Migration

### Command

```bash
python scripts/migrate-to-unified-v7.py \
  --panjiva-dir "D:/OneDrive/NelsonData/email/panjiva/" \
  --output "D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx"
```

### Dry-run (test first)

```bash
python scripts/migrate-to-unified-v7.py \
  --panjiva-dir "D:/OneDrive/NelsonData/email/panjiva/" \
  --dry-run
```

Outputs audit report WITHOUT modifying any files.

### Expect:

1. **Backup rotation:** `contact_unified_v6.xlsx` → `contact_unified_v6_backup_20260423_1200.xlsx` (14 old backups kept)
2. **Audit log:** `backups/migration_v7_audit_20260423_1200.csv` (rows processed, matched, new inserts)
3. **Output:** `contact_unified_v7.xlsx` (2-sheet: CNEE + SHIPPER)
4. **Validation:** Script checks:
   - 0 NULL EMAIL rows (all email addresses present)
   - 5-col LOCK preserved (EMAIL_STATUS, SEND_COUNT_EMAIL, etc. match v6)
   - 62 columns present (v6 41 + v7 21 new)

---

## Post-Migration Validation

After running migration:

1. **Open v7 file:** `contact_unified_v7.xlsx`
2. **Check CNEE sheet:**
   - Column count = 62 ✓
   - Row count ≥ 22,800 (should be 22,854+) ✓
   - New columns visible: `REVENUE_USD`, `PIC_NAME`, `PIC_POSITION`, `POL_LIST`, `TIER_AUTO_SCORE` ✓
3. **Spot-check 10 rows:**
   - EMAIL column: all populated ✓
   - REVENUE_USD: contains numbers or blank (not errors) ✓
   - TIER_AUTO_SCORE: HOT / WARM / COLD values ✓
   - POL_LIST: shows "VN" or "VN,MY" or blank (no errors) ✓
4. **Check SHIPPER sheet:**
   - Row count ≥ 2,300 ✓
   - Same 62-col schema as CNEE ✓
5. **Verify v6 locked columns:**
   - SEND_COUNT_EMAIL, LAST_SENT_EMAIL, REPLY_STATUS unchanged from v6 ✓

---

## Quarterly Refresh Schedule

| Quarter | Commodity focus | Expected size | Notes |
|---------|---|---|---|
| Q1 (Jan–Mar) | FLOORING, FURNITURE | ~20K new rows total | Post-Chinese New Year surge |
| Q2 (Apr–Jun) | CANDLE, RUBBER, PLASTIC | ~18K new | Summer inventory build |
| Q3 (Jul–Sep) | FURNITURE_OUTDOOR, GARMENT | ~15K new | Back-to-school / holiday prep |
| Q4 (Oct–Dec) | All commodities | ~25K new | Holiday buying peak |

**Schedule:** Run migration 1st week of next quarter (April 1, July 1, Oct 1, Jan 1).

---

## Troubleshooting

### No Contact Info sheet found

**Symptom:** Migration log shows "No Contact Info sheet in Panjiva-CANDLE-MY-shipment.xlsx"

**Cause:** File is buyer-level, not shipment-level. Shipment-level files have exactly 3 sheets.

**Fix:** Delete buyer-level file, download shipment-level again.

---

### Email coverage < 20% warning

**Symptom:** Migration script warns "Contact Info sheet only 50 rows (4% coverage)"

**Cause:** Small HS code or low-activity supplier combination.

**Action:** OK to skip. Script auto-skips low-coverage files.

---

### REVENUE_USD all NULL

**Symptom:** New rows have empty REVENUE_USD column.

**Cause:** Buyer-level file didn't include revenue field, OR buyer has no revenue data in Panjiva.

**Fix:** Panjiva limitation. Use TOTAL_SHIPMENTS_ALL as proxy for company size (more reliable).

---

### Duplicate emails in new CNEE

**Symptom:** Web dashboard shows "alice@company.com" with SEND_COUNT_EMAIL = 0 (new row) AND = 5 (v6 row).

**Cause:** Migration didn't catch exact duplicate (name variation, role change).

**Fix:** Manual dedup in v7 file. Delete duplicate, keep v6 row (preserves send history). Commit to git: `git add contact_unified_v7.xlsx && git commit -m "manual-dedup: alice@company.com role change"`

---

## Firmographic Data Quality Notes

### Revenue

- **Source:** Panjiva estimate from customs data (product value + shipment frequency)
- **Accuracy:** ±30% typical
- **Use:** HOT (>$1M revenue) vs WARM ($100K–$1M) vs COLD (<$100K) segmentation
- **Caution:** Blanks are common; don't assume NULL = small company

### Employees

- **Source:** Business database aggregation (varies by country)
- **Accuracy:** Supplier-reported or estimated
- **Use:** B2B segmentation (large orgs = slow decision cycle; small = fast)
- **Note:** VN companies often have inflated employee counts (registration artifacts)

### Top Suppliers

- **Source:** Customs records (aggregate shipment counts)
- **Accuracy:** 100% (based on real shipments)
- **Use:** Identify if company is trade house (many suppliers) vs single-source importer
- **Format:** JSON array of (Company name, shipment count) tuples

### Decision Maker (PIC)

- **Source:** Contact Info sheet (customs shipment doc signer or point of contact)
- **Accuracy:** 98% (actual names from government records)
- **Reliability:** High (not self-reported, extraction from official docs)
- **Caution:** Name may be generic role ("Imports Manager") not individual person

---

## Reference

- **Master file:** `D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx`
- **Migration script:** `scripts/migrate-to-unified-v7.py`
- **Panjiva parser:** `scripts/panjiva_clean_v3.py`
- **Schema reference:** `docs/MASTER_V7_SCHEMA.md`
- **Panjiva account:** panjiva.com (Nelson's subscription)

---

**Last Updated:** 2026-04-23 by Nelson Huynh  
**Next Quarterly Refresh:** ~2026-07-01 (Q3)
