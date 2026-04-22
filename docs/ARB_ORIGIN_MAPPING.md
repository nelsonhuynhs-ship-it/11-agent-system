# ARB Origin Mapping — Shipping Market Rules

**Last updated:** 2026-04-22 23:00
**Status:** 📋 Reference doc (implementation pending in `email_engine/core/rule_engine.py`)
**Source:** `email_engine/data/arb_rates.yaml` + Nelson market knowledge (confirmed 2026-04-22)

---

## Overview

ARB (Additional Rate Base) mapping determines the **Port of Loading (POL)** and **arbitrage pricing origin** based on customer's origin country. This is critical for accurate rate quoting to international CNEE contacts.

**Key insight:** 91% of CNEE master data has empty POL column → fallback to ORIGIN_COUNTRY field for default routing.

---

## Mapping Rules by Origin Country

### Vietnam (VN)

| Field | Value | Notes |
|-------|-------|-------|
| POL default | HCM (South) / HPH (North) | Split by inland location |
| ARB key | None | Direct Vietnam → US routes, no arbitrage |
| Rate source | HPH/HCM direct carrier contracts | ONE, CMA, HPL, YML, etc. |

**Rule:** Vietnamese shippers route direct (no cross-origin markup). Use HPH if North, HCM if South.

---

### Malaysia (MY)

| Field | Value | Notes |
|-------|-------|-------|
| POL default | **PKG** (Port Klang) | CRITICAL: 7,232 CNEE (32% of pool) incorrectly default to HPH |
| ARB key | `port_klang` | ARB surcharge file reference |
| Rate source | Malaysia direct carrier contract | ONE, CMA, HPL, YML |

**🔴 URGENT finding:** 7,232 Malaysia contacts currently route through HPH (wrong). Must implement fallback rule to `port_klang` when POL is empty AND ORIGIN_COUNTRY='MY'.

**Implementation:** In `rule_engine.py`, check ORIGIN_COUNTRY before defaulting to HCM.

---

### Thailand (TH)

| Field | Value | Notes |
|-------|-------|-------|
| POL default | BKK / LAEM CHABA | Same port, different naming |
| ARB key | `lat_krabang` | ARB surcharge for Thailand cross-origin |
| Rate source | Thailand direct carrier contract | ONE, CMA, HPL, YML |

---

### China (CN) — ⚠️ CRITICAL CORRECTION

| Field | Value | Notes |
|-------|-------|-------|
| POL | SHA (Shanghai) or NGB (Ningbo) | Depends on origin shipper location |
| ARB key | `shanghai` or `ningbo` | **FULL RATE, not surcharge** |
| Rate source | China direct carrier (ONE/CMA/HPL/YML) | **NEVER transit via Vietnam** |

### ❌ WRONG assumption (corrected 2026-04-22)

**Previous AI statement:** "China ports transit via HPH"

**Nelson correction:** China → USA routes have **direct lanes** with China-based carriers. No Vietnam intermediate. Each China port (SHA/NGB/YTN) has its own ARB rate table (full pricing, not surcharge on top of HPH).

**Implication:** Do NOT use HCM + ARB `phnom_penh`-style surcharge logic for China. China ARB keys point to complete rate pricing, not incremental.

---

### Cambodia (KH)

| Field | Value | Notes |
|-------|-------|-------|
| POL default | HCM (via transit) | Cambodia has no deep-sea port |
| ARB key | `phnom_penh` | Surcharge ON TOP of HCM base rate |
| Rate source | HCM base + Cambodia surcharge | Phnom Penh → HCM consolidation |

**Correct model:** Base HCM rate + ARB `phnom_penh` increment.

---

### Bangladesh (BD) — TODO

| Field | Value | Notes |
|-------|-------|-------|
| POL | CGP (Chittagong) | Currently not in `arb_rates.yaml` |
| ARB key | TBD | Research required |
| Rate source | TBD | Need carrier mapping |

**Status:** Not yet researched. Add to next session TODO.

---

## Data Findings (CNEE Master Sheet)

**Summary (22,842 total CNEE):**

| Category | Count | % | Status |
|----------|-------|-----|--------|
| POL empty (needs fallback) | 20,864 | 91% | CRITICAL |
| POL specified (VN/TH/CN/KH/etc.) | ~1,978 | 9% | OK |
| ORIGIN_COUNTRY = MY | 7,232 | 32% | ⚠️ Currently misrouted to HPH |
| ORIGIN_COUNTRY = VN | ~10,500 | 46% | OK (direct VN routes) |
| ORIGIN_COUNTRY = TH | ~200 | 0.9% | OK |
| ORIGIN_COUNTRY = CN | ~40 | 0.2% | OK (direct CN routes) |
| ORIGIN_COUNTRY = KH | 6 | 0.03% | OK (via HCM) |

**Insight:** The **Malaysia segment (7,232 contacts)** is the highest-priority fix — currently all route through HPH instead of Port Klang.

---

## Configuration File Reference

**Path:** `email_engine/data/arb_rates.yaml`

Structure:
```yaml
arb_origins:
  port_klang:
    carriers: [ONE, CMA, HPL]
    routes:
      - {from: "port_klang", to: ["USLGB", "USLAX"], rate_per_40hq: 2500}
  
  lat_krabang:
    carriers: [ONE, CMA]
    routes:
      - {from: "lat_krabang", to: ["USLGB"], rate_per_40hq: 2600}
  
  shanghai:
    carriers: [ONE, CMA, HPL, YML]
    routes:
      - {from: "shanghai", to: ["USLGB", "USLAX"], rate_per_40hq: 3200}
  
  phnom_penh:
    base_route: "HCM"
    surcharge_per_40hq: 500
```

---

## Implementation Pointer (for `rule_engine.py`)

Target file: `email_engine/core/rule_engine.py` (to be created in next session)

**Pseudocode:**

```python
ARB_MAPPING = {
    "VN": {
        "pol_default": "HCM",  # fallback to HCM for South Vietnam
        "arb_key": None
    },
    "MY": {
        "pol_default": "PKG",  # CRITICAL: Port Klang, not HCM
        "arb_key": "port_klang"
    },
    "TH": {
        "pol_default": "BKK",
        "arb_key": "lat_krabang"
    },
    "CN": {
        "pol_default": "SHA",  # Shanghai default, can switch to NGB
        "arb_key": "shanghai"  # Full rate, not surcharge
    },
    "KH": {
        "pol_default": "HCM",  # Transit consolidation
        "arb_key": "phnom_penh"  # Surcharge model
    }
}

def resolve_pol_and_arb(row, user_markup_usd=20):
    """
    Resolve POL and ARB origin from contact row.
    
    Args:
        row: contact dict with ORIGIN_COUNTRY, POL, DESTINATION columns
        user_markup_usd: Nelson's fixed markup per batch (default 20)
    
    Returns:
        {
            "pol": "PORT",
            "arb_origin": "arb_key_or_none",
            "markup_usd": user_markup_usd,
            "destination": "USLGB,USLAX"
        }
    """
    country = row.get("ORIGIN_COUNTRY", "VN").upper().strip()
    rule = ARB_MAPPING.get(country, ARB_MAPPING["VN"])
    
    # Use POL from row if present, else fallback to rule default
    pol = row.get("POL", "").upper().strip()
    if not pol:
        pol = rule["pol_default"]
    
    # Special case: China Ningbo variant
    if country == "CN" and pol in ("NGB", "NINGBO"):
        arb_origin = "ningbo"
    else:
        arb_origin = rule["arb_key"]
    
    return {
        "pol": pol,
        "arb_origin": arb_origin,
        "markup_usd": user_markup_usd,
        "destination": row.get("DESTINATION", "USLGB,USLAX")
    }
```

---

## Markup Strategy (2026-04-22 Decision)

**Rule:** Nelson applies **single markup value** to entire batch (not per-tier).

| Field | Behavior |
|-------|----------|
| UI input | "Markup USD" field (1 value) |
| Default | 20 USD/container (if UI left empty) |
| Applied to | All emails in batch |
| Override | None (not per-customer) |

---

## Related Documentation

- [System Standards Section 2](./SYSTEM_STANDARDS.md#section-2--charge-name-mapping-parquet) — Charge name mapping (Total Ocean Freight)
- [Email Dashboard v6](./EMAIL_DASHBOARD_V6.md) — Complete email pipeline context
- [Email Pipeline Source of Truth](./EMAIL_PIPELINE_SOURCE_OF_TRUTH.md) — Architecture + data flow

---

## Research TODO (Next Session)

1. **Bangladesh (BD)** — Verify POL (likely CGP), find carrier mapping in `arb_rates.yaml`
2. **India (IN)** — Check coverage (expected Port Delhi or Chennai)
3. **Philippines (PH)** — Check coverage (expected Port Manila)
4. **Indonesia (ID)** — Check coverage (expected Jakarta or Surabaya)
5. **Subject line randomization** — Implement 5+ template variants to avoid spam filter fingerprinting
6. **Preview modal** — Build sample rate table renderer in web UI before batch Send confirmation

---

## Incident History

**2026-04-22 — AI Correction**
- **Issue:** AI documentation said China routes transit via Vietnam (HPH)
- **Reality:** China has direct carrier lanes with full independent pricing (Shanghai, Ningbo)
- **Impact:** Would have under/over-quoted China shipments if implemented without correction
- **Resolution:** Nelson clarified; document corrected; implementation postponed pending `rule_engine.py` session

**2026-04-22 — Malaysia Segment Discovery**
- **Issue:** 7,232 Malaysia CNEE (32% of pool) have empty POL → default to HCM (wrong)
- **Fix:** Implement ORIGIN_COUNTRY='MY' → `port_klang` fallback rule
- **Priority:** HIGH (affects ~7K quotes)

