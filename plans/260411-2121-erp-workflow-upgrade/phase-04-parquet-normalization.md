# Phase 4 — Parquet 45'HQ + Legacy Refresh Cleanup

**Priority:** HIGH (silent data bug) | **Status:** PENDING | **Effort:** 1-2h | **Tier:** 2

## Context

Two independent data-layer bugs surfaced in Audit B:

1. **45'HQ column name collision** — `refresh-v14.py:105-106` renames "45'HQ" column to "45HQ" AFTER the pivot. If a route's raw rows contain BOTH "45'HQ" and "45HQ" values, pivot creates two separate columns, rename causes silent data loss (second column overwrites first).
2. **Legacy `ERP/core/refresh.py`** is missing the Eff filter → would load 197K stale rows (5+ years old) if any code path still calls it.

## Action 4.1 — Normalize 45'HQ PRE-pivot in `refresh-v14.py`

File: `D:/OneDrive/NelsonData/erp/refresh-v14.py`

Current (lines 60-110):
```python
print("\n[1/4] Loading Parquet...")
df = pd.read_parquet(PARQUET)
print(f"  {len(df):,} rows total")

df['Eff'] = pd.to_datetime(df['Eff'], errors='coerce')
df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
df['RefreshDate'] = df['Eff'].where(df['Eff'].notna(), df['Exp'])
# ...
```

Add 1 line after `df = pd.read_parquet(PARQUET)`:
```python
# Normalize container type variants — parquet has both "45'HQ" and "45HQ"
# (import pipeline drift). Must happen BEFORE pivot so dedup treats them as one.
if 'Container_Type' in df.columns:
    df['Container_Type'] = df['Container_Type'].replace({"45'HQ": "45HQ"})
```

Remove the post-pivot rename (lines 105-106) — no longer needed:
```python
# DELETE these lines:
# if "45'HQ" in pivot.columns:
#     pivot = pivot.rename(columns={"45'HQ": "45HQ"})
```

## Action 4.2 — Validate the fix

```bash
# Before fix — count 45'HQ vs 45HQ in current parquet
python -c "
import duckdb
q = duckdb.sql(\"\"\"
    SELECT Container_Type, COUNT(*) as n
    FROM read_parquet('D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet')
    WHERE Container_Type IN ('45''HQ', '45HQ')
    GROUP BY Container_Type
\"\"\").fetchall()
print(q)
"
# Expected output: both values present if bug active
```

Then run `refresh-v14.py` on a COPY of the xlsm, compare `Pricing Dry` row count before/after:
```bash
# Backup live xlsm first
cp "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm" "D:/OneDrive/NelsonData/pricing/_backup/pre-p4-260411/"

# Run refresh
cd "D:/OneDrive/NelsonData/erp" && python refresh-v14.py "ERP_Master_v14.xlsm"

# Run test stack
scripts\run-erp-tests.bat
```

Expected: row count differs by at most a few rows (the duplicates collapsed). No data loss.

## Action 4.3 — Add unit test for normalize helper

Extract the normalize step into a small function so we can unit-test it:
```python
# refresh-v14.py
def normalize_container_types(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse '45HQ' vs "45'HQ" so pivot sees one container column."""
    if 'Container_Type' in df.columns:
        df = df.copy()
        df['Container_Type'] = df['Container_Type'].replace({"45'HQ": "45HQ"})
    return df
```

Test (`tests/unit/test_refresh_v14_normalize.py`):
```python
import pandas as pd
import sys, importlib.util
from pathlib import Path

def _load():
    p = Path("D:/OneDrive/NelsonData/erp/refresh-v14.py")
    spec = importlib.util.spec_from_file_location("refresh_v14", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_normalize_collapses_45hq_variants():
    m = _load()
    df = pd.DataFrame({"Container_Type": ["45'HQ", "45HQ", "40HQ", "20GP"]})
    out = m.normalize_container_types(df)
    assert set(out["Container_Type"]) == {"45HQ", "40HQ", "20GP"}
    assert (out["Container_Type"] == "45HQ").sum() == 2
```

## Action 4.4 — Kill legacy `ERP/core/refresh.py`

Grep for callers first:
```bash
grep -rn "from ERP.core.refresh\|ERP/core/refresh\|refresh\.refresh_data\|refresh\.load_and_process_parquet" --include="*.py"
grep -rn "ERP.core.refresh" --include="*.py"
```

Expected: maybe `ERP/core/control.py` or an ERP menu entry. Audit each:
- If caller still used → redirect to `refresh-v14.py` via subprocess
- If no caller → delete `ERP/core/refresh.py` + its tests

Replace body of `ERP/core/refresh.py`:
```python
"""DEPRECATED — legacy v13 refresh with broken Eff filter.

Canonical refresh is `D:/OneDrive/NelsonData/erp/refresh-v14.py`.
This file exists only to fail loudly if old code still imports it.
"""
import warnings
import sys
from pathlib import Path

warnings.warn(
    "ERP.core.refresh is deprecated — use refresh-v14.py (OneDrive). "
    "See docs/rate-pipeline-contract.md §refresh.",
    DeprecationWarning,
    stacklevel=2,
)


def refresh_data(*args, **kwargs):
    raise RuntimeError(
        "ERP.core.refresh.refresh_data() is dead code. "
        "Run: python D:/OneDrive/NelsonData/erp/refresh-v14.py ERP_Master_v14.xlsm"
    )


def load_and_process_parquet(*args, **kwargs):
    raise RuntimeError(
        "ERP.core.refresh.load_and_process_parquet() is dead code. "
        "Canonical: refresh-v14.py::load_parquet + build_pricing_dashboard."
    )
```

## Verification

```bash
# 1. Unit test normalize
pytest tests/unit/test_refresh_v14_normalize.py -v

# 2. Integration test — run refresh on test copy
python -c "
import importlib.util, pathlib
p = pathlib.Path('D:/OneDrive/NelsonData/erp/refresh-v14.py')
spec = importlib.util.spec_from_file_location('r', p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# refresh-v14 runs top-level — verify no exceptions
"

# 3. Regression
scripts\run-erp-tests.bat

# 4. Verify legacy raises
python -c "from ERP.core.refresh import refresh_data; refresh_data()"
# Expected: RuntimeError
```

## Success criteria
- [ ] `normalize_container_types` helper added, unit-tested
- [ ] `refresh-v14.py` uses it BEFORE pivot
- [ ] Post-pivot rename line removed
- [ ] `ERP/core/refresh.py` raises RuntimeError if called
- [ ] No caller of legacy refresh remains (grep clean)
- [ ] Regression green

## Risk
- MED — live refresh-v14 touches production xlsm. Backup first.
- LOW for legacy kill — if something silently still depends on it, RuntimeError surfaces the caller for manual fix.

## Next
→ P5: Markup per-lane schema
