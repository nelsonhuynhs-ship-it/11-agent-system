"""
test_milestone_smoke.py — 6 smoke scenarios for cnee_milestone.py

These tests simulate the security + logic gates WITHOUT touching
real Outlook or ERP (uses mocks where COM access required).

Scenarios:
    T1: Valid ATD mail → compose should succeed (mocked Outlook)
    T2: Same mail again → dedup hit, 0 drafts
    T3: Mail with "VESSEL CHANGE" → blacklist rejection
    T4: Mail missing Auth-Results → reject
    T5: Mail with 5 Bkg → bulk rejection
    T6: Kill switch file exists → abort immediately

Run:
    C:/Users/Nelson/anaconda3/python scripts/test_milestone_smoke.py

All scenarios print PASS or FAIL. Exit code 0 if all pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import email_engine.core.cnee_milestone as cm

# Force UTF-8 output on Windows console (avoids cp1258 encoding errors)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, str, str]] = []


def _make_mock_mail(
    subject: str = "ATD Update — Vessel Departed",
    body: str = "Update ATD// 20/04/2026\nBKG SGNG47156900\nloaded on board",
    sender: str = "ops@pudongprime.vn",
    auth_pass: bool = True,
    entry_id: str = "mock-entry-123",
) -> MagicMock:
    """Build a minimal mock Outlook MailItem."""
    mail = MagicMock()
    mail.Subject = subject
    mail.Body = body
    mail.ReceivedTime = datetime(2026, 4, 20, 10, 0)
    mail.EntryID = entry_id

    # Auth-Results header mock
    if auth_pass:
        auth_header = (
            "Authentication-Results: mx.server.com;\n"
            "  spf=pass; dkim=pass; dmarc=pass"
        )
    else:
        auth_header = (
            "Authentication-Results: mx.server.com;\n"
            "  spf=fail; dkim=none"
        )
    mail.PropertyAccessor.GetProperty.return_value = auth_header
    return mail


def _make_identifiers(bkg_list: list[str]) -> dict:
    return {"HBL": [], "BKG": bkg_list, "CTN": []}


def _reset_module_state(tmp_path: Path):
    """Point module state files to tmp_path for isolation."""
    cm.KILL_SWITCH = tmp_path / "AUTO_NOTIFY_DISABLED"
    cm.STATE_FILE = tmp_path / "milestone_state.jsonl"
    cm.DAILY_COUNTER = tmp_path / "milestone_daily.json"
    cm._telegram_lines = []


def run_scenario(name: str, fn) -> bool:
    try:
        fn()
        results.append((name, PASS, ""))
        print(f"{PASS} {name}")
        return True
    except AssertionError as e:
        results.append((name, FAIL, str(e)))
        print(f"{FAIL} {name}: {e}")
        return False
    except Exception as e:
        results.append((name, FAIL, f"Exception: {e}"))
        print(f"{FAIL} {name}: {type(e).__name__}: {e}")
        return False


# ─── Scenario T1: Happy path — valid ATD, mocked Outlook ───────────────────

def t1_valid_atd():
    """Valid ATD mail from allowed sender → should reach Outlook draft creation."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        mail = _make_mock_mail(auth_pass=True)
        ids = _make_identifiers(["SGNG47156900"])
        sender = "ops@pudongprime.vn"

        # Allowlist the sender
        original_allowlist = cm.OPS_ALLOWLIST.copy()
        cm.OPS_ALLOWLIST.add(sender)

        # Mock CRM + Active Jobs reads to return opt-in data
        mock_job = {
            "CUSTOMER": "SORACHI",
            "BKG_NO": "SGNG47156900",
            "HBL_NO": "PYTO26010027",
            "ETD": "2026-04-02",
            "ETA": "2026-04-28",
            "ETA_DATE": "",
            "EMAIL": "buyer@sorachi.com",
            "CARRIER": "ONE",
            "POL-POD": "HCM-TACOMA",
            "FINAL DEST": "TACOMA",
        }

        drafted = []

        def fake_create_draft(to_list, tmpl_type, ctx):
            drafted.append((to_list, tmpl_type, ctx))
            return True

        with (
            patch.object(cm, "_find_active_job", return_value=mock_job),
            patch.object(cm, "_crm_auto_notify", return_value=True),
            patch.object(cm, "_lookup_cnee_emails", return_value=["buyer@sorachi.com"]),
            patch.object(cm, "_create_outlook_draft_polite", side_effect=fake_create_draft),
        ):
            result = cm.on_atd_detected(mail, ["ATD"], ids, sender)

        cm.OPS_ALLOWLIST.discard(sender)
        cm.OPS_ALLOWLIST.update(original_allowlist)

        assert result is True, f"Expected True, got {result}"
        assert len(drafted) == 1, f"Expected 1 draft, got {len(drafted)}"
        # Verify sidecar written
        assert tmp_path.joinpath("milestone_state.jsonl").exists(), "Sidecar not written"
        lines = tmp_path.joinpath("milestone_state.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["bkg"] == "SGNG47156900"
        assert entry["type"] == "ATD"


# ─── Scenario T2: Dedup — second run returns 0 drafts ──────────────────────

def t2_dedup():
    """Second scan for same BKG/ATD → dedup fires, 0 new drafts."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        # Pre-populate state
        entry = json.dumps({"ts": "2026-04-20T10:00:00", "bkg": "SGNG47156900",
                             "type": "ATD", "date": "2026-04-20", "mail_entry_id": "x"})
        tmp_path.joinpath("milestone_state.jsonl").write_text(entry + "\n")

        # Verify dedup hits
        result = cm._already_notified("SGNG47156900", "ATD")
        assert result is True, f"Expected dedup=True, got {result}"


# ─── Scenario T3: Blacklist — VESSEL CHANGE → skip ─────────────────────────

def t3_blacklist():
    """Mail containing VESSEL CHANGE → blacklist fires, no draft."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        mail = _make_mock_mail(
            subject="RE: VESSEL CHANGE NOTICE — SGNG47156900",
            body="We regret to inform that the vessel has been changed.\nBKG SGNG47156900",
        )
        ids = _make_identifiers(["SGNG47156900"])
        sender = "ops@pudongprime.vn"

        original_allowlist = cm.OPS_ALLOWLIST.copy()
        cm.OPS_ALLOWLIST.add(sender)

        # Blacklist should fire before draft attempt
        draft_calls = []
        with patch.object(cm, "_create_outlook_draft_polite",
                          side_effect=lambda *a, **kw: draft_calls.append(a) or True):
            result = cm.on_atd_detected(mail, ["CHANGE_VESSEL"], ids, sender)

        cm.OPS_ALLOWLIST.discard(sender)
        cm.OPS_ALLOWLIST.update(original_allowlist)

        assert result is False, f"Expected False (blacklisted), got {result}"
        assert len(draft_calls) == 0, f"Draft should not be called, got {len(draft_calls)}"


# ─── Scenario T4: Auth-Results missing/fail → reject ────────────────────────

def t4_auth_fail():
    """Mail with bad/missing Auth-Results → rejected, 0 drafts."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        mail = _make_mock_mail(auth_pass=False)  # spf=fail, dkim=none
        ids = _make_identifiers(["SGNG47156900"])
        sender = "ops@pudongprime.vn"

        original_allowlist = cm.OPS_ALLOWLIST.copy()
        cm.OPS_ALLOWLIST.add(sender)

        result = cm.on_atd_detected(mail, ["ATD"], ids, sender)

        cm.OPS_ALLOWLIST.discard(sender)
        cm.OPS_ALLOWLIST.update(original_allowlist)

        assert result is False, f"Expected False (auth fail), got {result}"


# ─── Scenario T5: Bulk mail — 5 Bkg → reject ────────────────────────────────

def t5_bulk_reject():
    """Mail with 5 Bkg numbers → bulk detection, 0 drafts."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        mail = _make_mock_mail(auth_pass=True)
        bulk_bkgs = ["BKG0001", "BKG0002", "BKG0003", "BKG0004", "BKG0005"]
        ids = _make_identifiers(bulk_bkgs)
        sender = "ops@pudongprime.vn"

        original_allowlist = cm.OPS_ALLOWLIST.copy()
        cm.OPS_ALLOWLIST.add(sender)

        result = cm.on_atd_detected(mail, ["ATD"], ids, sender)

        cm.OPS_ALLOWLIST.discard(sender)
        cm.OPS_ALLOWLIST.update(original_allowlist)

        assert result is False, f"Expected False (bulk), got {result}"
        # Telegram should have a bulk warning queued
        assert any("bulk" in line.lower() or "WARN" in line
                   for line in cm._telegram_lines), \
            f"Expected bulk warning in telegram, got: {cm._telegram_lines}"


# ─── Scenario T6: Kill switch → abort immediately ───────────────────────────

def t6_kill_switch():
    """Kill switch file present → on_atd_detected returns False immediately."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _reset_module_state(tmp_path)

        # Create kill switch
        cm.KILL_SWITCH.touch()
        assert cm.KILL_SWITCH.exists(), "Kill switch file should exist"

        mail = _make_mock_mail(auth_pass=True)
        ids = _make_identifiers(["SGNG47156900"])

        # Kill switch should fire before any other check
        draft_calls = []
        with patch.object(cm, "_create_outlook_draft_polite",
                          side_effect=lambda *a, **kw: draft_calls.append(a) or True):
            result = cm.on_atd_detected(mail, ["ATD"], ids, "ops@pudongprime.vn")

        assert result is False, f"Expected False (kill switch), got {result}"
        assert len(draft_calls) == 0, "Draft should not be created with kill switch"

        # Cleanup
        cm.KILL_SWITCH.unlink()


# ─── Main runner ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("CNEE Milestone Smoke Tests")
    print("=" * 60)
    print()

    scenarios = [
        ("T1: Valid ATD → draft created", t1_valid_atd),
        ("T2: Dedup → 0 drafts on second run", t2_dedup),
        ("T3: VESSEL CHANGE → blacklist skip", t3_blacklist),
        ("T4: Auth-Results fail → reject", t4_auth_fail),
        ("T5: 5 Bkg → bulk rejection", t5_bulk_reject),
        ("T6: Kill switch → abort", t6_kill_switch),
    ]

    all_pass = True
    for name, fn in scenarios:
        ok = run_scenario(name, fn)
        if not ok:
            all_pass = False

    print()
    print("=" * 60)
    passed = sum(1 for _, status, _ in results if status == PASS)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)

    sys.exit(0 if all_pass else 1)
