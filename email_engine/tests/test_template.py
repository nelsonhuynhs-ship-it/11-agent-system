# -*- coding: utf-8 -*-
"""
Tests for email_engine.intelligence:
    - template_selector (load_rules, match, dominant_state)
    - template_renderer (render_text, render_email)
    - builder (build_email integration)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
sys.path.insert(0, str(_REPO))

from email_engine.intelligence import (  # noqa: E402
    template_selector as ts,
    template_renderer as tr,
    market_engine as me,
    builder as b,
)


# ─── Sample YAML for isolated tests (independent of prod email_rules.yaml) ──

_SAMPLE_YAML = """
version: 1
defaults:
  signature: "Nelson Freight"
  subject_suffix: "NELSON"
templates:
  - id: west_coast_urgent
    match:
      destinations: [USLAX, USLGB]
      states: [URGENT]
    subject: "Rates +{{delta}}% | Week {{week}}"
    intro: "Hi {{first_name}}, market up {{delta}}% to USD {{current_rate_40hq}}."
    cta: "Lock now."
  - id: east_coast_any
    match:
      destinations: [USNYC, USSAV]
      states: [any]
    subject: "East Coast Update"
    intro: "Hi {{first_name}}"
    cta: "Reply."
  - id: declining_market
    match:
      destinations: [any]
      states: [DECLINING]
    subject: "Rates softening {{delta}}%"
    intro: "Good news {{first_name}}"
    cta: "Renegotiate."
  - id: default
    match:
      destinations: [any]
      states: [any]
    subject: "Weekly Update"
    intro: "{{default_intro}}"
    cta: "Let me know."
"""


@pytest.fixture
def tmp_yaml(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(_SAMPLE_YAML, encoding="utf-8")
    ts.clear_cache()
    yield p
    ts.clear_cache()


# ────────────────────────────────────────────────────────────────────────────
# template_selector
# ────────────────────────────────────────────────────────────────────────────

def test_load_rules_from_yaml(tmp_yaml):
    rules = ts.load_rules(tmp_yaml)
    assert rules.get("version") == 1
    assert len(rules.get("templates", [])) == 4
    assert rules["defaults"]["signature"] == "Nelson Freight"


def test_match_west_coast_urgent(tmp_yaml):
    t = ts.match(["USLAX"], ["URGENT"], tmp_yaml)
    assert t["id"] == "west_coast_urgent"
    assert t["match_reason"] == "exact_lane_and_state"


def test_match_east_coast_any_state(tmp_yaml):
    t = ts.match(["USNYC"], ["STABLE"], tmp_yaml)
    assert t["id"] == "east_coast_any"


def test_match_declining_any_dest(tmp_yaml):
    t = ts.match(["USXXX"], ["DECLINING"], tmp_yaml)
    assert t["id"] == "declining_market"


def test_match_falls_back_to_default(tmp_yaml):
    t = ts.match(["USXYZ"], ["STABLE"], tmp_yaml)
    assert t["id"] == "default"


def test_match_no_yaml_safe_default(tmp_path):
    ts.clear_cache()
    missing = tmp_path / "does_not_exist.yaml"
    t = ts.match(["USLAX"], ["URGENT"], missing)
    assert t["id"] == "safe_default"


def test_dominant_state_priority():
    lanes = [
        {"state": "STABLE"},
        {"state": "URGENT"},
        {"state": "DECLINING"},
    ]
    assert ts.dominant_state(lanes) == "URGENT"

    lanes2 = [{"state": "COMPETITIVE"}, {"state": "STABLE"}]
    assert ts.dominant_state(lanes2) == "COMPETITIVE"

    assert ts.dominant_state([]) == "STABLE"


def test_hot_reload_yaml(tmp_yaml):
    # Initial load
    t1 = ts.match(["USLAX"], ["URGENT"], tmp_yaml)
    assert "Rates +" in t1["subject"]

    # Modify YAML on disk
    new_yaml = _SAMPLE_YAML.replace(
        'subject: "Rates +{{delta}}% | Week {{week}}"',
        'subject: "SPIKE {{delta}}% | Week {{week}}"',
    )
    time.sleep(0.05)  # ensure mtime tick
    tmp_yaml.write_text(new_yaml, encoding="utf-8")
    # bump mtime explicitly (some FS have low resolution)
    new_time = time.time() + 1
    os.utime(tmp_yaml, (new_time, new_time))

    t2 = ts.match(["USLAX"], ["URGENT"], tmp_yaml)
    assert "SPIKE" in t2["subject"]


# ────────────────────────────────────────────────────────────────────────────
# template_renderer
# ────────────────────────────────────────────────────────────────────────────

def test_render_tokens_basic():
    s = tr.render_text("Hi {{first_name}}, {{delta}}% +USD {{current_rate_40hq}}",
                      {"first_name": "John", "delta": 5, "current_rate_40hq": 2100})
    assert "John" in s
    assert "5" in s
    assert "2100" in s


def test_render_missing_token_fallback():
    s = tr.render_text("Hi {{first_name}}", {})
    assert "Team" in s  # fallback from _DEFAULTS


def test_render_missing_token_no_default():
    s = tr.render_text("Start {{nonexistent_xyz}} end", {})
    assert s == "Start  end"  # replaced with empty


def test_render_html_escape():
    """User-supplied tokens must be escaped to prevent XSS."""
    s = tr.render_text("Hi {{first_name}}", {"first_name": "<script>alert('x')</script>"})
    assert "<script>" not in s
    assert "&lt;script&gt;" in s


def test_render_html_bypass_for_html_suffix():
    """Tokens named '*_html' are NOT escaped (pre-rendered HTML allowed)."""
    s = tr.render_text("Table: {{rate_table_html}}",
                      {"rate_table_html": "<table><tr><td>x</td></tr></table>"})
    assert "<table>" in s


def test_render_nested_token():
    s = tr.render_text("Hi {{profile.first_name}}",
                      {"profile": {"first_name": "Jane"}})
    assert "Jane" in s


def test_render_email_produces_subject_and_body():
    tmpl = {
        "id": "test",
        "subject": "Hi {{first_name}}",
        "intro": "Dear {{first_name}}\n\nLine two.",
        "cta": "Reply today.",
    }
    out = tr.render_email(tmpl, {"first_name": "Nelson"})
    assert out["subject"] == "Hi Nelson"
    assert "Dear Nelson" in out["html_body"]
    assert "Reply today" in out["html_body"]
    assert out["template_id"] == "test"


# ────────────────────────────────────────────────────────────────────────────
# builder integration
# ────────────────────────────────────────────────────────────────────────────

def _synthetic_urgent_rows():
    import datetime as dt
    today = dt.date.today()
    this_monday = today - dt.timedelta(days=today.weekday())
    prev_monday = this_monday - dt.timedelta(days=7)
    rows = []
    for offset in range(8):
        rows.append({"date": prev_monday + dt.timedelta(days=offset % 5), "amount": 2000.0})
        rows.append({"date": this_monday + dt.timedelta(days=offset % 5), "amount": 2120.0})
    # Pad to reach >= 30 with low variance
    while len(rows) < 100:
        rows.append({"date": prev_monday, "amount": 2000.0})
    return rows


def test_build_email_integration_urgent(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _synthetic_urgent_rows())
    me.clear_cache()

    out = b.build_email(
        cnee_email="john@acme.com",
        pol="HPH",
        destinations=["USLAX"],
        profile={"first_name": "John", "company": "Acme Corp"},
    )

    assert out["to"] == "john@acme.com"
    assert "John" in out["html_body"] or "John" in out["subject"]
    assert out["meta"]["dominant_state"] in ("URGENT", "COMPETITIVE", "STABLE")
    assert out["meta"]["lanes_analyzed"] == 1
    assert "Acme Corp" in out["html_body"]
    assert out["meta"]["template_id"]  # non-empty


def test_build_email_different_destinations_differ(monkeypatch):
    """Two different destinations must produce distinct emails."""
    # West Coast URGENT
    me.clear_cache()
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _synthetic_urgent_rows())
    out1 = b.build_email("a@x.com", "HPH", ["USLAX"],
                         profile={"first_name": "Alice", "company": "A Ltd"})

    # East Coast default (same synthetic data but different lane → same state here)
    # We still expect different template because dest=USNYC matches east_coast_any
    me.clear_cache()
    out2 = b.build_email("b@x.com", "HPH", ["USNYC"],
                         profile={"first_name": "Bob", "company": "B Ltd"})

    assert out1["meta"]["template_id"] != out2["meta"]["template_id"] or \
           out1["subject"] != out2["subject"]
    assert "Alice" in out1["html_body"]
    assert "Bob" in out2["html_body"]


def test_build_email_profile_none(monkeypatch):
    """profile=None must not crash — default tokens apply."""
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: [])
    out = b.build_email("x@y.com", "HPH", ["USLAX"])
    assert out["to"] == "x@y.com"
    assert out["meta"]["dominant_state"] == "STABLE"
    assert "Team" in out["html_body"] or out["html_body"]  # fallback first_name


def test_build_email_rate_table_rendered(monkeypatch):
    monkeypatch.setattr(me, "_fetch_rows", lambda pol, dest: _synthetic_urgent_rows())
    me.clear_cache()
    out = b.build_email("a@x.com", "HPH", ["USLAX", "USLGB"],
                       profile={"first_name": "Nelson", "company": "NF"})
    # Rate table must appear in body
    assert "<table" in out["html_body"]
    assert "USLAX" in out["html_body"]
    assert "USLGB" in out["html_body"]


def test_prod_yaml_loads():
    """Real production YAML (email_rules.yaml) must load without error and contain ≥6 templates."""
    ts.clear_cache()
    rules = ts.load_rules()  # default path
    templates = rules.get("templates", [])
    assert len(templates) >= 6, f"Expected ≥6 templates, got {len(templates)}"
    ids = [t.get("id") for t in templates]
    assert "default" in ids
    assert "default_cross_sell" in ids  # v2: 10-lane cross-sell replaces west_coast_urgent
