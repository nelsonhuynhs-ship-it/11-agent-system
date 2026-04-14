# F9 Transit Time Auto-Calculator — Report

**Date:** 2026-04-14
**Feature:** Active Jobs v4 — Feature 9
**Files delivered:**
- `ERP/jobs/transit_time.py` (292 lines)
- `tests/unit/test_transit_time.py` (28 tests, 28 passed)

---

## Route Class Decision Tree

```
INPUT: POD string  +  Door_Address (col 20)
         |
         v
  ┌─────────────────────────────────────────────────────────┐
  │ Does POD contain PRINCE RUPERT / VANCOUVER / CAPRR?     │
  │ Yes → base = CA_WC                                      │
  └────────────────────────┬────────────────────────────────┘
                           │ No
                           v
  ┌─────────────────────────────────────────────────────────┐
  │ Does POD contain MONTREAL / HALIFAX / CAHAL / CAMTR?    │
  │ Yes → base = CA_EC                                      │
  └────────────────────────┬────────────────────────────────┘
                           │ No
                           v
  ┌─────────────────────────────────────────────────────────┐
  │ Does POD contain LAX/LGB/OAK/SEA/TAC/USLAX/USLGB?      │
  │ Yes → base = WC                                         │
  └────────────────────────┬────────────────────────────────┘
                           │ No
                           v
  ┌─────────────────────────────────────────────────────────┐
  │ Does POD contain NYC/SAV/CHS/NORFOLK/BAL/BOS/…?         │
  │ Yes → base = EC                                         │
  └────────────────────────┬────────────────────────────────┘
                           │ No
                           v
  ┌─────────────────────────────────────────────────────────┐
  │ Does POD contain HOUSTON/HOU/NEW ORLEANS/MOB/MIAMI?      │
  │ Yes → base = GULF                                       │
  └────────────────────────┬────────────────────────────────┘
                           │ No
                           v
              WARNING issued → default base = EC

                           │
                           v
  ┌─────────────────────────────────────────────────────────┐
  │ INLAND CHECK: Door_Address set AND contains NO port      │
  │ keyword?                                                │
  │  Yes → return "{base}+INLAND"                          │
  │  No  → return base                                      │
  └─────────────────────────────────────────────────────────┘
```

---

## Transit Windows

| Route Class    | Min | Max | Median | Notes                          |
|----------------|-----|-----|--------|--------------------------------|
| WC             | 18  | 20  | 19     | Long Beach / LA / Oakland / SEA |
| EC             | 40  | 50  | 45     | NYC / SAV / CHS / NOR / BAL / BOS |
| GULF           | 40  | 50  | 45     | HOU / New Orleans / Mobile / MIA |
| CA_WC          | 18  | 22  | 20     | Prince Rupert / Vancouver      |
| CA_EC          | 35  | 45  | 40     | Montreal / Halifax             |
| WC+INLAND      | 23  | 25  | 24     | WC base + 5-day inland leg     |
| EC+INLAND      | 45  | 55  | 50     | EC base + 5-day inland leg     |
| GULF+INLAND    | 45  | 55  | 50     | GULF base + 5-day inland leg   |
| CA_WC+INLAND   | 23  | 27  | 25     | CA_WC base + 5-day inland leg  |
| CA_EC+INLAND   | 40  | 50  | 45     | CA_EC base + 5-day inland leg  |

---

## Notes column format

Appended to col 24 Notes (existing content preserved):

```
[TT 14Apr 09:30] ETA 28/Apr—30/Apr (WC)
```

---

## Test coverage

| Test class        | Cases | Pass |
|-------------------|-------|------|
| TestClassifyRoute | 14    | 14   |
| TestTransitWindow | 8     | 8    |
| TestEstimateEta   | 6     | 6    |
| **Total**         | **28**| **28** |
