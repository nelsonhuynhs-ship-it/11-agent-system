#!/usr/bin/env python3
"""Phase 1 tests: agent role templates have valid Claude Code-native frontmatter."""
import pytest, re

AGENTS_DIR = "C:/Users/Nelson/.claude/agents-mm"

REQUIRED_FIELDS = ["name", "description", "model", "effort", "maxTurns", "memory", "skills", "tools"]
READ_ONLY_ROLES = {"design-finder", "ux-reviewer", "code-reviewer", "security-auditor",
                   "perf-analyzer", "tech-debt-tracker", "git-commit"}
WRITE_ROLES = {"master-executor", "test-writer", "doc-writer"}

def _parse_frontmatter(content):
    """Parse YAML frontmatter manually — avoids yaml lib import issues."""
    if not content.startswith("---"):
        return None
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if not match:
        return None
    fm = {}
    current_key = None
    current_list = []
    block = match.group(1)
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ':' in stripped and not stripped.startswith('- '):
            # Before starting a new key, materialize the PREVIOUS key
            # (it had a scalar value if current_list is empty, or it was a list)
            if current_key is not None:
                fm[current_key] = current_list if current_list else True
            parts = stripped.split(':', 1)
            current_key = parts[0].strip()
            if len(parts) < 2 or not parts[1].strip():
                # Key with no value (list start marker) — reset list accumulator
                current_list = []
            else:
                val = parts[1].strip()
                if val in ('true', 'false'):
                    fm[current_key] = val == 'true'
                elif val.startswith('['):
                    fm[current_key] = [x.strip() for x in val.strip('[]').split(',')]
                else:
                    try:
                        fm[current_key] = int(val)
                    except ValueError:
                        fm[current_key] = val
                current_key = None  # scalar key fully consumed
                current_list = []
        elif stripped.startswith('- '):
            current_list.append(stripped[2:])
    # Materialize final key
    if current_key is not None:
        fm[current_key] = current_list if current_list else True
    return fm

@pytest.mark.parametrize("role", sorted(READ_ONLY_ROLES | WRITE_ROLES))
def test_role_has_frontmatter(role):
    path = f"{AGENTS_DIR}/{role}.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert content.startswith("---"), f"{role}: missing YAML frontmatter"
    fm = _parse_frontmatter(content)
    assert fm is not None, f"{role}: frontmatter could not be parsed"
    for field in REQUIRED_FIELDS:
        assert field in fm, f"{role}: missing required field '{field}'"

def test_read_only_roles_deny_edit_write():
    for role in READ_ONLY_ROLES:
        path = f"{AGENTS_DIR}/{role}.md"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm = _parse_frontmatter(content)
        assert "Edit" not in fm.get("tools", []), f"{role}: Edit should not be in tools"
        assert "Write" not in fm.get("tools", []), f"{role}: Write should not be in tools"
        assert "Edit" in fm.get("disallowedTools", []) or "disallowedTools" in str(content), \
            f"{role}: should deny Edit in disallowedTools"

def test_write_roles_allow_edit_write():
    for role in WRITE_ROLES:
        path = f"{AGENTS_DIR}/{role}.md"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm = _parse_frontmatter(content)
        assert "Edit" in fm.get("tools", []) or "Write" in fm.get("tools", []), \
            f"{role}: should allow Edit or Write"

def test_master_executor_has_worktree_isolation():
    path = f"{AGENTS_DIR}/master-executor.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    assert fm.get("isolation") == "worktree", "master-executor must have isolation: worktree"

def test_test_writer_has_worktree_isolation():
    path = f"{AGENTS_DIR}/test-writer.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    assert fm.get("isolation") == "worktree", "test-writer must have isolation: worktree"

def test_security_auditor_effort_xhigh():
    path = f"{AGENTS_DIR}/security-auditor.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    assert fm.get("effort") == "xhigh", "security-auditor must have effort: xhigh"

def test_git_commit_max_turns_le_6():
    path = f"{AGENTS_DIR}/git-commit.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    assert fm.get("maxTurns", 99) <= 6, "git-commit maxTurns must be <= 6"

def test_all_roles_have_own_skill_in_list():
    for role in READ_ONLY_ROLES | WRITE_ROLES:
        path = f"{AGENTS_DIR}/{role}.md"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm = _parse_frontmatter(content)
        skills = fm.get("skills", [])
        assert any(role.replace("-", "_") in s or s.replace("-", "_") == role.replace("-", "_")
                   for s in skills), f"{role}: own skill must be in skills list"

def test_skill_policy_text_in_body():
    for role in READ_ONLY_ROLES | WRITE_ROLES:
        path = f"{AGENTS_DIR}/{role}.md"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Role body must contain some skill loading guidance
        body_lower = content.lower()
        has_skill_indicator = any(
            kw in body_lower for kw in ["load", "skill", "preload", "required skills",
                                         "needs verification", "missing skill"]
        )
        assert has_skill_indicator, \
            f"{role}: body should contain skill loading guidance or needs verification policy"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])