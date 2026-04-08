#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
claude-run.py — Fox Spirit wrapper to invoke Claude Code CLI on a target project.

Usage:
    python claude-run.py <project> [--plan] <prompt tokens...>

Examples:
    python claude-run.py engine sua bug rate column trong webapp
    python claude-run.py webapp --plan them button dark mode
    python claude-run.py bot add command /status moi

Projects registry: hardcoded below. Add new entries when new projects are added.
"""
import sys
import os
import shutil
import subprocess

PROJECTS = {
    "engine": r"D:\NELSON\2. Areas\Engine_test",
    "webapp": r"D:\NELSON\2. Areas\Engine_test\webapp",
    "bot":    r"D:\NELSON\2. Areas\Engine_test\TelegramBot_v5",
    "erp":    r"D:\NELSON\2. Areas\Engine_test\ERP",
    "email":  r"D:\NELSON\2. Areas\Engine_test\email_engine",
    "goclaw": r"D:\GoClaw",
}

ALLOWED_TOOLS = "Read,Write,Edit,Bash,Glob,Grep"
MAX_TURNS = "30"


def main() -> int:
    # Force UTF-8 stdout so Vietnamese/Unicode output from Claude renders OK
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7

    args = sys.argv[1:]
    if not args:
        print_usage()
        return 1

    project = args[0].lower()
    args = args[1:]

    if project not in PROJECTS:
        print(f"ERROR: Unknown project '{project}'")
        print(f"Available projects: {', '.join(PROJECTS.keys())}")
        return 2

    # Check for --plan flag (plan mode = dry-run preview)
    mode = "auto"
    if args and args[0] == "--plan":
        mode = "plan"
        args = args[1:]

    if not args:
        print("ERROR: Missing prompt")
        print_usage()
        return 1

    prompt = " ".join(args)
    cwd = PROJECTS[project]

    if not os.path.isdir(cwd):
        print(f"ERROR: Project directory not found: {cwd}")
        return 3

    # Resolve claude CLI path (Windows: claude.cmd needs shutil.which to find)
    claude_exe = shutil.which("claude")
    if not claude_exe:
        print("ERROR: 'claude' command not found on PATH. Install: npm install -g @anthropic-ai/claude-code")
        return 127

    cmd = [
        claude_exe,
        "-p", prompt,
        "--permission-mode", mode,
        "--max-turns", MAX_TURNS,
        "--allowedTools", ALLOWED_TOOLS,
        "--output-format", "text",
    ]

    # Force UTF-8 output on Windows so Vietnamese text renders OK
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,  # 10 minutes hard cap
        )
    except subprocess.TimeoutExpired:
        print("ERROR: Claude Code CLI timed out after 600 seconds")
        return 124
    except FileNotFoundError:
        print("ERROR: 'claude' command not found. Install: npm install -g @anthropic-ai/claude-code")
        return 127

    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(f"STDERR: {result.stderr}", file=sys.stderr)

    return result.returncode


def print_usage() -> None:
    print("Usage: python claude-run.py <project> [--plan] <prompt tokens...>")
    print(f"Projects: {', '.join(PROJECTS.keys())}")
    print("Modes: default = auto (execute with classifier), --plan = dry-run preview")


if __name__ == "__main__":
    sys.exit(main())
