#!/usr/bin/env python3
"""Regression tests: harness routing matches workflow/SKILL.md."""
import re, os, yaml

HARNESS = "D:/NELSON/2. Areas/Engine_test/harness/harness-config.yaml"

def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def test_judgment_phases_use_commander():
    """design-finder, ux-reviewer, code-reviewer, security-auditor, perf-analyzer, tech-debt-tracker use commander."""
    data = load_yaml(HARNESS)
    judgment_roles = ["design-finder", "ux-reviewer", "code-reviewer",
                      "security-auditor", "perf-analyzer", "tech-debt-tracker"]
    for phase in data["phases"]:
        if phase["name"] in judgment_roles:
            assert phase["model"] == "commander", \
                f"{phase['name']} should use 'commander' but uses '{phase['model']}'"

def test_mechanical_phases_use_executor():
    """master-executor, test-writer, doc-writer, git-commit use executor."""
    data = load_yaml(HARNESS)
    mechanical_roles = ["master-executor", "test-writer", "doc-writer", "git-commit"]
    for phase in data["phases"]:
        if phase["name"] in mechanical_roles:
            assert phase["model"] == "executor", \
                f"{phase['name']} should use 'executor' but uses '{phase['model']}'"

def test_routing_default_policy_set():
    """harness has routing.default_policy = workflow."""
    data = load_yaml(HARNESS)
    assert "routing" in data, "Missing routing section"
    assert data["routing"].get("default_policy") == "workflow", \
        f"default_policy should be 'workflow', got {data['routing']}"

def test_all_m2_override_false():
    """all_m2_override is false."""
    data = load_yaml(HARNESS)
    assert data["routing"].get("all_m2_override") == False, \
        "all_m2_override should be false"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])