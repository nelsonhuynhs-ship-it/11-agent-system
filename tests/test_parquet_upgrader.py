# -*- coding: utf-8 -*-
"""
test_parquet_upgrader.py — Task 1.2.2: Parquet Schema Upgrade Tests
====================================================================
Tests the parquet_upgrader.py pipeline components.
"""

import sys
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from Pricing_Engine.normalization.parquet_upgrader import (
    _normalize_chunk, _get_row_count, run_validate, run_dry_run,
)
from shared.paths import PARQUET_FILE as ORIGINAL

UPGRADED = ORIGINAL.parent / "Cleaned_Master_History_normalized.parquet"


def test_dry_run_produces_correct_sample():
    """Dry run processes sample rows and adds 6 new columns."""
    result = run_dry_run(ORIGINAL, sample_size=50)
    new_cols = ['raw_amount', 'normalized_amount', 'hdl_fee',
                'carrier_commission', 'rate_basis', 'surcharge_included']
    for col in new_cols:
        assert col in result.columns, f"Missing column: {col}"
    assert len(result) == 50, f"Expected 50 rows, got {len(result)}"
    print(f"  ✓ dry_run: 50 rows with 6 new columns")


def test_unknown_carrier_handling():
    """Unknown carriers get normalized_amount == raw_amount, hdl_fee == 0."""
    df = pd.DataFrame({
        'Carrier': ['UNKNOWN_CARRIER', 'HPL'],
        'Rate_Type': ['FAK', 'FAK'],
        'Amount': [1500.0, 1800.0],
        'Container_Type': ['40HQ', '40HQ'],
        'POL': ['HCM', 'HCM'],
        'Note': ['', ''],
    })
    result = _normalize_chunk(df)

    # Unknown carrier
    unknown = result[result['Carrier'] == 'UNKNOWN_CARRIER'].iloc[0]
    assert unknown['normalized_amount'] == 1500.0, "Unknown should passthrough"
    assert unknown['hdl_fee'] == 0.0, "Unknown should have 0 HDL"

    # Known carrier
    known = result[result['Carrier'] == 'HPL'].iloc[0]
    assert known['hdl_fee'] == 20.0, f"HPL FAK HDL should be 20, got {known['hdl_fee']}"
    assert known['normalized_amount'] == 1780.0
    print("  ✓ unknown_carrier: passthrough with 0 HDL")


def test_soc_rate_basis_detection():
    """SOC in Note field sets rate_basis to 'SOC'."""
    df = pd.DataFrame({
        'Carrier': ['ONE', 'ONE'],
        'Rate_Type': ['FAK', 'FAK'],
        'Amount': [1500.0, 1500.0],
        'Container_Type': ['40HQ', '40HQ'],
        'POL': ['HCM', 'HCM'],
        'Note': ['SOC DIRECT', 'TRANSIT VIA YTN'],
    })
    result = _normalize_chunk(df)

    soc_row = result[result['Note'] == 'SOC DIRECT'].iloc[0]
    non_soc = result[result['Note'] == 'TRANSIT VIA YTN'].iloc[0]

    assert soc_row['rate_basis'] == 'SOC', f"SOC note should set rate_basis=SOC, got {soc_row['rate_basis']}"
    assert non_soc['rate_basis'] == 'FAK', f"Non-SOC should be FAK, got {non_soc['rate_basis']}"
    print("  ✓ SOC detection: Note='SOC DIRECT' → rate_basis='SOC'")


def test_normalized_never_exceeds_raw():
    """Normalized amount never exceeds raw amount."""
    df = pd.DataFrame({
        'Carrier': ['HPL', 'CMA', 'ZIM', 'HMM', 'YML'],
        'Rate_Type': ['FAK', 'FAK', 'FAK', 'FIX', 'FIX'],
        'Amount': [1800.0, 1700.0, 2000.0, 2500.0, 2000.0],
        'Container_Type': ['40HQ'] * 5,
        'POL': ['HCM'] * 5,
        'Note': [''] * 5,
    })
    result = _normalize_chunk(df)

    violations = result[result['normalized_amount'] > result['raw_amount']]
    assert len(violations) == 0, \
        f"Found {len(violations)} rows where normalized > raw"
    print("  ✓ normalized_amount ≤ raw_amount: no violations")


def test_row_count_preserved_in_upgrade():
    """Upgraded Parquet has same row count as original."""
    if not UPGRADED.exists():
        print("  ⚠ Upgraded Parquet not found, skipping")
        return

    original_count = _get_row_count(ORIGINAL.as_posix())
    upgraded_count = _get_row_count(UPGRADED.as_posix())

    assert original_count == upgraded_count, \
        f"Row count mismatch: original={original_count:,} vs upgraded={upgraded_count:,}"
    print(f"  ✓ Row count preserved: {original_count:,} == {upgraded_count:,}")


def test_validate_passes_on_upgraded():
    """--validate passes on the upgraded Parquet."""
    if not UPGRADED.exists():
        print("  ⚠ Upgraded Parquet not found, skipping")
        return

    errors = run_validate(UPGRADED)
    assert errors == 0, f"Validation failed with {errors} errors"
    print(f"  ✓ Validation passed: 0 errors")


def test_all_six_columns_in_upgraded():
    """All 6 normalization columns exist in upgraded Parquet."""
    if not UPGRADED.exists():
        print("  ⚠ Upgraded Parquet not found, skipping")
        return

    con = duckdb.connect()
    cols = con.execute(f"""
        DESCRIBE SELECT * FROM read_parquet('{UPGRADED.as_posix()}')
    """).fetchall()
    col_names = [c[0] for c in cols]
    con.close()

    required = ['raw_amount', 'normalized_amount', 'hdl_fee',
                'carrier_commission', 'rate_basis', 'surcharge_included']
    for col in required:
        assert col in col_names, f"Missing: {col}"

    print(f"  ✓ All 6 columns present ({len(col_names)} total)")


if __name__ == "__main__":
    print("=" * 60)
    print("  PARQUET UPGRADER TESTS — Task 1.2.2")
    print("=" * 60)

    tests = [
        test_dry_run_produces_correct_sample,
        test_unknown_carrier_handling,
        test_soc_rate_basis_detection,
        test_normalized_never_exceeds_raw,
        test_row_count_preserved_in_upgrade,
        test_validate_passes_on_upgraded,
        test_all_six_columns_in_upgraded,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
    if failed > 0:
        sys.exit(1)
    print("\n✅ ALL TESTS PASSED")
