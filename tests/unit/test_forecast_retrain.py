"""Unit tests for forecast_retrain state + trigger logic.

All tests run against a tempdir state file — never touches OneDrive.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Pricing_Engine.forecast_retrain import state as st  # noqa: E402
from Pricing_Engine.forecast_retrain import check_retrain as cr  # noqa: E402


@pytest.fixture
def tmp_state_file(tmp_path):
    return tmp_path / "retrain_state.json"


# -----------------------------------------------------------------------------
# state.load_state / save_state
# -----------------------------------------------------------------------------
def test_load_state_returns_default_when_file_missing(tmp_state_file):
    state = st.load_state(tmp_state_file)
    assert state.imports_since_train == 0
    assert state.last_trained_at is None
    assert state.data_deltas == []


def test_save_and_reload_state_preserves_fields(tmp_state_file):
    s = st.RetrainState(
        last_trained_at="2026-04-01T00:00:00+00:00",
        last_train_parquet_rows=3000,
        imports_since_train=2,
        data_deltas=[
            st.ImportDelta(at="2026-04-02T10:00:00+00:00", rows_added=100, source="FAK"),
        ],
    )
    st.save_state(s, tmp_state_file)

    loaded = st.load_state(tmp_state_file)
    assert loaded.last_train_parquet_rows == 3000
    assert loaded.imports_since_train == 2
    assert len(loaded.data_deltas) == 1
    assert loaded.data_deltas[0].source == "FAK"


def test_load_state_corrupt_file_returns_default(tmp_state_file):
    tmp_state_file.write_text("{ this is not json")
    state = st.load_state(tmp_state_file)
    assert state.imports_since_train == 0  # default


# -----------------------------------------------------------------------------
# bump_import_counter
# -----------------------------------------------------------------------------
def test_bump_increments_counter_and_appends_delta(tmp_state_file):
    s1 = st.bump_import_counter(rows_added=150, source="FAK", path=tmp_state_file)
    s2 = st.bump_import_counter(rows_added=80, source="SCFI", path=tmp_state_file)

    assert s1.imports_since_train == 1
    assert s2.imports_since_train == 2
    assert len(s2.data_deltas) == 2
    assert s2.data_deltas[1].source == "SCFI"
    assert s2.data_deltas[1].rows_added == 80


def test_bump_trims_history_to_last_50(tmp_state_file):
    for i in range(60):
        st.bump_import_counter(rows_added=1, source="FAK", path=tmp_state_file)
    state = st.load_state(tmp_state_file)
    assert len(state.data_deltas) == 50
    assert state.imports_since_train == 60  # counter not trimmed


# -----------------------------------------------------------------------------
# mark_trained
# -----------------------------------------------------------------------------
def test_mark_trained_resets_counters(tmp_state_file):
    st.bump_import_counter(rows_added=200, source="FAK", path=tmp_state_file)
    st.bump_import_counter(rows_added=200, source="FAK", path=tmp_state_file)
    st.mark_trained(parquet_rows=5000, path=tmp_state_file)

    state = st.load_state(tmp_state_file)
    assert state.imports_since_train == 0
    assert state.data_deltas == []
    assert state.last_train_parquet_rows == 5000
    assert state.last_trained_at is not None


# -----------------------------------------------------------------------------
# should_retrain — signal evaluation
# -----------------------------------------------------------------------------
def _state_with(**kw) -> st.RetrainState:
    """Build a state with happy-path defaults that DOES NOT trigger retrain."""
    base = dict(
        last_trained_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        last_train_parquet_rows=3000,
        imports_since_train=0,
        data_deltas=[],
        last_accuracy=st.AccuracySnapshot(week="2026-W14", avg_error_pct=5.0, checked_at="x"),
    )
    base.update(kw)
    return st.RetrainState(**base)


def test_should_retrain_quiet_state_returns_false():
    fire, reason = cr.should_retrain(_state_with())
    assert fire is False
    assert "quiet" in reason


def test_should_retrain_fires_on_import_count():
    fire, reason = cr.should_retrain(_state_with(imports_since_train=3))
    assert fire is True
    assert "imports_since_train" in reason


def test_should_retrain_fires_on_rows_delta():
    deltas = [st.ImportDelta(at="x", rows_added=600, source="FAK")]
    fire, reason = cr.should_retrain(_state_with(data_deltas=deltas))
    assert fire is True
    assert "rows_delta" in reason


def test_should_retrain_fires_on_days_stale():
    stale = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    fire, reason = cr.should_retrain(_state_with(last_trained_at=stale))
    assert fire is True
    assert "days_since_train" in reason


def test_should_retrain_fires_on_accuracy_drift():
    bad = st.AccuracySnapshot(week="2026-W14", avg_error_pct=25.0, checked_at="x")
    fire, reason = cr.should_retrain(_state_with(last_accuracy=bad))
    assert fire is True
    assert "accuracy_error" in reason


def test_should_retrain_fires_on_never_trained():
    fire, reason = cr.should_retrain(_state_with(last_trained_at=None))
    assert fire is True
    assert "never trained" in reason


# -----------------------------------------------------------------------------
# run_check dry-run — must not spawn subprocess
# -----------------------------------------------------------------------------
def test_run_check_dry_run_returns_fire_flag_without_spawning(monkeypatch, tmp_state_file):
    # Redirect STATE_FILE to tmp
    monkeypatch.setattr(st, "STATE_FILE", tmp_state_file)
    monkeypatch.setattr(cr, "load_state", lambda: st.load_state(tmp_state_file))

    # Ensure retrain would fire (never-trained state)
    result = cr.run_check(dry_run=True)
    assert result["fire"] is True
    assert result["dry_run"] is True
    assert result["action"] == "dry-run — skipping actual retrain"
