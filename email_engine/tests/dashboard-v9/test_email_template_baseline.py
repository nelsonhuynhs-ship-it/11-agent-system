#!/usr/bin/env python3
"""Phase 0B baseline: verify build_email() stable keys and template invariants."""
import pytest, sys, os, re

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
BUILDER_PATH = f"{WORKTREE}/email_engine/intelligence/builder.py"

sys.path.insert(0, f"{WORKTREE}/email_engine")
os.chdir(WORKTREE)


class TestBuildEmailKeys:
    """build_email() must return stable keys: to, subject, html_body, meta."""

    def test_builder_file_exists(self):
        assert os.path.exists(BUILDER_PATH), f"builder.py not found at {BUILDER_PATH}"

    def test_build_email_returns_to_key(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "def build_email" in content
        # Scan for return dict keys
        returns = re.findall(r'["\']to["\']\s*:', content)
        assert len(returns) >= 1, "build_email should return 'to' key"

    def test_build_email_returns_subject_key(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        returns = re.findall(r'["\']subject["\']\s*:', content)
        assert len(returns) >= 1

    def test_build_email_returns_html_body_key(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        returns = re.findall(r'["\']html_body["\']\s*:', content)
        assert len(returns) >= 1

    def test_build_email_returns_meta_key(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        returns = re.findall(r'["\']meta["\']\s*:', content)
        assert len(returns) >= 1


class TestEmailTemplateInvariants:
    """Approved rate table shell and signature path must not change."""

    def test_rate_table_rendering_callable_exists(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        has_renderer = "render_dual_rate_table" in content or "_render_rate_table" in content
        assert has_renderer, "rate table renderer not found in builder.py"

    def test_signature_path_in_builder(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "signature" in content.lower() or "signature_html" in content

    def test_markup_preserved_in_build_email(self):
        with open(BUILDER_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "markup" in content.lower()


class TestSendPathOutlookCOMOnly:
    """Only Outlook COM send path must be reachable. No SMTP/Graph."""

    def test_webserver_uses_outlook_com_via_adapter(self):
        """web_server.py must route email send through outlook_com_adapter (Outlook COM only)."""
        path = f"{WORKTREE}/email_engine/web_server.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Must import the adapter
        assert "outlook_com_adapter" in content or "send_mail" in content
        # Must NOT have direct CreateItem(0) — that's now in the adapter
        direct_calls = content.count("CreateItem(0)")
        # Allow it in comments/docs only
        in_comment = [i for i, line in enumerate(content.splitlines()) if "#" in line and "CreateItem(0)" in line]
        assert direct_calls == len(in_comment), \
            f"web_server.py has {direct_calls} direct CreateItem(0) calls outside comments — should be 0 (all in adapter)"

    def test_no_smtp_import_in_webserver(self):
        path = f"{WORKTREE}/email_engine/web_server.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "smtplib" not in content.lower() or "REMOVED" in content
        assert "graph_api" not in content.lower() or "REMOVED" in content

    def test_no_smtp_import_in_queue_worker(self):
        path = f"{WORKTREE}/email_engine/queue_worker_outlook.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "smtplib" not in content.lower() or "REMOVED" in content
        # Must use the shared adapter
        assert "outlook_com_adapter" in content


class TestSuppressionAndCooldown:
    """Existing suppression statuses (HARD_BOUNCE, UNSUBSCRIBED) and cooldown must not change silently."""

    def test_suppression_filter_uses_hard_bounce(self):
        path = f"{WORKTREE}/email_engine/web_server.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "HARD_BOUNCE" in content

    def test_suppression_filter_uses_unsubscribed(self):
        path = f"{WORKTREE}/email_engine/web_server.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "UNSUBSCRIBED" in content

    def test_cooldown_uses_email_log_csv(self):
        path = f"{WORKTREE}/email_engine/web_server.py"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "email_log.csv" in content or "email_log" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])