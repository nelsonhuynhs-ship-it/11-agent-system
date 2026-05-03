---
phase: 2
title: "POL Extraction from CAMPAIGN_ID + MY Routing Fix"
status: pending
priority: P1
effort: "2h"
dependencies: [1]
---

# Phase 2: POL Extraction from CAMPAIGN_ID + MY Routing Fix

## Overview

Parse POL + country + ARB key trực tiếp từ `CAMPAIGN_ID` field. `TANJUNG PELEPAS LOC` → POL=TPNG, country=MY, arb_key=port_klang. Fix MY routing đang sai (hiện tại MY → HCM base thay vì PKG/TPNG base).

## Requirements

- Functional: CAMPAIGN_ID chứa LOC/TANJUNG/PORT KLANG → extract POL + set country=MY + arb_key
- Non-functional: Không break existing VN/CN/TH routing

## Architecture

```
CNEE row.CAMPAIGN_ID
    │
    ▼
pol_from_campaign(campaign_id: str) → dict {pol, country, arb_key} | None
    │
    ├── Check CAMPAIGN_ID against pol_patterns in commodity_groups.yaml
    ├── Match: return {pol, country, arb_key}
    └── No match: return None → caller falls back to ORIGIN_COUNTRY logic
```

**YAML extension (`email_engine/config/commodity_groups.yaml`):**
```yaml
pol_patterns:
  # Malaysia — POL = Port Klang / Tanjung Pelepas
  - patterns: ["TANJUNG PELEPAS", "TANJUNG PELEPAS LOC", "LOC PLASTIC", "LOC", "TANJUNG"]
    pol: TPNG
    country: MY
    arb_key: port_klang
  - patterns: ["PORT KLANG", "PORT KLANG LOC", "MALAYSIA"]
    pol: PKG
    country: MY
    arb_key: port_klang
  - patterns: ["PENANG", "PNG"]
    pol: PNG
    country: MY
    arb_key: port_klang
```

**Updated resolve_config() flow:**
```python
country = _normalize_country(g("ORIGIN_COUNTRY"))

# 1. Try POL from CAMPAIGN_ID (Malaysia LOC patterns)
pol_config = pol_from_campaign(g("CAMPAIGN_ID"))
if pol_config:
    pol = pol_config["pol"]
    arb_origin = pol_config["arb_key"]
    country = pol_config["country"]  # override
else:
    # 2. Fallback: POL from row (existing)
    pol = _resolve_pol(g("POL"), country)
    # 3. ARB from POL+country
    arb_origin = _resolve_arb_key(pol, country)
```

## Related Code Files

- Modify: `email_engine/core/rule_engine.py` (add `pol_from_campaign()`, update `resolve_config()`)
- Modify: `email_engine/config/commodity_groups.yaml` (add `pol_patterns` section)

## Implementation Steps

1. Thêm `pol_patterns` section vào `commodity_groups.yaml`
2. Viết `load_pol_patterns()` — đọc YAML section, cache
3. Viết `pol_from_campaign(campaign_id: str) -> dict | None` — regex/pattern match trên CAMPAIGN_ID
4. Cập nhật `resolve_config()` — gọi `pol_from_campaign()` trước `_resolve_pol()`
5. Verify: MY rows (VN→MY confusion) phải resolve đúng POL và ARB
6. Regression test: VN/CN/TH routing không bị ảnh hưởng

## Success Criteria

- [ ] `pol_from_campaign("TANJUNG PELEPAS LOC")` → `{pol: TPNG, country: MY, arb_key: port_klang}`
- [ ] `pol_from_campaign("RUBBER LOC")` → `{pol: TPNG, country: MY, arb_key: port_klang}`
- [ ] `pol_from_campaign("FLOORING")` → `None` (không match)
- [ ] `resolve_config({'ORIGIN_COUNTRY': 'MY', 'CAMPAIGN_ID': 'TANJUNG PELEPAS LOC'})['arb_origin']` → `port_klang`
- [ ] `resolve_config({'ORIGIN_COUNTRY': 'VN', 'CAMPAIGN_ID': 'FLOORING'})['arb_origin']` → `None` (VN domestic)

## Risk Assessment

- **Risk:** MY CAMPAIGN_ID (VD: `RUBBER LOC`) bị override country từ `ORIGIN_COUNTRY=MY` → correct nhưng cần verify
  - **Mitigation:** `pol_from_campaign` chỉ triggered khi CAMPAIGN_ID match pol_patterns, không phải lúc nào cũng override
- **Risk:** LOC pattern quá broad (VD: `PLASTIC CANADA LOC` match LOC → sai)
  - **Mitigation:** Pattern order: specific first (`TANJUNG PELEPAS`) → generic (`LOC`). Stop at first match.
