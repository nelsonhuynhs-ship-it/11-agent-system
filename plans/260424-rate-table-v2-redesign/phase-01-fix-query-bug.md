---
phase: 1
status: pending
priority: CRITICAL
effort: ~2h
blocks: [phase-02, phase-03, phase-04, phase-05]
---

# Phase 01 — Fix `_query_best_rates` Groupby Bug

## Context Links
- **Design:** `plans/reports/rate-table-v2-design-20260424.md` §1 (Problem) + §3.D2
- **Evidence:** `plans/reports/hotfix-send-a-debug-20260424.md`
- **Plan overview:** [plan.md](plan.md)

## Overview
**Priority:** 🔴 CRITICAL — blocker cho tất cả downstream phases
**Effort:** ~2h (30m read + 30m fix + 60m verify)
**Status:** ⏳ Pending

Single-function fix trong `_query_best_rates`. Change groupby key để SCFI và FAK compete độc lập thay vì gom chung bị loại.

## Key Insights
- **Current bug:** `groupby("Carrier")` + filter `Exp >= max_exp - 1 day` → HPL FAK (Exp May 14) kill HPL SCFI (Exp May 3)
- **Fix:** `groupby(["Carrier", "Rate_Type"])` — SCFI/FAK/Special trở thành 3 candidates độc lập, mỗi cái giữ row rẻ nhất
- **DuckDB verify:** HCM→USSAV hiện parquet có HPL SCFI $2,988 < HPL FAK $3,559 → chênh $571/cont

## Requirements

### Functional
- After fix: `_query_best_rates("HCM", "USSAV")` trả về ≥2 rows cho HPL (1 SCFI + 1 FAK)
- Other carriers (CMA/ONE/YML/ZIM) giữ nguyên behavior — 1 row (cheapest variant)
- Phase 2 sẽ handle dedupe per carrier — phase này CHỈ mở rộng output

### Non-functional
- DuckDB query count không đổi (same SQL)
- No schema change
- Memory footprint +20% acceptable (more rows returned)

## Architecture

**Before:**
```python
# auto_rate_builder.py:243-253
for carrier, grp in results_40.groupby("Carrier"):
    grp["_exp_ts"] = pd.to_datetime(grp["Exp"], errors="coerce")
    max_exp = grp["_exp_ts"].max()
    latest = grp[grp["_exp_ts"] >= max_exp - pd.Timedelta(days=1)]
    best_row = latest.loc[latest["Amount"].idxmin()]
```

**After:**
```python
# Groupby (Carrier, Rate_Type) — each combo keeps cheapest
for (carrier, rate_type), grp in results_40.groupby(["Carrier", "Rate_Type"]):
    # Filter valid Exp only (not expired)
    valid = grp[pd.to_datetime(grp["Exp"]) >= TODAY]
    if valid.empty:
        continue
    best_row = valid.loc[valid["Amount"].idxmin()]
    # emit: 1 row per (carrier, rate_type) combination
```

## Related Code Files

### Modify
- `email_engine/core/auto_rate_builder.py` — function `_query_best_rates()` lines ~188-280

### Read for context
- `email_engine/core/auto_rate_builder.py` entire file
- `email_engine/tests/test_auto_rate_builder.py` — existing test coverage
- `shared/paths.py` — verify parquet path resolution

### Do NOT touch
- Parquet schema / data
- Other functions trong `auto_rate_builder.py`
- Template rendering (Phase 4)

## Implementation Steps

1. **Read** full `_query_best_rates` function (lines 188-280)
2. **Read** existing unit tests để hiểu expected output shape
3. **Snapshot** current behavior:
   ```bash
   python -c "from email_engine.core.auto_rate_builder import _query_best_rates; \
     import pandas as pd; \
     r = _query_best_rates(pol='HCM', pod='USSAV'); \
     print(r[r['Carrier']=='HPL'])"
   ```
   → Expect 1 row (HPL FAK) before fix
4. **Apply fix:**
   - Change line ~243 groupby key: `"Carrier"` → `["Carrier", "Rate_Type"]`
   - Remove "latest Exp first" filter (lines ~246-247)
   - Keep "cheapest Amount" selection
   - Update unpacking: `for (carrier, rate_type), grp in ...`
5. **Re-run snapshot** — expect ≥2 rows (HPL SCFI + HPL FAK)
6. **Run existing tests:** `pytest email_engine/tests/test_auto_rate_builder.py -v`
7. **Document** change trong docstring

## Todo List
- [ ] Read `auto_rate_builder.py` lines 188-280
- [ ] Read test file
- [ ] Run baseline snapshot (HCM→USSAV HPL rows)
- [ ] Apply groupby key change
- [ ] Remove stale Exp filter
- [ ] Update tuple unpacking
- [ ] Run snapshot again — verify ≥2 HPL rows
- [ ] Run pytest — all pass
- [ ] Update docstring
- [ ] Manual test HCM→USLAX (regression — ONE still wins)
- [ ] Commit: `fix(rate-builder): groupby by (Carrier, Rate_Type) to surface SCFI`

## Success Criteria
1. ✅ `HCM→USSAV` query returns ≥2 rows for HPL (one SCFI Amount=$2,988, one FAK Amount~$3,559)
2. ✅ `HCM→USLAX` query still returns ONE as cheapest (no regression)
3. ✅ `pytest email_engine/tests/` fully passes
4. ✅ No new warnings in logs

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Rate_Type có typo variants ("SCFI" vs "scfi") | Normalize `.str.upper().str.strip()` trước groupby |
| Existing tests assume 1 row/carrier | Tests sẽ fail → update assertion để accept multi-row per carrier |
| Phase 2 chưa dedupe → email hiện 2 HPL rows | Document: Phase 2 sẽ handle, Phase 1 output intentionally larger |
| Performance: +20% rows returned | Acceptable — Phase 2 sẽ filter về top 3 distinct |

## Security Considerations
None — query logic only, không expose new data paths, không user input.

## Next Phase
→ Phase 2: Implement `select_top3_distinct_carriers()` để filter output từ Phase 1 về TOP 3 distinct carriers với SCFI-anchored tie-break.
