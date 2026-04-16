"""Unit tests for email_engine.scanner.*

Run:  pytest email_engine/tests/test_scanner.py -v
These tests are 100% offline (no Outlook, no Telegram, no intel.db).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Ensure the repo root is on sys.path so `email_engine.*` imports work
# regardless of where pytest is invoked.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from email_engine.scanner import classifier, handlers, telegram, daily_report  # noqa: E402
from email_engine.scanner.classifier import classify, load_patterns  # noqa: E402


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------
def make_item(sender: str = "", subject: str = "", body: str = ""):
    """Lightweight Outlook MailItem stand-in."""
    return SimpleNamespace(
        SenderEmailAddress=sender,
        Subject=subject,
        Body=body,
        Categories="",
        Class=43,
    )


@pytest.fixture
def patterns():
    return load_patterns()


@pytest.fixture
def cnee_set():
    return {"buyer@bigco.com", "ops@anothercnee.com"}


# -------------------------------------------------------------------
# classifier.classify
# -------------------------------------------------------------------
def test_classify_bounce_by_sender(patterns, cnee_set):
    item = make_item(
        sender="postmaster@example.com",
        subject="Delivery Status Notification (Failure)",
        body="Your message to x@y.com could not be delivered",
    )
    assert classify(item, patterns, cnee_set) == "BOUNCE"


def test_classify_bounce_by_subject(patterns, cnee_set):
    item = make_item(
        sender="mailsys@someserver.net",
        subject="Undeliverable: Nelson Freight Quote HPH-USLAX",
        body="User unknown",
    )
    assert classify(item, patterns, cnee_set) == "BOUNCE"


def test_classify_auto_reply(patterns, cnee_set):
    item = make_item(
        sender="buyer@bigco.com",
        subject="Automatic reply: Out of office until Monday",
        body="I am on vacation.",
    )
    assert classify(item, patterns, cnee_set) == "AUTO_REPLY"


def test_classify_real_reply(patterns, cnee_set):
    item = make_item(
        sender="buyer@bigco.com",
        subject="Re: HPL quote HPH-USLAX",
        body="Please send me the best rate for 40HQ.",
    )
    assert classify(item, patterns, cnee_set) == "REAL_REPLY"


def test_classify_unsubscribe(patterns, cnee_set):
    item = make_item(
        sender="buyer@bigco.com",
        subject="Please remove me from your list",
        body="unsubscribe.",
    )
    assert classify(item, patterns, cnee_set) == "UNSUBSCRIBE"


def test_classify_irrelevant(patterns, cnee_set):
    item = make_item(
        sender="random@unknown.com",
        subject="Newsletter: Industry trends Q2",
        body="Sign up for our weekly update.",
    )
    assert classify(item, patterns, cnee_set) == "IRRELEVANT"


# -------------------------------------------------------------------
# handlers.extract_bounced_email (regex coverage)
# -------------------------------------------------------------------
@pytest.mark.parametrize(
    "body,expected",
    [
        (
            "Your message to ops@example.com could not be delivered because the address was rejected.",
            "ops@example.com",
        ),
        (
            "Final-Recipient: rfc822; buyer.failed@company.co.uk\nAction: failed",
            "buyer.failed@company.co.uk",
        ),
        (
            "Delivery has failed to these recipients:\n    recipient: purchase@client-corp.net\n",
            "purchase@client-corp.net",
        ),
    ],
)
def test_extract_bounced_email_variants(body, expected):
    got = handlers.extract_bounced_email(body)
    assert got == expected


def test_extract_bounced_email_skips_daemon():
    body = "Failure from postmaster@mail.server.com to nothing useful"
    # Should NOT return postmaster itself
    got = handlers.extract_bounced_email(body)
    assert got != "postmaster@mail.server.com"


# -------------------------------------------------------------------
# handlers.handle_bounce calls intel.log_event via module seam
# -------------------------------------------------------------------
def test_handle_bounce_calls_log_event(monkeypatch):
    calls = []

    def fake_log(event_type, **fields):
        calls.append((event_type, fields))

    # Patch the bound reference inside handlers module
    monkeypatch.setattr(handlers, "_log_event", fake_log)
    # Silence telegram
    monkeypatch.setattr(telegram, "send_alert", lambda msg: True)
    monkeypatch.setattr(handlers.tg, "send_alert", lambda msg: True)

    item = make_item(
        sender="postmaster@example.com",
        subject="Undeliverable",
        body="Final-Recipient: rfc822; failed@cnee.com\nthe user does not exist",
    )
    handlers.handle_bounce(item, "failed@cnee.com")

    assert any(c[0] == "BOUNCE" for c in calls)
    args = dict(calls[0][1])
    assert args.get("email") == "failed@cnee.com"
    assert args.get("severity") in ("HARD", "SOFT")


def test_handle_auto_reply_logs_event(monkeypatch):
    calls = []
    monkeypatch.setattr(handlers, "_log_event", lambda t, **f: calls.append((t, f)))
    monkeypatch.setattr(handlers.tg, "send_alert", lambda msg: True)

    item = make_item(
        sender="buyer@bigco.com",
        subject="Automatic reply: Out of Office",
        body="I am on vacation until Mar 10",
    )
    handlers.handle_auto_reply(item, "buyer@bigco.com")
    assert any(c[0] == "AUTO_REPLY" for c in calls)


def test_handle_real_reply_logs_event_and_alerts(monkeypatch):
    log_calls = []
    alert_calls = []
    monkeypatch.setattr(handlers, "_log_event", lambda t, **f: log_calls.append((t, f)))
    monkeypatch.setattr(handlers.tg, "send_alert", lambda msg: alert_calls.append(msg) or True)

    item = make_item(
        sender="buyer@bigco.com",
        subject="Re: HPH-USLAX quote",
        body="Please send me your best rate for 40HQ, we would like to book.",
    )
    handlers.handle_real_reply(item, {"EMAIL": "buyer@bigco.com", "COMPANY": "BigCo"})
    assert any(c[0] == "REPLY" for c in log_calls)
    # booking_intent triggers HOT alert
    assert alert_calls and "HOT LEAD" in alert_calls[0]


def test_handle_unsubscribe_suppresses(monkeypatch):
    writeback_calls = []
    monkeypatch.setattr(handlers, "_log_event", lambda t, **f: None)
    monkeypatch.setattr(handlers, "_evaluate_event", lambda t, **f: {})
    monkeypatch.setattr(handlers, "_update_master", lambda e, u: writeback_calls.append((e, u)) or True)
    monkeypatch.setattr(handlers.tg, "send_alert", lambda msg: True)

    item = make_item(sender="buyer@bigco.com", subject="Unsubscribe", body="Please remove me")
    handlers.handle_unsubscribe(item, "buyer@bigco.com")
    assert writeback_calls
    email, updates = writeback_calls[0]
    assert email == "buyer@bigco.com"
    assert updates.get("EMAIL_STATUS") == "UNSUBSCRIBED"
    assert updates.get("ACTION") == "SUPPRESS"


# -------------------------------------------------------------------
# telegram.send_alert — no crash on missing env
# -------------------------------------------------------------------
def test_telegram_missing_env_returns_false(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_NELSON_CHAT_ID", raising=False)
    # Also ensure the dotenv loader cannot populate it
    monkeypatch.setattr(telegram, "_load_dotenv_if_present", lambda: None)
    assert telegram.send_alert("hello world") is False


def test_telegram_batch_empty_is_noop():
    assert telegram.send_batch_alert([]) is True


def test_telegram_batch_single_delegates(monkeypatch):
    sent = []
    monkeypatch.setattr(telegram, "send_alert", lambda msg: sent.append(msg) or True)
    assert telegram.send_batch_alert(["only one"]) is True
    assert sent == ["only one"]


# -------------------------------------------------------------------
# daily_report.generate_summary
# -------------------------------------------------------------------
def test_daily_report_summary_stub_mode():
    """No intel module -> friendly 'scanner alive' fallback message."""
    summary = daily_report.generate_summary()
    assert "Nelson Scanner" in summary
    assert "Daily Report" in summary


def test_daily_report_summary_with_events(monkeypatch):
    fake_events = [
        {"event_type": "REPLY", "email": "a@x.com", "company": "ACME",
         "intent": "booking_intent", "tier_change": "PROMOTED"},
        {"event_type": "REPLY", "email": "b@x.com", "company": "ACME",
         "intent": "price_inquiry"},
        {"event_type": "BOUNCE", "email": "c@x.com", "severity": "HARD"},
        {"event_type": "AUTO_REPLY", "email": "d@x.com"},
        {"event_type": "UNSUBSCRIBE", "email": "e@x.com"},
    ]
    monkeypatch.setattr(daily_report, "_fetch_events_last_24h", lambda: fake_events)
    summary = daily_report.generate_summary()
    assert "Replies:" in summary
    assert "Bounces:" in summary
    assert "Unsubscribes:" in summary
    # One booking_intent -> hot leads should be 1
    assert "Hot leads:" in summary


# -------------------------------------------------------------------
# classifier.load_patterns always returns dict (never None)
# -------------------------------------------------------------------
def test_load_patterns_returns_dict():
    p = load_patterns()
    assert isinstance(p, dict)
    assert "bounce" in p and "auto_reply" in p and "unsubscribe" in p


def test_load_patterns_fallback_on_missing_yaml(tmp_path):
    fake = tmp_path / "does_not_exist.yaml"
    p = load_patterns(fake)
    assert isinstance(p, dict)
    assert "bounce" in p  # fallback kicks in


# -------------------------------------------------------------------
# reply_analyzer upgrades
# -------------------------------------------------------------------
def test_reply_analyzer_intent_and_sentiment():
    from email_engine.core.reply_analyzer import analyze_reply

    res = analyze_reply(
        subject="Re: HPH-USLAX quote",
        body="Please send me your best rate for 40HQ, we would like to book.",
    )
    assert res["intent"] == "booking_intent"
    assert res["sentiment"] == "POSITIVE"
    assert 0.0 <= res["confidence"] <= 1.0


def test_reply_analyzer_objection_sentiment_negative():
    from email_engine.core.reply_analyzer import analyze_reply

    # Use a subject free of intent keywords so objection wins cleanly.
    res = analyze_reply(
        subject="Re: Nelson proposal",
        body="Rate is too high, not competitive. Not interested.",
    )
    assert res["intent"] == "objection"
    assert res["sentiment"] == "NEGATIVE"


def test_reply_analyzer_general_fallback():
    from email_engine.core.reply_analyzer import analyze_reply

    res = analyze_reply(subject="Hi Nelson", body="Hope you're well.")
    assert res["intent"] == "general"
    assert res["sentiment"] in ("NEUTRAL", "UNKNOWN", "POSITIVE")
