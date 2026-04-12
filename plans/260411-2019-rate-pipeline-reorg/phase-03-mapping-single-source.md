# Phase 3 — Mapping single source of truth

**Priority:** MEDIUM (prevent future divergence) | **Status:** PENDING
**Effort:** 1 hour | **Files touched:** `shared/paths.py`, `rate_importer.py`, repo `Pricing_Engine/Mapping/`

## Context

Two identical copies of `CARRIER_RATE_MAPPING.json` exist:
1. **OneDrive canonical:** `D:/OneDrive/NelsonData/pricing/mapping/CARRIER_RATE_MAPPING.json` — has siblings: `MASTER_MAPPING_HISTORY.csv`, `V4_FINAL_CHECK_*.csv`
2. **Repo copy:** `Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json` — isolated, no siblings

Verified identical by `diff -q` on 2026-04-11. Since OneDrive has the full mapping ecosystem (history + validation CSVs), **OneDrive wins**.

## Why consolidate

- Any future edit in one location silently diverges from the other
- Nelson must remember which copy to edit (decision fatigue)
- No audit trail — history CSV only lives with OneDrive copy
- Repo copy won't sync across machines (OneDrive does)

## Actions

### 3.1 Add MAPPING_DIR to shared/paths.py
```python
# shared/paths.py — add under existing OneDrive path resolution
MAPPING_DIR = ONEDRIVE_PRICING / "mapping"
CARRIER_RATE_MAPPING = MAPPING_DIR / "CARRIER_RATE_MAPPING.json"
```
Ensures one symbolic constant → all code imports `from shared.paths import CARRIER_RATE_MAPPING`.

### 3.2 Grep all current references
```bash
grep -rn "CARRIER_RATE_MAPPING\|Pricing_Engine/Mapping" --include="*.py" .
```
Expected hits (from audit): `rate_importer.py`, `master_loader_v2.py`, `rate_monitor.py`, possibly `tools/goclaw/*.py`.

### 3.3 Replace hardcoded paths
For each hit, swap hardcoded string for `sp.CARRIER_RATE_MAPPING`:

```python
# before
mapping_path = Path(__file__).parent / "Mapping" / "CARRIER_RATE_MAPPING.json"
# after
from shared import paths as sp
mapping_path = sp.CARRIER_RATE_MAPPING
```

### 3.4 Delete repo copy + leave stub README
```bash
rm Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json
```

Create `Pricing_Engine/Mapping/README.md`:
```markdown
# Mapping — moved to OneDrive

Canonical location: `D:/OneDrive/NelsonData/pricing/mapping/`
Access in code: `from shared.paths import CARRIER_RATE_MAPPING`

History + validation CSVs live in the OneDrive folder.
Edit there, never here.
```

### 3.5 Regression
- `python -m pytest tests/integration` → 11 pass / 3 skip
- `python -c "from shared.paths import CARRIER_RATE_MAPPING; import json; print(len(json.loads(CARRIER_RATE_MAPPING.read_text())))"` → prints column count
- Run `rate_importer.py --dry-run` if such flag exists, else `python Pricing_Engine/rate_importer.py --help`

## Success criteria
- [ ] `shared/paths.py` defines `CARRIER_RATE_MAPPING` pointing to OneDrive
- [ ] Zero hardcoded `"Mapping/CARRIER_RATE_MAPPING.json"` strings in codebase (grep clean)
- [ ] Repo `Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json` deleted
- [ ] `Pricing_Engine/Mapping/README.md` points to OneDrive
- [ ] Git commit: `refactor(pricing): single-source CARRIER_RATE_MAPPING via shared/paths`

## Risk
- LOW — mapping is read-only, no runtime mutation
- Rollback: git revert

## Next
P4 documents the folder contract so this never happens again.
