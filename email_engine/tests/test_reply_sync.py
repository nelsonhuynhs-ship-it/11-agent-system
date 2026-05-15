#!/usr/bin/env python3
"""Phase 5 tests: Reply Detection + Follow-up Suggestions."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timezone

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


class TestReplyClassification:
    """_classify_reply_subject() maps subject patterns to reply classes."""

    def test_hot_reply_quote(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        # "quote 40hq" clearly signals buying intent — quote fires first
        assert _classify_reply_subject("Quote 40hq to Long Beach") == "HOT_REPLY"
        assert _classify_reply_subject("Container rate needed") == "HOT_REPLY"

    def test_quote_request(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("Please quote for 20gp to Long Beach") == "QUOTE_REQUEST"
        assert _classify_reply_subject("Can you send price for 1x40hc") == "QUOTE_REQUEST"

    def test_rate_question(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("How much to ship 40hc") == "RATE_QUESTION"
        assert _classify_reply_subject("What's the shipping charge") == "RATE_QUESTION"

    def test_auto_reply(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("Auto reply: out of office") == "AUTO_REPLY"

    def test_unsubscribe(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("Please unsubscribe me") == "UNSUBSCRIBE"

    def test_not_interested(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("Not interested in freight") == "NOT_INTERESTED"

    def test_needs_human_reply(self):
        from email_engine.core.reply_sync import _classify_reply_subject
        assert _classify_reply_subject("Thanks for your email") == "NEEDS_HUMAN_REPLY"
        assert _classify_reply_subject("Hello John") == "NEEDS_HUMAN_REPLY"


class TestStripReplyPrefix:
    """_strip_reply_prefix() removes RE:/FW: prefixes."""

    def test_strips_re_prefix(self):
        from email_engine.core.reply_sync import _strip_reply_prefix
        assert _strip_reply_prefix("RE: Freight Quote") == "Freight Quote"
        assert _strip_reply_prefix("RE: Your rates") == "Your rates"

    def test_strips_fw_prefix(self):
        from email_engine.core.reply_sync import _strip_reply_prefix
        assert _strip_reply_prefix("FW: Container shipping") == "Container shipping"

    def test_passthrough_no_prefix(self):
        from email_engine.core.reply_sync import _strip_reply_prefix
        assert _strip_reply_prefix("Hello there") == "Hello there"


class TestDetectReplyByConversation:
    """detect_reply_by_conversation() with fake Outlook COM."""

    def test_detects_reply_by_conv_id(self):
        from email_engine.core.reply_sync import detect_reply_by_conversation

        fake_item = MagicMock()
        fake_item.Class = 43
        fake_item.SenderEmailAddress = "john@gmail.com"
        fake_item.ConversationID = "CID123"
        fake_item.Subject = "RE: Freight Quote"
        fake_item.ReceivedTime = datetime(2026, 5, 14, 10, 0, 0)
        fake_item.Body = "Please quote 40hq to LA, thanks!"

        fake_ns = MagicMock()
        fake_inbox = MagicMock()
        fake_inbox.Items = MagicMock()
        fake_inbox.Items.Restrict.return_value = [fake_item]
        fake_ns.GetDefaultFolder.return_value = fake_inbox

        fake_app = MagicMock()
        fake_app.GetNamespace.return_value = fake_ns

        result = detect_reply_by_conversation(
            conversation_id="CID123",
            sender_email="john@gmail.com",
            outlook_app=fake_app,
            hours_back=72,
        )
        assert result["found"] is True
        assert result["reply_class"] == "HOT_REPLY"
        assert result["sender"] == "john@gmail.com"

    def test_returns_not_found_when_no_match(self):
        from email_engine.core.reply_sync import detect_reply_by_conversation

        fake_ns = MagicMock()
        fake_inbox = MagicMock()
        fake_inbox.Items = MagicMock()
        fake_inbox.Items.Restrict.return_value = []
        fake_ns.GetDefaultFolder.return_value = fake_inbox

        fake_app = MagicMock()
        fake_app.GetNamespace.return_value = fake_ns

        result = detect_reply_by_conversation(
            conversation_id="CID999",
            sender_email="notexist@gmail.com",
            outlook_app=fake_app,
            hours_back=72,
        )
        assert result["found"] is False
        assert result["reply_class"] == "UNKNOWN_REPLY"


class TestGenerateWritebackPayload:
    """generate_writeback_payload() returns correct structure."""

    def test_payload_structure(self):
        from email_engine.core.reply_sync import generate_writeback_payload, ReplyDetectionResult

        detection: ReplyDetectionResult = {
            "found": True,
            "reply_class": "HOT_REPLY",
            "sender": "john@gmail.com",
            "subject": "RE: Freight Quote",
            "detected_at": "2026-05-14T10:00:00",
            "conversation_id": "CID123",
            "raw_snippet": "Please quote 40hq",
        }

        payload = generate_writeback_payload("john@gmail.com", detection, campaign_id="C1")
        assert payload["cnee_email"] == "john@gmail.com"
        assert payload["reply_class"] == "HOT_REPLY"
        assert payload["do_not_cold_send"] is True
        assert payload["needs_human_reply"] is False

    def test_do_not_cold_send_hot_reply(self):
        from email_engine.core.reply_sync import generate_writeback_payload, ReplyDetectionResult

        detection: ReplyDetectionResult = {
            "found": True,
            "reply_class": "HOT_REPLY",
            "sender": "a@b.com",
            "subject": "Quote",
            "detected_at": "",
            "conversation_id": None,
            "raw_snippet": "",
        }
        payload = generate_writeback_payload("a@b.com", detection)
        assert payload["do_not_cold_send"] is True

    def test_not_interested_do_not_cold_send(self):
        from email_engine.core.reply_sync import generate_writeback_payload, ReplyDetectionResult

        detection: ReplyDetectionResult = {
            "found": True,
            "reply_class": "NOT_INTERESTED",
            "sender": "c@d.com",
            "subject": "Not interested",
            "detected_at": "",
            "conversation_id": None,
            "raw_snippet": "",
        }
        payload = generate_writeback_payload("c@d.com", detection)
        assert payload["do_not_cold_send"] is True

    def test_needs_human_reply_flag(self):
        from email_engine.core.reply_sync import generate_writeback_payload, ReplyDetectionResult

        detection: ReplyDetectionResult = {
            "found": True,
            "reply_class": "NEEDS_HUMAN_REPLY",
            "sender": "e@f.com",
            "subject": "Thanks",
            "detected_at": "",
            "conversation_id": None,
            "raw_snippet": "",
        }
        payload = generate_writeback_payload("e@f.com", detection)
        assert payload["needs_human_reply"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])