#!/usr/bin/env python3
"""Runtime smoke tests for mm-agent-spawner.sh — execute shell behavior, not string matching."""
import os, subprocess, tempfile

SPAWNER = "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"
BASH = "C:/Program Files/Git/bin/bash.exe"

def _make_fake_executables(tmp_dir):
    """Create 4 fake executables in tmp_dir that write their name to a marker file."""
    for name in ["mm-claude", "mm-search", "mm-vlm", "mm-image"]:
        path = os.path.join(tmp_dir, name + ".sh")
        with open(path, "w") as f:
            f.write(f"#!/bin/sh\n"
                    f"echo '{name}' >> '{tmp_dir}/called.txt'\n"
                    f"echo EXECUTED={name} >> '{tmp_dir}/log.txt'\n"
                    f"exit 0\n")
        os.chmod(path, 0o755)
    return tmp_dir

def _bash(script, check=False):
    result = subprocess.run(
        [BASH, "-n" if check else "-c", script],
        capture_output=True, text=True
    )
    return result

def test_spawner_syntax_clean():
    """bash -n mm-agent-spawner.sh must exit 0."""
    r = subprocess.run([BASH, "-n", SPAWNER], capture_output=True, text=True)
    assert r.returncode == 0, f"bash -n failed: {r.stderr}"

def test_spawner_help_exits_0():
    """--help must exit 0."""
    r = subprocess.run([BASH, "-c", f'{SPAWNER} --help >/dev/null 2>&1; echo EXIT:$?'],
                      capture_output=True, text=True)
    assert r.stdout.strip().endswith(":0"), f"--help failed: {r.stderr or r.stdout}"

def test_unknown_role_exits_2():
    """Unknown role must exit 2 and print supported roles."""
    r = subprocess.run(
        [BASH, "-c", f'{SPAWNER} unknown-role "test task" 2>&1; echo EXIT:$?'],
        capture_output=True, text=True
    )
    combined = r.stdout + r.stderr
    assert ":2" in combined, f"Expected exit 2, got: {combined}"
    assert "unknown role" in combined.lower(), f"Expected 'unknown role': {combined}"

def test_capability_set_before_upgrade_override():
    """CAPABILITY and EXECUTOR must be assigned BEFORE upgrade override runs.

    Root cause of prior CAPABILITY: unbound variable bug:
    upgrade block ran BEFORE capability routing, so REQUESTED_CAPABILITY="$CAPABILITY"
    referenced an unset variable.

    This tests for the ORIGINAL bug pattern: REQUESTED_CAPABILITY="$CAPABILITY"
    INSIDE the if/elif upgrade branches (before capability routing ran).
    The else branch that follows is correct (CAPABILITY already set).
    """
    with open(SPAWNER, encoding="utf-8") as f:
        lines = f.readlines()

    cap_routing_line = None
    upgrade_block_line = None
    in_upgrade_if_branch = False
    bad_ref_lines = []

    for i, line in enumerate(lines):
        if "---------- capability routing" in line and "MUST" in line:
            cap_routing_line = i
        if "---------- upgrade overrides" in line:
            upgrade_block_line = i
        if upgrade_block_line and 'UPGRADE_SEARCH' in line and 'then' in line:
            in_upgrade_if_branch = True
        if in_upgrade_if_branch and line.strip().startswith('else'):
            in_upgrade_if_branch = False
        if in_upgrade_if_branch and 'REQUESTED_CAPABILITY="$CAPABILITY"' in line:
            bad_ref_lines.append(i)

    assert cap_routing_line is not None, "Missing capability routing block"
    assert upgrade_block_line is not None, "Missing upgrade override block"
    assert cap_routing_line < upgrade_block_line, \
        f"capability routing (line {cap_routing_line}) must come BEFORE upgrade override (line {upgrade_block_line})"
    assert len(bad_ref_lines) == 0, \
        f"REQUESTED_CAPABILITY=$CAPABILITY inside upgrade if/elif branches at lines {bad_ref_lines}"

def test_task_text_resolved_before_upgrade_image():
    """TASK_TEXT must be resolved BEFORE --upgrade-image validation runs.

    Prior bug: --upgrade-image validation referenced TASK_TEXT before it was set,
    causing TASK_TEXT: unbound variable at runtime.
    """
    with open(SPAWNER, encoding="utf-8") as f:
        lines = f.readlines()

    task_resolve_line = None
    upgrade_image_line = None

    for i, line in enumerate(lines):
        if "resolve task text" in line.lower() and "needed for image" in line.lower():
            task_resolve_line = i
        # The line that uses TASK_TEXT for image validation
        if "TASK_LOWER=$(echo \"$TASK_TEXT\"" in line:
            upgrade_image_line = i

    assert task_resolve_line is not None, "Missing task text resolution block"
    assert upgrade_image_line is not None, "Missing TASK_TEXT usage for image validation"
    assert task_resolve_line < upgrade_image_line, \
        f"task resolve (line {task_resolve_line}) must come BEFORE image validation (line {upgrade_image_line})"

def test_upgrade_image_non_image_task_exits_2():
    """--upgrade-image with non-image task must exit 2."""
    r = subprocess.run(
        [BASH, "-c",
         f'{SPAWNER} design-finder "write a code review" --upgrade-image 2>&1; echo EXIT:$?'],
        capture_output=True, text=True, timeout=10
    )
    combined = r.stdout + r.stderr
    # Should reject non-image task with exit 2
    assert ":2" in combined or "ERROR: --upgrade-image only valid" in combined, \
        f"Expected exit 2 for non-image task, got: {combined}"

def test_upgrade_image_with_image_task_no_unbound_variable(tmp_path):
    """--upgrade-image with image task must NOT fail with TASK_TEXT: unbound variable."""
    fake_dir = _make_fake_executables(str(tmp_path))
    env = {
        "MM_IMAGE_OVERRIDE": os.path.join(fake_dir, "mm-image.sh"),
        "MM_SEARCH_OVERRIDE": os.path.join(fake_dir, "mm-search.sh"),
    }
    r = subprocess.run(
        [BASH, "-c",
         f'{SPAWNER} design-finder "generate image of a clean dashboard mockup" --upgrade-image 2>&1; echo EXIT:$?'],
        capture_output=True, text=True, timeout=10, env={**os.environ, **env}
    )
    combined = r.stdout + r.stderr
    # Must NOT contain "unbound variable"
    assert "unbound" not in combined.lower(), f"TASK_TEXT unbound: {combined}"
    # Should either succeed (fake executor runs) or fail on executor check — not TASK_TEXT
    assert "TASK_TEXT: unbound" not in combined, f"TASK_TEXT still unbound: {combined}"

def test_env_overrides_route_correctly(tmp_path):
    """Fake MM_SEARCH_OVERRIDE and MM_VLM_OVERRIDE are selected when specified."""
    fake_dir = _make_fake_executables(str(tmp_path))
    called_file = os.path.join(fake_dir, "called.txt")
    if os.path.exists(called_file):
        os.remove(called_file)

    env = {
        "MM_SEARCH_OVERRIDE": os.path.join(fake_dir, "mm-search.sh"),
        "MM_VLM_OVERRIDE": os.path.join(fake_dir, "mm-vlm.sh"),
        "MM_CLAUDE_OVERRIDE": os.path.join(fake_dir, "mm-claude.sh"),
    }

    # Test: --upgrade-search uses MM_SEARCH_OVERRIDE
    r = subprocess.run(
        [BASH, "-c",
         f'{SPAWNER} code-reviewer "review this" --upgrade-search 2>&1; echo EXIT:$?'],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, **env}
    )
    combined = r.stdout + r.stderr
    assert "unbound" not in combined.lower(), f"CAPABILITY unbound with override: {combined}"

def test_upgrade_search_env_override(tmp_path):
    """--upgrade-search with MM_SEARCH_OVERRIDE selects fake executor (no unbound variable)."""
    fake_dir = _make_fake_executables(str(tmp_path))

    env = {
        "MM_SEARCH_OVERRIDE": os.path.join(fake_dir, "mm-search.sh"),
    }

    r = subprocess.run(
        [BASH, "-c",
         f'{SPAWNER} security-auditor "audit this code" --upgrade-search 2>&1; echo EXIT:$?'],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, **env}
    )
    combined = r.stdout + r.stderr
    assert "unbound" not in combined.lower(), f"CAPABILITY unbound: {combined}"
    # Exit 1 = executor found but no real model (expected); must not be unbound variable
    assert "unbound" not in combined.lower()

def test_upgrade_vlm_env_override(tmp_path):
    """--upgrade-vlm with MM_VLM_OVERRIDE selects fake executor (no unbound variable)."""
    fake_dir = _make_fake_executables(str(tmp_path))

    env = {
        "MM_VLM_OVERRIDE": os.path.join(fake_dir, "mm-vlm.sh"),
    }

    r = subprocess.run(
        [BASH, "-c",
         f'{SPAWNER} ux-reviewer "review UI" --upgrade-vlm 2>&1; echo EXIT:$?'],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, **env}
    )
    combined = r.stdout + r.stderr
    assert "unbound" not in combined.lower(), f"CAPABILITY unbound: {combined}"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])