#!/usr/bin/env python3
"""Phase 4 tests: Post-Send Reconciliation — fake COM objects."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


class TestNDRClassification:
    """_classify_ndr_subject() maps subject patterns to NDR classes."""

    def test_hard_bounce_pattern(self):
        from email_engine.core.outlook_reconcile import _classify_ndr_subject
        assert _classify_ndr_subject("Mail delivery failed") == "HARD_BOUNCE"
        assert _classify_ndr_subject("Undeliverable mail") == "HARD_BOUNCE"

    def test_delayed_pattern(self):
        from email_engine.core.outlook_reconcile import _classify_ndr_subject
        assert _classify_ndr_subject("Delivery delay notification") == "DELAYED"
        assert _classify_ndr_subject("Message delayed") == "DELAYED"

    def test_mailbox_full_pattern(self):
        from email_engine.core.outlook_reconcile import _classify_ndr_subject
        assert _classify_ndr_subject("Mailbox is full") == "MAILBOX_FULL"

    def test_auto_reply_pattern(self):
        from email_engine.core.outlook_reconcile import _classify_ndr_subject
        assert _classify_ndr_subject("Auto reply: out of office") == "AUTO_REPLY"

    def test_unknown_pattern(self):
        from email_engine.core.outlook_reconcile import _classify_ndr_subject
        assert _classify_ndr_subject("Hello from John") == "UNKNOWN"


class TestFindSentMail:
    """find_sent_mail() with fake Outlook COM."""

    def test_finds_sent_mail_by_to_and_subject(self):
        from email_engine.core.outlook_reconcile import find_sent_mail

        fake_item = MagicMock()
        fake_item.Class = 43
        fake_item.SentOn = datetime(2026, 5, 15, 10, 0, 0)
        fake_item.To = "john@gmail.com"
        fake_item.Subject = "Freight Quote"
        fake_item.EntryID = "EID123"
        fake_item.ConversationID = "CID456"

        fake_ns = MagicMock()
        fake_sent_folder = MagicMock()
        fake_sent_folder.Items = MagicMock()
        fake_sent_folder.Items.Restrict.return_value = [fake_item]
        fake_ns.GetDefaultFolder.return_value = fake_sent_folder

        fake_app = MagicMock()
        fake_app.GetNamespace.return_value = fake_ns

        result = find_sent_mail(
            message_key="key123",
            to="john@gmail.com",
            subject="Freight Quote",
            sent_after=datetime(2026, 5, 15, 8, 0, 0, tzinfo=timezone.utc),
            outlook_app=fake_app,
        )
        assert result["found"] is True
        assert result["verification_status"] == "SENT_CONFIRMED"
        assert result["matched_by"] == "to_subject"

    def test_returns_pending_when_not_found(self):
        from email_engine.core.outlook_reconcile import find_sent_mail

        fake_ns = MagicMock()
        fake_sent_folder = MagicMock()
        fake_sent_folder.Items = MagicMock()
        fake_sent_folder.Items.Restrict.return_value = []
        fake_ns.GetDefaultFolder.return_value = fake_sent_folder

        fake_app = MagicMock()
        fake_app.GetNamespace.return_value = fake_ns

        result = find_sent_mail(
            message_key="key123",
            to="nobody@gmail.com",
            subject="No such email",
            sent_after=datetime(2026, 5, 15, 8, 0, 0, tzinfo=timezone.utc),
            outlook_app=fake_app,
        )
        assert result["found"] is False
        assert result["verification_status"] == "SENT_PENDING_VERIFICATION"


class TestReconcile:
    """Full reconcile() bundles sent confirmation + NDR scan."""

    def test_reconcile_returns_both_keys(self):
        from email_engine.core.outlook_reconcile import reconcile

        with patch("email_engine.core.outlook_reconcile.find_sent_mail") as mock_find, \
             patch("email_engine.core.outlook_reconcile.scan_inbox_for_ndr") as mock_ndr:
            mock_find.return_value = {"found": True, "verification_status": "SENT_CONFIRMED",
                                      "outlook_entry_id": "EID1", "conversation_id": "CID1",
                                      "sent_at": "2026-05-15T10:00:00", "matched_by": "to_subject"}
            mock_ndr.return_value = []

            result = reconcile(to="a@b.com", subject="Test", message_key="k1")
            assert "sent_confirmed" in result
            assert "ndr_results" in result
            assert result["sent_confirmed"]["found"] is True
            assert result["ndr_results"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])