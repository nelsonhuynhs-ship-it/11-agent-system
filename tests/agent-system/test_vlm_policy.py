#!/usr/bin/env python3
"""Regression tests: VLM policy in role templates."""
import os

AGENTS_DIR = "C:/Users/Nelson/.claude/agents-mm"

def test_master_executor_includes_vlm_trigger():
    """master-executor includes UI/CSS/layout verification trigger."""
    path = os.path.join(AGENTS_DIR, "master-executor.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "--upgrade-vlm" in content or "VLM" in content or "screenshot" in content.lower(), \
        "master-executor missing VLM trigger"

def test_ux_review_includes_vlm():
    """ux-reviewer has VLM for screenshot/UI audit."""
    path = os.path.join(AGENTS_DIR, "ux-reviewer.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "VLM" in content or "screenshot" in content.lower() or "mm-vlm" in content, \
        "ux-reviewer missing VLM capability"

def test_perf_analyzer_includes_vlm():
    """perf-analyzer has VLM for flame graph screenshots."""
    path = os.path.join(AGENTS_DIR, "perf-analyzer.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "VLM" in content or "flame graph" in content.lower() or "screenshot" in content.lower(), \
        "perf-analyzer missing VLM capability"

def test_capability_policy_mentions_upgrade_vlm():
    """Capability policy mentions --upgrade-vlm."""
    files = ["master-executor.md", "code-reviewer.md", "security-auditor.md"]
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "--upgrade-vlm" in content, f"{f} missing --upgrade-vlm"

def test_degraded_mode_for_vlm_unavailable():
    """Templates note degraded mode if VLM unavailable."""
    files = ["master-executor.md", "ux-reviewer.md", "perf-analyzer.md"]
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "NEEDS VERIFICATION" in content or "degraded" in content.lower(), \
            f"{f} missing degraded-mode note"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])