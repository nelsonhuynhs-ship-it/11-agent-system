# ============================================================
#  ÉM — Builder Specialist (N.E.L.S.O.N AI OS)
#  "Does what it's told. No opinion. Just builds."
#  All file modifications go through LÍNH (Guard) first.
#  Inject checkpoints at A (after command) and B (before exit).
#  Persona: terse, action-focused
# ============================================================
AGENT = "ÉM"
import os, subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import guard
import notifier
import mailbox as agent_mailbox


class BuildResult:
    """Build operation result."""
    def __init__(self, success, message, files_changed=None, backup_paths=None):
        self.success = success
        self.message = message
        self.files_changed = files_changed or []
        self.backup_paths = backup_paths or []

    def __repr__(self):
        return f"<BuildResult {'OK' if self.success else 'FAIL'}: {self.message}>"


def modify_file(filepath, new_content, task_name=""):
    """
    Guard-wrapped file modification.
    1. Pre-modify safety check (backup + diff threshold)
    2. Write new content
    Returns BuildResult.
    """
    filepath = os.path.normpath(filepath)
    notifier.progress("Builder", os.path.basename(filepath), f"Modifying for: {task_name}")

    # Guard pre-check
    allowed, msg, backup_path = guard.pre_modify_check(filepath, new_content)
    if not allowed:
        return BuildResult(False, msg)

    # Write
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return BuildResult(True, "Modified OK", [filepath], [backup_path] if backup_path else [])
    except Exception as e:
        return BuildResult(False, f"Write failed: {e}", [], [backup_path] if backup_path else [])


def create_file(filepath, content, task_name=""):
    """
    Guard-wrapped file creation.
    No backup needed for new files.
    """
    filepath = os.path.normpath(filepath)
    notifier.progress("Builder", os.path.basename(filepath), f"Creating for: {task_name}")

    if os.path.exists(filepath):
        # Existing file — treat as modify
        return modify_file(filepath, content, task_name)

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return BuildResult(True, "Created OK", [filepath], [])
    except Exception as e:
        return BuildResult(False, f"Create failed: {e}")


def read_file(filepath):
    """Read a file and return contents."""
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _check_inject():
    """Check inject queue for steer messages (Checkpoint A/B)."""
    try:
        from cto_agent import check_inject_queue
        injected = check_inject_queue()
        for msg in injected:
            print(f"  [BUILDER INJECT] {msg}")
        return injected
    except ImportError:
        return []


def run_command(command, cwd=None, task_name=""):
    """
    Safety-checked command execution.
    Checkpoint A: after command completes.
    """
    # Guard check
    safe, reason = guard.check_forbidden_command(command)
    if not safe:
        return BuildResult(False, reason)

    cwd = cwd or config.WORKSPACE
    notifier.progress("Builder", "command", f"`{command[:60]}...`")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # ── Checkpoint A: after command execution ──
        _check_inject()

        if result.returncode == 0:
            return BuildResult(True, result.stdout.strip() or "Command completed", [], [])
        else:
            return BuildResult(False, f"Exit {result.returncode}: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        return BuildResult(False, "Command timed out (120s)")
    except Exception as e:
        return BuildResult(False, f"Command error: {e}")


def run_build_script():
    """Run the ERP build script. Checkpoint B before return."""
    result = run_command(
        f'python "{config.BUILD_SCRIPT}"',
        cwd=os.path.dirname(config.BUILD_SCRIPT),
        task_name="ERP V13 Build"
    )
    # ── Checkpoint B: before loop exit ──
    _check_inject()
    if result.success:
        agent_mailbox.send_message("Builder", "LEAD", "status_update", "Build script completed successfully")
    return result
