# -*- coding: utf-8 -*-
"""
test_duckdb_engine.py — Task 1.1.2: FreightDB Engine Tests
=============================================================
Tests all 5 FreightDB methods against real Parquet data.
"""

import sys
import tracemalloc
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.duckdb_engine import FreightDB
from shared.paths import PARQUET_FILE as PARQUET


def get_db() -> FreightDB:
    return FreightDB(PARQUET)


def test_query_rates():
    """query_rates returns DataFrame with expected columns."""
    db = get_db()
    df = db.query_rates(days=90)  # Wider window for guaranteed results
    assert len(df) > 0, "No rates returned"
    for col in ['POL', 'POD', 'Carrier', 'Container_Type', 'Amount']:
        assert col in df.columns, f"Missing column: {col}"
    assert df['Amount'].min() > 0, "Amount should be > 0"
    print(f"  ✓ query_rates: {len(df):,} rows, {df['Carrier'].nunique()} carriers")


def test_query_rates_filtered():
    """query_rates with POL/container filter narrows results."""
    db = get_db()
    df_all = db.query_rates(days=90)
    df_hph = db.query_rates(pol="HPH", container_type="40HQ", days=90)
    assert len(df_hph) <= len(df_all), "Filtered should be <= unfiltered"
    if len(df_hph) > 0:
        assert all(df_hph['POL'].str.upper().str.strip() == 'HPH')
        assert all(df_hph['Container_Type'].str.upper() == '40HQ')
    print(f"  ✓ query_rates filtered: {len(df_hph):,} HPH/40HQ rates")


def test_get_route_median():
    """get_route_median returns a positive float for known route."""
    db = get_db()
    # Use a broad search to find any route with data
    df = db.query_rates(days=90)
    if len(df) == 0:
        print("  ⚠ No data in 90 days, skipping median test")
        return

    # Pick the first available route
    sample = df.iloc[0]
    pol = sample['POL']
    pod = str(sample['POD']).split(',')[0].strip()
    ct = sample['Container_Type']

    median = db.get_route_median(pol, pod, ct, days=90)
    print(f"  ✓ get_route_median({pol} → {pod} / {ct}): ${median:,.0f}")
    assert median > 0, f"Median should be > 0, got {median}"


def test_get_market_envelope():
    """get_market_envelope returns valid p2.5/mean/p97.5 structure."""
    db = get_db()
    df = db.query_rates(days=90)
    if len(df) == 0:
        print("  ⚠ No data, skipping envelope test")
        return

    sample = df.iloc[0]
    pol = sample['POL']
    pod = str(sample['POD']).split(',')[0].strip()
    ct = sample['Container_Type']

    env = db.get_market_envelope(pol, pod, ct, days=90)
    print(f"  ✓ get_market_envelope({pol} → {pod} / {ct}):")
    print(f"    Low: ${env['market_low']:,.0f} | Avg: ${env['market_avg']:,.0f} | High: ${env['market_high']:,.0f}")
    print(f"    Data points: {env['data_points']} | Carriers: {env['carriers']}")

    assert env['data_points'] > 0, "Should have data points"
    assert env['market_low'] <= env['market_avg'] <= env['market_high'], \
        f"Envelope order wrong: {env['market_low']} <= {env['market_avg']} <= {env['market_high']}"
    assert env['carriers'] > 0, "Should have carriers"


def test_get_carrier_list():
    """get_carrier_list returns list of carrier strings."""
    db = get_db()
    carriers = db.get_carrier_list()
    assert isinstance(carriers, list), "Should return list"
    assert len(carriers) > 0, "Should have carriers"
    print(f"  ✓ get_carrier_list: {len(carriers)} carriers — {', '.join(carriers[:10])}")


def test_get_carrier_list_filtered():
    """get_carrier_list with POL filter."""
    db = get_db()
    all_carriers = db.get_carrier_list()
    hph_carriers = db.get_carrier_list(pol="HPH")
    assert len(hph_carriers) <= len(all_carriers)
    print(f"  ✓ get_carrier_list(HPH): {len(hph_carriers)} carriers")


def test_get_rate_stats():
    """get_rate_stats returns combined stats dict."""
    db = get_db()
    df = db.query_rates(days=90)
    if len(df) == 0:
        print("  ⚠ No data, skipping stats test")
        return

    sample = df.iloc[0]
    pol = sample['POL']
    pod = str(sample['POD']).split(',')[0].strip()
    ct = sample['Container_Type']

    stats = db.get_rate_stats(pol, pod, ct, days=90)
    print(f"  ✓ get_rate_stats({pol} → {pod} / {ct}):")
    print(f"    Min: ${stats['min']:,.0f} | Max: ${stats['max']:,.0f}")
    print(f"    Avg: ${stats['avg']:,.0f} | Std: ${stats.get('std_dev', 0):,.2f}")
    print(f"    Data points: {stats['data_points']}")

    assert stats['data_points'] > 0
    assert stats['min'] <= stats['avg'] <= stats['max']


def test_memory_usage():
    """FreightDB queries stay under 200MB memory."""
    tracemalloc.start()

    db = get_db()
    db.query_rates(days=90)
    db.get_market_envelope("HPH", "LAX", "40HQ", days=90)
    db.get_rate_stats("HPH", "LAX", "40HQ", days=90)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    print(f"  ✓ Memory: current={current / (1024*1024):.1f}MB, peak={peak_mb:.1f}MB")
    assert peak_mb < 200, f"Peak memory {peak_mb:.1f}MB exceeds 200MB limit"
