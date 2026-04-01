# -*- coding: utf-8 -*-
"""
test_duckdb_parquet.py — Task 1.1.1: DuckDB Parquet Validation
================================================================
Validates DuckDB can read Cleaned_Master_History.parquet correctly.
Benchmarks DuckDB vs Pandas for 30-day filtered queries.
"""

import time
import sys
import os
from pathlib import Path

import duckdb
import pandas as pd

# ── Paths ──
BASE_DIR = Path(__file__).parent.parent
PARQUET_FILE = BASE_DIR / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"


def test_duckdb_reads_parquet():
    """DuckDB can load the full Parquet without errors."""
    assert PARQUET_FILE.exists(), f"Parquet not found: {PARQUET_FILE}"

    con = duckdb.connect()
    result = con.execute(f"""
        SELECT COUNT(*) as cnt,
               MIN(Eff) as min_eff,
               MAX(Eff) as max_eff
        FROM read_parquet('{PARQUET_FILE.as_posix()}')
    """).fetchone()

    row_count, min_eff, max_eff = result
    print(f"\n{'='*50}")
    print(f"  Total rows:     {row_count:,}")
    print(f"  Date range:     {min_eff} → {max_eff}")
    print(f"{'='*50}")

    assert row_count > 0, "Parquet has no rows"
    assert min_eff is not None, "MIN(Eff) is NULL"
    assert max_eff is not None, "MAX(Eff) is NULL"
    con.close()


def test_duckdb_carrier_list():
    """DuckDB returns all distinct carriers from Parquet."""
    con = duckdb.connect()
    carriers = con.execute(f"""
        SELECT DISTINCT Carrier
        FROM read_parquet('{PARQUET_FILE.as_posix()}')
        WHERE Carrier IS NOT NULL
        ORDER BY Carrier
    """).fetchall()

    carrier_list = [c[0] for c in carriers]
    print(f"\n  Carriers ({len(carrier_list)}): {', '.join(carrier_list)}")

    assert len(carrier_list) >= 5, f"Expected ≥5 carriers, got {len(carrier_list)}"
    con.close()


def test_duckdb_30day_filter_performance():
    """30-day filtered query completes in < 2 seconds via DuckDB."""
    con = duckdb.connect()

    start = time.perf_counter()
    result = con.execute(f"""
        SELECT Carrier, POL, POD, Container_Type, Amount, Eff, Exp
        FROM read_parquet('{PARQUET_FILE.as_posix()}')
        WHERE Eff >= CURRENT_DATE - INTERVAL 30 DAY
          AND Charge_Name = 'Total Ocean Freight'
          AND Amount > 0
    """).fetchdf()
    duckdb_time = time.perf_counter() - start

    print(f"\n  DuckDB 30-day query: {len(result):,} rows in {duckdb_time:.3f}s")

    assert duckdb_time < 2.0, f"DuckDB query took {duckdb_time:.1f}s (limit: 2s)"
    con.close()
    return duckdb_time, len(result)


def test_pandas_vs_duckdb_benchmark():
    """Benchmark: DuckDB vs Pandas for the same 30-day filter."""
    # Pandas approach (current system)
    start = time.perf_counter()
    df = pd.read_parquet(PARQUET_FILE)
    df['Eff'] = pd.to_datetime(df['Eff'], errors='coerce')
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
    filtered = df[
        (df['Eff'] >= cutoff) &
        (df['Charge_Name'] == 'Total Ocean Freight') &
        (df['Amount'] > 0)
    ]
    pandas_time = time.perf_counter() - start

    # DuckDB approach
    con = duckdb.connect()
    start = time.perf_counter()
    result = con.execute(f"""
        SELECT Carrier, POL, POD, Container_Type, Amount, Eff, Exp
        FROM read_parquet('{PARQUET_FILE.as_posix()}')
        WHERE Eff >= CURRENT_DATE - INTERVAL 30 DAY
          AND Charge_Name = 'Total Ocean Freight'
          AND Amount > 0
    """).fetchdf()
    duckdb_time = time.perf_counter() - start
    con.close()

    speedup = pandas_time / duckdb_time if duckdb_time > 0 else float('inf')

    print(f"\n{'='*50}")
    print(f"  BENCHMARK RESULTS")
    print(f"  Pandas:   {pandas_time:.3f}s ({len(filtered):,} rows)")
    print(f"  DuckDB:   {duckdb_time:.3f}s ({len(result):,} rows)")
    print(f"  Speedup:  {speedup:.1f}x")
    print(f"{'='*50}")


def test_duckdb_column_schema():
    """Verify all expected columns exist in the Parquet."""
    con = duckdb.connect()
    columns = con.execute(f"""
        SELECT column_name, column_type
        FROM (DESCRIBE SELECT * FROM read_parquet('{PARQUET_FILE.as_posix()}'))
    """).fetchall()

    col_names = [c[0] for c in columns]
    print(f"\n  Columns ({len(col_names)}): {', '.join(col_names)}")

    expected = ['POL', 'POD', 'Carrier', 'Container_Type', 'Amount', 'Eff', 'Exp', 'Charge_Name']
    for exp_col in expected:
        assert exp_col in col_names, f"Missing expected column: {exp_col}"

    con.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  DUCKDB PARQUET VALIDATION — Task 1.1.1")
    print("=" * 60)

    test_duckdb_reads_parquet()
    test_duckdb_carrier_list()
    test_duckdb_column_schema()
    test_duckdb_30day_filter_performance()
    test_pandas_vs_duckdb_benchmark()

    print("\n✅ ALL TESTS PASSED")
