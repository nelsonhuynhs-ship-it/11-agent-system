# F4 + F7 Implementation Report — FAST ID & Reefer Plug Fee
Date: 2026-04-14

---

## Feature 4 — FAST ID Validator (`ERP/jobs/fast_id.py`)

### FAST ID Format Specification

```
{PREFIX}{YY}{MM}/{SEQ}
```

| Part   | Rule                              | Example |
|--------|-----------------------------------|---------|
| PREFIX | 2–4 uppercase letters             | SE, NF, ARB, NFVN |
| YY     | 2-digit year                      | 26 (= 2026) |
| MM     | 2-digit month (01–12)             | 03 |
| SEQ    | 4+ digits, zero-padded left       | 0266 |

Valid examples: `SE2603/0266`  `NF2604/1200`  `ARB2512/9999`

### Normalizer behavior
- Strips leading/trailing whitespace
- Uppercases the entire string
- Zero-pads SEQ to minimum 4 digits (`266` → `0266`)
- Raises `ValueError` with a human-readable message if format is invalid

### Public functions
| Function | Purpose |
|----------|---------|
| `normalize_fast_id(raw)` | Normalize or raise ValueError |
| `validate_active_jobs(erp_file)` | Returns `{invalid, duplicates, missing_delivered}` |
| `stamp_warnings(erp_file, report)` | Colors col 29: yellow=invalid, red=duplicate |

### CLI
```bash
python ERP/jobs/fast_id.py --check              # report only, no writes
python ERP/jobs/fast_id.py --fix                # normalize in-place + color cells
python ERP/jobs/fast_id.py --check --file path  # custom ERP file
```

### Column mapping (Active Jobs, row 7 = headers)
| Column | Index | Content |
|--------|-------|---------|
| B      | 2     | CRM / job reference |
| C      | 3     | Status (check "Delivered") |
| AC     | 29    | FAST_JOB_NO |

---

## Feature 7 — Reefer Plug Fee (`ERP/jobs/reefer_plug.py`)

### Business logic
- Reefer (RF) containers require shore power ("plug") at terminal while sitting on dock.
- Terminal charges $/day **after** the free period (`freetime_days`).
- Separate demurrage (storage) fee starts after a longer free period (7 days default).
- **Optimal drop date** = `ATA + freetime_days` — last day with $0 plug fee.

### Fee formula
```
days_at_terminal = (drop_date - ATA).days
plug_days        = max(0, days_at_terminal - freetime_days)
plug_fee         = plug_days × daily_fee_{cont_type}
demurrage_days   = max(0, days_at_terminal - demurrage.freetime_days)
demurrage_fee    = demurrage_days × demurrage.daily_fee_{cont_type}
total            = plug_fee + demurrage_fee
```

### Config file: `ERP/data/reefer_freetime.yaml`
**Nelson adjusts rates here — no code changes needed.**

```yaml
terminals:
  USLGB: {freetime_days: 4, daily_fee_20RF: 150, daily_fee_40RF: 200}
  USLAX: {freetime_days: 4, daily_fee_20RF: 160, daily_fee_40RF: 210}
  USNYC: {freetime_days: 5, daily_fee_20RF: 180, daily_fee_40RF: 230}
  default: {freetime_days: 4, daily_fee_20RF: 150, daily_fee_40RF: 200}

demurrage:
  freetime_days: 7
  daily_fee_20RF: 100
  daily_fee_40RF: 140
```

To add a new port: copy any terminal block, change the key to the POD code (e.g. `USSAV`).
The `default` block is used for any POD not listed.

### Public functions
| Function | Purpose |
|----------|---------|
| `load_reefer_rules()` | Load YAML; auto-creates if missing |
| `plug_cost(eta, drop_date, pod, cont_type, rules)` | Returns cost breakdown dict |
| `optimal_drop_date(eta, pod, cont_type, rules)` | Returns last free drop date + cost |
| `compute_for_active_jobs(erp_file)` | Scans all RF rows, returns list of dicts |
| `write_notes_to_jobs(erp_file, results)` | Writes note to col 24 (Notes), ribbon-safe |

### Notes format written to col 24
```
[RF 01APR] Optimal drop: 5/Apr | Plug: $0 (if on time) | $200/day after freetime
```

### CLI
```bash
python ERP/jobs/reefer_plug.py              # print table only
python ERP/jobs/reefer_plug.py --write      # also write to Notes col
python ERP/jobs/reefer_plug.py --write --file path/to/ERP.xlsm
```

### Column mapping used
| Column | Index | Content |
|--------|-------|---------|
| E      | 5     | POD |
| F      | 6     | ETA |
| G      | 7     | ATA (preferred over ETA when available) |
| J      | 10    | Container_Type (scans for 20RF / 40RF) |
| X      | 24    | Notes (written to) |

---

## Worked examples

### FAST ID normalizer
| Input | Output |
|-------|--------|
| `SE2603/0266` | `SE2603/0266` |
| ` se2603/266 ` | `SE2603/0266` |
| `XX/123` | ValueError |
| `SE2613/0100` | ValueError (month 13) |

### Reefer plug cost — USLGB 40RF, ATA = 2026-04-01
| Drop date | Days at terminal | Plug days | Plug fee | Dem days | Dem fee | Total |
|-----------|-----------------|-----------|----------|----------|---------|-------|
| Apr 05 (ATA+4) | 4 | 0 | $0 | 0 | $0 | $0 |
| Apr 06 (ATA+5) | 5 | 1 | $200 | 0 | $0 | $200 |
| Apr 11 (ATA+10) | 10 | 6 | $1,200 | 3 | $420 | $1,620 |
| May 01 (ATA+30) | 30 | 26 | $5,200 | 23 | $3,220 | $8,420 |

**Optimal drop date = Apr 05** (ATA + 4 freetime days)

---

## Files delivered
| File | Lines | Purpose |
|------|-------|---------|
| `ERP/jobs/fast_id.py` | 202 | FAST ID validator + normalizer + CLI |
| `ERP/jobs/reefer_plug.py` | 219 | Reefer plug fee calculator + CLI |
| `ERP/data/reefer_freetime.yaml` | 22 | Fee config (Nelson edits this) |
| `tests/test_fast_id.py` | — | 25 pure-Python unit tests |
| `tests/test_reefer_plug.py` | — | 20 pure-Python unit tests |

Tests: **45/45 passed** (0.14s, no Excel / OneDrive required)
