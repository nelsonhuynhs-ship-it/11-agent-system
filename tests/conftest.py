"""Shared pytest fixtures for ERP Phase 1 regression tests.

Provides:
  - erp_copy   : per-test copy of live ERP_Master_v14.xlsm in tmpdir (openpyxl-only)
  - seeded_erp : erp_copy pre-seeded with 5+ Active Jobs rows covering all 7 stages
  - sample_rules: booking_rules.json loaded as dict
  - excel_app  : xlwings session (kept for integration markers, no-op if xlwings absent)
  - erp_workbook: xlwings workbook fixture (skipped if xlwings absent)

CRITICAL: No fixture may write to the live OneDrive ERP_Master_v14.xlsm.
"""
from __future__ import annotations

import faulthandler
import gc
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
import pytest

faulthandler.disable()

_DEFAULT_MASTER = Path("D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm")
MASTER_XLSM = Path(os.environ.get("ERP_MASTER_XLSM", str(_DEFAULT_MASTER)))

RULES_FILE = Path(__file__).parent.parent / "ERP" / "carrier_rules" / "booking_rules.json"

# Active Jobs layout constants (mirror ERP modules)
AJ_SHEET_KEYWORD = "Active"
AJ_HDR_ROW = 7
AJ_DATA_START = 8


# ── openpyxl-based fixtures (no COM / no xlwings) ──────────────────────────

@pytest.fixture(scope="function")
def erp_copy(tmp_path):
    """Copy live ERP_Master_v14.xlsm to a tmpdir. Tests mutate freely."""
    if not MASTER_XLSM.exists():
        pytest.skip(f"Live ERP not found: {MASTER_XLSM}")
    dst = tmp_path / "ERP_Master_v14_test.xlsm"
    shutil.copy2(MASTER_XLSM, dst)
    yield dst
    # cleanup handled by tmp_path fixture


def _seed_active_jobs_rows(erp_path: Path) -> None:
    """Write 7 seed rows into Active Jobs (rows 8-14) covering stages 1-7."""
    wb = openpyxl.load_workbook(str(erp_path), keep_vba=True)
    sheet = next((s for s in wb.sheetnames if AJ_SHEET_KEYWORD in s), None)
    if sheet is None:
        wb.close()
        raise RuntimeError("Active Jobs sheet not found in ERP copy")
    ws = wb[sheet]

    now = datetime.now()

    # Seed rows: (col values dict)
    # Col layout: 1=CRM_ID 3=Routing 4=Bkg_No 5=ETD 6=ETA 7=ATA 8=Carrier
    # 9=Contract_Type 10=Container_Type 11=Quantity 16=Status 17=SI_Received
    # 18=CY_Cutoff 19=Door_Delivery 24=Notes 29=FAST_JOB_NO 30=HBL_NO
    # 33=RELEASE_EMAIL_SENT 34=RELEASE_CONFIRMED
    seeds = [
        # Stage 1 BKG — booking pending, no contract
        {1: "NAFOODS", 3: "HPH-USLGB", 4: "NFBKG001", 8: "ONE",
         10: "40HQ", 11: 2, 16: "Booked", 19: "No"},
        # Stage 2 Conf — bkg + contract
        {1: "SIRI", 3: "HPH-USLGB", 4: "SRBKG002", 8: "MSC",
         9: "SHA0005N25", 10: "40HQ", 11: 1, 16: "Confirmed", 19: "No"},
        # Stage 3 SI Cut
        {1: "VIFON", 3: "HCM-USLAX", 4: "VFBKG003", 8: "CMA",
         9: "CMA-2026", 10: "40GP", 11: 2, 16: "Confirmed",
         17: now - timedelta(days=2), 19: "No"},
        # Stage 5 ATD — ETD in past
        {1: "WESTFOOD", 3: "HPH-USNYC", 4: "WFBKG004", 8: "OOCL",
         9: "OO2026", 10: "40HQ", 11: 1,
         5: now - timedelta(days=10), 16: "In Transit", 19: "No"},
        # Stage 6 ETA — ATA set
        {1: "PANDA", 3: "HCM-USLAX", 4: "PDBKG005", 8: "COSCO",
         9: "CS2026", 10: "20GP", 11: 3,
         5: now - timedelta(days=20), 7: now - timedelta(days=1),
         16: "Arrived", 19: "No"},
        # Stage 7 Done — delivered
        {1: "TRANANH", 3: "HPH-USLGB", 4: "TABKG006", 8: "ONE",
         9: "SHA0005N25", 10: "40RF", 11: 1,
         5: now - timedelta(days=30), 7: now - timedelta(days=10),
         16: "Delivered", 19: "Yes"},
        # Release-email-sent case for release_alerts tests
        {1: "OCEANSEA", 3: "HCM-USLAX", 4: "OSBKG007", 8: "CMA",
         9: "CMA-2026", 10: "40HQ", 11: 1,
         5: now - timedelta(days=25), 6: now + timedelta(days=2),
         16: "Arrived", 19: "No",
         33: now - timedelta(hours=3)},  # release email 3h ago, no confirm
    ]

    for i, row_data in enumerate(seeds):
        r = AJ_DATA_START + i
        for col, val in row_data.items():
            ws.cell(r, col, val)

    wb.save(str(erp_path))
    wb.close()


@pytest.fixture(scope="function")
def seeded_erp(tmp_path):
    """Copy + seed 7 Active Jobs rows covering stages 1-7 plus release-alert case."""
    if not MASTER_XLSM.exists():
        pytest.skip(f"Live ERP not found: {MASTER_XLSM}")
    dst = tmp_path / "ERP_Master_seeded.xlsm"
    shutil.copy2(MASTER_XLSM, dst)
    _seed_active_jobs_rows(dst)
    yield dst


@pytest.fixture(scope="session")
def sample_rules():
    """Load booking_rules.json as dict."""
    with open(str(RULES_FILE), "r", encoding="utf-8") as f:
        return json.load(f)


# ── xlwings fixtures (integration only — skipped when xlwings missing) ──────

@pytest.fixture(scope="session")
def excel_app():
    """Start one headless Excel instance for the whole test session."""
    try:
        import xlwings as xw
    except ImportError:
        pytest.skip("xlwings not installed — skip COM integration tests")
        return
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    try:
        yield app
    finally:
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
    """Open a fresh copy of ERP_Master_v14.xlsm per test via xlwings."""
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
