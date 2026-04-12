"""Smoke tests for ERP_Master_v14.xlsm driven by xlwings headless.

These tests open a fresh copy of the workbook per test (via the
`erp_workbook` fixture in conftest.py), then exercise the non-interactive
VBA entry points that do NOT pop up MsgBox dialogs.

Scope covered:
- Workbook opens with expected sheets (Pricing Dry, Pricing Reefer, Quotes, ...)
- Pricing sheets have data rows
- ERPv14Core.AutoExpireOnOpen runs clean
- ERPv14Core.ApplyRateFreshnessColors runs clean
- ERPv14Core.RefreshJobsSummary runs clean
- ERPv14Ribbon.LoadRowToRibbon(row) callable against a data row

Tests that touch MsgBox-laden callbacks (OnAction_GenerateQuote,
OnAction_MarkQuoteWin, OnAction_RefreshRates) live in
test_erp_quote_flow.py and are skipped until the VBA refactor in P2.
"""
from __future__ import annotations

import pytest

# ERP v14 splits the old "Pricing Dashboard" sheet into Dry + Reefer.
# Priority order matters: ERPv14Core.GetActivePricingSheet() picks the
# first existing one in this order.
PRICING_SHEET_CANDIDATES = ("Pricing Dry", "Pricing Reefer")
CORE_SHEETS = {"Quotes", "Active Jobs", "CRM", "Markup_Store", "PUC_Lookup",
               "RateVersions", "ChargeBreakdown"}


def _first_pricing_sheet(wb):
    for name in PRICING_SHEET_CANDIDATES:
        if name in [s.name for s in wb.sheets]:
            return wb.sheets[name]
    pytest.skip(f"No pricing sheet found in {[s.name for s in wb.sheets]}")


# -----------------------------------------------------------------------------
# Structural assertions
# -----------------------------------------------------------------------------
def test_workbook_opens_with_expected_sheets(erp_workbook):
    names = {s.name for s in erp_workbook.sheets}
    # v14 has Dry + Reefer split; at least one must exist.
    assert names & set(PRICING_SHEET_CANDIDATES), (
        f"No pricing sheet found. Expected one of {PRICING_SHEET_CANDIDATES}. "
        f"Got: {sorted(names)}"
    )
    missing = CORE_SHEETS - names
    assert not missing, f"Missing core sheets: {sorted(missing)}. Got: {sorted(names)}"


def test_pricing_dry_has_data_rows(erp_workbook):
    ws = _first_pricing_sheet(erp_workbook)
    last_row = ws.range("A1").end("down").row
    # Memory says ~3,753 rows refreshed from parquet. Conservative floor.
    assert last_row >= 100, (
        f"{ws.name} has only {last_row} rows — refresh likely broken"
    )


def test_pricing_sheet_header_row_present(erp_workbook):
    ws = _first_pricing_sheet(erp_workbook)
    header = ws.range("A1:J1").value
    assert any(h for h in header), f"{ws.name} row 1 is empty — missing headers"


def test_quotes_sheet_accessible(erp_workbook):
    ws = erp_workbook.sheets["Quotes"]
    a1 = ws.range("A1").value
    # Either empty (fresh) or has QuoteID header from a prior GenerateQuote.
    assert a1 is None or str(a1).strip() == "" or str(a1).strip().lower().startswith("quote")


# -----------------------------------------------------------------------------
# VBA entry points — non-interactive (no MsgBox)
# -----------------------------------------------------------------------------
def test_autoexpire_on_open_runs_clean(erp_workbook):
    """AutoExpireOnOpen should scan Quotes and mark past-exp as EXPIRED."""
    erp_workbook.macro("ERPv14Core.AutoExpireOnOpen")()


def test_apply_rate_freshness_colors_runs_clean(erp_workbook):
    """Paints green/yellow/red on Pricing Dashboard based on Exp date."""
    erp_workbook.macro("ERPv14Core.ApplyRateFreshnessColors")()


def test_refresh_jobs_summary_runs_clean(erp_workbook):
    """Aggregates Active Jobs counts into summary cells."""
    erp_workbook.macro("ERPv14Core.RefreshJobsSummary")()


# -----------------------------------------------------------------------------
# Ribbon state loader — read-only, safe to call
# -----------------------------------------------------------------------------
def test_load_row_to_ribbon_does_not_error(erp_workbook):
    """LoadRowToRibbon(row) populates module-level state from a data row."""
    ws = _first_pricing_sheet(erp_workbook)
    ws.activate()
    ws.range("A2").select()
    # Row 2 is the first data row
    erp_workbook.macro("ERPv14Ribbon.LoadRowToRibbon")(2)


# -----------------------------------------------------------------------------
# Sanity regression: module constants / macros reachable
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "macro_name",
    [
        "ERPv14Core.AutoExpireOnOpen",
        "ERPv14Core.ApplyRateFreshnessColors",
        "ERPv14Core.RefreshJobsSummary",
    ],
)
def test_core_macros_reachable(erp_workbook, macro_name):
    """Parameterized smoke: each macro is bound and callable from xlwings."""
    erp_workbook.macro(macro_name)()
