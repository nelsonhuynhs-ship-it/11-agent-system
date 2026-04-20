---
date: 2026-04-20
agent: P2
task: Build CRM sheet from customer_rules.json + Shipments.xlsx
---

# Agent P2 — CRM Build Report

## Sources & Stats

| Source | Path | Count |
|--------|------|-------|
| customer_rules.json | `D:/OneDrive/NelsonData/email/customer_rules.json` | 59 customers |
| Shipments.xlsx | `C:/Users/Nelson/OneDrive/Desktop/Shipments.xlsx` | 26 unique customers across 12 monthly sheets (NONE row filtered) |
| **Merged total** | — | **72 unique** (after union + NAFOODS skip) |

Shipments.xlsx sheets used: May 2025 → Apr 2026 (12 sheets). Skipped: Sheet1, Sheet2, Sheet3.

## Merge Algorithm

1. **Normalize key**: `UPPERCASE → strip punctuation → collapse whitespace`
   - Used as dedup key for both sources and for existing CRM rows
2. **Union keys**: `all_keys = set(rules) | set(shipments)`
3. **Per key merge priority**:
   - `Customer_Type` → prefer `customer_rules.json` (`DIRECT`→BCO, `FWD`→FORWARDER, `CNEE`→CONSIGNEE)
   - `Preferred_Carriers` → rules list first, then append top shipment carriers if not already listed
   - `POL_Options` / `POD_Options` → union of both sources, sorted
   - `Container_Types` → shipments only (rules don't carry this field)
   - `Is_Reefer` → auto-set "Yes" if any container type contains "RF" (40RF/20RF)
   - `Status` → "Active" if shipment_count > 0 OR last_etd within 6 months; else "Prospect"
   - `Contact1_Email` → `seen_senders[0]` from rules if available
4. **Sort**: by `shipment_count DESC` then `display_name ASC` — most active customers first
5. **NAFOODS skip**: normalized variants `NAFOODS GROUP`, `NAFOODS`, `NAFOOD GROUP` all skipped → row 2 preserved as-is
6. **Idempotency**: on re-run, `read_existing_crm()` builds `dict[norm_key → row_number]`; existing rows are UPDATEd (not duplicated), new rows APPENDed

## Dry-Run Row Count

```
[DRY-RUN] Summary: +70 new / 0 updated / 2 skipped (NAFOODS)
```

CRM_IDs assigned: CS001290 → CS001359 (70 new rows, starting after NAFOODS CS001289)

Active customers (have shipments): 22
Prospect customers (rules-only, no shipments yet): 48

## Edge Cases

| Case | How Handled |
|------|-------------|
| `NAFOODS GROUP` (row 2) + `NAFOODS` + `NAFOOD GROUP` in sources | All 3 variants normalized and skipped — 2 skipped total (rules has NAFOOD, shipments has NAFOOD GROUP) |
| `WEST FOOD` (Shipments) vs `WESTFOOD` (rules) | Two separate normalized keys: `WEST FOOD` ≠ `WESTFOOD` → 2 separate rows (CS001301 West Food, CS001356 Westfood). Nelson should manually merge if same entity. |
| `SIRI` vs `SIRI LOG` | Both in Shipments as distinct customers, SIRI LOG also in rules → 2 separate rows. SIRI is BCO (no rules entry), SIRI LOG is FORWARDER from rules. |
| `CREATIVE` vs `CREATIVE LIGHT` | Different customers — separate rows CS001303 and CS001304. Correct. |
| `D&K` in Shipments | Punctuation stripped → normalized key `D K`. Display name = "D K". No rules entry. |
| `PANDA HN`, `PANDA HCM`, `PANDA BN`, `PANDA HAI PHONG` | 4 separate Shipments entries with distinct routes — kept separate rows CS001292/294/308/309. Nelson should consolidate if same PANDA GROUP forwarder. `PANDA GROUP` from rules also a separate row (Prospect, no shipments). |
| `MEKONG SEA` vs `MEKONG SEAFOOD` | Both in Shipments + rules → 2 separate rows. May be same entity (HCM vs HPH origin). |
| `ACT LOG` (Shipments) vs `ACT` (rules) | Different normalized keys → 2 rows: `ACT LOG` (Active, shipments) and `ACT` (Prospect, rules-only). |
| `NAFOOD` in Shipments has Rotterdam POD | Included in POD_Options. Non-US port is valid data. |
| Customers with all-empty fields (BERNHARDT, LULULEMON, etc.) | Still included as CONSIGNEE Prospect — they exist in rules from email folder discovery |
| `gmail.com` as email_domain | PT FOOD, HER HUI WOOD, MEKONG SEA, PULLION LLC have gmail senders. Contact1_Email populated from seen_senders. |
| Carrier cleanup | `carrier_affinity` values like `"ONE SOC"` → first word only = `"ONE"`. `"HPL SCFI"` → `"HPL"`. |
| `LCB` in ACT LOG POL | ACT LOG has `LCB` as POL from Shipments routing. Unusual but kept as-is. |

## File Created

- `scripts/erp-build-crm.py` — 290 lines, fully idempotent, dry-run safe

## Usage

```bash
# Preview (safe, no file write):
python scripts/erp-build-crm.py --dry-run

# Apply to live xlsm (requires Excel closed):
python scripts/erp-build-crm.py
```

## Safety Checklist

- [x] `save_preserving_ribbon` used — gotcha #6 respected
- [x] Backup created before any write (`ERP_Master_v14.backup_YYYYMMDD_HHMMSS.xlsm`)
- [x] File-lock check (`~$ERP_Master_v14.xlsm`)
- [x] `keep_vba=True` on workbook open
- [x] Row 2 (NAFOODS GROUP) preserved — NAFOODS variants explicitly skipped
- [x] Idempotent — UPDATE existing, APPEND new
- [x] DO NOT TOUCH: Active Jobs / Archive / VBA / .bas (not in scope)

**Status:** DONE
**Summary:** Script `scripts/erp-build-crm.py` created. Dry-run validates 70 new CRM rows (CS001290–CS001359) from 59 customer_rules + 26 Shipments customers, 2 NAFOODS skipped, NAFOODS row 2 preserved. Edge cases documented above — Nelson should review WEST FOOD/WESTFOOD and PANDA variants for potential manual dedup.
**Concerns:** None blocking. WEST FOOD vs WESTFOOD and PANDA variants may need manual consolidation post-import.
