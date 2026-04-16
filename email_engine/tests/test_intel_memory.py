"""
test_intel_memory.py — Phase 02 unit tests for intel package.

Run from repo root:
    python -m pytest email_engine/tests/test_intel_memory.py -v
"""
from __future__ import annotations

import importlib
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Reload memory + writeback per session so the module-level _DB_PATH /
# _master_path get reset to the per-test paths.
from email_engine.intel import (
    memory,
    tier_engine,
    writeback,
    build_sent_event,
    build_reply_event,
    build_bounce_event,
    build_unsubscribe_event,
    build_tier_event,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_writeback_buffer():
    """Each test starts with a clean writeback buffer."""
    with writeback._buffer_lock:
        writeback._buffer.clear()
    yield
    with writeback._buffer_lock:
        writeback._buffer.clear()


@pytest.fixture
def intel_db(tmp_path) -> str:
    """Isolated intel.db per test."""
    db = tmp_path / "intel_test.db"
    memory.init_db(str(db))
    return str(db)


def _ts(days_ago: float = 0) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# memory.py — basic CRUD + queries
# ---------------------------------------------------------------------------

def test_init_db_creates_schema(intel_db):
    import sqlite3
    conn = sqlite3.connect(intel_db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "email_events" in tables
    assert "cnee_state" in tables


def test_log_event_sent_returns_id(intel_db):
    rid = memory.log_event(build_sent_event(
        cnee_email="alice@x.com",
        subject="Rates +5%",
        template_id="urgent_v1",
        market_state="URGENT",
        delta_pct=5.0,
        batch_id="B100",
        campaign_id="FURNITURE",
    ))
    assert rid > 0


def test_log_event_reply_persists_snippet(intel_db):
    long_body = "x" * 1000
    memory.log_event(build_reply_event(
        cnee_email="bob@x.com",
        reply_subject="Re: Rates",
        reply_body_snippet=long_body,
        sentiment="POSITIVE",
        intent="booking",
        reply_delay_hours=12.0,
    ))
    timeline = memory.get_timeline("bob@x.com")
    assert len(timeline) == 1
    assert timeline[0]["sentiment"] == "POSITIVE"
    assert timeline[0]["intent"] == "booking"
    assert len(timeline[0]["reply_body_snippet"]) == 500   # trimmed


def test_log_event_unknown_type_raises(intel_db):
    with pytest.raises(ValueError):
        memory.log_event({"event_type": "WHAT", "cnee_email": "a@b.com"})


def test_get_timeline_orders_desc_with_10_events(intel_db):
    cnee = "carol@x.com"
    for i in range(10):
        ev = build_sent_event(cnee_email=cnee, subject=f"step{i}", batch_id=f"B{i}")
        ev["timestamp"] = _ts(days_ago=10 - i)
        memory.log_event(ev)
    # add 2 replies in between
    r = build_reply_event(cnee_email=cnee, sentiment="POSITIVE", intent="booking")
    r["timestamp"] = _ts(days_ago=4.5)
    memory.log_event(r)

    timeline = memory.get_timeline(cnee, limit=20)
    assert len(timeline) == 11
    timestamps = [row["timestamp"] for row in timeline]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_cnee_summary_aggregates(intel_db):
    cnee = "dan@x.com"
    for i in range(5):
        ev = build_sent_event(cnee_email=cnee, subject=f"s{i}")
        ev["timestamp"] = _ts(days_ago=20 - i)
        memory.log_event(ev)
    for i, intent in enumerate(["booking", "price_inquiry"]):
        ev = build_reply_event(cnee_email=cnee, sentiment="POSITIVE",
                               intent=intent, reply_delay_hours=10.0 + i)
        ev["timestamp"] = _ts(days_ago=10 - i)
        memory.log_event(ev)
    memory.log_event(build_bounce_event(cnee_email=cnee, bounce_type="HARD",
                                        bounce_reason="user unknown"))

    s = memory.get_cnee_summary(cnee)
    assert s["total_sent"] == 5
    assert s["total_replied"] == 2
    assert s["total_bounced"] == 1
    assert s["reply_rate"] == round(2 / 5, 4)
    assert s["intent_distribution"] == {"booking": 1, "price_inquiry": 1}
    assert s["last_subject"] == "s4"
    assert s["avg_reply_delay_hours"] is not None


def test_get_stale_returns_only_stale_unreplied(intel_db):
    # 8d ago, no reply -> stale
    ev1 = build_sent_event(cnee_email="stale@x.com", subject="old")
    ev1["timestamp"] = _ts(days_ago=8)
    memory.log_event(ev1)

    # 5d ago, no reply -> NOT stale (within 7d window)
    ev2 = build_sent_event(cnee_email="fresh@x.com", subject="recent")
    ev2["timestamp"] = _ts(days_ago=5)
    memory.log_event(ev2)

    # 8d ago BUT with reply 6d ago -> NOT stale (replied since)
    ev3 = build_sent_event(cnee_email="replied@x.com", subject="r")
    ev3["timestamp"] = _ts(days_ago=8)
    memory.log_event(ev3)
    rev = build_reply_event(cnee_email="replied@x.com", sentiment="NEUTRAL")
    rev["timestamp"] = _ts(days_ago=6)
    memory.log_event(rev)

    stale = memory.get_stale(days=7)
    emails = {row["cnee_email"] for row in stale}
    assert "stale@x.com" in emails
    assert "fresh@x.com" not in emails
    assert "replied@x.com" not in emails


def test_count_events_filters(intel_db):
    for i in range(3):
        memory.log_event(build_sent_event(cnee_email="e@x.com", subject=f"s{i}"))
    memory.log_event(build_bounce_event(cnee_email="e@x.com"))
    assert memory.count_events("SENT") == 3
    assert memory.count_events("SENT", cnee_email="e@x.com") == 3
    assert memory.count_events("BOUNCE") == 1


def test_log_events_bulk_performance(intel_db):
    """1000 SENT events in a single transaction must complete < 2s."""
    events = [
        build_sent_event(cnee_email=f"p{i}@x.com", subject=f"s{i}",
                         batch_id="BULK")
        for i in range(1000)
    ]
    start = time.perf_counter()
    n = memory.log_events_bulk(events)
    elapsed = time.perf_counter() - start
    assert n == 1000
    assert elapsed < 2.0, f"bulk insert too slow: {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# tier_engine.py — promotion / demotion rules
# ---------------------------------------------------------------------------

def test_tier_promotion_warm_b_to_warm_a(intel_db):
    cnee = "promote@x.com"
    action = tier_engine.apply_promotion_rules(
        cnee, "REPLY",
        sentiment="POSITIVE", intent="booking",
        current_tier="WARM_B",
    )
    assert action is not None
    assert action["new_tier"] == "WARM_A"
    assert action["new_action"] == "SEND_NOW"
    assert action["promoted"] is True
    assert action["writeback_fields"]["TIER"] == "WARM_A"


def test_tier_promotion_warm_a_to_hot(intel_db):
    action = tier_engine.apply_promotion_rules(
        "hot@x.com", "REPLY",
        sentiment="POSITIVE", intent="price_inquiry",
        current_tier="WARM_A",
    )
    assert action["new_tier"] == "HOT"
    assert action["new_action"] == "FOLLOW_UP"


def test_tier_promotion_neutral_reply_on_cool(intel_db):
    action = tier_engine.apply_promotion_rules(
        "cool@x.com", "REPLY",
        sentiment="NEUTRAL", intent="general",
        current_tier="COOL",
    )
    assert action is not None
    assert action["new_tier"] == "WARM_B"


def test_tier_no_change_on_neutral_warm_b(intel_db):
    action = tier_engine.apply_promotion_rules(
        "x@x.com", "REPLY",
        sentiment="NEUTRAL", intent="general",
        current_tier="WARM_B",
    )
    assert action is None


def test_tier_demotion_three_hard_bounces_park(intel_db):
    cnee = "bouncer@x.com"
    # log 2 bounces directly (state cache increments)
    for _ in range(2):
        memory.log_event(build_bounce_event(cnee_email=cnee, bounce_type="HARD"))
    # 3rd bounce: log first, then evaluate -> should park
    memory.log_event(build_bounce_event(cnee_email=cnee, bounce_type="HARD"))
    action = tier_engine.apply_demotion_rules(
        cnee, "BOUNCE",
        extra={"bounce_type": "HARD", "current_tier": "WARM_B"},
    )
    assert action is not None
    assert action["new_tier"] == "PARK"
    assert action["new_action"] == "SKIP"
    assert action["writeback_fields"]["EMAIL_STATUS"] == "HARD_BOUNCE"


def test_tier_demotion_first_bounce_quality_penalty(intel_db):
    cnee = "softfail@x.com"
    memory.log_event(build_bounce_event(cnee_email=cnee, bounce_type="HARD"))
    action = tier_engine.apply_demotion_rules(
        cnee, "BOUNCE",
        extra={"bounce_type": "HARD", "current_tier": "WARM_A"},
    )
    assert action is not None
    assert action["new_tier"] == "WARM_A"   # unchanged
    assert action["writeback_fields"]["EMAIL_QUALITY_SCORE_DELTA"] == -15


def test_tier_demotion_unsubscribe_parks(intel_db):
    cnee = "leave@x.com"
    memory.log_event(build_unsubscribe_event(cnee_email=cnee))
    action = tier_engine.apply_demotion_rules(
        cnee, "UNSUBSCRIBE", extra={"current_tier": "HOT"},
    )
    assert action["new_tier"] == "PARK"
    assert action["writeback_fields"]["ACTION"] == "SKIP"


def test_tier_silent_demotion_180d():
    last_reply = (datetime.utcnow() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    action = tier_engine.evaluate_silent_demotion(
        "silent@x.com", "HOT", last_reply, None,
    )
    assert action is not None
    assert action["new_tier"] == "COOL"


def test_tier_silent_demotion_skipped_within_window():
    last_reply = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    assert tier_engine.evaluate_silent_demotion(
        "silent@x.com", "HOT", last_reply, None,
    ) is None


def test_evaluate_event_dispatches(intel_db):
    ev = build_reply_event(cnee_email="dispatch@x.com",
                           sentiment="POSITIVE", intent="booking")
    ev["_current_tier"] = "WARM_B"
    actions = tier_engine.evaluate_event(ev)
    assert len(actions) == 1
    assert actions[0]["new_tier"] == "WARM_A"


# ---------------------------------------------------------------------------
# writeback.py — debounce + xlsx round-trip
# ---------------------------------------------------------------------------

def _make_master_xlsx(path: Path, emails: list[str]) -> None:
    """Create a minimal cnee_master_v2-shaped xlsx for writeback tests."""
    import pandas as pd
    df = pd.DataFrame({
        "EMAIL": emails,
        "COMPANY": [f"Co{i}" for i in range(len(emails))],
        "TIER": ["WARM_B"] * len(emails),
        "ACTION": ["SEND_NOW"] * len(emails),
        "REPLY_STATUS": [""] * len(emails),
        "EMAIL_QUALITY_SCORE": [80] * len(emails),
        "SEND_COUNT": [0] * len(emails),
    })
    df.to_excel(path, index=False, engine="openpyxl")


def test_writeback_round_trip(tmp_path):
    master = tmp_path / "master.xlsx"
    _make_master_xlsx(master, ["one@x.com", "two@x.com"])
    writeback.set_master_path(str(master))

    writeback.update_master("one@x.com", {
        "TIER": "HOT", "ACTION": "FOLLOW_UP",
    })
    n = writeback.flush()
    assert n == 1

    import pandas as pd
    df = pd.read_excel(master, engine="openpyxl")
    row = df[df["EMAIL"] == "one@x.com"].iloc[0]
    assert row["TIER"] == "HOT"
    assert row["ACTION"] == "FOLLOW_UP"


def test_writeback_quality_score_delta(tmp_path):
    master = tmp_path / "master.xlsx"
    _make_master_xlsx(master, ["delta@x.com"])
    writeback.set_master_path(str(master))

    writeback.update_master("delta@x.com",
                            {"EMAIL_QUALITY_SCORE_DELTA": -15})
    writeback.update_master("delta@x.com",
                            {"EMAIL_QUALITY_SCORE_DELTA": -10})
    writeback.flush()

    import pandas as pd
    df = pd.read_excel(master, engine="openpyxl")
    row = df[df["EMAIL"] == "delta@x.com"].iloc[0]
    assert row["EMAIL_QUALITY_SCORE"] == 80 - 25


def test_writeback_debounce_buffers_under_threshold(tmp_path):
    """Updates under FLUSH_BUFFER_SIZE should NOT auto-flush — buffer holds them."""
    master = tmp_path / "master.xlsx"
    _make_master_xlsx(master, [f"u{i}@x.com" for i in range(3)])
    writeback.set_master_path(str(master))

    for i in range(3):
        writeback.update_master(f"u{i}@x.com", {"TIER": "HOT"})

    # nothing flushed yet — file untouched (TIER still WARM_B)
    import pandas as pd
    df_before = pd.read_excel(master, engine="openpyxl")
    assert (df_before["TIER"] == "WARM_B").all()
    with writeback._buffer_lock:
        assert len(writeback._buffer) == 3

    # now flush manually and verify
    writeback.flush()
    df_after = pd.read_excel(master, engine="openpyxl")
    assert (df_after["TIER"] == "HOT").all()


def test_writeback_buffer_flush_size_triggers(tmp_path):
    """51 updates -> burst flush thread spawns. Verify file written within 5s."""
    master = tmp_path / "master.xlsx"
    _make_master_xlsx(master, [f"b{i}@x.com" for i in range(60)])
    writeback.set_master_path(str(master))

    for i in range(51):
        writeback.update_master(f"b{i}@x.com", {"TIER": "HOT"})

    # auto-flush burst thread runs — wait briefly
    deadline = time.time() + 5
    while time.time() < deadline:
        with writeback._buffer_lock:
            empty = len(writeback._buffer) == 0
        if empty:
            break
        time.sleep(0.1)

    import pandas as pd
    df = pd.read_excel(master, engine="openpyxl")
    hot_rows = df[df["TIER"] == "HOT"]
    assert len(hot_rows) == 51


def test_writeback_missing_master_keeps_buffer(tmp_path):
    writeback.set_master_path(str(tmp_path / "does_not_exist.xlsx"))
    writeback.update_master("ghost@x.com", {"TIER": "HOT"})
    n = writeback.flush()
    assert n == 0
    # buffer should be restored for retry
    with writeback._buffer_lock:
        assert "ghost@x.com" in writeback._buffer


def test_writeback_unknown_email_skipped(tmp_path):
    master = tmp_path / "master.xlsx"
    _make_master_xlsx(master, ["known@x.com"])
    writeback.set_master_path(str(master))

    writeback.update_master("nope@x.com", {"TIER": "HOT"})
    writeback.update_master("known@x.com", {"TIER": "HOT"})
    n = writeback.flush()
    assert n == 1
