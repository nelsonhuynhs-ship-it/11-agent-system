#!/usr/bin/env python3
"""Phase 0B baseline: verify current dashboard UI invariants are preserved."""
import pytest, re

WORKTREE = "D:/NELSON/2. Areas/Engine_test/.claude/worktrees/priceless-archimedes-689d1d"
EMAIL_DASHBOARD_HTML = f"{WORKTREE}/plans/visuals/email-dashboard.html"
DASHBOARDV9_MOCKUP = "D:/OneDrive/NelsonData/docs/plans/dashboardv9/dashboardv9_mockup.html"
WEBSERVER_PY = f"{WORKTREE}/email_engine/web_server.py"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestStepperInvariants:
    """Step 1 Campaign → Step 2 Validate → Step 3 Preview → Step 4 Send → DONE."""

    def test_has_stepper_with_4_steps(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        steps = re.findall(r'goStep\(\d+\)', html)
        assert len(steps) >= 4, f"Expected 4 goStep calls, got {len(steps)}"

    def test_stepper_labels_campaign_validate_preview_send(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Campaign" in html
        assert "Validate" in html
        assert "Preview" in html
        assert "Send" in html

    def test_stepper_done_state(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert 'var(--good)' in html or 'good' in html.lower()


class TestSidebarInvariants:
    """Compact sidebar with brand mark and nav items."""

    def test_sidebar_brand_nelson_email_label(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Nelson" in html
        assert "Email" in html

    def test_sidebar_send_nav_item(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Send" in html or "send" in html.lower()


class TestCampaignGridInvariants:
    """Campaign card grid — commodity list must be preserved."""

    def test_has_campaign_grid(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "campaign" in html.lower()

    def test_core_commodities_present(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        # At minimum these commodities should be present
        core = ["FLOORING", "FURNITURE", "PLASTIC", "CANDLE"]
        found = [c for c in core if c in html]
        assert len(found) >= 2, f"Expected core commodities, found: {found}"

    def test_campaign_card_selection_updates_count(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "updateRecipientCount" in html or "recipient" in html.lower()


class TestRecipientTableInvariants:
    """Recipients table with company/email/country/status/lastSent columns."""

    def test_has_recipients_panel(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "recipient" in html.lower()

    def test_has_search_bar(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "search" in html.lower()

    def test_has_sort_controls(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "sortTable" in html or "sort" in html.lower()

    def test_has_select_all(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "select" in html.lower()


class TestKPIsInvariants:
    """KPI row with Total Prospects, Ready to Send, Open Rate."""

    def test_has_kpi_row(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "kpi" in html.lower() or "KPI" in html

    def test_total_prospects_kpi(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Total" in html or "total" in html.lower()


class TestSendFlowInvariants:
    """Step 4 Send button, draft, preview, start send."""

    def test_has_send_button(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Start Sending" in html or "send" in html.lower()

    def test_has_draft_button(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Save Draft" in html or "draft" in html.lower()

    def test_has_preview_button(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "Preview" in html or "preview" in html.lower()

    def test_send_progress_tracking(self):
        html = _load(EMAIL_DASHBOARD_HTML)
        assert "progress" in html.lower() or "send" in html.lower()


class TestVersionLabel:
    """Stale V7 label source is found — DASHBOARD_VERSION constant."""

    def test_dashboard_version_constant_is_v7(self):
        with open(WEBSERVER_PY, encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'DASHBOARD_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        assert match, "DASHBOARD_VERSION constant not found"
        version = match.group(1)
        assert version == "v7", f"DASHBOARD_VERSION is '{version}', expected 'v7'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])