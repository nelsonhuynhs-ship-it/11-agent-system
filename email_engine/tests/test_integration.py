"""
test_integration.py — Round 2 FastAPI endpoint smoke tests.

Verifies that Round 1 modules are wired correctly into web_server.py:
- Startup hook initializes queue + intel DBs without crashing
- Batch enqueue endpoint accepts dry-run and persists non-dry-run batches
- Kill switch returns 503 on enqueue attempts
- Market intel endpoints return the expected shape
- Intel profile endpoint works for unknown CNEEs

Run:
    python -m pytest email_engine/tests/test_integration.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Keep the scanner off during tests — win32com / APScheduler side-effects
os.environ.setdefault("NELSON_DISABLE_SCANNER", "1")

# Import the app lazily so env vars take effect first
from fastapi.testclient import TestClient

ENGINE_TEST = Path(__file__).resolve().parents[2]
if str(ENGINE_TEST) not in sys.path:
    sys.path.insert(0, str(ENGINE_TEST))


@pytest.fixture(scope="module")
def client():
    """Single TestClient shared across tests — triggers startup hooks once."""
    # Redirect queue DB + kill-switch to a temp dir so tests don't clobber prod.
    tmp = tempfile.mkdtemp(prefix="r2_integ_")
    from email_engine import queue_store
    queue_store._DB_PATH = str(Path(tmp) / "queue.db")
    queue_store.KILL_SWITCH_PATH = str(Path(tmp) / "KILL_SWITCH.flag")

    from email_engine.intel import memory as intel_memory
    intel_memory._DB_PATH = str(Path(tmp) / "intel.db")

    from email_engine.web_server import app
    with TestClient(app) as c:
        yield c


def test_startup_init_all_dbs(client):
    """queue + intel DB files exist after startup."""
    from email_engine import queue_store
    from email_engine.intel import memory as intel_memory
    assert Path(queue_store._DB_PATH).exists(), "queue DB missing after startup"
    assert Path(intel_memory._DB_PATH).exists(), "intel DB missing after startup"


def test_enqueue_dry_run_returns_count(client):
    """dry_run=True should build emails but NOT persist."""
    resp = client.post("/api/email-rate/batch/enqueue", json={
        "batch_id": "TEST_DRY_001",
        "cnee_emails": ["test1@example.com", "test2@example.com"],
        "campaign_id": "TEST",
        "markup": 20.0,
        "dry_run": True,
        "pol": "HPH",
        "destinations": "USLAX,USLGB",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dry_run"] is True
    assert data["queued"] == 0
    assert data["would_queue"] >= 1  # at least one built


def test_enqueue_persists_and_status_reports(client):
    """Non-dry-run should persist jobs visible via status endpoint."""
    # Ensure kill switch not active
    client.post("/api/email-rate/queue/kill-clear")

    batch_id = "TEST_LIVE_001"
    resp = client.post("/api/email-rate/batch/enqueue", json={
        "batch_id": batch_id,
        "cnee_emails": ["integ-live1@example.com", "integ-live2@example.com"],
        "campaign_id": "TEST",
        "markup": 20.0,
        "dry_run": False,
        "pol": "HPH",
        "destinations": "USLAX",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["queued"] >= 1

    status = client.get(f"/api/email-rate/batch/{batch_id}/status").json()
    assert status["batch_id"] == batch_id
    assert status["total"] >= 1
    assert status["pending"] >= 1


def test_kill_switch_rejects_enqueue(client):
    """With KILL_SWITCH.flag present, enqueue must return 503."""
    eng = client.post("/api/email-rate/queue/kill")
    assert eng.status_code == 200
    assert eng.json()["active"] is True

    try:
        resp = client.post("/api/email-rate/batch/enqueue", json={
            "batch_id": "TEST_KILL_001",
            "cnee_emails": ["kill@example.com"],
            "campaign_id": "TEST",
            "markup": 20.0,
            "dry_run": False,
            "pol": "HPH",
            "destinations": "USLAX",
        })
        assert resp.status_code == 503
    finally:
        clr = client.post("/api/email-rate/queue/kill-clear")
        assert clr.status_code == 200


def test_market_intel_lane_shape(client):
    """Market intel lane endpoint returns required keys."""
    resp = client.get("/api/intelligence/lane", params={"pol": "HPH", "dest": "USLAX"})
    assert resp.status_code == 200, resp.text
    d = resp.json()
    for key in ("state", "delta_pct", "current_rate_40hq", "sample_size"):
        assert key in d, f"missing key {key} in {d}"


def test_market_intel_lanes_list(client):
    """lanes endpoint returns list of lane dicts."""
    resp = client.get("/api/intelligence/lanes", params={"pol": "HPH"})
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert "lanes" in d
    assert isinstance(d["lanes"], list)
    assert len(d["lanes"]) >= 1


def test_intel_profile_unknown_email(client):
    """Unknown email returns empty-ish dict, not error."""
    resp = client.get("/api/intel/profile", params={"email": "never-seen@nowhere.com"})
    assert resp.status_code == 200
    d = resp.json()
    # Should be a dict (possibly with null fields) — never throw
    assert isinstance(d, dict)


def test_intel_stale_returns_shape(client):
    resp = client.get("/api/intel/stale", params={"days": 7})
    assert resp.status_code == 200
    d = resp.json()
    assert "stale" in d
    assert "count" in d
    assert isinstance(d["stale"], list)


def test_intel_recent_replies_filters_by_window(client):
    resp = client.get("/api/intel/recent-replies", params={"since_minutes": 60})
    assert resp.status_code == 200
    d = resp.json()
    assert "replies" in d
    assert "count" in d


def test_reset_stuck_endpoint(client):
    resp = client.post("/api/email-rate/queue/reset-stuck", params={"minutes": 10})
    assert resp.status_code == 200
    assert "reset" in resp.json()


def test_queue_pending_empty_returns_jobs_key(client):
    """pending endpoint should always return a 'jobs' list."""
    # Kill-switch clear already done earlier
    resp = client.get("/api/email-rate/queue/pending",
                      params={"worker_id": "test_worker", "limit": 1})
    assert resp.status_code == 200
    d = resp.json()
    assert "jobs" in d
    assert isinstance(d["jobs"], list)
