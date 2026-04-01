# -*- coding: utf-8 -*-
"""
parquet_upgrader.py — Parquet Schema Upgrade Pipeline
=======================================================
Adds normalization columns to Cleaned_Master_History.parquet:
  - surcharge_included, rate_basis, normalized_amount,
    hdl_fee, carrier_commission, raw_amount

Processes in chunks (500K rows) to avoid OOM on 2GB VPS.
Reads via DuckDB, writes via PyArrow/Pandas.

Usage:
    # Dry run (100 rows sample)
    python parquet_upgrader.py --dry-run

    # Full upgrade
    python parquet_upgrader.py

    # Validate output
    python parquet_upgrader.py --validate

    # Custom paths
    python parquet_upgrader.py --input path/to/input.parquet --output path/to/output.parquet
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ── Setup paths ──────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent
_ENGINE_TEST = _THIS_DIR.parent.parent if _THIS_DIR.name == "normalization" else _THIS_DIR.parent
sys.path.insert(0, str(_ENGINE_TEST))

from Pricing_Engine.normalization.hdl_rules import normalize_rate, HDL_RULES

log = logging.getLogger("parquet_upgrader")

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_INPUT = _ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
DEFAULT_OUTPUT = _ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History_normalized.parquet"
CHUNK_SIZE = 500_000  # rows per chunk


def _get_row_count(parquet_path: str) -> int:
    """Get total row count via DuckDB."""
    con = duckdb.connect()
    count = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
    ).fetchone()[0]
    con.close()
    return count


def _read_chunk(parquet_path: str, offset: int, limit: int) -> pd.DataFrame:
    """Read a chunk of rows from Parquet via DuckDB."""
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT *, ROW_NUMBER() OVER () AS _rownum
        FROM read_parquet('{parquet_path}')
        LIMIT {limit} OFFSET {offset}
    """).fetchdf()
    con.close()
    if '_rownum' in df.columns:
        df = df.drop(columns=['_rownum'])
    return df


def _normalize_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Apply normalization to a DataFrame chunk, adding 6 new columns."""
    # Pre-allocate new columns
    n = len(df)
    raw_amounts = df['Amount'].values.copy()
    normalized_amounts = raw_amounts.copy().astype(float)
    hdl_fees = [0.0] * n
    carrier_commissions = [0.0] * n
    rate_bases = [''] * n
    surcharge_included = [False] * n

    carriers = df['Carrier'].astype(str).values
    rate_types = df['Rate_Type'].astype(str).values if 'Rate_Type' in df.columns else ['FAK'] * n
    container_types = df['Container_Type'].astype(str).values if 'Container_Type' in df.columns else ['40HQ'] * n
    pols = df['POL'].astype(str).values if 'POL' in df.columns else ['HCM'] * n
    notes = df['Note'].astype(str).values if 'Note' in df.columns else [''] * n

    unknown_carriers = set()

    for i in range(n):
        carrier = str(carriers[i]).strip().upper()
        rate_type = str(rate_types[i]).strip()
        amount = float(raw_amounts[i]) if pd.notna(raw_amounts[i]) else 0.0
        ct = str(container_types[i]).strip()
        pol = str(pols[i]).strip()
        note = str(notes[i]).strip().upper()

        # Determine rate_basis: check for SOC in Note
        if 'SOC' in note:
            rb = 'SOC'
        elif rate_type.upper() in ('FAK', 'FIX', 'SCFI'):
            rb = rate_type.upper()
        else:
            rb = 'FAK'  # default

        # Check if carrier has HDL rules
        if carrier in HDL_RULES:
            result = normalize_rate(carrier, rate_type, amount, ct, pol)
            normalized_amounts[i] = result.normalized_amount
            hdl_fees[i] = result.hdl_fee
            carrier_commissions[i] = result.carrier_commission
            surcharge_included[i] = result.surcharge_included
        else:
            # Unknown carrier — pass through
            normalized_amounts[i] = amount
            hdl_fees[i] = 0.0
            carrier_commissions[i] = 0.0
            surcharge_included[i] = False
            unknown_carriers.add(carrier)

        rate_bases[i] = rb

    if unknown_carriers:
        log.warning("Unknown carriers (no HDL rules): %s", sorted(unknown_carriers))

    # Add new columns
    df = df.copy()
    df['raw_amount'] = raw_amounts.astype(float)
    df['normalized_amount'] = normalized_amounts
    df['hdl_fee'] = hdl_fees
    df['carrier_commission'] = carrier_commissions
    df['rate_basis'] = rate_bases
    df['surcharge_included'] = surcharge_included

    return df


def run_dry_run(input_path: Path, sample_size: int = 100):
    """Process sample rows and print normalization preview."""
    parquet = input_path.as_posix()
    total = _get_row_count(parquet)
    print(f"\n{'='*70}")
    print(f"  DRY RUN — Sample of {sample_size} rows from {total:,} total")
    print(f"{'='*70}")

    df = _read_chunk(parquet, 0, sample_size)
    result = _normalize_chunk(df)

    # Show summary
    new_cols = ['raw_amount', 'normalized_amount', 'hdl_fee', 'carrier_commission', 'rate_basis', 'surcharge_included']
    print(f"\n  New columns added: {new_cols}")
    print(f"\n  Rate basis distribution:")
    for rb, cnt in result['rate_basis'].value_counts().items():
        print(f"    {rb}: {cnt}")

    print(f"\n  HDL fee distribution:")
    for fee, cnt in result['hdl_fee'].value_counts().head(10).items():
        print(f"    ${fee}: {cnt} rows")

    # Sample rows
    print(f"\n  Sample normalized rows:")
    display_cols = ['Carrier', 'Rate_Type', 'Amount', 'raw_amount', 'normalized_amount', 'hdl_fee', 'rate_basis']
    avail_cols = [c for c in display_cols if c in result.columns]
    print(result[avail_cols].head(20).to_string(index=False))

    # Validation checks on sample
    errors = 0
    null_norm = result['normalized_amount'].isna().sum()
    if null_norm > 0:
        print(f"\n  ⚠ {null_norm} NULL normalized_amount values")
        errors += null_norm

    over = (result['normalized_amount'] > result['raw_amount']).sum()
    if over > 0:
        print(f"\n  ⚠ {over} rows where normalized_amount > raw_amount")
        errors += over

    if errors == 0:
        print(f"\n  ✅ Sample looks correct — 0 errors")
    else:
        print(f"\n  ⚠ {errors} issues found in sample")

    return result


def run_upgrade(input_path: Path, output_path: Path):
    """Full Parquet upgrade with chunked processing."""
    parquet = input_path.as_posix()
    total = _get_row_count(parquet)
    num_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"\n{'='*70}")
    print(f"  PARQUET SCHEMA UPGRADE")
    print(f"  Input:  {input_path} ({input_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  Output: {output_path}")
    print(f"  Rows:   {total:,}")
    print(f"  Chunks: {num_chunks} × {CHUNK_SIZE:,}")
    print(f"{'='*70}")

    # Backup original
    backup_path = input_path.with_suffix('.parquet.bak')
    if not backup_path.exists():
        print(f"\n  Backing up original → {backup_path.name}")
        shutil.copy2(input_path, backup_path)
    else:
        print(f"\n  Backup already exists: {backup_path.name}")

    start_time = time.perf_counter()
    writer = None
    rows_processed = 0
    error_count = 0

    try:
        for chunk_idx in range(num_chunks):
            offset = chunk_idx * CHUNK_SIZE
            chunk_start = time.perf_counter()

            df = _read_chunk(parquet, offset, CHUNK_SIZE)
            if df.empty:
                break

            result = _normalize_chunk(df)

            # Convert to PyArrow table and write
            table = pa.Table.from_pandas(result, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(
                    str(output_path), table.schema,
                    compression='snappy',
                )

            writer.write_table(table)
            rows_processed += len(result)

            chunk_time = time.perf_counter() - chunk_start
            pct = (rows_processed / total) * 100
            print(f"  Chunk {chunk_idx + 1}/{num_chunks}: "
                  f"{len(result):,} rows in {chunk_time:.1f}s "
                  f"({pct:.0f}% complete)")

    finally:
        if writer:
            writer.close()

    total_time = time.perf_counter() - start_time
    output_size = output_path.stat().st_size / 1024 / 1024

    print(f"\n{'='*70}")
    print(f"  UPGRADE COMPLETE")
    print(f"  Rows processed: {rows_processed:,}")
    print(f"  Time:           {total_time:.1f}s")
    print(f"  Output size:    {output_size:.1f} MB")
    print(f"  Speed:          {rows_processed / total_time:,.0f} rows/sec")
    print(f"  Errors:         {error_count}")
    print(f"{'='*70}")

    return rows_processed, total_time, error_count


def run_validate(parquet_path: Path):
    """Validate upgraded Parquet for data integrity."""
    path_str = parquet_path.as_posix()
    con = duckdb.connect()

    print(f"\n{'='*70}")
    print(f"  VALIDATING: {parquet_path.name}")
    print(f"{'='*70}")

    errors = 0

    # 1. Check all 6 new columns exist
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path_str}')").fetchall()
    col_names = [c[0] for c in cols]
    required = ['raw_amount', 'normalized_amount', 'hdl_fee', 'carrier_commission', 'rate_basis', 'surcharge_included']
    for col in required:
        if col not in col_names:
            print(f"  ✗ Missing column: {col}")
            errors += 1
        else:
            print(f"  ✓ Column exists: {col}")

    # 2. No NULL normalized_amount
    null_count = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{path_str}')
        WHERE normalized_amount IS NULL
    """).fetchone()[0]
    if null_count > 0:
        print(f"  ✗ {null_count:,} NULL normalized_amount values")
        errors += 1
    else:
        print(f"  ✓ Zero NULL normalized_amount values")

    # 3. All rate_basis valid
    invalid_rb = con.execute(f"""
        SELECT DISTINCT rate_basis FROM read_parquet('{path_str}')
        WHERE rate_basis NOT IN ('FAK', 'FIX', 'SCFI', 'SOC', 'UNKNOWN')
    """).fetchall()
    if invalid_rb:
        print(f"  ✗ Invalid rate_basis values: {[r[0] for r in invalid_rb]}")
        errors += 1
    else:
        rb_dist = con.execute(f"""
            SELECT rate_basis, COUNT(*) FROM read_parquet('{path_str}')
            GROUP BY rate_basis ORDER BY COUNT(*) DESC
        """).fetchall()
        print(f"  ✓ All rate_basis valid: {dict(rb_dist)}")

    # 4. normalized_amount <= raw_amount
    over = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{path_str}')
        WHERE normalized_amount > raw_amount + 0.01
    """).fetchone()[0]
    if over > 0:
        print(f"  ✗ {over:,} rows where normalized_amount > raw_amount")
        errors += 1
    else:
        print(f"  ✓ All normalized_amount ≤ raw_amount")

    # 5. Row count
    row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path_str}')").fetchone()[0]
    print(f"  ℹ Row count: {row_count:,}")

    # 6. HDL fee stats
    hdl_stats = con.execute(f"""
        SELECT MIN(hdl_fee), AVG(hdl_fee), MAX(hdl_fee),
               SUM(CASE WHEN hdl_fee > 0 THEN 1 ELSE 0 END) as with_hdl
        FROM read_parquet('{path_str}')
    """).fetchone()
    print(f"  ℹ HDL fee: min=${hdl_stats[0]:.0f}, avg=${hdl_stats[1]:.1f}, "
          f"max=${hdl_stats[2]:.0f}, rows_with_hdl={hdl_stats[3]:,}")

    con.close()

    print(f"\n{'='*70}")
    if errors == 0:
        print(f"  ✅ VALIDATION PASSED — 0 errors")
    else:
        print(f"  ✗ VALIDATION FAILED — {errors} errors")
    print(f"{'='*70}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Parquet Schema Upgrade Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process 100 rows sample, print preview, don't write")
    parser.add_argument("--validate", action="store_true",
                        help="Validate an upgraded Parquet file")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Input Parquet path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output Parquet path")
    parser.add_argument("--sample-size", type=int, default=100,
                        help="Number of rows for --dry-run preview")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    if args.dry_run:
        run_dry_run(args.input, args.sample_size)
    elif args.validate:
        target = args.output if args.output.exists() else args.input
        errors = run_validate(target)
        sys.exit(1 if errors > 0 else 0)
    else:
        rows, elapsed, errs = run_upgrade(args.input, args.output)
        print(f"\nRunning validation on output...")
        errors = run_validate(args.output)
        sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
