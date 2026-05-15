#!/usr/bin/env python3
"""Phase 5 tests: workflow state machine in harness-config.yaml."""
import pytest, yaml

CONFIG = "D:/NELSON/2. Areas/Engine_test/harness/harness-config.yaml"

REQUIRED_STATES = {"PLAN", "SCOUT", "REVIEW", "EXECUTE", "VERIFY", "OBSERVE", "RETRY", "STOP"}
REQUIRED_TRANSITIONS = {
    "STOP": [],
    "RETRY": ["EXECUTE", "STOP"],
}
REQUIRED_HANDOFF_FIELDS = ["trace_id", "task_id", "phase", "role",
                            "input_files", "output_report", "verification_command", "status", "needs_verification"]

def test_required_states_exist():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    states = set(wsm.get("states", []))
    for s in REQUIRED_STATES:
        assert s in states, f"Missing required state: {s}"

def test_stop_state_has_no_outgoing_transitions():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    transitions = wsm.get("transitions", {})
    assert transitions.get("STOP") == [], "STOP must have no outgoing transitions"

def test_retry_only_goes_to_execute_or_stop():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    transitions = wsm.get("transitions", {})
    retry_targets = set(transitions.get("RETRY", []))
    assert retry_targets <= {"EXECUTE", "STOP"}, \
        f"RETRY can only go to EXECUTE or STOP, got: {retry_targets}"

def test_handoff_payload_required_fields():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    handoff = wsm.get("handoff_payload", {})
    fields = handoff.get("required_fields", [])
    for f in REQUIRED_HANDOFF_FIELDS:
        assert f in fields, f"Missing handoff field: {f}"

def test_retry_policy_bounded():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    rp = wsm.get("retry_policy", {})
    assert rp.get("max_retries_per_agent", 0) >= 1
    assert rp.get("max_total_workflow_retries", 0) >= 1
    assert "require_degraded_mode_marker" in rp

def test_all_states_have_transition_entries():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    states = set(wsm.get("states", []))
    transitions = wsm.get("transitions", {})
    for s in states:
        assert s in transitions, f"State {s} has no transition entry"

def test_no_transition_points_to_unknown_state():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    wsm = cfg.get("workflow_state_machine", {})
    states = set(wsm.get("states", []))
    transitions = wsm.get("transitions", {})
    for src, targets in transitions.items():
        for t in targets:
            assert t in states, f"Transition from {src} points to unknown state: {t}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])