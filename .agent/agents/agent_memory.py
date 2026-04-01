# ============================================================
#  Ổ — Memory Specialist (N.E.L.S.O.N AI OS)
#  "Reads and writes all persistent state."
#  Manages: 05_active_context.md, session_log.md,
#           lesson_learned.md, task_board.db, mailbox.db
#  Persona: quiet, reliable, only speaks when needed
# ============================================================
AGENT = "Ổ"
import os, datetime, re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


def read_context():
    """Read the full active context file. Returns string."""
    if not os.path.exists(config.ACTIVE_CONTEXT):
        return ""
    with open(config.ACTIVE_CONTEXT, "r", encoding="utf-8") as f:
        return f.read()


def update_last_session(tasks_completed, status="All PASS"):
    """Update the 'Last Session' section in active context."""
    content = read_context()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    task_bullets = "\n".join(f"  - {t}" for t in tasks_completed)
    new_section = (
        f"## Last Session\n\n"
        f"- **Date:** {now}\n"
        f"- **Tasks completed:**\n{task_bullets}\n"
        f"- **Status:** {status}\n"
    )

    # Replace existing Last Session section
    pattern = r"## Last Session\n.*?(?=\n## |\Z)"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_section.rstrip(), content, flags=re.DOTALL)
    else:
        content += "\n" + new_section

    with open(config.ACTIVE_CONTEXT, "w", encoding="utf-8") as f:
        f.write(content)


def update_priorities(priorities):
    """Update the 'Current Priorities' section."""
    content = read_context()
    prio_bullets = "\n".join(f"{i+1}. {p}" for i, p in enumerate(priorities))
    new_section = f"## Current Priorities\n\n{prio_bullets}\n"

    pattern = r"## Current Priorities\n.*?(?=\n## |\Z)"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_section.rstrip(), content, flags=re.DOTALL)
    else:
        content += "\n" + new_section

    with open(config.ACTIVE_CONTEXT, "w", encoding="utf-8") as f:
        f.write(content)


def log_task(task_name, status, files_changed, backup_path, reviewer_notes):
    """
    Append a task entry to session_log.md.
    Status: PASS / FAIL / WARN
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    file_list = ", ".join(files_changed) if files_changed else "none"

    entry = (
        f"\n## [{now}] {task_name}\n"
        f"- Status: {status}\n"
        f"- Files changed: {file_list}\n"
        f"- Backup: {backup_path or 'N/A'}\n"
        f"- Reviewer notes: {reviewer_notes}\n"
    )

    with open(config.SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def read_log(last_n_lines=20):
    """Read last N lines of session log."""
    if not os.path.exists(config.SESSION_LOG):
        return "No session log found."
    with open(config.SESSION_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-last_n_lines:])


def get_current_state():
    """Parse active context for quick summary (for /status)."""
    content = read_context()
    # Extract key info
    lines = content.split("\n")
    summary_parts = []
    in_session = False
    for line in lines:
        if "## Last Session" in line:
            in_session = True
        elif in_session and line.startswith("## "):
            in_session = False
        elif in_session and line.strip().startswith("- **"):
            summary_parts.append(line.strip())
    return "\n".join(summary_parts) if summary_parts else "No active context."
