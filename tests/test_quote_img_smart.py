"""test_quote_img_smart.py — Pytest coverage for QuoteImage_CollectLatestGroup (Python reimplementation).

Logic under test (VBA source: erp-v14-ribbon-callbacks.bas ~line 3373):
  Walk from row 5 downward. Match if:
    - refGid is non-empty AND gid == refGid  (group_id wins over customer+date)
    - OR cust == refCust AND dt == refDate   (same customer + same date)
  Stop at first non-match. Return 1-indexed row numbers (5, 6, 7, ...).

Input: list of dicts with keys quote_id / date / customer / group_id.
  Caller trims to row 5+, so list index 0 = sheet row 5.
  date values are date objects or strings in yyyy-mm-dd format.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Python reimplementation of VBA QuoteImage_CollectLatestGroup
# ---------------------------------------------------------------------------

def collect_latest_group(rows: list[dict]) -> list[int]:
    """Python port of QuoteImage_CollectLatestGroup (erp-v14-ribbon-callbacks.bas ~3373).

    Parameters
    ----------
    rows : list[dict]
        Sheet rows as dicts. Keys: quote_id, date, customer, group_id.
        Caller passes rows trimmed to row 5+, so index 0 = sheet row 5.
        Empty quote_id (falsy) ends the walk.

    Returns
    -------
    list[int]
        1-indexed sheet row numbers (5, 6, 7, ...) for rows that belong to
        the latest quote group.
    """
    if not rows:
        return []

    # Row 5 reference (index 0 in the trimmed list)
    ref = rows[0]
    ref_cust = ref["customer"].upper() if ref["customer"] else ""
    ref_date = _norm_date(ref["date"])
    ref_gid = ref["group_id"].strip() if ref["group_id"] else ""

    # Empty quote_id at row 5 → no group
    if not ref.get("quote_id", "").strip():
        return []

    collected: list[int] = []
    r = 5  # sheet row number starts at 5

    for row in rows:
        qid = row.get("quote_id", "") or ""
        if not qid.strip():
            break  # empty quote_id → stop walk

        cust = (row.get("customer") or "").upper()
        dt = _norm_date(row.get("date"))
        gid = (row.get("group_id") or "").strip()

        match = False
        if ref_gid != "" and gid == ref_gid:
            match = True
        elif cust == ref_cust and dt == ref_date:
            match = True

        if not match:
            break

        collected.append(r)
        r += 1

    return collected


def _norm_date(val) -> str:
    """Coerce val to yyyy-mm-dd string for comparison."""
    if val is None:
        return ""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)


# ---------------------------------------------------------------------------
# Fixtures — fake Quotes sheet data
# ---------------------------------------------------------------------------

@pytest.fixture
def row(qid, date, customer, group_id):
    """Single-row factory for composing test cases."""
    return dict(quote_id=qid, date=date, customer=customer, group_id=group_id)


def make_rows(*tuples):
    """Build list of dicts from (qid, date, customer, group_id) tuples.

    date arg accepts string 'yyyy-mm-dd' or date object.
    """
    rows = []
    for qid, date, customer, group_id in tuples:
        rows.append(dict(quote_id=qid, date=date, customer=customer, group_id=group_id))
    return rows


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCollectLatestGroup:
    """Happy-path and edge-case coverage for collect_latest_group."""

    def test_happy_single_quote(self):
        """1 quote at row 5 → returns [5]."""
        rows = make_rows(("Q001", "2026-04-28", "NAFOODS", "QG-001"))
        assert collect_latest_group(rows) == [5]

    def test_happy_group_3_rows(self):
        """3 quotes same customer + same day + same group_id → returns [5, 6, 7]."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", "QG-001"),
            ("Q002", "2026-04-28", "NAFOODS", "QG-001"),
            ("Q003", "2026-04-28", "NAFOODS", "QG-001"),
        )
        assert collect_latest_group(rows) == [5, 6, 7]

    def test_stop_at_different_customer(self):
        """Row 5,6 same customer+date; row 7 different customer → returns [5, 6]."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", ""),
            ("Q002", "2026-04-28", "NAFOODS", ""),
            ("Q003", "2026-04-28", "SIRONE", ""),
        )
        assert collect_latest_group(rows) == [5, 6]

    def test_stop_at_different_date(self):
        """Row 5,6 same customer+date; row 7 different date → returns [5, 6]."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", ""),
            ("Q002", "2026-04-28", "NAFOODS", ""),
            ("Q003", "2026-04-27", "NAFOODS", ""),
        )
        assert collect_latest_group(rows) == [5, 6]

    def test_prefer_group_id_over_customer(self):
        """group_id match wins; customer+date fallback only used when group_id empty.

        Per VBA line 3399-3403: when refGid non-empty but gid differs,
        the ElseIf still tries customer+date match. So rows sharing the same
        customer+date are included even if group_id differs — group_id does NOT
        create an exclusive filter.

        Row 5: group_id=QG-X, customer=NAFOODS, date=2026-04-28
        Row 6: group_id=QG-Y, same customer+date → included (fallback match)
        Row 7: group_id=QG-X, same customer+date → included (group match)
        """
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", "QG-X"),
            ("Q002", "2026-04-28", "NAFOODS", "QG-Y"),
            ("Q003", "2026-04-28", "NAFOODS", "QG-X"),
        )
        # All three rows share customer+date → all included (group_id fallback)
        assert collect_latest_group(rows) == [5, 6, 7]

    def test_empty_sheet(self):
        """No quotes (empty list) → returns []."""
        assert collect_latest_group([]) == []

    def test_single_match_then_gap(self):
        """Row 5 match; row 6 empty quote_id → stops at [5]."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", ""),
            ("", "2026-04-28", "NAFOODS", ""),
            ("Q003", "2026-04-28", "NAFOODS", ""),
        )
        assert collect_latest_group(rows) == [5]

    def test_group_id_empty_falls_back_to_customer_date(self):
        """Row 5 group_id empty → match by customer+date, not by group_id."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", ""),
            ("Q002", "2026-04-28", "NAFOODS", ""),
            ("Q003", "2026-04-28", "SIRONE", ""),
        )
        assert collect_latest_group(rows) == [5, 6]

    def test_mixed_group_then_customer_match(self):
        """Rows 5-6 same group_id; row 7 same customer+date but no group_id → row 7 included."""
        rows = make_rows(
            ("Q001", "2026-04-28", "NAFOODS", "QG-001"),
            ("Q002", "2026-04-28", "NAFOODS", "QG-001"),
            ("Q003", "2026-04-28", "NAFOODS", ""),
        )
        # Row 7 has empty group_id so falls to customer+date match
        assert collect_latest_group(rows) == [5, 6, 7]

    def test_date_object_coercion(self):
        """date stored as Python date object → still matches correctly."""
        from datetime import date
        rows = [
            dict(quote_id="Q001", date=date(2026, 4, 28), customer="NAFOODS", group_id=""),
            dict(quote_id="Q002", date=date(2026, 4, 28), customer="NAFOODS", group_id=""),
        ]
        assert collect_latest_group(rows) == [5, 6]

    def test_row_5_empty_quote_id_returns_empty(self):
        """Row 5 quote_id is empty string → returns [], no crash."""
        rows = make_rows(("", "2026-04-28", "NAFOODS", ""))
        assert collect_latest_group(rows) == []
