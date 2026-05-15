#!/usr/bin/env python3
"""Phase 3 tests: Operational Event Store — email_events table."""
import pytest
import sys
import tempfile
from pathlib import Path

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


@pytest.fixture
def fresh_db():
    import email_engine.queue_store as qs
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    # Close any cached connections before starting
    qs._DB_PATH = tmp
    import sqlite3
    conn = sqlite3.connect(tmp)
    conn.executescript(qs.SCHEMA_SQL)
    for sql in qs._MIGRATION_SQL:
        try:
            conn.executescript(sql)
        except Exception:
            pass
    conn.close()
    yield tmp
    try:
        Path(tmp).unlink(missing_ok=True)
    except Exception:
        pass


class TestEmailEventsSchema:
    """email_events table must exist and have correct columns."""

    def test_email_events_table_exists_after_init(self, fresh_db):
        import sqlite3
        conn = sqlite3.connect(fresh_db)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='email_events'"
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None, "email_events table not found"

    def test_email_events_has_required_columns(self, fresh_db):
        import sqlite3
        conn = sqlite3.connect(fresh_db)
        cur = conn.execute("PRAGMA table_info(email_events)")
        cols = {r[1] for r in cur.fetchall()}
        conn.close()
        required = {
            "event_id", "message_key", "campaign_id", "customer_id",
            "cnee_email", "event_type", "status", "reason_code",
            "subject", "outlook_entry_id", "conversation_id",
            "source_folder", "detected_at", "raw_json",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_indexes_exist(self, fresh_db):
        import sqlite3
        conn = sqlite3.connect(fresh_db)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_email_events%'"
        )
        indexes = {r[0] for r in cur.fetchall()}
        conn.close()
        assert "idx_email_events_key" in indexes
        assert "idx_email_events_email" in indexes
        assert "idx_email_events_status" in indexes


class TestLogEvent:
    """log_event() appends events, duplicate event_id is a no-op."""

    def test_log_event_inserts(self, fresh_db):
        from email_engine.queue_store import log_event, ET_PRE_SEND_VALIDATED
        eid = log_event(
            event_id="test-001",
            cnee_email="john@gmail.com",
            event_type=ET_PRE_SEND_VALIDATED,
            status="candidate",
            campaign_id="C1",
            db_path=fresh_db,
        )
        assert eid > 0

    def test_log_event_idempotent(self, fresh_db):
        from email_engine.queue_store import log_event, ET_PRE_SEND_VALIDATED
        r1 = log_event(event_id="dup-001", cnee_email="a@b.com",
                       event_type=ET_PRE_SEND_VALIDATED, status="x",
                       db_path=fresh_db)
        r2 = log_event(event_id="dup-001", cnee_email="a@b.com",
                       event_type=ET_PRE_SEND_VALIDATED, status="x",
                       db_path=fresh_db)
        assert r2 == 0  # duplicate — no-op

    def test_get_events_for_email(self, fresh_db):
        from email_engine.queue_store import log_event, get_events_for_email, ET_PRE_SEND_VALIDATED
        log_event(event_id="ev-1", cnee_email="jane@gmail.com",
                  event_type=ET_PRE_SEND_VALIDATED, status="x",
                  campaign_id="C1", db_path=fresh_db)
        events = get_events_for_email("jane@gmail.com", db_path=fresh_db)
        assert len(events) >= 1
        assert events[0]["cnee_email"] == "jane@gmail.com"


class TestEventSummary:
    """event_summary() aggregates by status."""

    def test_event_summary_empty(self, fresh_db):
        from email_engine.queue_store import event_summary
        result = event_summary(db_path=fresh_db)
        assert result["total"] == 0
        assert result["by_status"] == {}

    def test_event_summary_grouped(self, fresh_db):
        from email_engine.queue_store import (
            log_event, event_summary,
            ET_PRE_SEND_VALIDATED, ET_SENT_CONFIRMED,
        )
        log_event(event_id="s-1", cnee_email="a@b.com",
                  event_type=ET_PRE_SEND_VALIDATED, status="candidate",
                  campaign_id="C1", db_path=fresh_db)
        log_event(event_id="s-2", cnee_email="b@c.com",
                  event_type=ET_SENT_CONFIRMED, status="sent_confirmed",
                  campaign_id="C1", db_path=fresh_db)
        result = event_summary(campaign_id="C1", db_path=fresh_db)
        assert result["total"] == 2
        assert result["by_status"]["candidate"] == 1
        assert result["by_status"]["sent_confirmed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])