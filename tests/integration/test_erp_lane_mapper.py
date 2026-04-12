"""Integration test for ERPv14Core.GetLaneFromPOD (Phase 5).

Invokes the VBA function via xlwings against a fresh ERP_Master_v14.xlsm
copy (see tests/conftest.py::erp_workbook).

The test is parametrized over representative POD strings covering WC, EC,
GULF and the default fallback. If the helper has not yet been imported
into the xlsm (main agent applies the bas patches + re-imports later),
the test skips gracefully — same pattern used by test_erp_quote_flow.py.
"""
from __future__ import annotations

import pytest


# (pod, expected lane)
LANE_CASES = [
    # WC
    ("LAX-LGB", "WC"),
    ("LONG BEACH", "WC"),
    ("OAKLAND", "WC"),
    ("VANCOUVER, BC", "WC"),
    ("SEATTLE", "WC"),
    # EC
    ("NEW YORK, NY", "EC"),
    ("NEW YORK", "EC"),
    ("BALTIMORE", "EC"),
    ("CHARLESTON", "EC"),
    ("MIAMI", "EC"),
    ("MONTREAL", "EC"),
    ("TORONTO", "EC"),
    # GULF
    ("HOUSTON, TX", "GULF"),
    ("HOUSTON", "GULF"),
    ("NEW ORLEANS", "GULF"),
    ("MOBILE", "GULF"),
    # Default / unknown
    ("UNKNOWN_PORT", "*"),
    ("", "*"),
]


def _require_lane_mapper(wb):
    """Skip if ERPv14Core.GetLaneFromPOD has not been imported into the xlsm.

    Phase 5 adds GetLaneFromPOD to erp-v14-quick-wins.bas. Until that file
    is re-imported via `scripts/reimport-erp-vba.py` (requires the Excel
    'Trust access to the VBA project object model' setting), the xlsm
    still has the old module without this helper — skip gracefully so
    non-re-imported runs stay green.
    """
    try:
        result = wb.macro("ERPv14Core.GetLaneFromPOD")("")
    except Exception as e:  # xlwings surfaces COM errors here
        msg = str(e).lower()
        if (
            "cannot run the macro"
            in msg
            or "not be available" in msg
            or "macro may not be available" in msg
        ):
            pytest.skip(
                "ERPv14Core.GetLaneFromPOD not found in xlsm. Apply Phase 5 "
                "patches and re-import VBA via "
                "`python scripts/reimport-erp-vba.py` after enabling Excel "
                "'Trust access to the VBA project object model' setting."
            )
        raise
    # Empty string should map to the default lane
    assert result == "*", f"Sanity check failed: empty POD → {result!r}"


@pytest.mark.parametrize("pod,expected", LANE_CASES)
def test_get_lane_from_pod(erp_workbook, pod, expected):
    """GetLaneFromPOD should map POD strings to {WC, EC, GULF, *}."""
    _require_lane_mapper(erp_workbook)
    result = erp_workbook.macro("ERPv14Core.GetLaneFromPOD")(pod)
    assert result == expected, (
        f"POD={pod!r} expected lane={expected!r}, got {result!r}"
    )
