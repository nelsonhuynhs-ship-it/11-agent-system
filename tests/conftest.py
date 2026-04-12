"""Shared pytest fixtures for ERP automation tests.

Boots xlwings with headless Excel once per session, copies the master
ERP_Master_v14.xlsm to a tempdir per test so we never touch the live
OneDrive file.
"""
from __future__ import annotations

import faulthandler
import gc
import os
import shutil
import time
from pathlib import Path

import pytest

# Excel COM teardown can raise harmless RPC errors (0x800706be / 0x800706ba)
# as xlwings releases the Application. Disable faulthandler's noisy tracebacks
# for those — exit code and pass/fail reporting are unaffected.
faulthandler.disable()

# OneDrive master file — single source of truth for ERP tests.
# Override via env var ERP_MASTER_XLSM if moved.
_DEFAULT_MASTER = Path("D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm")
MASTER_XLSM = Path(os.environ.get("ERP_MASTER_XLSM", str(_DEFAULT_MASTER)))


@pytest.fixture(scope="session")
def excel_app():
    """Start one headless Excel instance for the whole test session."""
    import xlwings as xw  # lazy import so non-Excel tests don't require it

    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    try:
        yield app
    finally:
        # Force-close any leftover books before quit to avoid COM RPC errors.
        try:
            for wb in list(app.books):
                try:
                    wb.close()
                except Exception:
                    pass
        except Exception:
            pass
        gc.collect()
        time.sleep(0.2)
        try:
            app.quit()
        except Exception:
            pass
        gc.collect()


@pytest.fixture(scope="function")
def erp_workbook(excel_app, tmp_path):
    """Open a fresh copy of ERP_Master_v14.xlsm per test.

    We copy the master to a tempdir so concurrent tests and dirty writes
    never corrupt the OneDrive file. Workbook is closed on teardown.
    """
    if not MASTER_XLSM.exists():
        pytest.skip(f"Master xlsm not found: {MASTER_XLSM}")

    dst = tmp_path / "ERP_Master_v14_test.xlsm"
    shutil.copy2(MASTER_XLSM, dst)

    wb = excel_app.books.open(str(dst), update_links=False, read_only=False)
    try:
        yield wb
    finally:
        try:
            wb.close()
        except Exception:
            pass
