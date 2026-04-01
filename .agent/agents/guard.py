# ============================================================
#  LÍNH — Guard Specialist (N.E.L.S.O.N AI OS)
#  "Runs BEFORE ÉM on every write task. No exceptions."
#  Hardcoded rules that CANNOT be overridden.
#  Persona: terse, military, protective
# ============================================================
AGENT = "LÍNH"
import os, shutil, datetime, difflib
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import mailbox as agent_mailbox


def timestamp():
    """Current timestamp string for filenames."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(filepath):
    """
    Create timestamped backup BEFORE any modification.
    Returns backup path on success, raises on failure.
    """
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        return None  # Nothing to backup for new files

    fname = os.path.basename(filepath)
    backup_name = f"{timestamp()}_{fname}"
    backup_path = os.path.join(config.BACKUP_DIR, backup_name)

    try:
        shutil.copy2(filepath, backup_path)
        return backup_path
    except Exception as e:
        raise RuntimeError(f"GUARD: Backup FAILED for {filepath}: {e}. ABORTING task.")


def is_protected_file(filepath):
    """Check if file is in read-only list."""
    filepath = os.path.normpath(filepath)
    return filepath in config.READ_ONLY_FILES


def is_protected_extension(filepath):
    """Check if file has a protected extension (cannot be deleted)."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in config.PROTECTED_EXTENSIONS


def check_forbidden_command(command):
    """
    Check if command contains any forbidden patterns.
    Returns (safe: bool, reason: str).
    """
    cmd_lower = command.lower()
    for forbidden in config.FORBIDDEN_COMMANDS:
        if forbidden.lower() in cmd_lower:
            return False, f"BLOCKED: Command contains forbidden pattern '{forbidden}'"
    return True, "OK"


def check_diff_size(original_path, new_content):
    """
    Check if diff exceeds MAX_DIFF_PERCENT.
    Returns (ok: bool, pct: float).
    """
    if not os.path.exists(original_path):
        return True, 0.0  # New file, no diff concern

    with open(original_path, "r", encoding="utf-8", errors="replace") as f:
        original_lines = f.readlines()

    new_lines = new_content.splitlines(keepends=True)
    if len(original_lines) == 0:
        return True, 0.0

    diff = list(difflib.unified_diff(original_lines, new_lines))
    changed = sum(1 for line in diff if line.startswith("+") or line.startswith("-"))
    # Subtract the header lines (--- and +++)
    changed = max(0, changed - 4)
    pct = (changed / len(original_lines)) * 100

    if pct > config.MAX_DIFF_PERCENT:
        return False, round(pct, 1)
    return True, round(pct, 1)


def safe_delete(filepath):
    """
    NEVER delete protected files. Move to backup instead.
    """
    filepath = os.path.normpath(filepath)
    if is_protected_extension(filepath):
        backup_path = backup_file(filepath)
        return f"GUARD: File moved to backup (not deleted): {backup_path}"
    else:
        os.remove(filepath)
        return f"Deleted: {filepath}"


def get_latest_backup(filename_pattern):
    """Find the most recent backup matching a filename pattern."""
    backups = []
    for f in os.listdir(config.BACKUP_DIR):
        if filename_pattern in f:
            backups.append(os.path.join(config.BACKUP_DIR, f))
    if not backups:
        return None
    return sorted(backups, reverse=True)[0]


def rollback(filepath):
    """
    Rollback a file to its latest backup.
    Returns (success: bool, message: str).
    """
    filepath = os.path.normpath(filepath)
    fname = os.path.basename(filepath)
    latest = get_latest_backup(fname)
    if latest is None:
        return False, f"No backup found for {fname}"

    # Backup current before rollback
    backup_file(filepath)
    shutil.copy2(latest, filepath)
    return True, f"Rolled back {fname} from {os.path.basename(latest)}"


def pre_modify_check(filepath, new_content=None):
    """
    Full pre-modification safety check.
    Returns (allowed: bool, message: str, backup_path: str|None).
    """
    filepath = os.path.normpath(filepath)

    # Check read-only
    if is_protected_file(filepath):
        return False, f"GUARD: {os.path.basename(filepath)} is READ-ONLY", None

    # Create backup
    try:
        backup_path = backup_file(filepath)
    except RuntimeError as e:
        return False, str(e), None

    # Check diff size if we have new content
    if new_content and os.path.exists(filepath):
        ok, pct = check_diff_size(filepath, new_content)
        if not ok:
            return False, f"GUARD: Large change detected: {pct}% of {os.path.basename(filepath)}. Needs approval.", backup_path

    return True, "OK", backup_path
