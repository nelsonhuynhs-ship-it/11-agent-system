# -*- coding: utf-8 -*-
"""
sync-context.py — Sync CONTEXT.md files from workspace to GoClaw DB.

Reads CONTEXT.md from each agent's workspace folder and upserts into
the agent_context_files table. Idempotent — safe to run multiple times.

Usage:
    python sync-context.py           # Sync all 4 agents
    python sync-context.py --check   # Dry run, show what would change
"""
import argparse
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path(r"D:\GoClaw\data\goclaw.db")
WORKSPACE_ROOT = Path(r"D:\GoClaw\workspace")

AGENTS = {
    "little-fox":    "019d542e-aba5-7b8b-b28f-651cf0867be9",
    "deal-advisor":  "019d55d1-4690-7c8f-a720-f1b8dbb7f488",
    "scholar":       "019d55d2-fc2a-7a54-ae9c-bba3cc14fb06",
    "route-advisor": "019d55d5-80d0-7994-a0bd-d7b1b2b0fb92",
}

TENANT_ID = "0193a5b0-7000-7000-8000-000000000001"
FILE_NAME = "CONTEXT.md"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Sync CONTEXT.md to GoClaw DB")
    parser.add_argument("--check", action="store_true", help="Dry run")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    synced = 0
    for key, agent_id in AGENTS.items():
        ctx_path = WORKSPACE_ROOT / key / FILE_NAME
        if not ctx_path.exists():
            print(f"[SKIP] {key}/{FILE_NAME} not found")
            continue

        content = ctx_path.read_text(encoding="utf-8")

        cur.execute(
            "SELECT id, length(content) FROM agent_context_files WHERE agent_id = ? AND file_name = ?",
            (agent_id, FILE_NAME),
        )
        row = cur.fetchone()

        if row:
            if args.check:
                print(f"[WOULD UPDATE] {key}/{FILE_NAME}: {row[1]} → {len(content)} chars")
            else:
                cur.execute(
                    "UPDATE agent_context_files SET content = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                    (content, row[0]),
                )
                print(f"[UPDATE] {key}/{FILE_NAME} ({len(content)} chars)")
            synced += 1
        else:
            if args.check:
                print(f"[WOULD INSERT] {key}/{FILE_NAME}: {len(content)} chars")
            else:
                new_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO agent_context_files (id, agent_id, file_name, content, tenant_id) VALUES (?, ?, ?, ?, ?)",
                    (new_id, agent_id, FILE_NAME, content, TENANT_ID),
                )
                print(f"[INSERT] {key}/{FILE_NAME} ({len(content)} chars)")
            synced += 1

    if not args.check:
        conn.commit()
        print(f"\nSynced {synced}/{len(AGENTS)} CONTEXT.md files")
    else:
        print(f"\nDry run — {synced} files would be synced")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
