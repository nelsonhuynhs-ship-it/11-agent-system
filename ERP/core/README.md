# ERP Core — Mixed v13/v14 (READ WHICH IS LIVE)

This directory holds a mix of legacy v13 helpers and a couple of shared utilities.
**Most of the refresh logic has moved to v14 on OneDrive.**

| File | Status | Replacement |
|---|---|---|
| `refresh.py` | DEPRECATED v13 — raises `RuntimeError` | `D:/OneDrive/NelsonData/erp/refresh-v14.py` |
| `build_erp_v13_ribbon.py` | DEPRECATED v13 — unused | `refresh-v14.py` + manual VBE import |
| `control.py` | Check usage before editing | — |
| `customui_utils.py` | Shared — keep | — |
| `__init__.py` | Package marker | — |

## Why `refresh.py` is dead

- Missing `Eff` filter → loads ~197K stale rows (5+ years old) as if they were active.
- No 15d → 30d → 90d fallback cascade.
- Doesn't split `Pricing Dry` / `Pricing Reefer` sheets.
- `refresh-v14.py` on OneDrive is the authoritative implementation.

Calling `ERP.core.refresh.refresh_data()` now raises `RuntimeError`. Anyone
still importing this module should migrate to `refresh-v14.py`.

See `docs/erp-v14-source-of-truth.md` for the full refresh flow and the
v14 file map.
