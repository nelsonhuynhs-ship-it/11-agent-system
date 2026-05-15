#!/usr/bin/env python3
"""Phase 6 tests: Backend API Contract."""
import pytest
import sys
from pathlib import Path

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
sys.path.insert(0, f"{WORKTREE}/email_engine")


class TestCanonicalOkShape:
    """canonical_ok() returns the correct shape."""

    def test_returns_ok_true(self):
        from email_engine.api.routes.email_contract import canonical_ok
        r = canonical_ok()
        assert r["ok"] is True
        assert r["version"] == "v9"
        assert r["source"] == "outlook_com"

    def test_returns_all_canonic_fields(self):
        from email_engine.api.routes.email_contract import canonical_ok
        r = canonical_ok(campaign_id="C1", counts={"sent": 5})
        assert "ok" in r
        assert "version" in r
        assert "source" in r
        assert "campaign_id" in r
        assert "counts" in r
        assert "items" in r
        assert "warnings" in r
        assert "needs_verification" in r

    def test_defaults_empty_lists(self):
        from email_engine.api.routes.email_contract import canonical_ok
        r = canonical_ok()
        assert r["items"] == []
        assert r["warnings"] == []
        assert r["needs_verification"] == []


class TestCanonicalError:
    """canonical_error() returns correct shape."""

    def test_returns_ok_false(self):
        from email_engine.api.routes.email_contract import canonical_error
        r = canonical_error("something broke")
        assert r["ok"] is False
        assert r["error"] == "something broke"
        assert r["version"] == "v9"


class TestEmailContractRouter:
    """Email contract router is mounted and has correct routes."""

    def test_router_has_13_routes(self):
        from email_engine.api.routes.email_contract import router
        assert len(router.routes) == 13

    def test_get_dashboard_status_route(self):
        from email_engine.api.routes.email_contract import router
        paths = [r.path for r in router.routes]
        assert any("/dashboard/v9/status" in p for p in paths)

    def test_validate_route(self):
        from email_engine.api.routes.email_contract import router
        methods_by_path = {r.path: r.methods for r in router.routes}
        validate_paths = [p for p in methods_by_path if "validate" in p]
        assert any("POST" in methods_by_path[p] for p in validate_paths)

    def test_send_outlook_route(self):
        from email_engine.api.routes.email_contract import router
        paths = [r.path for r in router.routes]
        assert any("send-outlook" in p for p in paths)

    def test_quarantine_routes(self):
        from email_engine.api.routes.email_contract import router
        paths = [r.path for r in router.routes]
        assert any("quarantine" in p for p in paths)
        assert any("quarantine/resolve" in p for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])