---
phase: 3
status: pending
priority: HIGH
effort: ~3h
blockedBy: [phase-02]
blocks: [phase-04, phase-05]
---

# Phase 03 — Gateway Routing for Inland POD (RIPI/IPI)

## Context Links
- **Design:** `plans/reports/rate-table-v2-design-20260424.md` §3.D4
- **Plan overview:** [plan.md](plan.md)
- **Predecessor:** [phase-02-top3-carriers.md](phase-02-top3-carriers.md)

## Overview
**Priority:** 🟡 HIGH
**Effort:** ~3h (most complex phase — routing + data availability check)
**Status:** ⏳ Pending (blocked by Phase 2)

Inland POD cần route qua gateway ports (không phải direct). USATL đặc biệt — **RIPI via EC** (Charleston/Norfolk/Savannah) rẻ hơn IPI via WC. USCHI/USDAL/USDEN dùng IPI via LAX/OAK default.

## Key Insights
- **Parquet không có direct rate** cho USATL từ HPH/HCM — phải query rates to CHS/NOR/SAV (EC) hoặc LAX (WC) rồi add inland haul cost
- **RIPI cheaper than IPI** cho ATL do rail distance ngắn hơn từ EC
- **Nelson preference confirmed:** USATL RIPI wins nếu tie (§8 Q5)
- **Carrier preference routing:** Q1 decision — carrier tự chọn gateway nào cheapest, em không hardcode

## Requirements

### Functional
1. `resolve_inland_gateway(pod, carrier)` returns `(gateway_port, routing_label)`
2. USATL: query EC ports (CHS/NOR/SAV) → if available, pick cheapest carrier match → label `"via CHS"` (or NOR/SAV)
3. USATL fallback: if no EC rate → IPI via LAX, label `"via LAX (IPI)"`
4. USCHI/USDAL/USDEN: direct LAX gateway, no label (IPI is expected default)
5. Integrate vào `_query_best_rates` — inland POD calls gateway resolver trước khi query parquet

### Non-functional
- Query count: +1 subquery per inland POD (4 extra queries per email = acceptable)
- Cache resolution result per session (same CNEE won't re-resolve)
- Fallback safe: if gateway resolution fails → skip POD (per Q3 decision)

## Architecture

```python
# auto_rate_builder.py additions

INLAND_GATEWAY_CONFIG = {
    "USATL": {
        "primary": {"type": "RIPI", "ports": ["USCHS", "USNOR", "USSAV"]},
        "fallback": {"type": "IPI", "ports": ["USLAX"]},
    },
    "USCHI": {"primary": {"type": "IPI", "ports": ["USLAX", "USOAK"]}, "fallback": None},
    "USDAL": {"primary": {"type": "IPI", "ports": ["USLAX", "USOAK"]}, "fallback": None},
    "USDEN": {"primary": {"type": "IPI", "ports": ["USLAX", "USOAK"]}, "fallback": None},
}


def resolve_inland_gateway(pol: str, pod: str, carrier: str) -> dict | None:
    """
    For inland POD, find the cheapest gateway port for given carrier.

    Returns:
        {"gateway_port": "USCHS", "routing_label": "via CHS", "rate_type": "RIPI",
         "amount_20gp": X, "amount_40hq": Y, "exp": "2026-05-03"}
        OR None if no rate available (skip POD per Q3 decision)
    """
    config = INLAND_GATEWAY_CONFIG.get(pod)
    if not config:
        return None  # POD không phải inland — shouldn't reach here

    # Try primary gateway type (RIPI for ATL, IPI for others)
    for port in config["primary"]["ports"]:
        rate = _query_carrier_rate(pol=pol, pod=port, carrier=carrier)
        if rate is not None:
            label = f"via {port[2:]}" if config["primary"]["type"] == "RIPI" else ""
            return {
                "gateway_port": port,
                "routing_label": label,
                "rate_type": config["primary"]["type"],
                **rate,
            }

    # Fallback (only USATL has this)
    if config["fallback"]:
        for port in config["fallback"]["ports"]:
            rate = _query_carrier_rate(pol=pol, pod=port, carrier=carrier)
            if rate is not None:
                return {
                    "gateway_port": port,
                    "routing_label": f"via {port[2:]} (IPI)",
                    "rate_type": "IPI",
                    **rate,
                }

    return None  # No rate found → skip POD
```

## Related Code Files

### Modify
- `email_engine/core/auto_rate_builder.py` — add `resolve_inland_gateway()` + `INLAND_GATEWAY_CONFIG` + `_query_carrier_rate()` helper
- `email_engine/core/auto_rate_builder.py:_query_best_rates()` — detect inland POD, dispatch to gateway resolver

### Read for context
- Parquet schema — verify CHS/NOR/SAV data availability
- Existing inland logic (if any) in `rule_engine.py` or `builder.py`

## Implementation Steps

1. **Data availability check (CRITICAL FIRST):**
   ```bash
   python -c "
   import duckdb, sys
   sys.path.insert(0, r'D:\NELSON\2. Areas\Engine_test')
   from shared.paths import PARQUET_FILE
   con = duckdb.connect(':memory:')
   df = con.execute(f\"\"\"
     SELECT POL, POD, Carrier, COUNT(*) as n
     FROM read_parquet('{PARQUET_FILE}')
     WHERE POL IN ('HPH','HCM') AND POD IN ('USCHS','USNOR','USSAV','USLAX','USOAK')
       AND Carrier IN ('HPL','CMA','ONE','YML','ZIM')
       AND CAST(Exp AS DATE) >= CURRENT_DATE
     GROUP BY POL, POD, Carrier ORDER BY n DESC
   \"\"\").df()
   print(df)
   "
   ```
   - If USCHS/USNOR/USSAV data sparse → **BLOCK** and report to Nelson
2. **Write unit tests:**
   ```python
   def test_resolve_atl_ripi_via_chs(): ...
   def test_resolve_atl_fallback_to_ipi(): ...
   def test_resolve_chi_ipi_default(): ...
   def test_resolve_no_rate_returns_none(): ...
   ```
3. **Implement** `INLAND_GATEWAY_CONFIG` constant
4. **Implement** `_query_carrier_rate()` helper — single (pol, pod, carrier) lookup
5. **Implement** `resolve_inland_gateway()` per spec
6. **Integrate** into `_query_best_rates`:
   ```python
   if pod in INLAND_GATEWAY_CONFIG:
       # Gateway resolution path
       gateway_rate = resolve_inland_gateway(pol, pod, carrier)
       if gateway_rate:
           results.append(gateway_rate)
       # else: skip POD silently (Q3)
   else:
       # Main port direct query (existing path)
       ...
   ```
7. **Test** `HPH→USATL` — verify HPL routes via CHS/NOR/SAV (not LAX)
8. **Test** `HPH→USCHI` — verify routes via LAX
9. **Test** `HPH→USATL` with missing EC data (simulate) — verify fallback IPI

## Todo List
- [ ] Run data availability check trên parquet (EC ports data)
- [ ] If data sparse → BLOCK, report Nelson (Option A: backfill; Option B: temporary all-IPI)
- [ ] Write 4 unit tests
- [ ] Define `INLAND_GATEWAY_CONFIG`
- [ ] Implement `_query_carrier_rate()`
- [ ] Implement `resolve_inland_gateway()`
- [ ] Integrate dispatch logic in `_query_best_rates`
- [ ] Test USATL (RIPI primary path)
- [ ] Test USATL fallback (no EC data scenario)
- [ ] Test USCHI/USDAL/USDEN (IPI default)
- [ ] Run full pytest — no regression
- [ ] Commit: `feat(rate-builder): gateway routing for inland POD (RIPI/IPI)`

## Success Criteria
1. ✅ `HPH→USATL` HPL → returns row with `gateway_port=USCHS/USNOR/USSAV`, label=`"via CHS"` (or NOR/SAV)
2. ✅ `HPH→USCHI` HPL → returns row with `gateway_port=USLAX`, label=`""` (no suffix)
3. ✅ USATL tie-break: if RIPI and IPI same price → RIPI wins (sort order)
4. ✅ Missing EC data → USATL falls back IPI cleanly
5. ✅ USATL no data at all → skipped silently, email renders 9 POD (not 10)

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| EC ports data sparse in parquet | **Data check Step 1 is BLOCKER** — verify BEFORE implementation |
| Gateway resolution adds 10+ queries per email | Cache per-(POL, carrier, POD) in session-level dict |
| Carrier doesn't ship to EC → wrong fallback | Validate data presence per carrier before dispatch |
| `via CHS` label mis-rendering in email | Label inline in rate-meta text (already tested in preview) |
| Data inconsistency: same rate but different gateway | Cheapest wins — log warning, keep cheapest |

## Security Considerations
None — read-only parquet queries.

## Next Phase
→ Phase 4: Update email HTML template renderer để apply side-by-side layout + HPH/HCM color theme + inland POD styling.
