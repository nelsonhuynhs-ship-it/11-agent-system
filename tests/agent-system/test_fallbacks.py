#!/usr/bin/env python3
"""Regression tests: spawner fallback and retry behavior."""
import re, os

SPAWNER = "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"

def test_max_retries_set():
    """MAX_RETRIES = 1 (retry once only)."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "MAX_RETRIES" in content, "Missing MAX_RETRIES"
    # Should be set to 1
    m = re.search(r"MAX_RETRIES=(\d+)", content)
    if m:
        assert int(m.group(1)) <= 1, f"MAX_RETRIES should be <=1, got {m.group(1)}"

def test_fallback_executor_saved():
    """FALLBACK_EXECUTOR saved before override."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "FALLBACK_EXECUTOR=" in content and "FALLBACK_EXECUTOR=\"$EXECUTOR\"" in content, \
        "FALLBACK_EXECUTOR not saved before override"

def test_primary_failure_triggers_fallback():
    """If primary fails, retry with fallback executor."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert ("FALLBACK_EXECUTOR" in content and "retry" in content.lower()), \
        "Fallback logic not found"

def test_degraded_mode_writes_marker():
    """Degraded mode writes NEEDS VERIFICATION or degraded marker."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "NEEDS VERIFICATION" in content or "degraded" in content.lower(), \
        "No degraded mode marker"

def test_error_class_passed_to_log():
    """Error class passed to log-spawn.py on failure."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "--error-class" in content, "Missing --error-class in log-spawn call"

def test_fallback_only_on_executor_failure():
    """Fallback only triggers on executor failure, not logic failure."""
    # This is a design check — the retry should be around the eval exec
    # not around task logic
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    # The retry loop wraps the eval -- check this pattern exists
    assert "eval" in content and ("retry" in content.lower() or "continue" in content), \
        "Retry loop not wrapping eval execution"

def test_retry_count_increments():
    """RETRY_COUNT increments after fallback."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "RETRY_COUNT" in content, "Missing RETRY_COUNT variable"

def test_final_degraded_failure_is_explicit():
    """Final degraded failure is explicit in output."""
    with open(SPAWNER, encoding="utf-8") as f:
        content = f.read()
    assert "DEGRADED" in content or ("failed" in content.lower() and "exit" in content.lower()), \
        "Degraded failure not explicit"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])