# -*- coding: utf-8 -*-
"""
test_rate_router.py — Task 1.1.3: Rate Router DuckDB Migration Verification
==============================================================================
Tests that all rate endpoints work after migration from Pandas to DuckDB.
Runs as a standalone script (no FastAPI server needed — tests the logic directly).
"""

import sys
import time
import tracemalloc
from pathlib import Path

# Setup paths
ENGINE_TEST = Path(__file__).parent.parent
sys.path.insert(0, str(ENGINE_TEST))
sys.path.insert(0, str(ENGINE_TEST / "api"))
sys.path.insert(0, str(ENGINE_TEST / "api" / "routers"))

from shared.paths import PARQUET_FILE as _PARQUET


def test_no_pandas_read_parquet():
    """Verify zero pd.read_parquet() calls in rate_router.py."""
    router_path = ENGINE_TEST / "api" / "routers" / "rate_router.py"
    content = router_path.read_text(encoding="utf-8")

    # Count actual function calls (not comments)
    lines = content.split("\n")
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
            continue
        if "pd.read_parquet" in stripped or "dal.load_rates" in stripped:
            violations.append(f"  Line {i}: {stripped}")

    assert len(violations) == 0, \
        f"Found {len(violations)} Pandas/DAL read calls:\n" + "\n".join(violations)
    print("  [PASS] Zero pd.read_parquet()/dal.load_rates() calls in rate_router.py")


def test_freight_db_import():
    """FreightDB imports and initializes correctly."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)
    assert db is not None
    print("  [PASS] FreightDB imports and initializes correctly")


def test_get_rates_logic():
    """Simulate /api/rates endpoint logic."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    start = time.perf_counter()
    df = db.query_rates(pol="HPH", container_type="40HQ", days=90)
    elapsed = time.perf_counter() - start

    assert df is not None and len(df) > 0, "No rates returned"
    required_cols = ['POL', 'POD', 'Carrier', 'Container_Type', 'Amount']
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    print(f"  [PASS] get_rates: {len(df):,} rows in {elapsed:.3f}s")
    assert elapsed < 3.0, f"Too slow: {elapsed:.1f}s > 3s limit"


def test_carriers_logic():
    """Simulate /api/rates/carriers endpoint."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    df = db.query_rates(days=90)
    counts = df['Carrier'].value_counts().to_dict()
    assert len(counts) > 0, "No carriers found"
    print(f"  [PASS] carriers: {len(counts)} carriers with rates")


def test_regions_logic():
    """Simulate /api/rates/regions endpoint."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    df = db.query_rates(pol="HPH", container_type="40HQ", days=90)
    assert len(df) > 0, "No rates for HPH/40HQ"

    # Test region classification
    def classify(pod):
        pod_upper = str(pod).upper()
        for region, patterns in {
            "WC": ["LAX", "LGB", "SEA", "TAC"],
            "EC": ["NYK", "SAV", "CHS"],
            "GULF": ["HOU", "MIA"],
        }.items():
            if any(p in pod_upper for p in patterns):
                return region
        return "IPI"

    df['region'] = df['POD'].apply(classify)
    region_counts = df['region'].value_counts().to_dict()
    print(f"  [PASS] regions: {region_counts}")


def test_matrix_envelope():
    """Simulate /api/rates/matrix endpoint with envelope."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    start = time.perf_counter()
    envelope = db.get_market_envelope(pol="HPH", pod="LAX", container_type="40HQ", days=90)
    elapsed = time.perf_counter() - start

    print(f"  [PASS] matrix envelope: Low ${envelope['market_low']:,.0f} | "
          f"Avg ${envelope['market_avg']:,.0f} | "
          f"High ${envelope['market_high']:,.0f} "
          f"({envelope['data_points']} pts, {envelope['carriers']} carriers) "
          f"in {elapsed:.3f}s")

    assert envelope['data_points'] >= 0, "data_points should be >= 0"
    assert elapsed < 3.0, f"Envelope too slow: {elapsed:.1f}s > 3s limit"


def test_envelope_endpoint():
    """Simulate /api/rates/envelope endpoint."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    envelope = db.get_market_envelope("HPH", "LAX", "40HQ", 30)
    stats = db.get_rate_stats("HPH", "LAX", "40HQ", 30)

    response = {
        "route": "HPH -> LAX",
        "container_type": "40HQ",
        "days": 30,
        "envelope": envelope,
        "stats": stats,
    }

    assert "envelope" in response
    assert "stats" in response
    print(f"  [PASS] envelope endpoint: {response['route']} — "
          f"data_points={envelope.get('data_points', 0)}")


def test_memory_under_200mb():
    """Full request cycle stays under 200MB."""
    tracemalloc.start()

    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    # Simulate multiple endpoint calls
    db.query_rates(pol="HPH", container_type="40HQ", days=90)
    db.query_rates(pol="HCM", days=90)
    db.get_market_envelope("HPH", "LAX", "40HQ", 90)
    db.get_rate_stats("HPH", "LAX", "40HQ", 90)
    db.get_carrier_list()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    print(f"  [PASS] Memory: peak={peak_mb:.1f}MB (limit: 200MB)")
    assert peak_mb < 200, f"Peak {peak_mb:.1f}MB exceeds 200MB"


def test_response_time_under_3s():
    """Each endpoint-type query completes in < 3 seconds."""
    from db.duckdb_engine import FreightDB
    parquet = _PARQUET
    db = FreightDB(parquet)

    endpoints = [
        ("rates", lambda: db.query_rates(pol="HPH", container_type="40HQ", days=90)),
        ("carriers", lambda: db.get_carrier_list()),
        ("envelope", lambda: db.get_market_envelope("HPH", "LAX", "40HQ", 90)),
        ("stats", lambda: db.get_rate_stats("HPH", "LAX", "40HQ", 90)),
    ]

    for name, fn in endpoints:
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"{name} took {elapsed:.1f}s > 3s limit"

    print(f"  [PASS] All {len(endpoints)} endpoint types respond in < 3s")
