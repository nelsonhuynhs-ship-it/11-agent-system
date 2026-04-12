"""Quote flow integration tests — P2-enabled via g_TestMode flag.

P2 refactor (2026-04-11) added `Public g_TestMode As Boolean` to
ERPv14Ribbon.bas. When True, success/info MsgBox calls are silenced
via the `MsgBoxOrSilent` wrapper, allowing headless xlwings execution.

Error MsgBox calls (vbExclamation/vbCritical) remain unchanged —
validation failures still pop up, which is correct for production.

Two tests remain skipped:
- test_mark_quote_win_promotes_to_active_jobs: blocked on InputBox for
  container quantity (not easily mockable via xlwings)
- test_refresh_rates_reopens_workbook: OnAction_RefreshRates closes +
  reopens the workbook via subprocess — incompatible with xlwings session
"""
from __future__ import annotations

import pytest


PRICING_SHEET_CANDIDATES = ("Pricing Dry", "Pricing Reefer")


def _first_pricing_sheet(wb):
    """Return the first available pricing sheet (Dry preferred)."""
    names = {s.name for s in wb.sheets}
    for name in PRICING_SHEET_CANDIDATES:
        if name in names:
            return wb.sheets[name]
    pytest.skip(f"No pricing sheet found in {sorted(names)}")


def _require_test_mode(wb):
    """Skip test if g_TestMode helpers haven't been re-imported into xlsm yet.

    P2 added SetTestMode/MsgBoxOrSilent to erp-v14-ribbon-callbacks.bas.
    Until `scripts/reimport-erp-vba.py` runs successfully (requires Excel
    Trust setting for VBA project access), the xlsm still has the old VBA
    without these helpers. Gracefully skip so non-re-imported runs stay green.
    """
    try:
        wb.macro("ERPv14Ribbon.SetTestMode")(True)
    except Exception as e:
        msg = str(e).lower()
        if "cannot run the macro" in msg or "not be available" in msg:
            pytest.skip(
                "SetTestMode macro not found in xlsm. Re-import VBA via "
                "`python scripts/reimport-erp-vba.py` after enabling Excel "
                "'Trust access to the VBA project object model' setting."
            )
        raise


def test_generate_quote_creates_quotes_sheet_row(erp_workbook):
    """Full quote flow: select row → set customer → generate → assert row in Quotes.

    Enables g_TestMode to silence success MsgBox, then:
      1. Activate a pricing sheet + select first data row
      2. LoadRowToRibbon populates m_Carrier, m_POL, m_POD, m_Buy*
      3. OnChange_Customer sets m_Customer
      4. OnAction_GenerateQuote writes a Quotes row

    Asserts a new row appears in Quotes with matching Customer + PENDING
    status. If the fixture's Quotes sheet already has rows, we track the
    delta rather than expecting a specific row index.
    """
    _require_test_mode(erp_workbook)  # enables g_TestMode or skips gracefully
    try:
        ws_dash = _first_pricing_sheet(erp_workbook)
        ws_quotes = erp_workbook.sheets["Quotes"]

        # Count Quotes rows before — use col A last-used row
        last_row_of_sheet = ws_quotes.cells.last_cell.row
        initial_last = ws_quotes.range(f"A{last_row_of_sheet}").end("up").row

        # Fire the quote flow.
        # OnAction_GenerateQuote was made Optional control so xlwings can call
        # it with no args (Office ribbon still passes its own IRibbonControl).
        # SetCustomerForTest sets m_Customer directly, bypassing the OnChange
        # callback path which expects an IRibbonControl xlwings can't synthesize.
        ws_dash.activate()
        ws_dash.range("A2").select()
        erp_workbook.macro("ERPv14Ribbon.LoadRowToRibbon")(2)
        erp_workbook.macro("ERPv14Ribbon.SetCustomerForTest")("TEST_CUSTOMER_P2")
        erp_workbook.macro("ERPv14Ribbon.OnAction_GenerateQuote")()

        # Assert — Quotes sheet has a new row
        new_last = ws_quotes.range(f"A{last_row_of_sheet}").end("up").row
        assert new_last > initial_last, (
            f"GenerateQuote did not add a row (before={initial_last}, "
            f"after={new_last}). Check g_TestMode / LoadRowToRibbon wiring."
        )

        # Col 3 = Customer, col 36 = Status per erp-v14-ribbon-callbacks.bas
        customer_cell = ws_quotes.range(f"C{new_last}").value
        status_cell = ws_quotes.range(f"AJ{new_last}").value
        assert customer_cell == "TEST_CUSTOMER_P2", (
            f"Customer column C{new_last} has '{customer_cell}', expected "
            f"'TEST_CUSTOMER_P2'"
        )
        assert status_cell == "PENDING", (
            f"Status column AJ{new_last} has '{status_cell}', expected 'PENDING'"
        )
    finally:
        erp_workbook.macro("ERPv14Ribbon.SetTestMode")(False)


@pytest.mark.skip(
    reason="OnAction_MarkQuoteWin uses InputBox for container quantity — "
    "not mockable via xlwings without deeper refactor (extract quantity "
    "parameter). Defer to P5+."
)
def test_mark_quote_win_promotes_to_active_jobs(erp_workbook):
    # TODO: extract quantity arg out of InputBox into a module parameter
    # so test harness can set it via SetTestModeQty(N) before calling Win.
    pass


@pytest.mark.skip(
    reason="OnAction_RefreshRates closes + reopens the workbook via Python "
    "subprocess — incompatible with the xlwings session that owns the xlsm. "
    "Would need a separate Excel instance + full round-trip."
)
def test_refresh_rates_reopens_workbook(erp_workbook):
    pass
