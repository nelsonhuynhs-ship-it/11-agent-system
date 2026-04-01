# ============================================================
#  MONITOR (NÓI) — Proactive health checks and scheduled digests
#  08:00 morning check | 17:00 EOD | Monday 08:30 weekly
# ============================================================
import os, sys, datetime, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import task_board
import learning_loop

RATE_IMPORTER_PATH = os.path.join(config.WORKSPACE, "Pricing_Engine", "data")
ERP_MASTER_PATH = os.path.join(config.WORKSPACE, "ERP", "data", "ERP_Master.xlsm")
PARQUET_PATH = os.path.join(config.WORKSPACE, "Pricing_Engine", "data", "Cleaned_Master_History.parquet")
PARQUET_MIN_SIZE = 500_000  # 500KB minimum expected


def morning_check():
    """08:00 — 4 health checks. Returns summary string."""
    checks = []
    now = datetime.datetime.now()

    # Check 1: Rate importer ran today?
    if os.path.isdir(RATE_IMPORTER_PATH):
        latest = 0
        for f in os.listdir(RATE_IMPORTER_PATH):
            fp = os.path.join(RATE_IMPORTER_PATH, f)
            if os.path.isfile(fp):
                mtime = os.path.getmtime(fp)
                latest = max(latest, mtime)
        if latest > 0:
            age_h = (time.time() - latest) / 3600
            if age_h > 24:
                checks.append("\u26A0\uFE0F Rate data stale ({:.0f}h old)".format(age_h))
            else:
                checks.append("\u2705 Rate data fresh ({:.0f}h old)".format(age_h))
        else:
            checks.append("\u26A0\uFE0F No rate data files found")
    else:
        checks.append("\u26A0\uFE0F Rate importer path not found")

    # Check 2: ERP_Master.xlsm modified in last 24h?
    if os.path.exists(ERP_MASTER_PATH):
        age_h = (time.time() - os.path.getmtime(ERP_MASTER_PATH)) / 3600
        if age_h > 24:
            checks.append("\u2139\uFE0F ERP no update today ({:.0f}h)".format(age_h))
        else:
            checks.append("\u2705 ERP updated ({:.0f}h ago)".format(age_h))
    else:
        checks.append("\u26A0\uFE0F ERP_Master.xlsm not found")

    # Check 3: Any FAIL tasks in last 24h?
    summary = task_board.get_board_summary()
    failed = summary.get("failed", [])
    recent_fails = []
    cutoff = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    for t in failed:
        if t.get("updated_at", "") >= cutoff:
            recent_fails.append(t)
    if recent_fails:
        checks.append(f"\U0001F6A8 {len(recent_fails)} task FAIL in 24h")
    else:
        checks.append("\u2705 No recent failures")

    # Check 4: Parquet file size?
    if os.path.exists(PARQUET_PATH):
        size = os.path.getsize(PARQUET_PATH)
        if size < PARQUET_MIN_SIZE:
            checks.append(f"\u26A0\uFE0F Parquet small ({size:,} bytes)")
        else:
            checks.append(f"\u2705 Parquet OK ({size:,} bytes)")
    else:
        checks.append("\u26A0\uFE0F Parquet file not found")

    header = f"\U0001F916 N\xd3I: Morning check {now.strftime('%Y-%m-%d %H:%M')}"
    return header + "\n" + "\n".join(checks)


def eod_digest():
    """17:00 — End of day summary."""
    now = datetime.datetime.now()
    summary = task_board.get_board_summary()

    completed = len(summary.get("complete", []))
    failed = len(summary.get("failed", []))
    in_prog = len(summary.get("in_progress", []))

    lessons = learning_loop.get_recent_lessons(1)

    msg = (
        f"\U0001F4CA N\xd3I: EOD Digest {now.strftime('%Y-%m-%d')}\n"
        f"Tasks completed: {completed}\n"
        f"Tasks failed: {failed}\n"
        f"In progress: {in_prog}\n"
        f"Lessons today: {len(lessons)}"
    )
    return msg


def weekly_report():
    """Monday 08:30 — Weekly intelligence report."""
    report = learning_loop.generate_weekly_report()
    summary = task_board.get_board_summary()
    total = sum(len(v) for v in summary.values())

    msg = (
        f"\U0001F4CA N\xd3I: Weekly Intelligence\n"
        f"Board total: {total} tasks\n\n"
        f"{report}"
    )
    return msg


# ── Scheduler Thread ──
_scheduler_running = False


def _scheduler_loop():
    """Background scheduler for proactive checks."""
    import notifier
    while _scheduler_running:
        now = datetime.datetime.now()
        h, m = now.hour, now.minute

        try:
            # 08:00 - Morning check
            if h == 8 and m == 0:
                msg = morning_check()
                notifier.send(msg)
                time.sleep(60)  # prevent re-trigger

            # 17:00 - EOD digest
            elif h == 17 and m == 0:
                msg = eod_digest()
                notifier.send(msg)
                time.sleep(60)

            # Monday 08:30 - Weekly report
            elif now.weekday() == 0 and h == 8 and m == 30:
                msg = weekly_report()
                notifier.send(msg)
                time.sleep(60)

        except Exception as e:
            print(f"[MONITOR] Error: {e}")

        time.sleep(30)  # check every 30 seconds


def start_scheduler():
    """Start the proactive monitor as a daemon thread."""
    global _scheduler_running
    _scheduler_running = True
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    print("[MONITOR] Scheduler started: 08:00/17:00/Mon 08:30")
    return t


def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False
