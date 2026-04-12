"""Unit tests for rate_importer drift prevention helpers.

Covers:
- safe_move: successful move, retry on PermissionError
- drain_drift: removes incoming files already in processed

Tests monkey-patch INCOMING_DIR/PROCESSED_DIR to a tempdir so we never
touch OneDrive.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

# Add repo root to sys.path so Pricing_Engine imports resolve.
import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Pricing_Engine import rate_importer as ri  # noqa: E402


@pytest.fixture
def sandbox_dirs(tmp_path, monkeypatch):
    """Replace INCOMING_DIR and PROCESSED_DIR with tempdir equivalents."""
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()
    monkeypatch.setattr(ri, "INCOMING_DIR", incoming)
    monkeypatch.setattr(ri, "PROCESSED_DIR", processed)
    return incoming, processed


# ---------------------------------------------------------------------------
# drain_drift
# ---------------------------------------------------------------------------
def test_drain_drift_removes_files_that_exist_in_processed(sandbox_dirs):
    incoming, processed = sandbox_dirs
    # Same-name file in both folders → should be drained from incoming
    (incoming / "FAK_20260408.xlsx").write_text("staged")
    (processed / "FAK_20260408.xlsx").write_text("archived")

    removed = ri.drain_drift()

    assert removed == 1
    assert not (incoming / "FAK_20260408.xlsx").exists()
    assert (processed / "FAK_20260408.xlsx").exists()


def test_drain_drift_keeps_files_only_in_incoming(sandbox_dirs):
    incoming, processed = sandbox_dirs
    (incoming / "SCFI_20260411.xlsx").write_text("pending import")

    removed = ri.drain_drift()

    assert removed == 0
    assert (incoming / "SCFI_20260411.xlsx").exists()


def test_drain_drift_returns_zero_when_incoming_empty(sandbox_dirs):
    assert ri.drain_drift() == 0


def test_drain_drift_only_touches_xlsx(sandbox_dirs):
    incoming, processed = sandbox_dirs
    (incoming / "notes.txt").write_text("keep me")
    (processed / "notes.txt").write_text("processed copy")

    ri.drain_drift()

    assert (incoming / "notes.txt").exists(), \
        "drain_drift should only match *.xlsx, not other file types"


# ---------------------------------------------------------------------------
# safe_move
# ---------------------------------------------------------------------------
def test_safe_move_succeeds_on_first_try(tmp_path):
    src = tmp_path / "a.xlsx"
    src.write_text("data")
    dst = tmp_path / "out" / "a.xlsx"
    dst.parent.mkdir()

    assert ri.safe_move(src, dst, retries=1, delay_s=0.0) is True
    assert dst.exists()
    assert not src.exists()


def test_safe_move_retries_then_succeeds(tmp_path, monkeypatch):
    """Simulate first attempt raises PermissionError, second succeeds."""
    src = tmp_path / "b.xlsx"
    src.write_text("data")
    dst = tmp_path / "out" / "b.xlsx"
    dst.parent.mkdir()

    attempts = {"count": 0}
    real_move = shutil.move

    def flaky_move(s, d):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PermissionError("simulated lock")
        return real_move(s, d)

    monkeypatch.setattr(ri.shutil, "move", flaky_move)

    assert ri.safe_move(src, dst, retries=3, delay_s=0.01) is True
    assert attempts["count"] == 2
    assert dst.exists()


def test_safe_move_returns_false_after_all_retries_fail(tmp_path, monkeypatch):
    src = tmp_path / "c.xlsx"
    src.write_text("data")
    dst = tmp_path / "out" / "c.xlsx"
    dst.parent.mkdir()

    def always_fail(s, d):
        raise PermissionError("locked forever")

    monkeypatch.setattr(ri.shutil, "move", always_fail)

    assert ri.safe_move(src, dst, retries=2, delay_s=0.01) is False
    assert src.exists(), "source should remain on failure"
