# Phase 02 — Two-Tier Detection Engine

**Priority:** P0 (core logic)
**Status:** DONE (2026-04-15)
**Depends on:** Phase 01 baseline
**Est. tokens:** ~12k

## Overview

Rewrite `compute_alerts()` trong `price_watch.py` để hỗ trợ 2 tier detection độc lập:

- **Tier 1 — ROUTINE (POL-POD match, any carrier):** alert khi carrier bất kỳ có buy < quoted buy. Priority P1 (cần re-quote ngay)
- **Tier 2 — LINE (POL-POD + same carrier):** alert khi chính carrier đó hạ giá. Priority P2 (nice to know, không cần đổi carrier)

Mỗi quote có thể fire cả 2 tier nếu cả routine + line đều có drop — lúc đó Tier 1 win (carrier alternative rẻ hơn).

## Key Insights

1. **Routine match nên strict hơn carrier match** — để tránh noise:
   - Cùng POL, cùng POD, cùng Cont type
   - Transit time region cùng nhóm (WC/EC/Gulf) — dùng bảng region từ `transit_time.py`
   - Place match fuzzy (Place = POD, hoặc Place = "" hoặc Place chứa POD)
2. **Alias map cho carrier** — hardcode 10 carrier top + substring fallback:
   ```python
   CARRIER_ALIAS = {
       "ONE": {"ONE", "OCEAN NETWORK EXPRESS"},
       "YML": {"YML", "YANG MING"},
       "WHL": {"WHL", "WAN HAI"},
       "CMA": {"CMA", "CMA-CGM", "CMA CGM"},
       "MSC": {"MSC"},
       "MAERSK": {"MAERSK", "MSK"},
       "HAPAG": {"HAPAG", "HAPAG-LLOYD", "HLC"},
       "COSCO": {"COSCO"},
       "EVERGREEN": {"EVERGREEN", "EMC", "EGL"},
       "ZIM": {"ZIM"},
   }
   ```
3. **Threshold per tier** — Tier 1 routine threshold cao hơn (vd $100) vì alternative carrier có cost khác, Tier 2 line thấp hơn (vd $50).
4. **Best candidate per tier** — với Tier 1, nếu có 5 carrier rẻ hơn, pick cheapest một (không list hết).

## Requirements

### Functional

1. **Normalize carrier string:**
   ```python
   def normalize_carrier(raw: str) -> str:
       raw = raw.upper().strip()
       for canonical, aliases in CARRIER_ALIAS.items():
           if any(a in raw for a in aliases):
               return canonical
       return raw  # fallback untouched
   ```

2. **Build 2 indices:**
   ```python
   pricing_by_routine: dict[(POL, POD, Cont), list[PricingRow]]   # Tier 1
   pricing_by_line:    dict[(POL, POD, Carrier, Cont), PricingRow]  # Tier 2
   ```

3. **compute_alerts_v2(quotes, pricing_by_routine, pricing_by_line, cfg):**
   - For each pending quote + each cont with buy rate:
     - Tier 2 (LINE): lookup `(POL, POD, Carrier, Cont)` → best (lowest) buy
       - if `buy < quoted - cfg.threshold_line` → emit P2 alert kind=LINE
     - Tier 1 (ROUTINE): lookup `(POL, POD, Cont)` → list all carriers sorted ASC by buy
       - best = cheapest carrier (skip same carrier as quote, đó là Tier 2)
       - if `best.buy < quoted - cfg.threshold_routine` → emit P1 alert kind=ROUTINE
   - De-dupe: nếu 1 quote có cả Tier 1 + Tier 2, emit cả 2 nhưng Tier 1 sort up top

4. **Status mapping:**
   - PENDING quote + DROP → P1 (action: "Re-quote ngay")
   - WIN quote + DROP → P2 (action: "Note for next round")
   - Any quote + RISE → P3 (information only)

### Non-Functional

- Performance: <3s cho 3500 Pricing rows + 500 Quote rows
- Memory: <200MB
- All dict key strings uppercase + stripped (canonical)

## Architecture

```
price_watch.py (v2 — rewrite compute_alerts)
  │
  ├─ @dataclass PricingRow(pol, pod, place, carrier_raw, carrier_norm, eff, source, buy_by_cont: dict)
  ├─ @dataclass Alert(quote_id, row, customer, route, tier, carrier_old, carrier_new, cont, quoted, current, delta, priority, action)
  │
  ├─ CARRIER_ALIAS: dict[str, set[str]]  (10 top + fallback substring)
  ├─ normalize_carrier(raw: str) -> str
  │
  ├─ load_pricing_v2(wb) -> (pricing_by_routine, pricing_by_line)
  │    scans Pricing Dry + Reefer, builds both indices in 1 pass
  │
  ├─ compute_alerts_v2(quotes, idx_routine, idx_line, cfg) -> list[Alert]
  │    Tier 2 first (simpler), then Tier 1 (exclude same carrier)
  │
  └─ PW_Config: dict — read from `PW_Config` sheet (fallback hardcoded defaults)
       threshold_routine = 100 USD
       threshold_line    = 50 USD
       enabled_tier_1    = True
       enabled_tier_2    = True
       ignore_expired    = True (skip quote với Exp < today)
```

## Related Code Files

**Modify:**
- `ERP/intelligence/price_watch.py` — rewrite `compute_alerts` + add 2-tier indices + alias map
- `ERP/core/active_jobs_cols.py` — NO CHANGE (col 39/40 đã đúng)

**Create:**
- `ERP/intelligence/carrier_alias.py` (30 lines — alias map + normalize function, reusable ngoài price_watch)

**Delete:**
- (none — rewrite in place)

## Implementation Steps

1. Create `ERP/intelligence/carrier_alias.py`:
   ```python
   CARRIER_ALIAS: dict[str, set[str]] = { ... }
   def normalize_carrier(raw: str) -> str: ...
   ```
2. Edit `price_watch.py`:
   - Replace `CONT_TO_PRICE_COL` with cleaner `CONT_TYPES = ["20GP", "40GP", "40HC", "45HC", "40NOR", "20RF", "40RF"]`
   - New `load_pricing_v2(wb)` returns tuple of 2 dicts (1 pass both sheets)
   - New `compute_alerts_v2(...)` — Tier 2 loop + Tier 1 loop (Tier 1 skip same carrier)
   - Fix Active Jobs col index: `AJ_COL["PRICE_WATCH_STATUS"]` = 39, not 35
3. Add `PW_Config` sheet auto-create nếu chưa có:
   ```
   A1=Key        B1=Value
   A2=threshold_routine  B2=100
   A3=threshold_line     B3=50
   A4=enabled_tier_1     B4=TRUE
   A5=enabled_tier_2     B5=TRUE
   A6=ignore_expired     B6=TRUE
   A7=autorun_on_refresh B7=TRUE
   ```
4. CLI: `--threshold-routine 100 --threshold-line 50 --tier all|routine|line`
5. `python -m py_compile ERP/intelligence/price_watch.py` → no syntax error
6. `python ERP/intelligence/price_watch.py --threshold-routine 100 --threshold-line 50` → inspect output

## Todo List

- [x] Create `ERP/intelligence/carrier_alias.py`
- [x] Rewrite `load_pricing_v2` (dual index)
- [x] Rewrite `compute_alerts_v2` (Tier 2 then Tier 1)
- [x] Add `load_pw_config(wb)` reading `PW_Config` sheet
- [x] Fix AJ_COL index bug (35→39, 36→40) — confirmed AJ_COL uses key lookup, col 39/40 correct
- [x] Add `--threshold-routine`, `--threshold-line`, `--tier` CLI flags
- [x] py_compile green on both files
- [ ] Unit test: normalize_carrier("Yang Ming") == "YML"  (manual logic verified, needs pytest)
- [ ] Smoke test: run on real ERP file

## Success Criteria

- Test quote MSC HPH-USLGB buy 2800 vs pricing CMA HPH-USLGB buy 2500 → emits 1 P1 Tier 1 ROUTINE alert
- Test quote MSC HPH-USLGB buy 2800 vs pricing MSC HPH-USLGB buy 2600 → emits 1 P2 Tier 2 LINE alert
- Test quote YML HPH-USLGB buy 2800 vs pricing "YANG MING" HPH-USLGB buy 2600 → alias matches, emits alert
- Run on real ERP: output lines contain "Tier1 ROUTINE" and "Tier2 LINE" labels, delta values match manual calculation
- `py_compile` green, `ruff check` green on modified files

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Tier 1 ra quá nhiều noise (10+ carriers cheaper) | Chỉ emit alert với best candidate per quote+cont, ignore phần còn lại |
| Alias map miss một carrier | Fallback substring match (k[3] in carrier or carrier in k[3]) |
| Quote Buy rate column empty (schema mismatch) | Guard `isinstance(quoted, (int, float))` + log warning |
| Performance chậm vì dict rebuild | Build index 1 lần outside loop; scan Pricing 1 pass |

## Security Considerations

- None (local file only, no network, no auth)

## Next Steps

→ Phase 03: visualize alerts lên Price_Watch sheet + inline highlight Quotes/Active Jobs
