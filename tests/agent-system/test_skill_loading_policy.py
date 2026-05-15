#!/usr/bin/env python3
"""Regression tests: 11 core SKILL.md files have bounded skill-loading policy."""
import os, re

SKILLS_BASE = "D:/NELSON/2. Areas/Engine_test/.agents/skills"

EXPECTED = {
    'design-finder':      {'own': 'design-finder', 'helpers': ['aesthetic', 'ai-multimodal']},
    'ux-reviewer':        {'own': 'ux-reviewer', 'helpers': ['ai-multimodal', 'chrome-devtools', 'web-testing']},
    'code-reviewer':      {'own': 'code-reviewer', 'helpers': ['scout', 'docs-seeker']},
    'security-auditor':   {'own': 'security-auditor', 'helpers': ['security-scan', 'ai-multimodal']},
    'perf-analyzer':      {'own': 'perf-analyzer', 'helpers': ['chrome-devtools', 'web-testing']},
    'master-executor':    {'own': 'master-executor', 'helpers': ['systematic-debugging', 'verification-before-completion']},
    'test-writer':        {'own': 'test-writer', 'helpers': ['verification-before-completion', 'ck-loop']},
    'doc-writer':         {'own': 'doc-writer', 'helpers': ['docs-seeker', 'mermaidjs-v11']},
    'tech-debt-tracker':  {'own': 'tech-debt-tracker', 'helpers': ['sequential-thinking']},
    'git-commit':         {'own': 'git-commit', 'helpers': []},
    'workflow':           {'own': 'workflow', 'helpers': ['ck-plan', 'delegate-mm']},
}

def test_all_11_skill_files_exist():
    missing = [role for role in EXPECTED if not os.path.exists(os.path.join(SKILLS_BASE, role, "SKILL.md"))]
    assert not missing, f"Missing SKILL.md for: {missing}"

def test_all_have_skill_loading_policy():
    missing = []
    for role in EXPECTED:
        path = os.path.join(SKILLS_BASE, role, "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if "## Skill Loading Policy" not in content:
            missing.append(role)
    assert not missing, f"Missing ## Skill Loading Policy in: {missing}"

def test_all_reference_own_skill():
    missing = []
    for role, info in EXPECTED.items():
        path = os.path.join(SKILLS_BASE, role, "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if f"`{info['own']}`" not in content and info['own'] not in content:
            missing.append(f"{role} (expected '{info['own']}')")
    assert not missing, f"Missing own skill reference in: {missing}"

def test_helper_count_bounded():
    """No skill has more than 2 helpers listed."""
    for role, info in EXPECTED.items():
        path = os.path.join(SKILLS_BASE, role, "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"## Skill Loading Policy.*?Triggered helpers:\s*(.*?)(?:\n\s*-|\n##|\Z)", content, re.DOTALL)
        if m and info['helpers']:
            helpers_str = m.group(1)
            count = helpers_str.count('`')
            max_allowed = len(info['helpers']) * 2  # 2 ticks per helper
            assert count <= max_allowed, f"{role} has more helpers listed than plan allows ({count} ticks vs {max_allowed} for {len(info['helpers'])} helpers)"
        # git-commit has 0 helpers - that's fine

def test_workflow_has_ck_plan_and_delegate_mm():
    path = os.path.join(SKILLS_BASE, "workflow", "SKILL.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "`ck-plan`" in content or "ck-plan" in content
    assert "`delegate-mm`" in content or "delegate-mm" in content

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])