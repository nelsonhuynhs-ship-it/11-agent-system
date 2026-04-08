#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
apply-multi-agent-migration.py

Migration script to configure Fox Spirit multi-agent delegation architecture.

IDEMPOTENT: safe to run multiple times. Each operation checks existence first.

Operations:
1. Create team 'nelson-ops-team' with Fox Spirit as lead
2. Add 4 agents to team (Fox as lead, 3 others as members)
3. Create 3 agent_links: Fox -> WATCHDOG, Fox -> OPS-ENGINE, Fox -> SALES-OPS (outbound)
4. Sync 4 SOUL.md files from workspace folder -> agent_context_files table

PREREQUISITE: GoClaw Lite must be closed to avoid DB lock contention.
"""
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path(r"D:\GoClaw\data\goclaw.db")
WORKSPACE_ROOT = Path(r"D:\GoClaw\workspace")

TENANT_ID = "0193a5b0-7000-7000-8000-000000000001"

AGENTS = {
    "little-fox":    "019d542e-aba5-7b8b-b28f-651cf0867be9",
    "deal-advisor":  "019d55d1-4690-7c8f-a720-f1b8dbb7f488",
    "scholar":       "019d55d2-fc2a-7a54-ae9c-bba3cc14fb06",
    "route-advisor": "019d55d5-80d0-7994-a0bd-d7b1b2b0fb92",
}

FOX_ID = AGENTS["little-fox"]
TEAM_NAME = "nelson-ops-team"
TEAM_DESCRIPTION = "Nelson Freight Operations Team - Fox Spirit orchestrator delegates to specialist agents"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        team_id = ensure_team(cur)
        ensure_team_members(cur, team_id)
        ensure_agent_links(cur)
        sync_soul_files(cur)
        conn.commit()
        print("\nSUCCESS: migration complete")
        print(f"  Team ID: {team_id}")
        print("  All 4 agents linked, SOUL files synced")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"\nERROR: migration failed, rolled back: {exc}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        conn.close()


def ensure_team(cur: sqlite3.Cursor) -> str:
    """Create team if not exists. Return team_id."""
    cur.execute(
        "SELECT id FROM agent_teams WHERE name = ? AND tenant_id = ?",
        (TEAM_NAME, TENANT_ID),
    )
    row = cur.fetchone()
    if row:
        print(f"[SKIP] Team '{TEAM_NAME}' already exists: {row[0]}")
        return row[0]

    team_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO agent_teams (id, name, lead_agent_id, description, status, created_by, tenant_id)
        VALUES (?, ?, ?, ?, 'active', 'nelson', ?)
        """,
        (team_id, TEAM_NAME, FOX_ID, TEAM_DESCRIPTION, TENANT_ID),
    )
    print(f"[CREATE] Team '{TEAM_NAME}' id={team_id}, lead=Fox Spirit")
    return team_id


def ensure_team_members(cur: sqlite3.Cursor, team_id: str) -> None:
    """Add all 4 agents to team. Fox as lead, others as members."""
    for key, agent_id in AGENTS.items():
        role = "lead" if key == "little-fox" else "member"
        cur.execute(
            "SELECT 1 FROM agent_team_members WHERE team_id = ? AND agent_id = ?",
            (team_id, agent_id),
        )
        if cur.fetchone():
            print(f"[SKIP] Member {key} already in team")
            continue
        cur.execute(
            """
            INSERT INTO agent_team_members (team_id, agent_id, role, tenant_id)
            VALUES (?, ?, ?, ?)
            """,
            (team_id, agent_id, role, TENANT_ID),
        )
        print(f"[CREATE] Member {key} as {role}")


def ensure_agent_links(cur: sqlite3.Cursor) -> None:
    """Create outbound links Fox -> 3 specialist agents."""
    targets = [
        ("route-advisor", "Fox delegates infrastructure planning to WATCHDOG"),
        ("scholar",       "Fox delegates data pipeline planning to OPS-ENGINE"),
        ("deal-advisor",  "Fox delegates business/UX planning to SALES-OPS"),
    ]
    for target_key, description in targets:
        target_id = AGENTS[target_key]
        cur.execute(
            "SELECT 1 FROM agent_links WHERE source_agent_id = ? AND target_agent_id = ?",
            (FOX_ID, target_id),
        )
        if cur.fetchone():
            print(f"[SKIP] Link Fox -> {target_key} already exists")
            continue
        link_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO agent_links (
                id, source_agent_id, target_agent_id, direction,
                description, max_concurrent, status, created_by, tenant_id
            )
            VALUES (?, ?, ?, 'outbound', ?, 3, 'active', 'nelson', ?)
            """,
            (link_id, FOX_ID, target_id, description, TENANT_ID),
        )
        print(f"[CREATE] Link Fox -> {target_key}")


def sync_soul_files(cur: sqlite3.Cursor) -> None:
    """Sync SOUL.md content from workspace folder to agent_context_files table."""
    for key, agent_id in AGENTS.items():
        soul_path = WORKSPACE_ROOT / key / "SOUL.md"
        if not soul_path.exists():
            print(f"[SKIP] {key}/SOUL.md not found at {soul_path}")
            continue

        content = soul_path.read_text(encoding="utf-8")
        cur.execute(
            """
            SELECT id FROM agent_context_files
            WHERE agent_id = ? AND file_name = ?
            """,
            (agent_id, "SOUL.md"),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """
                UPDATE agent_context_files
                SET content = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (content, row[0]),
            )
            print(f"[UPDATE] {key}/SOUL.md ({len(content)} chars)")
        else:
            new_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO agent_context_files (id, agent_id, file_name, content, tenant_id)
                VALUES (?, ?, 'SOUL.md', ?, ?)
                """,
                (new_id, agent_id, content, TENANT_ID),
            )
            print(f"[INSERT] {key}/SOUL.md ({len(content)} chars)")


if __name__ == "__main__":
    sys.exit(main())
