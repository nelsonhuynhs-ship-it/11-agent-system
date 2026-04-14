"""Test QuoteImage multi-route rendering (P4 2026-04-13).

Verifies that OnAction_QuoteImage correctly handles multiple routes
when given quote rows with different POL-PLACE combinations. The P4
fix moved Dim declarations out of For loops to prevent duplicate-
declaration errors on the second iteration in some Excel builds.

g_TestMode keeps the _QuoteImg sheet alive so we can inspect it.

Uses TestRunQuoteImage wrapper instead of calling OnAction_QuoteImage
directly — xlwings cannot pass Optional IRibbonControl correctly via
COM, which causes a hang. The wrapper calls it internally with Nothing.
"""
from __future__ import annotations

from datetime import datetime

import pytest


def _require_test_mode(wb):
    """Enable g_TestMode or skip if macro not available."""
    try:
        wb.macro("ERPv14Ribbon.SetTestMode")(True)
    except Exception as e:
        msg = str(e).lower()
        if "cannot run the macro" in msg or "not be available" in msg:
            pytest.skip(
                "SetTestMode macro not found. Re-import VBA via "
                "`python scripts/reimport-erp-vba.py`."
            )
        raise


def _cleanup_quote_img(wb):
    """Delete _QuoteImg sheet if present."""
    try:
        wb.app.display_alerts = False
        wb.sheets["_QuoteImg"].delete()
        wb.app.display_alerts = True
    except Exception:
        pass


def test_quote_image_multi_route(erp_workbook):
    """Select 5 quote rows with 3 different routes -> QuoteImage renders all 3.

    Route layout:
      Route 1: DAD - NEW YORK, NY  (2 rows: HPL, MSC)
      Route 2: HPH - CHICAGO, IL   (1 row:  ONE)
      Route 3: HCM - NEW YORK, NY  (2 rows: CMA, ZIM)

    Asserts:
      - TestRunQuoteImage returns "OK" (no VBA error)
      - _QuoteImg sheet is created and kept (test mode)
      - At least 3 route header rows exist (blue background bars)
      - At least 5 carrier data rows exist
    """
    _require_test_mode(erp_workbook)
    try:
        ws = erp_workbook.sheets["Quotes"]

        # Clean any leftover _QuoteImg from prior runs
        _cleanup_quote_img(erp_workbook)

        # Column map from VBA constants:
        # 1=QuoteID 2=Date 3=Customer 4=Carrier 5=POL 6=POD 7=Place
        # 8=Note(Via) 9=Eff 10=Exp 11=Source  29=Sell_20GP 31=Sell_40HC
        test_rows = [
            # Route 1: DAD - NEW YORK, NY (2 rows)
            ("IMGTEST-001", datetime(2026, 4, 13), "TESTCUST", "HPL", "DAD",
             "NEW YORK, NY", "NEW YORK, NY", "",
             datetime(2026, 4, 8), datetime(2026, 4, 14), "COC", 3000, 4000),
            ("IMGTEST-002", datetime(2026, 4, 13), "TESTCUST", "MSC", "DAD",
             "NEW YORK, NY", "NEW YORK, NY", "",
             datetime(2026, 4, 9), datetime(2026, 4, 14), "COC", 3100, 4100),
            # Route 2: HPH - CHICAGO, IL (1 row)
            ("IMGTEST-003", datetime(2026, 4, 13), "TESTCUST", "ONE", "HPH",
             "NEW YORK, NY", "CHICAGO, IL", "",
             datetime(2026, 4, 9), datetime(2026, 4, 14), "COC", 3200, 4200),
            # Route 3: HCM - NEW YORK, NY (2 rows)
            ("IMGTEST-004", datetime(2026, 4, 13), "TESTCUST", "CMA", "HCM",
             "NEW YORK, NY", "NEW YORK, NY", "",
             datetime(2026, 4, 1), datetime(2026, 4, 7), "COC", 3300, 4300),
            ("IMGTEST-005", datetime(2026, 4, 13), "TESTCUST", "ZIM", "HCM",
             "NEW YORK, NY", "NEW YORK, NY", "",
             datetime(2026, 4, 1), datetime(2026, 4, 7), "COC", 3400, 4400),
        ]

        start_row = 2
        col_map = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # first 11 cols
        for i, row_data in enumerate(test_rows):
            r = start_row + i
            for j, col in enumerate(col_map):
                ws.cells(r, col).value = row_data[j]
            ws.cells(r, 29).value = row_data[11]  # Sell_20GP
            ws.cells(r, 31).value = row_data[12]  # Sell_40HC

        end_row = start_row + len(test_rows) - 1

        # Activate Quotes and select the test rows
        ws.activate()
        ws.range(f"A{start_row}:A{end_row}").select()

        # Call via wrapper (avoids IRibbonControl COM hang)
        result = erp_workbook.macro("ERPv14Ribbon.TestRunQuoteImage")()
        result_str = str(result)
        assert result_str.startswith("OK"), f"QuoteImage VBA error: {result_str}"

        # Inspect _QuoteImg sheet (kept alive by g_TestMode)
        sheet_names = [s.name for s in erp_workbook.sheets]
        assert "_QuoteImg" in sheet_names, (
            f"_QuoteImg sheet not found after QuoteImage. Sheets: {sheet_names}"
        )
        tmp_ws = erp_workbook.sheets["_QuoteImg"]

        # Scan _QuoteImg to count route headers and data rows.
        # Route headers start with "  " (2 spaces) and contain " - "
        # Column headers row has "Carrier" in col 1
        # Data rows have carrier names in col 1
        route_headers = 0
        data_rows = 0
        carriers_found = set()
        expected_carriers = {"HPL", "MSC", "ONE", "CMA", "ZIM"}

        for row in range(1, 50):
            val = tmp_ws.cells(row, 1).value
            if val is None:
                break
            val_str = str(val)

            # Route headers are "  DAD - NEW YORK, NY" (leading spaces + route)
            if val_str.startswith("  ") and " - " in val_str:
                route_headers += 1
                continue

            # Data rows have carrier abbreviations
            stripped = val_str.strip()
            if stripped in expected_carriers:
                data_rows += 1
                carriers_found.add(stripped)

        # Cleanup _QuoteImg
        _cleanup_quote_img(erp_workbook)

        # Clean test rows from Quotes
        for i in range(len(test_rows)):
            ws.range(f"A{start_row + i}:AK{start_row + i}").clear()

        # Assertions
        assert route_headers >= 3, (
            f"Expected >= 3 route headers, got {route_headers}. "
            f"VBA result: {result_str}. "
            f"Multi-route rendering may be broken."
        )
        assert data_rows >= 5, (
            f"Expected >= 5 data rows, got {data_rows}. "
            f"Carriers found: {carriers_found}. VBA result: {result_str}"
        )
        assert carriers_found == expected_carriers, (
            f"Missing carriers: {expected_carriers - carriers_found}"
        )

    finally:
        try:
            erp_workbook.macro("ERPv14Ribbon.SetTestMode")(False)
        except Exception:
            pass
        _cleanup_quote_img(erp_workbook)
