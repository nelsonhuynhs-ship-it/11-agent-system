---
phase: 3
title: "Wire arb_origins Config into builder.build_email()"
status: pending
priority: P1
effort: "2h"
dependencies: [1, 2]
---

# Phase 3: Wire arb_origins Config into builder.build_email()

## Overview

Thay hardcoded `_VN_POLS` frozenset bằng `arb_origins` YAML config. `builder.build_email()` phải truyền `arb_origin` vào `build_rate_table_for_customer()` để ARB surcharge được add vào rate table.

## Requirements

- Functional: Non-VN POLs (PKG/TPNG/BKK/SHA/NGB) → query HCM base + ARB surcharge
- Non-functional: Config-driven — thêm ARB origin mới chỉ cần edit YAML

## Architecture

```
builder.build_email(arb_origin: str | None)
    │
    ├── lookup_pol = arb_origins[arb_origin].pol if arb_origin else pol
    │               (Nếu arb_origin specified → dùng HCM làm base)
    │
    └── build_rate_table_for_customer(
            pol=lookup_pol,
            destinations=destinations,
            markup=markup,
            arb_origin=arb_origin  ← pass through
        )
```

**YAML extension (`email_engine/config/commodity_groups.yaml`):**
```yaml
arb_origins:
  shanghai:
    base_pol: SHA
    label: "Shanghai, China"
    flag: CN
  ningbo:
    base_pol: NGB
    label: "Ningbo, China"
    flag: CN
  lat_krabang:
    base_pol: BKK
    label: "Lat Krabang, Thailand"
    flag: TH
  port_klang:
    base_pol: PKG
    label: "Port Klang, Malaysia"
    flag: MY
  phnom_penh:
    base_pol: PNOM
    label: "Phnom Penh, Cambodia"
    flag: KH
  da_nang:
    base_pol: VNDAD
    label: "Da Nang, Vietnam"
    flag: VN
  qui_nhon:
    base_pol: VNUIH
    label: "Qui Nhon, Vietnam"
    flag: VN
```

**Changes to `builder.build_email()`:**
```python
def build_email(..., arb_origin: str | None = None):
    # Thay hardcode:
    #   lookup_pol = pol if pol in _VN_POLS else "HCM"
    # Bằng config-driven:
    if arb_origin:
        arb_cfg = get_arb_origin_config(arb_origin)  # đọc YAML
        lookup_pol = arb_cfg.base_pol if arb_cfg else pol
    else:
        lookup_pol = pol

    arb_result = build_rate_table_for_customer(
        pol=lookup_pol,
        destinations=",".join(destinations),
        markup=float(markup or 0),
        top_per_route=3,
        arb_origin=arb_origin,  # pass through để ARB surcharge được add
    )
```

**Changes to `auto_rate_builder.build_rate_table_for_customer()`:**
```python
def build_rate_table_for_customer(..., arb_origin: str = None):
    # Hiện tại: arb_origin chỉ dùng để add surcharge vào rate rows
    # Cần: verify arb_origin hợp lệ (có trong arb_rates.yaml) trước khi dùng
    if arb_origin:
        arb_rates = load_arb_rates()
        if arb_origin not in arb_rates:
            log.warning(f"[ARB] unknown arb_origin '{arb_origin}' — skipping surcharge")
            arb_origin = None  # skip ARB nếu không có trong rates
```

## Related Code Files

- Modify: `email_engine/config/commodity_groups.yaml` (add `arb_origins` section)
- Modify: `email_engine/intelligence/builder.py` (update `build_email()` logic)
- Modify: `email_engine/core/auto_rate_builder.py` (verify arb_origin, skip if not in rates)

## Implementation Steps

1. Thêm `arb_origins` section vào `commodity_groups.yaml`
2. Viết `load_arb_origins()` và `get_arb_origin_config(arb_key)` trong `builder.py`
3. Cập nhật `builder.build_email()` — thay `_VN_POLS` hardcode bằng config lookup
4. Cập nhật `auto_rate_builder.build_rate_table_for_customer()` — verify arb_origin trước khi dùng
5. Regression: VN rows (VN country, HCM/HPH POL) → không ARB surcharge, đúng base rate
6. Regression: MY rows (TANJUNG PELEPAS LOC) → ARB surcharge từ `port_klang` key
7. Regression: TH rows (Lat Krabang) → ARB surcharge từ `lat_krabang` key

## Success Criteria

- [ ] `build_email(... arb_origin="port_klang")` → rate table với ARB surcharge added
- [ ] VN domestic (HPH/HCM) → không có ARB surcharge badge
- [ ] MY (TANJUNG PELEPAS) → `port_klang` ARB surcharge hiển thị trong rate table
- [ ] Unknown arb_origin → log warning, skip ARB (không crash)
- [ ] Config thay đổi → không cần restart server (cache cleared on reload)

## Risk Assessment

- **Risk:** `_VN_POLS` hardcode còn được dùng ở nơi khác (ngoài `builder.build_email()`)
  - **Mitigation:** Grep toàn bộ codebase trước khi remove, verify không còn reference
- **Risk:** ARB surcharge applied nhưng `arb_rates.yaml` không có rate cho carrier đó
  - **Mitigation:** `build_cross_origin_rates()` skip rows nếu không tìm thấy ARB rate → carrier vẫn hiển thị với base rate
