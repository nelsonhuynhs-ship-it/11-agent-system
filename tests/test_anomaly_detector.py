# -*- coding: utf-8 -*-
"""
test_anomaly_detector.py — Task 2.1.1: Anomaly Detection Tests
================================================================
Tests AnomalyDetector: severity classification, bidirectional detection,
edge cases, batch processing, and route context.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.anomaly_detector import AnomalyDetector, AnomalyResult
from db.duckdb_engine import FreightDB
from shared.paths import PARQUET_FILE as PARQUET


def _make_detector_mock(median: float = 2000.0) -> AnomalyDetector:
    """Create detector with mocked FreightDB for unit tests."""
    mock_db = MagicMock(spec=FreightDB)
    mock_db.get_route_median.return_value = median
    mock_db.get_market_envelope.return_value = {
        "market_low": median * 0.8,
        "market_avg": median,
        "market_high": median * 1.2,
        "data_points": 100,
        "carriers": 5,
        "median": median,
    }
    return AnomalyDetector(mock_db)


def _make_detector_real() -> AnomalyDetector:
    """Create detector with real FreightDB for integration tests."""
    return AnomalyDetector(FreightDB(PARQUET))


def test_normal_rate():
    """Rate within 15% of median → normal."""
    d = _make_detector_mock(median=2000.0)
    r = d.check_rate("CMA", "HPH", "LAX", "40HQ", 2100.0)  # +5%
    assert r.is_anomaly is False
    assert r.severity == "normal"
    assert abs(r.deviation_pct - 5.0) < 0.1
    assert "✅" in r.message
    print(f"  ✓ normal: $2,100 vs median $2,000 = {r.deviation_pct:+.1f}% → {r.severity}")


def test_warning_above():
    """Rate 20% above median → warning."""
    d = _make_detector_mock(median=2000.0)
    r = d.check_rate("CMA", "HPH", "LAX", "40HQ", 2400.0)  # +20%
    assert r.is_anomaly is True
    assert r.severity == "warning"
    assert abs(r.deviation_pct - 20.0) < 0.1
    assert "⚠️" in r.message
    print(f"  ✓ warning (above): $2,400 vs median $2,000 = {r.deviation_pct:+.1f}% → {r.severity}")


def test_critical_above():
    """Rate 35% above median → critical."""
    d = _make_detector_mock(median=2000.0)
    r = d.check_rate("CMA", "HPH", "LAX", "40HQ", 2700.0)  # +35%
    assert r.is_anomaly is True
    assert r.severity == "critical"
    assert abs(r.deviation_pct - 35.0) < 0.1
    assert "🚨" in r.message
    assert "REVIEW" in r.message
    print(f"  ✓ critical (above): $2,700 vs median $2,000 = {r.deviation_pct:+.1f}% → {r.severity}")


def test_warning_below():
    """Rate 25% BELOW median → warning (bidirectional)."""
    d = _make_detector_mock(median=2000.0)
    r = d.check_rate("ONE", "HPH", "LAX", "40HQ", 1500.0)  # -25%
    assert r.is_anomaly is True
    assert r.severity == "warning"
    assert r.deviation_pct < 0, "Below median should be negative"
    assert abs(r.deviation_pct - (-25.0)) < 0.1
    print(f"  ✓ warning (below): $1,500 vs median $2,000 = {r.deviation_pct:+.1f}% → {r.severity}")


def test_critical_below():
    """Rate 40% BELOW median → critical (bidirectional)."""
    d = _make_detector_mock(median=2000.0)
    r = d.check_rate("ZIM", "HPH", "LAX", "40HQ", 1200.0)  # -40%
    assert r.is_anomaly is True
    assert r.severity == "critical"
    assert r.deviation_pct < 0
    print(f"  ✓ critical (below): $1,200 vs median $2,000 = {r.deviation_pct:+.1f}% → {r.severity}")


def test_no_data_route():
    """Zero median (no data) → not anomaly, insufficient data message."""
    d = _make_detector_mock(median=0.0)
    r = d.check_rate("CMA", "HPH", "XXXX", "40HQ", 1500.0)
    assert r.is_anomaly is False
    assert r.severity == "normal"
    assert "insufficient data" in r.message.lower()
    print(f"  ✓ no data: severity={r.severity}, message='{r.message[:60]}...'")


def test_batch_check():
    """Batch of 5 mixed rates → correct anomaly count."""
    d = _make_detector_mock(median=2000.0)
    quotes = [
        {"carrier": "CMA", "pol": "HPH", "pod": "LAX", "container_type": "40HQ", "quoted_rate": 2100.0},  # normal (+5%)
        {"carrier": "ONE", "pol": "HPH", "pod": "LAX", "container_type": "40HQ", "quoted_rate": 2400.0},  # warning (+20%)
        {"carrier": "ZIM", "pol": "HPH", "pod": "LAX", "container_type": "40HQ", "quoted_rate": 2700.0},  # critical (+35%)
        {"carrier": "MSC", "pol": "HPH", "pod": "LAX", "container_type": "40HQ", "quoted_rate": 1500.0},  # warning (-25%)
        {"carrier": "HPL", "pol": "HPH", "pod": "LAX", "container_type": "40HQ", "quoted_rate": 1950.0},  # normal (-2.5%)
    ]
    results = d.check_batch(quotes)
    assert len(results) == 5
    anomalies = [r for r in results if r.is_anomaly]
    normals = [r for r in results if not r.is_anomaly]
    assert len(anomalies) == 3, f"Expected 3 anomalies, got {len(anomalies)}"
    assert len(normals) == 2, f"Expected 2 normals, got {len(normals)}"

    severities = [r.severity for r in results]
    assert severities == ["normal", "warning", "critical", "warning", "normal"]
    print(f"  ✓ batch: {len(anomalies)} anomalies, {len(normals)} normal from {len(quotes)} quotes")


def test_route_context():
    """get_route_context returns envelope + thresholds."""
    d = _make_detector_real()
    ctx = d.get_route_context("HPH", "LAX", "40HQ", days=90)

    assert "median" in ctx
    assert "envelope" in ctx
    assert "thresholds" in ctx
    assert "carrier_count" in ctx
    assert "data_points" in ctx

    if ctx["median"] > 0:
        assert ctx["thresholds"]["warning_above"] > ctx["median"]
        assert ctx["thresholds"]["warning_below"] < ctx["median"]
        assert ctx["thresholds"]["critical_above"] > ctx["thresholds"]["warning_above"]
        assert ctx["thresholds"]["critical_below"] < ctx["thresholds"]["warning_below"]
        print(f"  ✓ route_context HPH→LAX/40HQ:")
        print(f"    Median: ${ctx['median']:,.0f}")
        print(f"    Warning band: ${ctx['thresholds']['warning_below']:,.0f}–${ctx['thresholds']['warning_above']:,.0f}")
        print(f"    Critical band: ${ctx['thresholds']['critical_below']:,.0f}–${ctx['thresholds']['critical_above']:,.0f}")
        print(f"    Data: {ctx['data_points']} points, {ctx['carrier_count']} carriers")
    else:
        print(f"  ✓ route_context: no data (median=0), structure valid")


def test_batch_performance():
    """Batch of 50 rates completes in < 1 second."""
    d = _make_detector_mock(median=2000.0)
    quotes = [
        {"carrier": "CMA", "pol": "HPH", "pod": f"PORT{i}", "container_type": "40HQ",
         "quoted_rate": 1500 + (i * 50)}
        for i in range(50)
    ]
    start = time.perf_counter()
    results = d.check_batch(quotes)
    elapsed = time.perf_counter() - start

    assert len(results) == 50
    assert elapsed < 1.0, f"Batch took {elapsed:.2f}s, must be < 1s"
    print(f"  ✓ batch performance: 50 rates in {elapsed*1000:.1f}ms")


if __name__ == "__main__":
    print("=" * 60)
    print("  ANOMALY DETECTOR TESTS — Task 2.1.1")
    print("=" * 60)

    tests = [
        test_normal_rate,
        test_warning_above,
        test_critical_above,
        test_warning_below,
        test_critical_below,
        test_no_data_route,
        test_batch_check,
        test_route_context,
        test_batch_performance,
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
