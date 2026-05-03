---
title: "Email Routing + Commodity Normalization"
description: "YAML-driven commodity grouping + POL extraction from CAMPAIGN_ID + ARB wiring + frontend routing preview"
status: completed
priority: P1
branch: "main"
tags: []
blockedBy: []
blocks: []
created: "2026-05-03T03:00:00.000Z"
createdBy: "ck:plan"
source: skill
---

# Email Routing + Commodity Normalization

## Overview

 Chuẩn hóa 4 vấn đề routing/commodity trong email pipeline:
 1. Commodity grouping (46 values → 8 canonical groups)
 2. POL extraction từ CAMPAIGN_ID (fix Malaysia routing)
 3. ARB origins wiring (config-driven thay vì hardcode)
 4. Frontend routing preview card (visibility)

**Root cause:** `CAMPAIGN_ID` chứa POL indicator (VD: `TANJUNG PELEPAS LOC`) nhưng bị dùng như commodity. `normalize_commodity()` không tồn tại. `builder.build_email()` hardcode `_VN_POLS`.

**Scope:**
- Frontend: `plans/visuals/email-dashboard.html`
- Backend: `email_engine/core/rule_engine.py`, `email_engine/intelligence/builder.py`
- Config: `email_engine/config/commodity_groups.yaml` (new)

**Current score: 6.5/10** — routing logic tồn tại nhưng phân tán, commodity mess, frontend không thấy routing decision.

## Phases

| Phase | Name | Priority | Effort | Description |
|-------|------|----------|--------|-------------|
| 1 | [commodity-groups.md](./commodity-groups.md) | P1 | 2h | `commodity_groups.yaml` + `normalize_commodity()` |
| 2 | [pol-extraction.md](./pol-extraction.md) | P1 | 2h | Parse POL từ CAMPAIGN_ID + fix MY routing |
| 3 | [arb-wiring.md](./arb-wiring.md) | P1 | 2h | Wire `arb_origins` config vào `builder.build_email()` |
| 4 | [routing-preview.md](./routing-preview.md) | P2 | 2h | Frontend routing card trong Send preview |

**Total estimated: ~8h**

## Dependencies

<!-- None — plan is self-contained, no cross-plan dependencies -->

## Cross-Reference

- `plans/260503-email-dashboard-hardening/` — frontend hardening plan (Phase 4 touches same `email-dashboard.html` file but different sections)

## Verification

1. `python -c "from email_engine.core.rule_engine import normalize_commodity; print(normalize_commodity('FLOORING,WOOD'))"` — expect `FLOORING`
2. `python -c "from email_engine.core.rule_engine import resolve_config; r=resolve_config({'ORIGIN_COUNTRY':'MY','CAMPAIGN_ID':'TANJUNG PELEPAS LOC'}); print(r['pol'], r['arb_origin'])"` — expect `TPNG port_klang`
3. Open dashboard → Send preview → verify routing card shows POL/ARB/POD
4. Run `grep -c "normalize_commodity\|pol_from_campaign\|arb_origins" email_engine/core/rule_engine.py` — expect >0
