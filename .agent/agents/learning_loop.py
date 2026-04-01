# ============================================================
#  LEARNING LOOP — Self-learning system for NELSON AI OS
#  SOI writes lessons. Ổ retrieves them. NÃO uses them.
# ============================================================
import os, sys, re, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

LESSON_FILE = os.path.join(config.MEMORY_DIR, "lesson_learned.md")


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _get_next_lesson_number():
    """Get the next lesson number from file."""
    if not os.path.exists(LESSON_FILE):
        return 1
    with open(LESSON_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    matches = re.findall(r"## Lesson #(\d+)", content)
    if matches:
        return max(int(m) for m in matches) + 1
    return 1


def add_lesson(task, result, root_cause="", fix_applied="",
               skill_updated="", never_do="", always_do=""):
    """
    Append a lesson entry after SOI review.
    Called after every FAIL or WARN.
    """
    num = _get_next_lesson_number()
    date = _now()
    entry = f"""
## Lesson #{num} -- {date}
Task: {task}
Result: {result}
Root cause: {root_cause}
Fix applied: {fix_applied}
Skill updated: {skill_updated}
Never do: {never_do}
Always do: {always_do}
"""
    with open(LESSON_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"[LEARN] Lesson #{num} added: {task} -> {result}")
    return num


def add_pass_lesson(task, notes=""):
    """Add a brief lesson for PASS results (optional, lighter format)."""
    num = _get_next_lesson_number()
    date = _now()
    entry = f"""
## Lesson #{num} -- {date}
Task: {task}
Result: PASS
Notes: {notes}
"""
    with open(LESSON_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[LEARN] Lesson #{num} (PASS): {task}")
    return num


def get_relevant_lessons(task_description, top_n=3):
    """
    Search lessons for keywords matching the task.
    Returns top N most relevant lessons as list of strings.
    """
    if not os.path.exists(LESSON_FILE):
        return []

    with open(LESSON_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into individual lessons
    lessons = re.split(r"(?=## Lesson #\d+)", content)
    lessons = [l.strip() for l in lessons if l.strip() and "## Lesson" in l]

    if not lessons:
        return []

    # Score each lesson by keyword overlap
    task_words = set(task_description.lower().split())
    scored = []
    for lesson in lessons:
        lesson_words = set(lesson.lower().split())
        overlap = len(task_words & lesson_words)
        if overlap > 0:
            scored.append((overlap, lesson))

    scored.sort(key=lambda x: -x[0])
    return [lesson for _, lesson in scored[:top_n]]


def get_warnings_count(pattern):
    """Count how many times a warning pattern has appeared."""
    if not os.path.exists(LESSON_FILE):
        return 0

    with open(LESSON_FILE, "r", encoding="utf-8") as f:
        content = f.read().lower()
    return content.count(pattern.lower())


def get_all_lessons():
    """Read all lessons."""
    if not os.path.exists(LESSON_FILE):
        return []
    with open(LESSON_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    lessons = re.split(r"(?=## Lesson #\d+)", content)
    return [l.strip() for l in lessons if l.strip() and "## Lesson" in l]


def get_recent_lessons(days=7):
    """Get lessons from the last N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    all_lessons = get_all_lessons()
    recent = []
    for lesson in all_lessons:
        match = re.search(r"-- (\d{4}-\d{2}-\d{2})", lesson)
        if match and match.group(1) >= cutoff:
            recent.append(lesson)
    return recent


def generate_weekly_report():
    """Generate weekly intelligence report from recent lessons."""
    recent = get_recent_lessons(7)
    if not recent:
        return "No lessons in the last 7 days."

    total = len(recent)
    passes = sum(1 for l in recent if "Result: PASS" in l)
    fails = sum(1 for l in recent if "Result: FAIL" in l)
    warns = sum(1 for l in recent if "Result: WARN" in l)

    # Extract common root causes
    causes = []
    for lesson in recent:
        match = re.search(r"Root cause: (.+)", lesson)
        if match and match.group(1).strip():
            causes.append(match.group(1).strip())

    report = (
        f"Weekly Intelligence Report ({_now()})\n"
        f"Tasks: {total} total, {passes} PASS, {fails} FAIL, {warns} WARN\n"
    )
    if causes:
        report += "Top root causes:\n"
        for c in causes[:5]:
            report += f"  - {c}\n"

    return report
