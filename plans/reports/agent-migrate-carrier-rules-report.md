# Agent MIGRATE-CARRIER-RULES — Report

**Date:** 2026-04-20
**Status:** DONE_WITH_CONCERNS

---

## Sources Merged Per Carrier

| CARRIER | SOC | PUC | COMMODITY | NOTES | WEIGHT | BOOKING |
|---------|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| ONE     | Y   | Y   | Y         | -     | -      | Y       |
| CMA     | Y   | Y   | Y         | Y     | -      | Y       |
| YML     | Y   | Y   | Y         | -     | Y      | Y       |
| HPL     | Y   | Y   | Y         | -     | Y      | Y       |
| ZIM     | -   | -   | Y         | Y     | Y      | Y       |
| MSC     | -   | -   | Y         | Y     | Y      | Y       |
| COSCO   | -   | -   | Y         | Y     | Y      | Y       |
| EMC     | -   | -   | Y         | Y     | -      | Y       |
| WHL     | -   | -   | Y         | -     | -      | Y       |
| MSK     | -   | -   | -         | -     | Y      | Y       |
| EMF     | -   | -   | -         | -     | -      | placeholder |

---

## Files Created / Modified

### New files (Deliverables 1–3)
- `D:/OneDrive/NelsonData/pricing/carrier_rules/_schema.json` — JSON schema for carrier rule files
- `D:/OneDrive/NelsonData/pricing/carrier_rules/_common.json` — universal rules (booking template + SOC routing + commodity universal)
- `D:/OneDrive/NelsonData/pricing/carrier_rules/ONE.json` + group_codes
- `D:/OneDrive/NelsonData/pricing/carrier_rules/ZIM.json` + service_codes Z7S/ZXB/ZEX + OWS tiers
- `D:/OneDrive/NelsonData/pricing/carrier_rules/CMA.json` + PREPAID booking rule
- `D:/OneDrive/NelsonData/pricing/carrier_rules/HPL.json` + SCFI charge mapping incident note
- `D:/OneDrive/NelsonData/pricing/carrier_rules/YML.json` + CA/US weight tables
- `D:/OneDrive/NelsonData/pricing/carrier_rules/MSC.json` + service group ref
- `D:/OneDrive/NelsonData/pricing/carrier_rules/COSCO.json` + US IPI weight tables
- `D:/OneDrive/NelsonData/pricing/carrier_rules/EMC.json` + CMEP/PCTF note rules
- `D:/OneDrive/NelsonData/pricing/carrier_rules/WHL.json`
- `D:/OneDrive/NelsonData/pricing/carrier_rules/MSK.json`
- `D:/OneDrive/NelsonData/pricing/carrier_rules/EMF.json` — placeholder

### New files (Deliverables 4–7)
- `scripts/migrate-carrier-rules.py` — idempotent migration + verification tool
- `Pricing_Engine/carrier_rules/__init__.py` — loader module with cache
- `Pricing_Engine/normalization/text_normalize.py` — standalone normalize_notes + normalize_text_data + helpers
- `tests/test_carrier_rules.py` — 48 unit tests (all pass)

### Modified files (Deliverable 6 — wire into pipelines)
- `scripts/master_loader_v2.py` line 127: `PUC_CARRIERS` now loaded from `get_puc_carriers()`, fallback to hardcoded set
- `Pricing_Engine/scripts/create_master_dashboard.py`: imports text_normalize module, all `normalize_notes()` + `normalize_text_data()` calls dispatch via `_dispatch_*()` wrappers
- `D:/OneDrive/NelsonData/erp/refresh-v14.py`: imports text_normalize module, `normalize_notes` wired after pivot (was missing before)

### Archives
- `D:/OneDrive/NelsonData/pricing/carrier_rules/_archive/20260420_*_pipeline_rules_pipeline_rules.json`
- `D:/OneDrive/NelsonData/pricing/carrier_rules/_archive/20260420_*_booking_rules_booking_rules.json`
- `D:/OneDrive/NelsonData/pricing/carrier_rules/_archive/20260420_*_weight_rules_MSK_MSK.json`

---

## Schema Decisions

1. **`_common.json` is loaded first, carrier file merged on top** — carrier-specific values override common. Booking template (greeting, pol_config, container_display, etc.) lives entirely in `_common.json` — carriers only override `extra_fields` and `carrier_display`.

2. **`puc_handling.strip_from_soc_tof`** is the authoritative flag — `get_puc_carriers()` in the loader derives the set dynamically. `master_loader_v2.py` no longer has a hardcoded set.

3. **Note shortcuts stored as structured objects** (trigger + output) rather than flat strings — this allows future code to re-implement the logic from JSON without regex in Python. The current Python code still uses inline logic (normalization is complex), but the JSON documents the intent.

4. **`_schema.json` uses additionalProperties: true** — allows forward-compatible extension without schema validation failures when adding new sections.

5. **EMF.json is a placeholder** — EMF exists only as a charge code in pipeline_rules.json (EIC/GFS/BAF/FDI), not as an actual carrier in the rate files. Kept per spec.

---

## Edge Cases

| Carrier | Section | Issue | Decision |
|---------|---------|-------|----------|
| ZIM | PUC | Not a SOC carrier — no PUC file | `strip_from_soc_tof: false` |
| HPL | SCFI charge | Inverted mapping vs other carriers | Documented in `charge_mapping_scfi` + `special_notes` incident 2026-04-17 |
| MSK | Weight | Data only in PDF, not extracted | `_note` documents manual extraction needed |
| EMF | All | Not a real carrier in rate files | Placeholder file created |
| ONE | Group codes | Complex priority-based logic | Preserved verbatim in `one_group_codes.rules[]` |
| ZIM | OWS tonnage warn | Dynamic tag appended to output | Documented in JSON, implemented in text_normalize.py |

---

## Before/After Diff Summary

### Architecture change
| Before | After |
|--------|-------|
| 5 scattered sources in 3+ locations | 1 canonical folder per carrier on OneDrive |
| `PUC_CARRIERS = {'CMA','ONE','YML','HPL'}` hardcoded | Loaded dynamically from JSON via `get_puc_carriers()` |
| `normalize_notes()` + `normalize_text_data()` duplicated across 2+ files | Single module `Pricing_Engine/normalization/text_normalize.py` |
| `refresh-v14.py` had no `normalize_notes` call | Wired after pivot, conditionally applied |
| No unit tests for normalization logic | 48 unit tests, all pass |

### Parquet regen (Deliverable 8 — NOT executed)
**Skipped: parquet regen requires Excel rate files to be present and is a destructive write.** Per governance rule: "Backup parquet before regen." This step should be triggered manually by Nelson after verifying Excel files are current. The pipeline is wired — next time `master_loader_v2.py --rebuild` is run, it will use `get_puc_carriers()` from JSON.

**To execute:**
```
# 1. Backup parquet first (manual step)
# 2. python scripts/master_loader_v2.py --rebuild
# 3. python scripts/migrate-carrier-rules.py  (re-verify)
```

---

## Known Concerns

1. **Deliverable 8 not executed** — parquet regen + PUC audit + Pricing Dry Note distinct count verification skipped. Requires live Excel rate files on PC Home and Nelson's explicit approval before destructive write.

2. **`builder.py` in `ERP/carrier_rules/`** — this file generates weight-only JSON to an old path (`ERP/config/carrier_rules/`). It was NOT deleted (per spec: archive only). The weight data from its output was manually merged into the canonical carrier JSON files. Nelson should decide whether to keep `builder.py` or deprecate it.

3. **`normalize_notes` / `normalize_text_data` in `create_master_dashboard.py`** — the original inline function bodies are still present (as fallback). In a future cleanup pass, they can be removed and the dispatch wrappers simplified to direct calls.

4. **refresh-v14.py note normalization is NEW** — before this migration, refresh-v14.py only called `normalize_commodity_display()`. Adding `normalize_notes()` after pivot may change Note values in the ERP Pricing Dry sheet on next refresh. Nelson should verify the output looks correct on first run.

5. **HMM carrier missing** — `builder.py` has HMM weight data but `pipeline_rules.json` has no HMM rules. HMM is not active in current rate files. Not included in carrier_rules/ per spec (spec lists 10 carriers + EMF placeholder).

---

**Status:** DONE_WITH_CONCERNS
**Summary:** 13 carrier JSON files created, loader module + normalize module extracted, 48 tests pass, 3 pipeline files wired. Parquet regen skipped pending Nelson approval.
**Concerns:** Parquet regen not run (destructive). `refresh-v14.py` note normalization is new — verify on first live refresh.
