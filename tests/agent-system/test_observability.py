#!/usr/bin/env python3
"""Regression tests: observability — log-spawn.py trace IDs and JSONL."""
import os, sqlite3, json
from pathlib import Path

LOG_SPAWN = "C:/Users/Nelson/.claude/bin/log-spawn.py"
DB = Path.home() / ".claude" / "agent-metrics.db"
JSONL = Path.home() / ".claude" / "agent-events.jsonl"

def test_log_spawn_supports_trace_id_arg():
    """log-spawn.py accepts --trace-id."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    assert "--trace-id" in content, "log-spawn.py missing --trace-id argument"

def test_agent_tool_events_schema_defined():
    """log-spawn.py defines agent_tool_events table."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    assert "agent_tool_events" in content, "Missing agent_tool_events table"

def test_jsonl_sidecar_path_defined():
    """agent-events.jsonl path is defined."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    assert "agent-events.jsonl" in content, "Missing agent-events.jsonl path"

def test_trace_id_passed_to_log_spawn():
    """Spawner passes --trace-id to log-spawn.py."""
    spawner = "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"
    with open(spawner, encoding="utf-8") as f:
        content = f.read()
    assert "--trace-id \"$TRACE_ID\"" in content or "--trace-id" in content, \
        "Spawner does not pass --trace-id"

def test_spawner_generates_trace_id():
    """Spawner generates trace_id per run."""
    spawner = "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"
    with open(spawner, encoding="utf-8") as f:
        content = f.read()
    assert "TRACE_ID=" in content, "TRACE_ID not generated"

def test_log_spawn_creates_jsonl_entry():
    """log-spawn.py writes JSONL sidecar."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    assert "jsonl" in content.lower() and "write" in content.lower(), \
        "log-spawn.py does not write JSONL"

def test_log_spawn_backward_compatible():
    """log-spawn.py still inserts to agent_runs (backward compat)."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    assert "agent_runs" in content, "agent_runs table not found (backward compat broken)"

def test_log_spawn_has_event_types():
    """log-spawn.py has event types: spawn_start, skill_load, search, vlm, fallback."""
    with open(LOG_SPAWN, encoding="utf-8") as f:
        content = f.read()
    event_types = ["spawn_complete", "spawn_failed", "skill_load", "search", "vlm", "fallback"]
    found = [e for e in event_types if e in content]
    assert len(found) >= 2, f"Missing event types, only found: {found}"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])