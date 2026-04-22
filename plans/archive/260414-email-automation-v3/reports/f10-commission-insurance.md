# F10 — Commission / Insurance / Trucking Calculator
**Date:** 2026-04-14  
**Feature:** Active Jobs v4 — Feature 10  
**Status:** DONE (26/26 tests pass)

---

## Decision Rationale: Commission Split Formula

### The "KICK BACK" model (Nelson's terminology)

Nelson runs a two-sided payout: a portion of gross profit is paid out as
kick-back (rebate) to the customer, and the company retains the remainder.
A withholding tax (3%) is applied on the company's retained share.

### Formula

```
kb_pool   = gross_profit × customer_rate      (default 50%)
net_co    = gross_profit - kb_pool
kb_client = kb_pool                            (entire pool → client)
kb_carrier = 0                                 (manual entry, default zero)
kb_tax    = net_co × withholding_tax_rate      (3% of company share)
net_company = net_co - kb_tax
```

### Why this split

1. **Customer rate first** — every customer has a negotiated kick-back %.
   VIFON EXPORT (40%) is a high-volume anchor, NAFOODS (45%) mid-tier,
   SIRI/PANDA DAD (50%) standard. Company must NOT pay out more than it
   agreed to.

2. **Carrier column is zero by default** — in practice Nelson's carrier
   kick-back is negotiated ad hoc per vessel/agent and entered manually
   in the monthly report. The formula provides the column but leaves it
   zero so manual override is never overwritten.

3. **Tax on company share, not gross** — Vietnamese withholding tax (3%)
   applies to the company's earned income, not the full gross. Applying
   it to `net_co` (after client payout) is the correct tax base.

4. **PAID gate** — commission is only accrued when status = PAID.
   CONFIRMED/BOOKING jobs carry risk; kick-back is only owed once money
   is received. This prevents over-accruing payables.

---

## Example Breakdown

**Customer:** SIRI | **Gross profit:** $1,200 | **Status:** PAID

| Line item | Calculation | USD |
|-----------|-------------|----:|
| Gross profit | given | $1,200.00 |
| KB pool (50%) | 1200 × 0.50 | $600.00 |
| Company retained | 1200 − 600 | $600.00 |
| KB Tax (3% of co.) | 600 × 0.03 | $18.00 |
| **Net company** | 600 − 18 | **$582.00** |

**Monthly report columns:**
- T (Profit Share) = $1,200
- U (KB Client) = $600
- V (KB Carrier) = $0
- W (KB Tax) = $18
- X (Net Profit) = $582

---

## Insurance Rate Logic

ICC class A applies the broadest coverage and the highest premium.
Reefer containers (20RF, 40RF) carry a 33% surcharge on ICC-A (0.20%
vs 0.15%) because temperature-sensitive cargo has higher loss probability.

| Class | Commodity | Rate | Example on $50k cargo |
|-------|-----------|------|-----------------------|
| A | General | 0.15% | $75 |
| A | Reefer | 0.20% | $100 |
| B | General | 0.10% | $50 |
| C | General | 0.05% | $25 |

---

## Trucking Fee Logic

CY-DOOR only — CY-CY ships never incur inland trucking.

`fee = zone_rate × container_factor + tthq_fee`

- 20GP pays 60% of the 40HC rate (volume/weight equivalence).
- TTHQ customs clearance ($150 flat) is added for every DOOR delivery.
- Port-direct destinations (LA, LB, NY, SAV) have zone_rate=0, so no
  TTHQ either (nothing to clear inland).

**Example: Chicago CY-DOOR, 40HC**
```
1,800 × 1.0 + 150 = $1,950
```

---

## Files Delivered

| File | Lines | Purpose |
|------|-------|---------|
| `ERP/data/commissions_rules.yaml` | 44 | Config: rates, zones, tax |
| `ERP/intelligence/cost_addons.py` | 245 | Calculator + CLI |
| `ERP/intelligence/enrich_monthly_report.py` | 135 | xlsx enrichment |
| `tests/test_cost_addons.py` | 196 | 26 unit tests |

All tests: **26 passed in 0.13s**
