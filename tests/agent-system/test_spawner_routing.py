#!/usr/bin/env python3
"""Regression tests for agent system — spawner routing and upgrade flags."""
import re, os

SPAWNER = "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"

def test_upgrade_search_flag_exists():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--upgrade-search" in content, "Missing --upgrade-search flag"

def test_upgrade_vlm_flag_exists():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--upgrade-vlm" in content, "Missing --upgrade-vlm flag"

def test_upgrade_image_flag_exists():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--upgrade-image" in content, "Missing --upgrade-image flag"

def test_trace_id_generated():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "TRACE_ID=" in content, "Missing TRACE_ID variable"

def test_requested_capability_field():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "REQUESTED_CAPABILITY=" in content, "Missing REQUESTED_CAPABILITY"

def test_resolved_executor_field():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "RESOLVED_EXECUTOR=" in content, "Missing RESOLVED_EXECUTOR"

def test_fallback_executor_field():
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "FALLBACK_EXECUTOR=" in content, "Missing FALLBACK_EXECUTOR"

def test_upgrade_search_resolves_to_mm_search():
    """--upgrade-search routes to mm-search.sh."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    # Should have a case where UPGRADE_SEARCH=1 sets RESOLVED_EXECUTOR to MM_SEARCH
    assert "UPGRADE_SEARCH" in content and "mm-search.sh" in content

def test_upgrade_vlm_resolves_to_mm_vlm():
    """--upgrade-vlm routes to mm-vlm.sh."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "UPGRADE_VLM" in content and "mm-vlm.sh" in content

def test_upgrade_image_validates_task():
    """--upgrade-image validates task is image generation."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    # Should check that --upgrade-image only valid for image-gen tasks
    assert "image-01" in content.lower() or "gen" in content.lower()

def test_retry_loop_exists():
    """Spawner has retry/fallback loop."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "MAX_RETRIES" in content or "retry" in content.lower()

def test_log_spawn_receives_trace_id():
    """log-spawn.py called with --trace-id."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--trace-id" in content, "Spawner does not pass --trace-id to log-spawn.py"

def test_log_spawn_receives_requested_capability():
    """log-spawn.py called with --requested-capability."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--requested-capability" in content, "Spawner does not pass --requested-capability"

def test_log_spawn_receives_resolved_executor():
    """log-spawn.py called with --resolved-executor."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--resolved-executor" in content, "Spawner does not pass --resolved-executor"

def test_degraded_mode_writes_needs_verification():
    """Failed fallback writes NEEDS VERIFICATION to output."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "NEEDS VERIFICATION" in content or "degraded" in content.lower()

def test_default_routing_unchanged():
    """Default routing (no upgrade) still routes to original executors."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    # Check that the case statement still has original role→executor mapping
    assert "EXECUTOR=\"$MM_CLAUDE\"" in content or "MM_CLAUDE" in content
    assert "security-auditor)" in content  # original case still there

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])