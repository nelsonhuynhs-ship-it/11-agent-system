# -*- coding: utf-8 -*-
"""DEPRECATED — legacy v13 refresh with broken Eff filter.

Canonical refresh is now `D:/OneDrive/NelsonData/erp/refresh-v14.py`.
This file exists only to fail loudly if old code still imports it.

## Why deprecated

- Missing Eff filter → would load ~197K stale rows (5+ years old) as if active
- No 15d→30d→90d fallback cascade
- Doesn't split Pricing Dry / Pricing Reefer sheets
- 45'HQ post-pivot rename bug (see P4)

## Canonical alternative

```bash
python "D:/OneDrive/NelsonData/erp/refresh-v14.py" "D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"
```

## Deprecation context

- Plan: plans/260411-2121-erp-workflow-upgrade/phase-04-parquet-normalization.md
- Audit: plans/reports/brainstorm-260411-2121-erp-workflow-upgrade-synthesis.md
- Source of truth: docs/erp-v14-source-of-truth.md
"""
import warnings

warnings.warn(
    "ERP.core.refresh is deprecated — use refresh-v14.py (OneDrive). "
    "See plans/260411-2121-erp-workflow-upgrade/phase-04-parquet-normalization.md",
    DeprecationWarning,
    stacklevel=2,
)


_DEAD_MSG = (
    "ERP.core.refresh is dead code. "
    'Run: python "D:/OneDrive/NelsonData/erp/refresh-v14.py" ERP_Master_v14.xlsm'
)


def refresh_data(*args, **kwargs):
    raise RuntimeError(_DEAD_MSG)


def load_and_process_parquet(*args, **kwargs):
    raise RuntimeError(_DEAD_MSG)


def write_to_erp(*args, **kwargs):
    raise RuntimeError(_DEAD_MSG)


def main(*args, **kwargs):
    raise RuntimeError(_DEAD_MSG)


if __name__ == "__main__":
    raise SystemExit(_DEAD_MSG)
