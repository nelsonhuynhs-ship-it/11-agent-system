---
phase: 1
title: "Commodity Groups YAML + normalize_commodity()"
status: pending
priority: P1
effort: "2h"
dependencies: []
---

# Phase 1: Commodity Groups YAML + normalize_commodity()

## Overview

Tạo `commodity_groups.yaml` — editable config định nghĩa 8 canonical commodity groups. Viết `normalize_commodity()` function đọc YAML, fuzzy-match raw commodity string → canonical group name.

## Requirements

- Functional: 46 COMMODITY_CATEGORY values → 8 canonical groups
- Non-functional: YAML editable by Nelson without code change

## Architecture

```
COMMODITY_CATEGORY raw values (46)
    │
    ▼
rule_engine.normalize_commodity(raw: str) → str (canonical group)
    │
    ├── Read commodity_groups.yaml
    ├── For each group: check if any pattern matches raw string
    ├── Return first match (priority order)
    └── Fallback: "OTHERS"
```

**YAML structure (`email_engine/config/commodity_groups.yaml`):**
```yaml
# Priority order matters — checked top to bottom
commodity_groups:
  - name: FLOORING
    patterns: [FLOORING, "FLOORING,WOOD", "FLOORING,PLASTIC", "FLOORING,FURNITURE_INDOOR"]
    arb_origin: null
    pod_default: [USLAX, USLGB]
  - name: FURNITURE
    patterns: [FURNITURE_INDOOR, FURNITURE_OUTDOOR]
    arb_origin: null
    pod_default: [USLAX, USLGB]
  - name: PLASTIC
    patterns: [PLASTIC, "PLASTIC,WOOD"]
    arb_origin: null
    pod_default: [USLAX, USHOU]
  - name: RUBBER
    patterns: [RUBBER, "RUBBER,WOOD"]
    arb_origin: null
    pod_default: [USLAX, USNYC]
  - name: PLYWOOD
    patterns: [PLYWOOD, "PLYWOOD,WOOD"]
    arb_origin: null
    pod_default: [USNYC, USSAV]
  - name: FOOD
    patterns: [FOOD, FOOD_AMBIENT, FOOD_FROZEN, FOOD_FRUIT, SEAFOOD]
    arb_origin: null
    pod_default: [USLAX, USMIA]
  - name: GARMENT
    patterns: [GARMENT, APPAREL, TOY, STEEL, LED_LIGHT]
    arb_origin: null
    pod_default: [USLAX, USNYC]
  - name: OTHERS
    patterns: [".*"]
    arb_origin: null
    pod_default: [USLAX, USLGB]
```

## Related Code Files

- Create: `email_engine/config/commodity_groups.yaml`
- Modify: `email_engine/core/rule_engine.py` (add `normalize_commodity()`, `load_commodity_groups()`)

## Implementation Steps

1. Tạo `email_engine/config/commodity_groups.yaml` với 8 groups và patterns
2. Viết `load_commodity_groups()` — đọc YAML, cache với `@lru_cache`
3. Viết `normalize_commodity(raw: str) -> str` — fuzzy match, priority order, fallback OTHERS
4. Viết `get_pod_default(commodity: str) -> list[str]` — đọc pod_default từ YAML
5. Verify: chạy test trên 46 raw values → phải map đúng vào 8 groups
6. Update `resolve_config()` để dùng `normalize_commodity()` thay vì raw `COMMODITY_CATEGORY`

## Success Criteria

- [ ] `normalize_commodity("FLOORING,WOOD")` → `"FLOORING"`
- [ ] `normalize_commodity("FURNITURE_INDOOR,WOOD")` → `"FURNITURE"`
- [ ] `normalize_commodity("TANJUNG PELEPAS LOC")` → `"OTHERS"` (không match commodity pattern)
- [ ] `normalize_commodity("CANDLE")` → `"CANDLE"` — CANDLE không trong groups → fallback OTHERS
- [ ] YAML load cached, không đọc file mỗi lần gọi
- [ ] `resolve_config()` dùng normalized commodity cho `commodity` key

## Risk Assessment

- **Risk:** `normalize_commodity()` breaking existing campaign filtering in dashboard
  - **Mitigation:** `resolve_config()` vẫn giữ `commodity` key trả về normalized group, `CAMPAIGN_ID` giữ nguyên để filter cũ vẫn work
- **Risk:** Fuzzy match conflicts (VD: `FLOORING,FURNITURE_INDOOR` match cả FLOORING và FURNITURE)
  - **Mitigation:** YAML order = priority order — FLOORING defined before FURNITURE → match FLOORING first
