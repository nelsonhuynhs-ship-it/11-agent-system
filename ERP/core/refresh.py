"""
ERP/core/refresh.py — DEPRECATED legacy v13 stub
=================================================
The legacy v13 refresh pipeline was removed 2026-04-13 (see CLAUDE.md
"Repo Cleanup Log"). This module exists only as a tripwire: any code that
still imports and calls the old refresh functions fails loudly so the
mistake is caught immediately instead of producing stale data.

Modern replacement: ``refresh-v14.py`` (OneDrive) + ``rate_importer.py``.

Do NOT restore real logic here. If a caller needs refresh behaviour, point
them at the v14 path. Tests in ``tests/unit/test_refresh_v14_normalize.py``
assert these raise RuntimeError("dead code...") so we keep the contract.
"""
from __future__ import annotations

_MSG = (
    "ERP.core.refresh is dead code removed on 2026-04-13. "
    "Use ERP/jobs or refresh-v14.py on OneDrive instead."
)


def refresh_data(*_args, **_kwargs):  # pragma: no cover - tripwire
    raise RuntimeError(_MSG)


def load_and_process_parquet(*_args, **_kwargs):  # pragma: no cover
    raise RuntimeError(_MSG)


def main(*_args, **_kwargs):  # pragma: no cover
    raise RuntimeError(_MSG)


__all__ = ["refresh_data", "load_and_process_parquet", "main"]
