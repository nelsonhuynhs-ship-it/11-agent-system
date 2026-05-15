#!/usr/bin/env python3
"""Log a spawn run to agent-metrics.db. Called by mm-agent-spawner.sh.
   Extended 2026-05-14: trace_id, capability events, JSONL sidecar."""

import argparse, sqlite3, sys, os, json
from datetime import datetime
from pathlib import Path

DB = Path.home() / ".claude" / "agent-metrics.db"
JSONL = Path.home() / ".claude" / "agent-events.jsonl"

SCHEMA_RUNS = """
CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  role TEXT NOT NULL,
  capability TEXT,
  cwd TEXT,
  duration_sec INTEGER,
  status TEXT,
  tokens_in INTEGER,
  tokens_out INTEGER,
  tools_used TEXT,
  report_path TEXT,
  error_excerpt TEXT
);
CREATE INDEX IF NOT EXISTS idx_role_ts ON agent_runs (role, ts);
CREATE INDEX IF NOT EXISTS idx_status_ts ON agent_runs (status, ts);
"""

SCHEMA_EVENTS = """
CREATE TABLE IF NOT EXISTS agent_tool_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  task_id TEXT,
  role TEXT NOT NULL,
  event_type TEXT NOT NULL,
  skill TEXT,
  tool TEXT,
  query TEXT,
  source_url TEXT,
  capability TEXT,
  status TEXT,
  duration_ms INTEGER,
  error_class TEXT,
  details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_trace ON agent_tool_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_role_event ON agent_tool_events (role, event_type);
"""

# Backward-compatible insert into agent_runs (no new columns)
INSERT_RUN = """INSERT INTO agent_runs
    (ts, role, capability, cwd, duration_sec, status,
     tokens_in, tokens_out, tools_used, report_path, error_excerpt)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)"""

INSERT_EVENT = """INSERT INTO agent_tool_events
    (ts, trace_id, task_id, role, event_type, skill, tool, query,
     source_url, capability, status, duration_ms, error_class, details_json)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def log_event(entry):
    """Append JSONL sidecar log."""
    try:
        with open(JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[log-spawn] JSONL write error: {e}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role", required=True)
    p.add_argument("--capability", default="text")
    p.add_argument("--cwd", default="")
    p.add_argument("--duration", type=int, default=0)
    p.add_argument("--status", default="completed")
    p.add_argument("--tokens-in", type=int, default=0)
    p.add_argument("--tokens-out", type=int, default=0)
    p.add_argument("--tools-used", default="")
    p.add_argument("--report-path", default="")
    p.add_argument("--error-excerpt", default="")
    # Extended args (2026-05-14)
    p.add_argument("--trace-id", default="")
    p.add_argument("--requested-capability", default="")
    p.add_argument("--resolved-executor", default="")
    p.add_argument("--fallback-executor", default="")
    p.add_argument("--error-class", default="")
    p.add_argument("--skill", default="")
    p.add_argument("--tool", default="")
    p.add_argument("--event-type", default="spawn_complete")
    args = p.parse_args()

    ts = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(str(DB))
        conn.executescript(SCHEMA_RUNS)
        conn.executescript(SCHEMA_EVENTS)

        # Backward-compatible agent_runs insert
        conn.execute(INSERT_RUN, (
            ts, args.role, args.capability, args.cwd,
            args.duration, args.status,
            args.tokens_in, args.tokens_out, args.tools_used,
            args.report_path, args.error_excerpt[:500] if args.error_excerpt else ""
        ))

        # New agent_tool_events insert (if trace_id present)
        if args.trace_id:
            conn.execute(INSERT_EVENT, (
                ts,
                args.trace_id,
                "",  # task_id (not used in spawner context)
                args.role,
                args.event_type,
                args.skill,
                args.tool,
                "",  # query
                "",  # source_url
                args.requested_capability or args.capability,
                args.status,
                args.duration * 1000 if args.duration else 0,
                args.error_class,
                json.dumps({
                    "resolved_executor": args.resolved_executor,
                    "fallback_executor": args.fallback_executor,
                    "report_path": args.report_path
                }, ensure_ascii=False) if args.resolved_executor else "{}"
            ))

        conn.commit()
        conn.close()

        # JSONL sidecar (always, for observability)
        jsonl_entry = {
            "ts": ts,
            "trace_id": args.trace_id,
            "role": args.role,
            "capability": args.capability,
            "requested_capability": args.requested_capability,
            "resolved_executor": args.resolved_executor,
            "fallback_executor": args.fallback_executor,
            "duration_sec": args.duration,
            "status": args.status,
            "error_class": args.error_class,
        }
        log_event(jsonl_entry)

    except Exception as e:
        # KHONG raise — spawner should never fail because of DB
        print(f"[log-spawn] error: {e}", file=sys.stderr)
        sys.exit(0)

if __name__ == "__main__":
    main()