"""
test_queue_store.py — Phase 01 unit tests for SQLite queue store.

Run from repo root:
    python -m pytest email_engine/tests/test_queue_store.py -v
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from email_engine import queue_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path) -> str:
    """Isolated SQLite path per test, initialized via init_db."""
    db = tmp_path / "queue_test.db"
    queue_store.init_db(str(db))
    return str(db)


def _make_emails(n: int, *, batch_id: str = "B1",
                 tier: str = "WARM_A", priority: int = 50):
    return [
        {
            "cnee_email": f"user{i}@example.com",
            "subject": f"Subject {i}",
            "html_body": f"<p>Body {i}</p>",
            "tier": tier,
            "priority_score": priority,
            "campaign_id": "CAND",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_init_creates_schema_with_wal(db_path):
    """init_db creates table + WAL mode + indexes."""
    with sqlite3.connect(db_path) as conn:
        # Table exists
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='email_queue'"
        ).fetchone()
        assert row is not None

        # WAL mode active
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

        # Indexes present
        idx_names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        assert "idx_queue_status_priority" in idx_names
        assert "idx_queue_batch" in idx_names


def test_enqueue_batch_inserts_200_rows(db_path):
    """200 rows insert, dedup constraint, perf budget < 500ms."""
    emails = _make_emails(200, batch_id="B1")
    t0 = time.perf_counter()
    n = queue_store.enqueue_batch("B1", emails)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert n == 200
    # Re-enqueue same batch → all duplicates → 0 inserted
    n2 = queue_store.enqueue_batch("B1", emails)
    assert n2 == 0

    # Different batch_id → all insert
    n3 = queue_store.enqueue_batch("B2", emails)
    assert n3 == 200

    assert elapsed_ms < 500, f"enqueue 200 rows took {elapsed_ms:.0f}ms (>500ms)"


def test_enqueue_handles_cc_list_and_meta_dict(db_path):
    """cc as list serializes to ;-separated; meta_json dict → JSON string."""
    emails = [{
        "cnee_email": "vip@x.com",
        "subject": "S",
        "html_body": "<p>B</p>",
        "cc": ["a@x.com", "b@x.com"],
        "meta_json": {"template_id": "T1", "delta_pct": -3.2},
    }]
    queue_store.enqueue_batch("B1", emails)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT cc, meta_json FROM email_queue").fetchone()

    assert row[0] == "a@x.com;b@x.com"
    assert '"template_id"' in row[1]
    assert '"delta_pct"' in row[1]


def test_pop_one_priority_vip_before_warm_b(db_path):
    """VIP popped before WARM_B regardless of insert order."""
    queue_store.enqueue_batch("B1", [
        {"cnee_email": "warm@x.com", "subject": "low", "html_body": "x",
         "tier": "WARM_B", "priority_score": 90},
        {"cnee_email": "vip@x.com", "subject": "high", "html_body": "x",
         "tier": "VIP", "priority_score": 10},
        {"cnee_email": "hot@x.com", "subject": "mid", "html_body": "x",
         "tier": "HOT", "priority_score": 50},
    ])

    j1 = queue_store.pop_one("W1")
    j2 = queue_store.pop_one("W1")
    j3 = queue_store.pop_one("W1")
    j4 = queue_store.pop_one("W1")

    assert j1["cnee_email"] == "vip@x.com"
    assert j2["cnee_email"] == "hot@x.com"
    assert j3["cnee_email"] == "warm@x.com"
    assert j4 is None  # empty


def test_pop_one_priority_score_within_same_tier(db_path):
    """Within WARM_A, higher priority_score popped first."""
    queue_store.enqueue_batch("B1", [
        {"cnee_email": "low@x.com", "subject": "s", "html_body": "x",
         "tier": "WARM_A", "priority_score": 10},
        {"cnee_email": "high@x.com", "subject": "s", "html_body": "x",
         "tier": "WARM_A", "priority_score": 99},
        {"cnee_email": "mid@x.com", "subject": "s", "html_body": "x",
         "tier": "WARM_A", "priority_score": 50},
    ])
    assert queue_store.pop_one("W1")["cnee_email"] == "high@x.com"
    assert queue_store.pop_one("W1")["cnee_email"] == "mid@x.com"
    assert queue_store.pop_one("W1")["cnee_email"] == "low@x.com"


def test_pop_one_marks_sending_and_records_worker(db_path):
    """pop_one transitions row to status='sending' + sets picked_at + worker_id."""
    queue_store.enqueue_batch("B1", _make_emails(1))
    job = queue_store.pop_one("worker-A")
    assert job is not None
    assert job["status"] == "sending"
    assert job["worker_id"] == "worker-A"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, worker_id, picked_at FROM email_queue WHERE id=?",
            (job["id"],),
        ).fetchone()
    assert row[0] == "sending"
    assert row[1] == "worker-A"
    assert row[2] is not None


def test_mark_sent_transition(db_path):
    """mark_sent → status='sent', sent_at set."""
    queue_store.enqueue_batch("B1", _make_emails(1))
    job = queue_store.pop_one("W1")
    queue_store.mark_sent(job["id"])

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, sent_at FROM email_queue WHERE id=?", (job["id"],)
        ).fetchone()
    assert row[0] == "sent"
    assert row[1] is not None


def test_mark_failed_retry_increments_attempts(db_path):
    """mark_failed when attempts < max → status back to 'pending', attempts++."""
    queue_store.enqueue_batch("B1", _make_emails(1))
    job = queue_store.pop_one("W1")
    queue_store.mark_failed(job["id"], "smtp 421")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, attempts, error_message FROM email_queue WHERE id=?",
            (job["id"],),
        ).fetchone()
    assert row[0] == "pending"
    assert row[1] == 1
    assert "smtp 421" in row[2]

    # Job should be poppable again
    job2 = queue_store.pop_one("W2")
    assert job2 is not None
    assert job2["id"] == job["id"]
    assert job2["attempts"] == 1


def test_mark_failed_permanent_after_max_attempts(db_path):
    """After max_attempts (default 3) failures → status='failed' permanent."""
    queue_store.enqueue_batch("B1", _make_emails(1))

    for expected_attempts in (1, 2, 3):
        job = queue_store.pop_one("W1")
        assert job is not None, f"job vanished at attempt {expected_attempts}"
        queue_store.mark_failed(job["id"], f"err {expected_attempts}")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, attempts FROM email_queue WHERE id=?", (job["id"],)
        ).fetchone()
    assert row[0] == "failed"
    assert row[1] == 3
    # Should not be popped again
    assert queue_store.pop_one("W1") is None


def test_reset_stuck_recovers_old_sending_jobs(db_path):
    """Jobs in status='sending' older than N min → reset to 'pending'."""
    queue_store.enqueue_batch("B1", _make_emails(2))
    job1 = queue_store.pop_one("W1")
    job2 = queue_store.pop_one("W1")
    assert job1 and job2

    # Backdate job1's picked_at to 11 min ago
    old_time = (datetime.utcnow() - timedelta(minutes=11)) \
        .strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE email_queue SET picked_at=? WHERE id=?",
                     (old_time, job1["id"]))
        conn.commit()

    n = queue_store.reset_stuck(older_than_min=10)
    assert n == 1, f"expected 1 reset, got {n}"

    with sqlite3.connect(db_path) as conn:
        statuses = dict(conn.execute(
            "SELECT id, status FROM email_queue"
        ).fetchall())
    assert statuses[job1["id"]] == "pending"
    assert statuses[job2["id"]] == "sending"  # still fresh


def test_kill_switch_detection(tmp_path, monkeypatch):
    """kill_switch_active() reflects file presence."""
    flag = tmp_path / "KILL_SWITCH.flag"
    monkeypatch.setattr(queue_store, "KILL_SWITCH_PATH", str(flag))

    assert queue_store.kill_switch_active() is False
    flag.write_text("stop")
    assert queue_store.kill_switch_active() is True

    # pop_one returns None when active
    queue_store.init_db(str(tmp_path / "qq.db"))
    queue_store.enqueue_batch("B", _make_emails(1))
    assert queue_store.pop_one("W1") is None

    flag.unlink()
    assert queue_store.kill_switch_active() is False
    # And now we can pop
    job = queue_store.pop_one("W1")
    assert job is not None


def test_get_batch_status_aggregates(db_path):
    """get_batch_status returns total/pending/sending/sent/failed counts."""
    queue_store.enqueue_batch("BX", _make_emails(5, batch_id="BX"))

    j = queue_store.pop_one("W1")
    queue_store.mark_sent(j["id"])
    j = queue_store.pop_one("W1")
    # leave this one as sending (don't mark)
    j = queue_store.pop_one("W1")
    # Force fail past max to permanent
    for _ in range(3):
        queue_store.mark_failed(j["id"], "boom")
        nxt = queue_store.pop_one("W1")
        if nxt and nxt["id"] == j["id"]:
            j = nxt

    status = queue_store.get_batch_status("BX")
    assert status["total"] == 5
    assert status["batch_id"] == "BX"
    assert status["sent"] >= 1
    assert status["failed"] >= 1
    assert "rate_per_min" in status
    assert "eta_finish" in status
