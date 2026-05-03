# Schema Audit Report — SHARED_SCHEMA Planning

**Date:** 2026-05-03
**Plan:** `260503-shared-schema`
**Status:** Phase 1 complete

---

## Category A — Docs Schema Definitions

### `MASTER_V7_SCHEMA.md` — 62 CNEE columns (44 extracted by pattern)
| Column Group | Count | Key Columns |
|---|---|---|
| Contact Identity | 15 | EMAIL, COMPANY, PIC, PHONE, CITY, STATE, COUNTRY |
| System Lock | 9 | EMAIL_STATUS, SEND_COUNT_EMAIL, LAST_SENT_EMAIL, REPLY_STATUS, TIER |
| Firmographic (v7 NEW) | 12 | COMMODITY_CATEGORY, ORIGIN_COUNTRY, DESTINATION_REGION |
| Other | ~26 | LINKEDIN, TIMEZONE, HS_CODE, etc. |

### `ARB_ORIGIN_MAPPING.md` — Country → POL + ARB rules (16 occurrences)
| Country | POL Default | ARB Key | Rate Type |
|---------|-------------|---------|-----------|
| VN | HCM / HPH | None | Direct |
| MY | PKG | `port_klang` | Surcharge on HCM base |
| TH | BKK / LCB | `lat_krabang` | Surcharge on HCM base |
| CN | SHA / NGB | `shanghai` / `ningbo` | FULL independent |
| KH | HCM | `phnom_penh` | Surcharge on HCM base |

### `CHARGE_NAME_SOURCE_OF_TRUTH.md` — Rate charge names
- Total Ocean Freight (all-in) → maps to all-in rate
- BAF, CAF, PSS, etc. → documented

### `rate-pipeline-contract.md` — Parquet rate schema
- Weekly aggregation of Cleaned_Master_History.parquet
- 18 key corridors tracked

---

## Category B — Code Schema References

### `email_engine/core/rule_engine.py` — ARB_MAPPING dict
```python
ARB_MAPPING = {
    "VN": {"pol_default": "HCM", "arb_key": None},
    "MY": {"pol_default": "PKG", "arb_key": "port_klang"},
    "TH": {"pol_default": "BKK", "arb_key": "lat_krabang"},
    "CN": {"pol_default": "SHA", "arb_key": "shanghai"},
    "KH": {"pol_default": "HCM", "arb_key": "phnom_penh"},
    "BD": {"pol_default": "CGP", "arb_key": None},
    "IN": {"pol_default": "NSA", "arb_key": None},
    "PH": {"pol_default": "MNL", "arb_key": None},
    "ID": {"pol_default": "JKT", "arb_key": None},
}
```

### `email_engine/config/commodity_groups.yaml` — ALL config in one file
```yaml
commodity_groups:    # 8 canonical groups + 1 OTHERS fallback
pol_patterns:        # MY/TH/CN/KH/SG POL patterns extracted from CAMPAIGN_ID
arb_origins:        # shanghai/ningbo/lat_krabang/port_klang/phnom_penh/da_nang/qui_nhon
vn_domestic_ports:  # 13 ports — no ARB surcharge applied
```

### `email_engine/core/arb_pricing.py` — ARB surcharge loading
- `load_arb_rates()` → reads `arb_rates.yaml`
- `get_arb_surcharge(arb_origin)` → returns `{40hq: X, 40gp: Y, 20gp: Z}`

---

## Duplicate Findings

| Rule | Location A | Location B | Resolution |
|------|-----------|-----------|-----------|
| Country → POL | `rule_engine.py:ARB_MAPPING` | `ARB_ORIGIN_MAPPING.md` | SHARED_SCHEMA.md links both |
| VN ports | `rule_engine.py:VN_PORTS` | `commodity_groups.yaml:vn_domestic_ports` | YAML is authoritative → link |
| ARB origins | `arb_pricing.py` | `ARB_ORIGIN_MAPPING.md` | Link to ARB_ORIGIN_MAPPING.md |

---

## What's NOT Documented Yet

1. **Parquet column baseline** — only referenced, full column list not in any doc
2. **ERP VBA schema** — no explicit doc, assumed same as CNEE master
3. **Rate type matrix** — `FAK` vs `FIX` vs `SCFI` booking requirements

---

## Conclusion for Phase 2

SHARED_SCHEMA.md should:
1. Reference MASTER_V7_SCHEMA.md (62 cols) — full detail there
2. Reference ARB_ORIGIN_MAPPING.md — full rules there
3. Embed critical Country→POL rules **inline** (not just link) — these are the most-frequently needed by all 3 CLI agents
4. Link commodity_groups.yaml — canonical source
5. Document the 7 VN domestic ports inline (small list, frequently needed)
