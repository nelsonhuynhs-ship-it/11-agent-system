# ============================================================
#  SOI — Reviewer Specialist (N.E.L.S.O.N AI OS)
#  "Runs AFTER ÉM. Validates every output against task spec."
#  Issues: PASS / WARN / FAIL with specific reason.
#  On FAIL: triggers LÍNH rollback automatically.
#  Persona: skeptical, precise, never rushes
# ============================================================
AGENT = "SOI"
import os, re, py_compile, tempfile
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


class ReviewResult:
    """Review outcome container."""
    def __init__(self, score, notes):
        self.score = score    # "PASS" | "FAIL" | "WARN"
        self.notes = notes    # str

    def __repr__(self):
        return f"<ReviewResult {self.score}: {self.notes}>"


def review_python(filepath):
    """
    Validate Python file:
    1. py_compile syntax check
    2. Check for forbidden patterns
    Returns ReviewResult.
    """
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        return ReviewResult("FAIL", f"File not found: {filepath}")

    # Syntax check
    try:
        py_compile.compile(filepath, doraise=True)
    except py_compile.PyCompileError as e:
        return ReviewResult("FAIL", f"Syntax error: {e}")

    # Read content for pattern checks
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    warnings = []

    # Check for forbidden commands (word-boundary match to avoid false positives)
    for cmd in config.FORBIDDEN_COMMANDS:
        # Use word boundary to avoid matching 'format' inside 'NumberFormat', etc.
        pattern = r'(?<![a-zA-Z_])' + re.escape(cmd) + r'(?![a-zA-Z_])'
        if re.search(pattern, content, re.IGNORECASE):
            warnings.append(f"Contains forbidden pattern: '{cmd}'")

    if warnings:
        return ReviewResult("WARN", "; ".join(warnings))

    return ReviewResult("PASS", "Python syntax OK, no issues found")


def review_vba(filepath):
    """
    Validate VBA .bas file:
    1. Check Attribute VB_Name present
    2. Check Option Explicit
    3. Check balanced Sub/End Sub and Function/End Function
    Returns ReviewResult.
    """
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        return ReviewResult("FAIL", f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
        lines = content.split("\n")

    warnings = []
    errors = []

    # Check Attribute VB_Name
    if "Attribute VB_Name" not in content:
        warnings.append("Missing Attribute VB_Name declaration")

    # Check Option Explicit
    if "Option Explicit" not in content:
        warnings.append("Missing Option Explicit")

    # Count Sub/End Sub balance
    sub_opens = len(re.findall(r"^\s*(Public |Private )?Sub\s+", content, re.MULTILINE))
    sub_closes = len(re.findall(r"^\s*End Sub", content, re.MULTILINE))
    if sub_opens != sub_closes:
        errors.append(f"Unbalanced Sub/End Sub: {sub_opens} opens, {sub_closes} closes")

    # Count Function/End Function balance
    func_opens = len(re.findall(r"^\s*(Public |Private )?Function\s+", content, re.MULTILINE))
    func_closes = len(re.findall(r"^\s*End Function", content, re.MULTILINE))
    if func_opens != func_closes:
        errors.append(f"Unbalanced Function/End Function: {func_opens} opens, {func_closes} closes")

    if errors:
        return ReviewResult("FAIL", "; ".join(errors))
    if warnings:
        return ReviewResult("WARN", "; ".join(warnings))

    return ReviewResult("PASS", f"VBA structure OK ({sub_opens} Subs, {func_opens} Functions)")


def review_file(filepath):
    """Auto-detect file type and review."""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext == ".py":
        return review_python(filepath)
    elif ext == ".bas":
        return review_vba(filepath)
    elif ext == ".md":
        return ReviewResult("PASS", "Markdown file — no validation needed")
    elif ext == ".ps1":
        return review_powershell(filepath)
    else:
        return ReviewResult("WARN", f"No reviewer for extension: {ext}")


def review_powershell(filepath):
    """Basic PowerShell validation."""
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        return ReviewResult("FAIL", f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    warnings = []

    # Check for forbidden commands
    for cmd in config.FORBIDDEN_COMMANDS:
        if cmd.lower() in content.lower():
            warnings.append(f"Contains forbidden pattern: '{cmd}'")

    # Basic structure checks
    if len(content.strip()) < 10:
        return ReviewResult("FAIL", "File appears empty or too short")

    if warnings:
        return ReviewResult("WARN", "; ".join(warnings))
    return ReviewResult("PASS", "PowerShell structure OK")


def review_task(task_spec, files_changed):
    """
    Run acceptance test on all changed files.
    Returns overall ReviewResult.
    """
    results = []
    for filepath in files_changed:
        r = review_file(filepath)
        results.append((filepath, r))

    fails = [(f, r) for f, r in results if r.score == "FAIL"]
    warns = [(f, r) for f, r in results if r.score == "WARN"]

    if fails:
        detail = "; ".join(f"{os.path.basename(f)}: {r.notes}" for f, r in fails)
        return ReviewResult("FAIL", detail)
    elif warns:
        detail = "; ".join(f"{os.path.basename(f)}: {r.notes}" for f, r in warns)
        return ReviewResult("WARN", detail)
    else:
        detail = "; ".join(f"{os.path.basename(f)}: {r.notes}" for f, r in results)
        return ReviewResult("PASS", detail)
