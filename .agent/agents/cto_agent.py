# ============================================================
#  NÃO — Lead CTO Agent (N.E.L.S.O.N AI OS)
#  "The brain. Thinks before acting. Never executes directly."
#  Phase 1: Task Board | Phase 2: Mailbox | Phase 3: Parallel
#  Persona: calm, strategic, brief
# ============================================================
import os, sys, json, time, datetime, traceback, threading
import queue as queue_mod
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import guard          # LÍNH
import notifier       # NÓI
import memory         # Ổ
import reviewer       # SOI
import builder        # ÉM
import intent_classifier
import task_board
import mailbox as agent_mailbox
import skill_router
import learning_loop
import monitor as agent_monitor
import system_prompt_nao

AGENT = "NÃO"

# ── Phase 3: Parallel Specialist Threads ──
session_active = False
_specialist_threads = []

# ── State ──
current_task = None
session_busy = False
_state_lock = threading.Lock()

# ── Queues ──
inject_queue = queue_mod.Queue(maxsize=5)
task_queue = queue_mod.Queue(maxsize=10)


def is_busy():
    with _state_lock:
        return session_busy

def set_busy(val):
    global session_busy
    with _state_lock:
        session_busy = val


def handle_command(command_text):
    text = command_text.strip()
    if text.startswith("/"):
        return _handle_slash(text)
    if is_busy():
        intent = intent_classifier.classify(text)
        print(f"[{AGENT}] Intent: {intent} (busy=True)")
        return _handle_intent(intent, text)
    # Check for test/conversation/question/greeting triggers even when not busy
    intent = intent_classifier.classify(text)
    if intent == "test_erp":
        return handle_test_erp()
    if intent == "new_conversation":
        return handle_new_conversation(text)
    if intent == "question":
        return handle_question(text)
    if intent == "greeting":
        return handle_greeting()
    if len(text) > 3:
        return handle_task(text)
    notifier.send(f"{AGENT}: Use /task /status /pause /rollback /log")
    return False


def _handle_slash(text):
    if text.startswith("/task "):
        task_desc = text[6:].strip()
        if is_busy():
            intent = intent_classifier.classify(task_desc)
            if intent in ("steer", "status_query", "cancel"):
                return _handle_intent(intent, task_desc)
            try:
                task_queue.put_nowait(task_desc)
                notifier.send(f"{AGENT}: Queued: {task_desc[:50]}...")
                return True
            except queue_mod.Full:
                notifier.send(f"{AGENT}: Queue full.")
                return False
        return handle_task(task_desc)
    elif text == "/status":   return handle_status()
    elif text == "/pause":    return handle_pause()
    elif text == "/rollback": return handle_rollback()
    elif text == "/log":      return handle_log()
    elif text == "/approve":  return handle_approve()
    elif text == "/reject":   return handle_reject()
    elif text == "/health":   return handle_health()
    elif text == "/backlog":  return handle_backlog()
    elif text == "/test":     return handle_test_erp()
    elif text == "/newchat":  return handle_new_conversation()
    else:
        notifier.send(f"{AGENT}: Unknown: {text}")
        return False


def _handle_intent(intent, text):
    if intent == "status_query":   return _get_activity()
    elif intent == "cancel":       return _abort_current()
    elif intent == "steer":        return _inject_steer(text)
    elif intent == "test_erp":      return handle_test_erp()
    elif intent == "new_conversation": return handle_new_conversation(text)
    elif intent == "question":      return handle_question(text)
    elif intent == "greeting":      return handle_greeting()
    elif intent == "new_task":
        try:
            task_queue.put_nowait(text)
            notifier.send(f"{AGENT}: Queued: {text[:50]}...")
            return True
        except queue_mod.Full:
            notifier.send(f"{AGENT}: Queue full.")
            return False
    return False


def _get_activity():
    if current_task:
        board_text = task_board.format_board_summary()
        mail_text = agent_mailbox.get_unread_summary()
        notifier.activity_reply(current_task["name"], current_task["status"],
                                f"{board_text}\n{mail_text}" if mail_text else board_text)
    else:
        notifier.send(f"{AGENT}: No active task.")
    return True


def _abort_current():
    global current_task
    set_busy(False)
    if current_task:
        name = current_task["name"]
        for fp in current_task.get("files_changed", []):
            guard.rollback(fp)
        notifier.send(f"{AGENT}: Cancelled: {name}")
        memory.log_task(name, "CANCELLED", [], "", "Aborted by Nelson")
        current_task = None
    return True


def _inject_steer(text):
    wrapped = f"[Nelson follow-up: {text}]"
    try:
        inject_queue.put_nowait(wrapped)
        notifier.send(f"{AGENT}: Noted, injecting: {text[:60]}")
        return True
    except queue_mod.Full:
        task_queue.put_nowait(text)
        return False


def check_inject_queue():
    messages = []
    while not inject_queue.empty():
        try: messages.append(inject_queue.get_nowait())
        except queue_mod.Empty: break
    return messages


# ============================================================
#  TASK BOARD PIPELINE — NÃO decomposes, delegates, monitors
# ============================================================

def decompose_task(task_desc):
    desc_lower = task_desc.lower()
    subtasks = []
    subtasks.append(("LÍNH: backup affected files", f"Backup before: {task_desc}", "LÍNH"))
    if "build" in desc_lower or "rebuild" in desc_lower or "fix" in desc_lower or "crm" in desc_lower:
        subtasks.append(("ÉM: execute task", task_desc, "ÉM"))
    elif "check" in desc_lower or "verify" in desc_lower:
        subtasks.append(("ÉM: analyze and check", task_desc, "ÉM"))
    else:
        subtasks.append(("ÉM: execute task", task_desc, "ÉM"))
    subtasks.append(("SOI: validate changes", f"Review: {task_desc}", "SOI"))
    subtasks.append(("Ổ: log result", f"Log: {task_desc}", "Ổ"))
    subtasks.append(("NÓI: send report", f"Report: {task_desc}", "NÓI"))
    return subtasks


def create_task_chain(task_desc):
    subtasks = decompose_task(task_desc)
    task_ids = []
    prev_id = None
    for i, (title, description, agent) in enumerate(subtasks):
        priority = 1 if i == 0 else 2
        tid = task_board.create_task(title=title, description=description,
                                     blocked_by=prev_id, priority=priority)
        task_ids.append(tid)
        prev_id = tid
    return task_ids


def execute_board_pipeline(task_desc, task_ids):
    all_files_changed = []
    all_backups = []

    for tid in task_ids:
        task = task_board.get_task(tid)
        if task is None: continue
        retries = 0
        while task["status"] == "blocked" and retries < 30:
            time.sleep(1)
            task = task_board.get_task(tid)
            retries += 1
        if task["status"] != "pending":
            if task["status"] == "complete": continue
            continue

        title = task["title"]
        if title.startswith("LÍNH:"):
            ok = task_board.claim_task(tid, "LÍNH")
            if not ok: continue
            result_msg = _run_guard_subtask(task)
        elif title.startswith("ÉM:"):
            ok = task_board.claim_task(tid, "ÉM")
            if not ok: continue
            result_msg, files, backups = _run_builder_subtask(task)
            all_files_changed.extend(files)
            all_backups.extend(backups)
        elif title.startswith("SOI:"):
            ok = task_board.claim_task(tid, "SOI")
            if not ok: continue
            result_msg = _run_reviewer_subtask(task, all_files_changed)
        elif title.startswith("Ổ:"):
            ok = task_board.claim_task(tid, "Ổ")
            if not ok: continue
            result_msg = _run_memory_subtask(task, task_desc, all_files_changed, all_backups)
        elif title.startswith("NÓI:"):
            ok = task_board.claim_task(tid, "NÓI")
            if not ok: continue
            result_msg = _run_notifier_subtask(task, task_desc, all_files_changed)
        else:
            ok = task_board.claim_task(tid, "ÉM")
            if not ok: continue
            result_msg = f"Done: {task['title']}"

        task_board.complete_task(tid, result_msg)

    return all_files_changed, all_backups


def _run_guard_subtask(task):
    desc = task.get("description", "")
    notifier.send(f"LÍNH: Backup bắt đầu. {desc[:40]}")
    files_to_backup = [config.BUILD_SCRIPT,
                       os.path.join(config.VBA_DIR, "QuoteBuilder_ERP.bas"),
                       os.path.join(config.VBA_DIR, "CRM_Sheet.bas")]
    backed = []
    for fp in files_to_backup:
        if os.path.exists(fp):
            bp = guard.backup_file(fp)
            if bp: backed.append(os.path.basename(bp))
    return f"LÍNH: Backup xong {len(backed)} files. ÉM được phép vào."


def _run_builder_subtask(task):
    desc = task.get("description", "")
    desc_lower = desc.lower()

    # ÉM loads skill + lessons before building
    skills = skill_router.route(desc)
    lessons = learning_loop.get_relevant_lessons(desc, top_n=3)
    if lessons:
        for l in lessons:
            first_line = l.split("\n")[0] if l else ""
            print(f"  [ÉM LESSON] {first_line}")

    notifier.send(f"ÉM: Build bắt đầu. Skills: {len(skills['skills'])} loaded.")
    # ÉM system prompt available for LLM calls
    print(f"  [ÉM] System prompt: {system_prompt_nao.SYSTEM_PROMPT_EM[:60]}")
    check_inject_queue()

    if "build" in desc_lower or "rebuild" in desc_lower:
        result = builder.run_build_script()
    elif "crm" in desc_lower and ("fix" in desc_lower or "not appearing" in desc_lower):
        crm_bas = os.path.join(config.VBA_DIR, "CRM_Sheet.bas")
        if not os.path.exists(crm_bas):
            return "ÉM: FAIL — CRM_Sheet.bas not found", [], []
        result = builder.run_build_script()
    else:
        result = builder.BuildResult(True, f"ÉM: Analyzed: {desc}", [], [])

    if result.success:
        return f"ÉM: Build xong. {result.message}", result.files_changed, result.backup_paths
    return f"ÉM: FAIL — {result.message}", [], []


def _run_reviewer_subtask(task, files_changed):
    # SOI loads skill to know what PASS looks like
    desc = task.get("description", "")
    skills = skill_router.route(desc)
    # SOI system prompt for validation context
    print(f"  [SOI] System prompt: {system_prompt_nao.SYSTEM_PROMPT_SOI[:60]}")
    notifier.send(f"SOI: Kiểm tra {len(files_changed)} files...")

    if files_changed:
        review = reviewer.review_task(desc, files_changed)
        result_str = f"SOI: {review.score}. {review.notes}"

        # Learning loop — SOI writes lesson after every task
        if review.score == "FAIL":
            learning_loop.add_lesson(desc, "FAIL", root_cause=review.notes,
                                     fix_applied="", never_do=review.notes)
        elif review.score == "WARN":
            learning_loop.add_lesson(desc, "WARN", root_cause=review.notes)
        return result_str
    return "SOI: PASS — no files to review."


def _run_memory_subtask(task, task_desc, files_changed, backups):
    backup_str = ", ".join(backups) if backups else "N/A"
    memory.log_task(task_desc, "PASS", files_changed, backup_str, "Board pipeline complete")
    memory.update_last_session([task_desc], "PASS")
    return "Ổ: Đã lưu session_log.md"


def _run_notifier_subtask(task, task_desc, files_changed):
    summary = task_board.format_board_summary()
    file_names = [os.path.basename(f) for f in files_changed]
    notifier.done(task_desc, file_names, "PASS", summary)
    # NÃO auto-discovery: check for backlog gaps
    _auto_discover(task_desc)
    return "NÓI: Report sent."


def _auto_discover(task_desc):
    """NÃO asks: what did this task reveal that needs fixing?"""
    backlog_path = os.path.join(config.MEMORY_DIR, "backlog.md")
    if os.path.exists(backlog_path):
        with open(backlog_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Check if task is already in backlog
        if task_desc[:30] not in content:
            # Don't add — let NÃO decide in next planning session
            pass


# ============================================================
#  MAIN TASK HANDLER — NÃO orchestrates
# ============================================================

def handle_task(task_desc):
    global current_task
    set_busy(True)
    current_task = {
        "name": task_desc, "started": datetime.datetime.now().isoformat(),
        "status": "planning", "files_changed": [], "backup_paths": [], "task_ids": [],
    }

    try:
        ctx = memory.read_context()
        print(f"[{AGENT}] Context loaded ({len(ctx)} chars)")

        # NÃO retrieves relevant lessons for briefing
        lessons = learning_loop.get_relevant_lessons(task_desc)
        if lessons:
            print(f"[{AGENT}] {len(lessons)} relevant lessons found")

        # RAG-enhanced planning with system prompt
        rag_context = ""
        try:
            import rag_engine
            rag_docs = rag_engine.query(task_desc, n=3)
            if rag_docs:
                rag_context = "\n---\n".join(rag_docs[:3])
                print(f"[{AGENT}] RAG: {len(rag_docs)} relevant docs found")
        except Exception as e:
            print(f"[{AGENT}] RAG skip: {e}")

        # Use system prompt + RAG for smarter planning
        if rag_context:
            plan_prompt = (
                f"{system_prompt_nao.SYSTEM_PROMPT_NAO}\n\n"
                f"Relevant context:\n{rag_context[:2000]}\n\n"
                f"Task: {task_desc}\n"
                f"Create 3-5 step execution plan. Be specific."
            )
            llm_plan = config.call_llm(plan_prompt, agent="NÃO", max_tokens=500)
            if llm_plan:
                print(f"[{AGENT}] LLM plan: {llm_plan[:200]}")

        task_ids = create_task_chain(task_desc)
        current_task["status"] = "planned"
        current_task["task_ids"] = task_ids

        subtasks = decompose_task(task_desc)
        plan_steps = [f"{title}" for title, _, _ in subtasks]
        notifier.plan(task_desc, plan_steps)

        # Prepend lessons to plan message
        if lessons:
            lesson_warnings = []
            for l in lessons[:3]:
                lines = l.strip().split("\n")
                for line in lines:
                    if line.startswith("Always do:") or line.startswith("Never do:"):
                        lesson_warnings.append(line)
            if lesson_warnings:
                notifier.send(f"{AGENT}: Lessons:\n" + "\n".join(lesson_warnings[:3]))

        print(f"[{AGENT}] Waiting 10s for /pause...")
        for _ in range(10):
            time.sleep(1)
            if not is_busy():
                notifier.send(f"{AGENT}: Task paused.")
                return False

        current_task["status"] = "executing"
        files_changed, backups = execute_board_pipeline(task_desc, task_ids)
        current_task["files_changed"] = files_changed
        current_task["backup_paths"] = backups
        current_task["status"] = "done"

        set_busy(False)
        _process_queued_tasks()
        return True

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[{AGENT}] ERROR: {e}\n{tb}")
        notifier.alert(f"{AGENT}: Pipeline error: {e}")
        memory.log_task(task_desc, "FAIL", [], "", str(e))
        current_task["status"] = "error"
        set_busy(False)
        return False


def _process_queued_tasks():
    if not task_queue.empty():
        try:
            next_task = task_queue.get_nowait()
            handle_task(next_task)
        except queue_mod.Empty:
            pass


# ============================================================
#  COMMANDS
# ============================================================

def handle_status():
    board_text = task_board.format_board_summary()
    mail_text = agent_mailbox.get_unread_summary()
    if current_task:
        msg = f"\U0001F4CA {AGENT}: {current_task['name']}\nPhase: {current_task['status']}\n\n{board_text}"
    else:
        msg = f"\U0001F4CA {AGENT}: No active task.\n\n{board_text}"
    if mail_text: msg += f"\n{mail_text}"
    notifier.send(msg)
    return True

def handle_pause():
    set_busy(False)
    notifier.send(f"{AGENT}: Paused.")
    return True

def handle_rollback():
    if current_task and current_task.get("files_changed"):
        for fp in current_task["files_changed"]: guard.rollback(fp)
        notifier.send(f"LÍNH: Rollback done.")
        memory.log_task(current_task["name"], "ROLLBACK", current_task["files_changed"], "", "Manual")
    else:
        notifier.send(f"LÍNH: Nothing to rollback.")
    return True

def handle_log():
    log_content = memory.read_log(20)
    notifier.send(f"Ổ: Log (last 20 lines):\n\n{log_content}")
    return True

def handle_approve():
    notifier.send(f"{AGENT}: Approved.")
    return True

def handle_reject():
    handle_rollback()
    notifier.send(f"{AGENT}: Rejected. Rolled back.")
    return True

def handle_health():
    msg = agent_monitor.morning_check()
    notifier.send(msg)
    return True

def handle_backlog():
    backlog_path = os.path.join(config.MEMORY_DIR, "backlog.md")
    if os.path.exists(backlog_path):
        with open(backlog_path, "r", encoding="utf-8") as f:
            content = f.read()
        notifier.send(f"{AGENT}: Backlog:\n{content[:1500]}")
    else:
        notifier.send(f"{AGENT}: No backlog.")
    return True


def handle_question(text):
    """NÃO answers directly using RAG + system knowledge. No pipeline."""
    print(f"[{AGENT}] Question mode: {text[:60]}")
    try:
        import rag_engine
        context_docs = rag_engine.query(text, n=3)
        context = "\n---\n".join(context_docs[:3]) if context_docs else ""
    except Exception as e:
        print(f"[{AGENT}] RAG skip: {e}")
        context = ""

    answer = config.call_llm(
        f"{system_prompt_nao.SYSTEM_PROMPT_NAO}\n\n"
        f"User asked: {text}\n"
        f"Context from knowledge base:\n{context[:2000]}\n\n"
        f"Answer conversationally in Vietnamese. Be concise. No pipeline needed.",
        agent="NÃO", max_tokens=500
    )
    if answer:
        notifier.send(f"NÃO: {answer}")
    else:
        notifier.send(f"NÃO: Em chưa trả lời được câu này. Anh thử /task để giao task cụ thể.")
    return True


def handle_greeting():
    """NÃO greets Nelson with task count."""
    try:
        tasks = task_board.get_pending_tasks()
        task_count = len(tasks)
    except Exception:
        task_count = 0
    notifier.send(
        f"NÃO: Chào anh Nelson! Team đang trực. "
        f"Có {task_count} tasks hôm nay. Cần gì không anh?"
    )
    return True


def handle_test_erp():
    """Run Excel live test suite with full board pipeline."""
    notifier.send(f"{AGENT}: Test suite starting. LÍNH backup trước.")
    try:
        import excel_tester
        tester = excel_tester.ExcelTester()
        results = tester.run_all_tests()
        notifier.send_test_report(results)
        # Log results
        passed = sum(1 for r in results if r["verdict"] == "PASS")
        total = len(results)
        memory.log_task(f"Excel Test Suite", f"{passed}/{total} PASS", [], "",
                        f"{passed} passed, {total - passed} failed")
        if passed < total:
            learning_loop.add_lesson("Excel Test Suite", f"FAIL ({passed}/{total})",
                                     root_cause="Test failures detected")
        return True
    except ImportError as e:
        notifier.send(f"{AGENT}: Test deps missing: {e}. Install: pip install pywin32 pyautogui Pillow pygetwindow")
        return False
    except Exception as e:
        notifier.alert(f"{AGENT}: Test error: {e}")
        return False


def handle_new_conversation(message=None):
    """Open new Claude conversation with active context."""
    notifier.send(f"{AGENT}: Opening new conversation...")
    try:
        import browser_bot
        url = browser_bot.new_conversation(message)
        notifier.send(f"NÓI: Conversation mới đã mở.\nContext loaded.\nURL: {url}")
        return True
    except ImportError as e:
        notifier.send(f"{AGENT}: Browser deps missing: {e}. Install: pip install selenium")
        return False
    except Exception as e:
        notifier.alert(f"{AGENT}: Browser error: {e}")
        return False


# ── CLI entry point ──
if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        handle_command(cmd)
    else:
        print(f"Usage: python cto_agent.py <command>")


# ============================================================
#  PHASE 3: Parallel Specialist Threads
# ============================================================

def specialist_loop(agent_name, execute_fn):
    while session_active:
        try:
            tasks = task_board.get_pending_tasks()
            for task in tasks:
                title = task.get("title", "")
                if not title.startswith(f"{agent_name}:"):
                    continue
                if task_board.claim_task(task["id"], agent_name):
                    print(f"[SPECIALIST] {agent_name} claimed {task['id']}")
                    try:
                        result_msg = execute_fn(task)
                        task_board.complete_task(task["id"], result_msg)
                        agent_mailbox.send_message(agent_name, "NÃO", "status_update",
                                                   f"Task {task['id']} done: {result_msg[:100]}")
                    except Exception as e:
                        task_board.fail_task(task["id"], str(e))
                        agent_mailbox.send_message(agent_name, "NÃO", "alert",
                                                   f"Task {task['id']} failed: {e}")
                    break
        except Exception as e:
            print(f"[SPECIALIST] {agent_name} error: {e}")
        time.sleep(2)


def start_specialists():
    global session_active, _specialist_threads
    session_active = True
    specs = [
        ("LÍNH", _run_guard_subtask),
        ("ÉM", lambda t: _run_builder_subtask(t)[0]),
        ("SOI", lambda t: _run_reviewer_subtask(t, [])),
    ]
    for name, fn in specs:
        t = threading.Thread(target=specialist_loop, args=(name, fn), daemon=True)
        t.start()
        _specialist_threads.append(t)
        print(f"[{AGENT}] Specialist started: {name}")
    agent_monitor.start_scheduler()
    print(f"[{AGENT}] {len(_specialist_threads)} specialists + monitor running")

def stop_specialists():
    global session_active
    session_active = False
    agent_monitor.stop_scheduler()
