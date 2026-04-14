"""tests/test_fast_id.py — Unit tests for ERP/jobs/fast_id.py (Feature 4).

All tests are pure Python — no Excel I/O, no OneDrive access.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ERP.jobs.fast_id import normalize_fast_id  # noqa: E402


# ===========================================================================
# normalize_fast_id — happy path
# ===========================================================================

class TestNormalizeHappyPath:
    def test_canonical_se(self):
        assert normalize_fast_id("SE2603/0266") == "SE2603/0266"

    def test_strip_whitespace(self):
        assert normalize_fast_id("  SE2603/0266  ") == "SE2603/0266"

    def test_lowercase_converted(self):
        assert normalize_fast_id("se2603/0266") == "SE2603/0266"

    def test_pads_seq_to_4_digits(self):
        """Sequence '266' padded to '0266'."""
        assert normalize_fast_id("SE2603/266") == "SE2603/0266"

    def test_pads_seq_to_4_digits_single(self):
        assert normalize_fast_id("SE2603/1") == "SE2603/0001"

    def test_seq_already_4_digits_unchanged(self):
        assert normalize_fast_id("NF2604/1200") == "NF2604/1200"

    def test_seq_more_than_4_digits_preserved(self):
        """5-digit sequence should not be truncated."""
        assert normalize_fast_id("SE2603/12345") == "SE2603/12345"

    def test_3_letter_prefix(self):
        assert normalize_fast_id("ARB2603/0001") == "ARB2603/0001"

    def test_4_letter_prefix(self):
        assert normalize_fast_id("NFVN2603/0010") == "NFVN2603/0010"

    def test_mixed_case_with_spaces(self):
        assert normalize_fast_id(" se2603/266 ") == "SE2603/0266"


# ===========================================================================
# normalize_fast_id — error cases
# ===========================================================================

class TestNormalizeErrors:
    def test_missing_slash(self):
        with pytest.raises(ValueError, match="missing '/'"):
            normalize_fast_id("XX123")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            normalize_fast_id("")

    def test_none_input(self):
        with pytest.raises(ValueError):
            normalize_fast_id(None)  # type: ignore[arg-type]

    def test_prefix_too_short(self):
        """Single-letter prefix is invalid (need 2–4)."""
        with pytest.raises(ValueError):
            normalize_fast_id("X2603/0266")

    def test_prefix_too_long(self):
        """5-letter prefix is invalid."""
        with pytest.raises(ValueError):
            normalize_fast_id("ABCDE2603/0266")

    def test_invalid_month_13(self):
        with pytest.raises(ValueError, match="month"):
            normalize_fast_id("SE2613/0100")

    def test_invalid_month_00(self):
        with pytest.raises(ValueError, match="month"):
            normalize_fast_id("SE2600/0100")

    def test_seq_non_digit(self):
        with pytest.raises(ValueError, match="digits only"):
            normalize_fast_id("SE2603/ABCD")

    def test_format_hint_in_error(self):
        """Error message should give an example format."""
        with pytest.raises(ValueError, match="SE2603"):
            normalize_fast_id("XX/123")


# ===========================================================================
# Duplicate detection logic (standalone, no Excel)
# ===========================================================================

class TestDuplicateDetection:
    """Test the duplicate-detection algorithm used in validate_active_jobs.

    We replicate the logic here to keep tests pure-Python (no xlsm needed).
    """

    def _run_detection(self, fast_ids: list[str | None]) -> list[tuple]:
        """Simulate the seen-dict loop from validate_active_jobs."""
        seen: dict[str, int] = {}
        duplicates = []
        for row_idx, raw in enumerate(fast_ids, start=8):
            if not raw:
                continue
            try:
                norm = normalize_fast_id(str(raw))
            except ValueError:
                continue
            if norm in seen:
                duplicates.append((seen[norm], row_idx, norm))
            else:
                seen[norm] = row_idx
        return duplicates

    def test_no_duplicates(self):
        ids = ["SE2603/0001", "SE2603/0002", "NF2604/0001"]
        assert self._run_detection(ids) == []

    def test_exact_duplicate(self):
        ids = ["SE2603/0001", "SE2603/0002", "SE2603/0001"]
        dups = self._run_detection(ids)
        assert len(dups) == 1
        first_row, dup_row, val = dups[0]
        assert val == "SE2603/0001"
        assert first_row == 8
        assert dup_row == 10  # row 8,9,10 → third entry

    def test_duplicate_after_normalization(self):
        """'se2603/266' and 'SE2603/0266' are the same after normalize."""
        ids = ["SE2603/0266", "se2603/266"]
        dups = self._run_detection(ids)
        assert len(dups) == 1
        assert dups[0][2] == "SE2603/0266"

    def test_none_skipped(self):
        ids = [None, "SE2603/0001", None]
        assert self._run_detection(ids) == []

    def test_invalid_skipped_in_duplicate_check(self):
        """Invalid IDs are skipped by duplicate detector."""
        ids = ["XX/123", "SE2603/0001", "XX/123"]
        dups = self._run_detection(ids)
        assert dups == []

    def test_triple_duplicate_reports_second_and_third(self):
        ids = ["SE2603/0001", "SE2603/0001", "SE2603/0001"]
        dups = self._run_detection(ids)
        # First dup = row8 vs row9, second dup = row8 vs row10
        assert len(dups) == 2
