#!/usr/bin/env python3
"""Phase 1 tests: Outlook COM adapter — fake COM object tests."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


class TestOutlookComAdapterUnit:
    """Unit tests using fake COM objects."""

    def test_create_message_key_deterministic(self):
        from email_engine.core.outlook_com_adapter import create_message_key, body_hash
        key1 = create_message_key("test@example.com", "Subject", "C1", "abc123")
        key2 = create_message_key("test@example.com", "Subject", "C1", "abc123")
        assert key1 == key2
        assert len(key1) == 32

    def test_create_message_key_changes_with_campaign(self):
        from email_engine.core.outlook_com_adapter import create_message_key, body_hash
        key1 = create_message_key("test@example.com", "Subject", "C1", "abc123")
        key2 = create_message_key("test@example.com", "Subject", "C2", "abc123")
        assert key1 != key2

    def test_body_hash(self):
        from email_engine.core.outlook_com_adapter import body_hash
        h = body_hash("<html><body>test</body></html>")
        assert len(h) == 16
        assert h == body_hash("<html><body>test</body></html>")  # deterministic

    def test_send_mail_returns_pending_verification(self):
        with patch("email_engine.core.outlook_com_adapter.get_outlook_app") as mock_app, \
             patch("email_engine.core.outlook_com_adapter.create_mail") as mock_create, \
             patch("email_engine.core.outlook_com_adapter.resolve_recipients") as mock_resolve:
            fake_mail = MagicMock()
            fake_mail.Send.return_value = None
            mock_app.return_value = MagicMock()
            mock_create.return_value = fake_mail
            mock_resolve.return_value = True
            fake_app = MagicMock()
            fake_app.CreateItem.return_value = fake_mail

            from email_engine.core.outlook_com_adapter import send_mail
            result = send_mail("test@example.com", "Hello", "<html>body</html>", campaign_id="TEST")
            assert result["ok"] is True
            assert result["verification_status"] == "SENT_PENDING_VERIFICATION"
            assert result["message_key"] is not None

    def test_resolution_failure_blocks_send(self):
        with patch("email_engine.core.outlook_com_adapter.get_outlook_app") as mock_app, \
             patch("email_engine.core.outlook_com_adapter.create_mail") as mock_create, \
             patch("email_engine.core.outlook_com_adapter.resolve_recipients") as mock_resolve:
            fake_mail = MagicMock()
            mock_app.return_value = MagicMock()
            mock_create.return_value = fake_mail
            mock_resolve.return_value = False  # resolution fails

            from email_engine.core.outlook_com_adapter import send_mail
            result = send_mail("unresolvable@example.com", "Subject", "<html>")
            assert result["ok"] is False
            assert result["verification_status"] == "RESOLUTION_FAILED"
            fake_mail.Send.assert_not_called()

    def test_com_unavailable_returns_error(self):
        with patch("email_engine.core.outlook_com_adapter.get_outlook_app") as mock_app:
            mock_app.side_effect = RuntimeError("Outlook not installed")

            from email_engine.core.outlook_com_adapter import send_mail
            result = send_mail("test@example.com", "Subject", "<html>")
            assert result["ok"] is False
            assert result["verification_status"] == "COM_UNAVAILABLE"
            assert result["error"] is not None


class TestOutlookSendResultShape:
    """TypedDict shape must have all required keys."""

    def test_result_has_required_keys(self):
        from email_engine.core.outlook_com_adapter import OutlookSendResult
        result: OutlookSendResult = {
            "ok": True,
            "message_key": "abc",
            "to": "a@b.com",
            "subject": "subj",
            "sent_at": "2026-01-01T00:00:00Z",
            "outlook_entry_id": None,
            "conversation_id": None,
            "verification_status": "SENT_PENDING_VERIFICATION",
            "error": None,
        }
        assert result["ok"] is True
        assert result["message_key"] == "abc"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])