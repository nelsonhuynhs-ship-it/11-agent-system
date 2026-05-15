#!/usr/bin/env python3
"""Phase 2 tests: EmailAddressGuard + Prefix Shield."""
import pytest
import sys
from pathlib import Path

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


class TestEmailAddressGuardFormat:
    """Format validation: empty local/domain, spaces, multiple @, missing dot."""

    def test_empty_email_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_missing_at_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("notanemail.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_double_at_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("a@b@c.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_space_in_local_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("hello world@gmail.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_empty_local_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("@gmail.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_consecutive_dots_rejected(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("user@gmail..com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "INVALID_FORMAT"

    def test_valid_email_accepted(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("john.doe@gmail.com")
        assert r["is_sendable"] is True
        assert r["reason_code"] == "OK"

    def test_uppercase_normalized(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("John@Gmail.Com")
        assert r["is_sendable"] is True
        assert r["normalized"] == "john@gmail.com"


class TestEmailAddressGuardPrefix:
    """Prefix validation: role/no-reply/corrupt prefixes blocked."""

    def test_noreply_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("noreply@company.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "ROLE_OR_NO_REPLY"

    def test_no_reply_variant_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("no-reply@company.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "ROLE_OR_NO_REPLY"

    def test_info_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("info@freight.com")
        assert r["is_sendable"] is False
        assert r["reason_code"] == "ROLE_OR_NO_REPLY"

    def test_admin_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("admin@pudongprime.vn")
        assert r["is_sendable"] is False

    def test_test_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("test@company.com")
        assert r["is_sendable"] is False

    def test_valid_personal_not_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("john@pudongprime.vn")
        assert r["is_sendable"] is True

    def test_contact_person_not_blocked(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        r = g.guard("contact@company.com")
        assert r["is_sendable"] is True  # contact is not in role list


class TestBulkGuard:
    """bulk_guard() aggregates quarantined and blocked_by_reason."""

    def test_bulk_guard_returns_summary(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        result = g.bulk_guard([
            "john@gmail.com",
            "noreply@corp.com",
            "test@freight.com",
            "invalid",
        ])
        assert "sendable_count" in result
        assert "quarantine_count" in result
        assert "blocked_by_reason" in result
        assert result["sendable_count"] >= 1
        assert result["quarantine_count"] >= 2

    def test_bulk_guard_blocked_by_reason(self):
        from email_engine.core.email_address_guard import EmailAddressGuard
        g = EmailAddressGuard()
        result = g.bulk_guard(["noreply@x.com", "test@x.com"])
        assert result["quarantine_count"] == 2
        assert "ROLE_OR_NO_REPLY" in result["blocked_by_reason"] or "BAD_PREFIX" in result["blocked_by_reason"]


class TestModuleLevelConvenience:
    """Module-level guard_email() returns same result as EmailAddressGuard().guard()."""

    def test_guard_email_convenience_function(self):
        from email_engine.core.email_address_guard import guard_email
        r = guard_email("john@gmail.com")
        assert r["is_sendable"] is True
        assert r["input"] == "john@gmail.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])