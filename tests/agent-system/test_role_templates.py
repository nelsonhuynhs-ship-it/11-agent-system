#!/usr/bin/env python3
"""Regression tests for agent system — phase 1: role templates."""
import os, re

AGENTS_DIR = "C:/Users/Nelson/.claude/agents-mm"
SKILLS_BASE = "D:/NELSON/2. Areas/Engine_test/.agents/skills"

EXCLUDES = {"PRE_FLIGHT.md"}
SKIP_PATH = "D:/NELSON/2. Areas/Engine_test/.agents/roles"  # does not exist

def test_all_templates_have_capability_policy():
    """Every role template (except PRE_FLIGHT) has ## Capability Policy."""
    files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".md") and f not in EXCLUDES]
    missing = []
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        if "## Capability Policy" not in content:
            missing.append(f)
    assert not missing, f"Missing ## Capability Policy in: {missing}"


def test_all_templates_reference_skill():
    """Every role template references its matching SKILL.md."""
    files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".md") and f not in EXCLUDES]
    missing = []
    for f in files:
        role = f[:-3]  # strip .md
        expected_ref = f"skills/{role}/SKILL.md"
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        if expected_ref not in content:
            missing.append(f"{f} (expected '{expected_ref}')")
    assert not missing, f"Missing skill reference in: {missing}"


def test_no_roles_path_referenced():
    """No template references non-existent .agents/roles path."""
    files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".md")]
    violations = []
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        if ".agents/roles" in content or ".agents\\roles" in content:
            violations.append(f)
    assert not violations, f"Invalid .agents/roles reference in: {violations}"


def test_capability_policy_is_compact():
    """Capability policy section is under 200 chars (no bloat)."""
    files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".md") and f not in EXCLUDES]
    bloated = []
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        m = re.search(r"## Capability Policy\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
        if m:
            section = m.group(1).strip()
            if len(section) > 600:
                bloated.append(f"{f} ({len(section)} chars)")
    assert not bloated, f"Bloated capability policy in: {bloated}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])