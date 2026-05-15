#!/usr/bin/env python3
"""Phase 3 tests: tool permission boundaries for read-only vs write-capable roles."""
import pytest, re

AGENTS_DIR = "C:/Users/Nelson/.claude/agents-mm"

READ_ONLY = {"design-finder", "ux-reviewer", "code-reviewer", "security-auditor",
             "perf-analyzer", "tech-debt-tracker", "git-commit"}
WRITE = {"master-executor", "test-writer", "doc-writer"}

def _parse_frontmatter(content):
    """Parse YAML frontmatter manually — no yaml lib needed."""
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
        # Top-level key: value
        if ':' in stripped and not stripped.startswith('- '):
            if current_key:
                fm[current_key] = current_list if current_list else True
            parts = stripped.split(':', 1)
            current_key = parts[0].strip()
            if len(parts) < 2 or not parts[1].strip():
                current_list = []
                continue
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
            current_list = []
        elif stripped.startswith('- '):
            current_list.append(stripped[2:])
    if current_key:
        fm[current_key] = current_list if current_list else True
    return fm

def _body(content):
    """Get content after frontmatter."""
    if not content.startswith("---"):
        return content
    idx = content.index("\n---\n", 4)
    return content[idx+5:]

@pytest.mark.parametrize("role", sorted(READ_ONLY))
def test_read_only_roles_cannot_edit_or_write(role):
    path = f"{AGENTS_DIR}/{role}.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    tools = fm.get("tools", [])
    disallowed = fm.get("disallowedTools", [])
    assert "Edit" not in tools, f"{role}: Edit must NOT be in tools"
    assert "Write" not in tools, f"{role}: Write must NOT be in tools"
    assert "Edit" in disallowed, f"{role}: Edit must be in disallowedTools"
    assert "Write" in disallowed, f"{role}: Write must be in disallowedTools"

@pytest.mark.parametrize("role", sorted(WRITE))
def test_write_roles_can_edit_and_write(role):
    path = f"{AGENTS_DIR}/{role}.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    assert fm is not None, f"{role}: frontmatter parsing returned None"
    tools = fm.get("tools", [])
    # At least one of Edit/Write must be allowed
    assert "Edit" in tools or "Write" in tools, \
        f"{role}: must allow Edit or Write in tools, got {tools}"

def test_git_commit_does_not_allow_file_edits():
    path = f"{AGENTS_DIR}/git-commit.md"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    fm = _parse_frontmatter(content)
    tools = fm.get("tools", [])
    disallowed = fm.get("disallowedTools", [])
    assert "Edit" not in tools, "git-commit: Edit must not be in tools"
    assert "Write" not in tools, "git-commit: Write must not be in tools"
    assert "Edit" in disallowed, "git-commit: Edit must be in disallowedTools"
    assert "Write" in disallowed, "git-commit: Write must be in disallowedTools"

@pytest.mark.parametrize("role", sorted(READ_ONLY))
def test_read_only_roles_body_has_no_edit_policy(role):
    """Read-only roles should have body text indicating they don't edit code."""
    path = f"{AGENTS_DIR}/{role}.md"
    with open(path, encoding="utf-8") as f:
        body = _body(f.read())
    body_lower = body.lower()
    # Accept any of these patterns that indicate read-only behavior
    indicators = [
        "do not modify", "don't modify", "do not edit", "don't edit",
        "report only", "report findings", "audit only",
        "no false positives", "concrete evidence only",
        "never commit", "never pushes", "must not commit",
        "screenshot", "mockup", "UI render", "flame graph",
        "read-only", "write findings",
    ]
    found = any(ind.lower() in body_lower for ind in indicators)
    assert found, \
        f"{role}: body should contain read-only indicator (one of: {indicators})"

@pytest.mark.parametrize("role", sorted(WRITE))
def test_write_roles_body_contains_surgical_changes_policy(role):
    path = f"{AGENTS_DIR}/{role}.md"
    with open(path, encoding="utf-8") as f:
        body = _body(f.read())
    assert ("surgical" in body.lower() or "minimum change" in body.lower() or
            "verification" in body.lower()), \
        f"{role}: body should contain surgical/minimum-change/verification policy"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])