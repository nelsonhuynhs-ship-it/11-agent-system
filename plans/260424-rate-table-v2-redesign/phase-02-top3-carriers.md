---
phase: 2
status: pending
priority: HIGH
effort: ~2h
blockedBy: [phase-01]
blocks: [phase-03, phase-04, phase-05]
---

# Phase 02 — TOP 3 Distinct Carriers Selection

## Context Links
- **Design:** `plans/reports/rate-table-v2-design-20260424.md` §3.D2 + §3.D3
- **Plan overview:** [plan.md](plan.md)
- **Predecessor:** [phase-01-fix-query-bug.md](phase-01-fix-query-bug.md) — output DataFrame có multi-row per carrier

## Overview
**Priority:** 🟡 HIGH
**Effort:** ~2h
**Status:** ⏳ Pending (blocked by Phase 1)

Implement selection algo filter output từ Phase 1 về **tối đa 3 distinct carriers** per POD, với SCFI-anchored tie-break rule.

## Key Insights
- Phase 1 output = DataFrame nhiều rows per carrier (SCFI + FAK + Special = 3 rows cho HPL)
- Phase 2 = dedupe per carrier, keep cheapest variant, SCFI ưu tiên nếu cùng giá
- Output: exactly 3 rows (hoặc ít hơn nếu < 3 distinct carriers available)

## Requirements

### Functional
1. Input: DataFrame từ Phase 1 với columns `[Carrier, Rate_Type, Amount, Exp, POD, POL, Container_Type]`
2. Output: DataFrame với ≤3 rows, mỗi row 1 carrier distinct
3. Rate type → carrier matrix validation (reject SCFI nếu Carrier ≠ HPL)
4. Expand YAML config `fast_bulk_default` từ 3 → 10 POD

### Non-functional
- O(n log n) — acceptable cho n ~50 rows/query
- No external calls
- Pure function (testable)

## Architecture

```python
def select_top3_distinct_carriers(rates: pd.DataFrame) -> pd.DataFrame:
    """
    Select top 3 distinct carriers by 40HQ price.
    Tie-break: SCFI wins over Special rate at same price (anchor pricing).

    Args:
        rates: DataFrame with ≥1 row per (Carrier, Rate_Type)

    Returns:
        DataFrame with ≤3 rows, 1 per carrier, cheapest variant.
    """
    # Step 1: Validate rate_type × carrier matrix
    valid = _validate_rate_type_matrix(rates)

    # Step 2: Per (Carrier, Rate_Type) → keep cheapest (should already be from Phase 1)
    per_combo = valid.loc[
        valid.groupby(["Carrier", "Rate_Type"])["Amount_40HQ"].idxmin()
    ]

    # Step 3: Per Carrier → keep cheapest, SCFI-preferred tie-break
    per_combo["_scfi_priority"] = (per_combo["Rate_Type"] == "SCFI").astype(int)
    per_combo = per_combo.sort_values(
        ["Carrier", "Amount_40HQ", "_scfi_priority"],
        ascending=[True, True, False]  # SCFI first at tie
    )
    per_carrier = per_combo.groupby("Carrier").head(1).drop(columns="_scfi_priority")

    # Step 4: Sort carriers by price, take top 3
    top3 = per_carrier.sort_values("Amount_40HQ").head(3)

    return top3


RATE_TYPE_CARRIER_MATRIX = {
    "SCFI": {"HPL"},
    "Special": {"CMA", "ONE", "HMM", "YML", "ZIM", "HPL"},
    "Special SOC": {"HPL", "YML"},
    "FAK COC": {"CMA", "ONE", "HMM", "YML", "ZIM", "HPL", "WHL"},
    "FAK SOC": {"HPL", "YML"},
}
```

## Related Code Files

### Modify
- `email_engine/core/auto_rate_builder.py` — add `select_top3_distinct_carriers()` + `_validate_rate_type_matrix()`
- `email_engine/config/default_routes.yaml` — expand POD list (3→10) với gateway metadata
- `email_engine/intelligence/builder.py` — load YAML as SOT (already has pattern), enforce `max_destinations_per_email: 10`

### Read for context
- Phase 1 modified `_query_best_rates` output shape
- Existing YAML structure

## Implementation Steps

1. **Write unit tests first (TDD):**
   ```python
   def test_top3_distinct_carriers_basic():
       # 5 carriers → return 3 cheapest
   def test_scfi_tiebreak_wins():
       # HPL SCFI $2988 vs HPL Special $2988 → SCFI wins
   def test_fewer_than_3_carriers():
       # 2 distinct carriers → return 2 rows (no padding)
   def test_invalid_rate_type_rejected():
       # SCFI with Carrier=ONE → logged warning, row excluded
   ```
2. **Implement** `select_top3_distinct_carriers()` per algo spec
3. **Implement** `_validate_rate_type_matrix()` helper
4. **Integrate** into `_query_best_rates` pipeline (wrap output)
5. **Update YAML** `default_routes.yaml`:
   ```yaml
   fast_bulk_default:
     pod_list:
       - {code: USLAX, city: "Los Angeles", type: main}
       - {code: USSAV, city: "Savannah",    type: main}
       - {code: USNYC, city: "New York",    type: main}
       - {code: USHOU, city: "Houston",     type: main}
       - {code: USMIA, city: "Miami",       type: main}
       - {code: USTIW, city: "Tacoma",      type: main}
       - {code: USATL, city: "Atlanta",     type: inland, gateway: RIPI, via: [CHS, NOR, SAV]}
       - {code: USCHI, city: "Chicago",     type: inland, gateway: IPI, via: [LAX, OAK]}
       - {code: USDAL, city: "Dallas",      type: inland, gateway: IPI, via: [LAX, OAK]}
       - {code: USDEN, city: "Denver",      type: inland, gateway: IPI, via: [LAX, OAK]}
     pol_list: [HPH, HCM]
     max_destinations_per_email: 10
   ```
6. **Update builder** to parse new YAML shape (backward-compat fallback)
7. **Run tests** — all pass
8. **Smoke test** `HCM→USSAV` returns 3 distinct carriers [HPL SCFI, ONE Special, CMA Special]

## Todo List
- [ ] Write 4 unit tests (TDD)
- [ ] Implement `select_top3_distinct_carriers()`
- [ ] Implement `_validate_rate_type_matrix()` with 5-type mapping
- [ ] Integrate into `_query_best_rates` pipeline
- [ ] Update `default_routes.yaml` with 10 POD + metadata
- [ ] Update `builder.py` to parse new YAML (with fallback)
- [ ] Update `web_server.py:DEFAULT_DESTINATIONS` to load from YAML (10 items)
- [ ] Run `pytest` — all pass
- [ ] Smoke test HCM→USSAV
- [ ] Smoke test HPH→USATL (will be filtered further in Phase 3)
- [ ] Commit: `feat(rate-builder): top 3 distinct carriers + 10 POD default`

## Success Criteria
1. ✅ Unit tests 4/4 pass
2. ✅ `HCM→USSAV` → 3 rows: HPL/ONE/CMA (HPL SCFI wins BEST)
3. ✅ `HPH→USMIA` → 3 rows với HPL SCFI BEST
4. ✅ `DEFAULT_DESTINATIONS` python var = 10 POD
5. ✅ YAML `max_destinations_per_email` enforced (>10 → truncate with log)
6. ✅ No regression: `HCM→USLAX` → ONE BEST unchanged

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| YAML schema change breaks existing consumers | Add fallback: old-format `pod_list: [USLAX, ...]` still loadable |
| SCFI tie-break logic edge case (3 rates all SCFI) | Impossible per matrix (SCFI=HPL only), but add assertion |
| CAVAN-style POD no longer in list | Nelson đã confirm 10 POD hết (không còn CAVAN) — non-issue |
| Tests flaky do parquet data shift | Mock DataFrame fixtures, không touch real parquet |

## Security Considerations
- YAML load phải dùng `yaml.safe_load()` (already current pattern)
- No user-controlled paths

## Next Phase
→ Phase 3: Implement gateway routing cho USATL (RIPI via CHS/NOR/SAV) + USCHI/USDAL/USDEN (IPI default WC).
