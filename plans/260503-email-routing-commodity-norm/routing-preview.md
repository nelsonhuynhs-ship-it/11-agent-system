---
phase: 4
title: "Frontend Routing Preview Card"
status: pending
priority: P2
effort: "2h"
dependencies: [1, 2, 3]
---

# Phase 4: Frontend Routing Preview Card

## Overview

Thêm routing preview card vào Send preview panel trong dashboard. Hiển thị: POL đang applied, ARB origin, POD (10 lanes), country. Cho Nelson thấy routing decision trước khi send.

## Requirements

- Functional: Send preview → routing card hiển thị POL/ARB/POD/country
- Non-functional: Không thay đổi existing send flow

## Architecture

```
GET /api/routing/preview?email=cnee@email.com&markup=20
    │
    ├── Load CNEE row from cnee_master
    ├── resolve_config(row) → {pol, arb_origin, arb_label, country, destination}
    ├── get_arb_surcharge(arb_origin) → {arb_20, arb_40}
    └── Return {pol, arb_origin, arb_label, country, pod_list, arb_surcharge_40hq}

Frontend: Send preview → fetch /api/routing/preview → render card
```

**API Response shape:**
```json
{
  "email": "cnee@email.com",
  "pol": "TPNG",
  "pol_label": "Tanjung Pelepas, Malaysia",
  "country": "MY",
  "arb_origin": "port_klang",
  "arb_label": "Port Klang, Malaysia",
  "arb_surcharge_40hq": 130,
  "pod_list": ["USLAX", "USLGB", "USNYC", "USSAV", "USHOU", "USMIA", "USTIW", "USATL", "USCHI", "USDAL"],
  "commodity_group": "OTHERS",
  "markup": 20
}
```

**HTML routing card (thêm vào Send preview section):**
```html
<div class="routing-card" id="routingCard" style="display:none">
  <div class="routing-header">📦 Routing Applied</div>
  <div class="routing-row">
    <span class="routing-label">POL</span>
    <span class="routing-value" id="rcPol">—</span>
  </div>
  <div class="routing-row">
    <span class="routing-label">Country</span>
    <span class="routing-value" id="rcCountry">—</span>
  </div>
  <div class="routing-row" id="rcArbRow">
    <span class="routing-label">ARB Surcharge</span>
    <span class="routing-value" id="rcArb">— (+$X/40HQ)</span>
  </div>
  <div class="routing-row">
    <span class="routing-label">POD Lanes</span>
    <span class="routing-value" id="rcPod">—</span>
  </div>
</div>
```

**CSS (thêm vào email-dashboard.html style section):**
```css
.routing-card{margin:12px 0;padding:12px 16px;background:#f0f9ff;
  border:1px solid #0ea5e9;border-radius:8px;font-size:13px}
.routing-header{font-weight:600;color:#0369a1;margin-bottom:8px}
.routing-row{display:flex;justify-content:space-between;padding:3px 0}
.routing-label{color:#64748b}
.routing-value{font-weight:500;color:#0f172a}
```

## Related Code Files

- Modify: `email_engine/web_server.py` (add `GET /api/routing/preview` endpoint)
- Modify: `plans/visuals/email-dashboard.html` (add routing card HTML + CSS + JS)

## Implementation Steps

1. Thêm `GET /api/routing/preview` endpoint vào `web_server.py`
   - Query params: `email`, `markup` (optional)
   - Load CNEE row → `resolve_config()` → `get_arb_surcharge()`
   - Return JSON với routing details
2. Thêm routing card HTML vào Send preview section trong `email-dashboard.html`
3. Thêm CSS cho `.routing-card` và `.routing-row`
4. Thêm JS: khi user chọn contact để preview → gọi `/api/routing/preview` → populate card
5. Thêm `loadRoutingPreview(email)` function với error handling
6. ARB surcharge hiển thị badge màu vàng khi có ARB, ẩn row khi không có ARB

## Success Criteria

- [ ] `/api/routing/preview?email=cnee@email.com` → valid JSON response
- [ ] Routing card hiển thị trong Send preview panel
- [ ] ARB row ẩn khi `arb_origin` là `null`
- [ ] ARB row hiển thị surcharge amount khi có ARB (VD: `+$130/40HQ`)
- [ ] POD lanes hiển thị comma-separated list (10 lanes)
- [ ] Error: email not found → card ẩn, no crash

## Risk Assessment

- **Risk:** `/api/routing/preview` thêm latency vào send preview
  - **Mitigation:** Cache resolve_config result trong 60s, chỉ gọi khi user mở preview
- **Risk:** Routing card làm clutter dashboard UI
  - **Mitigation:** Card nhỏ gọn ( collapsible), mặc định collapsed
