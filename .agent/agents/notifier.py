# ============================================================
#  NÓI — Notifier + Monitor (N.E.L.S.O.N AI OS)
#  "Sends ALL Telegram messages. No other agent sends directly."
#  Isolated HTTP: requests.Session + HTTPAdapter + IPv4 + Lock
#  Persona: enthusiastic, clear, uses emoji tastefully
# ============================================================
AGENT = "NÓI"
import json, threading, socket
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# ── Force IPv4 (avoid IPv6 fallback issues) ──
_original_getaddrinfo = socket.getaddrinfo

def _getaddrinfo_ipv4(host, port, family=0, *args, **kwargs):
    return _original_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

socket.getaddrinfo = _getaddrinfo_ipv4

# ── Isolated HTTP Session ──
import urllib.request
import urllib.parse

_session_lock = threading.Lock()
_session = None

def _get_session():
    """Get or create isolated HTTP session (thread-safe)."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                try:
                    import requests
                    from requests.adapters import HTTPAdapter
                    s = requests.Session()
                    adapter = HTTPAdapter(
                        pool_connections=64,
                        pool_maxsize=64,
                        max_retries=3,
                    )
                    s.mount("https://", adapter)
                    s.mount("http://", adapter)
                    _session = s
                except ImportError:
                    _session = "urllib"  # Fallback marker
    return _session


def send(message, parse_mode=None):
    """
    Send a message to Nelson via Telegram using isolated session.
    Returns (success: bool, response: dict).
    """
    session = _get_session()
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.NELSON_CHAT_ID,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    # Try requests.Session first, fall back to urllib
    if session != "urllib" and session is not None:
        try:
            resp = session.post(url, json=payload, timeout=10)
            result = resp.json()
            return result.get("ok", False), result
        except Exception as e:
            print(f"[NOTIFIER] requests.Session failed: {e}, falling back to urllib")

    # Fallback: urllib (always available)
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False), result
    except Exception as e:
        print(f"[NOTIFIER] Send failed: {e}")
        return False, {"error": str(e)}


# ── Template Methods (unchanged API) ──

def plan(task_name, steps):
    bullet_list = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
    msg = f"NÃO: Đã lên kế hoạch. {len(steps)} subtasks.\n{bullet_list}"
    return send(msg)


def progress(subagent, filename, detail=""):
    msg = f"\u2699\uFE0F [{subagent}] working on {filename}"
    if detail:
        msg += f"\n{detail}"
    return send(msg)


def done(task_name, files_changed, reviewer_score, backup_path=""):
    file_list = ", ".join(files_changed) if files_changed else "none"
    msg = (
        f"\u2705 {task_name} complete.\n"
        f"Changed: {file_list}\n"
        f"Reviewer: {reviewer_score}"
    )
    if backup_path:
        msg += f"\nBackup: {backup_path}"
    return send(msg)


def alert(reason, action="Reply /approve or /reject"):
    msg = f"\U0001F6A8 {reason}\nAction needed. {action}"
    return send(msg)


def warn(issue, detail=""):
    msg = f"\u26A0\uFE0F {issue}"
    if detail:
        msg += f"\n{detail}"
    return send(msg)


def fail(task_name, reason, rollback_path=""):
    msg = f"\u274C {task_name} FAILED\nReason: {reason}"
    if rollback_path:
        msg += f"\nRolled back from: {rollback_path}"
    return send(msg)


def online(erp_version, context_summary=""):
    msg = f"\U0001F916 CTO Agent online.\nERP: {erp_version}. Ready for tasks."
    if context_summary:
        msg += f"\n\n{context_summary}"
    return send(msg)


def status_report(current_task, progress_pct, details=""):
    bar_filled = int(progress_pct / 10)
    bar = "\u2588" * bar_filled + "\u2591" * (10 - bar_filled)
    msg = f"\U0001F4CA Status: {current_task}\n[{bar}] {progress_pct}%"
    if details:
        msg += f"\n{details}"
    return send(msg)


def activity_reply(task_name, status, detail=""):
    """Quick activity reply for status_query intent (no queue delay)."""
    msg = f"NÃO: {task_name}\nPhase: {status}"
    if detail:
        msg += f"\n{detail}"
    return send(msg)


def send_photo(photo_path, caption=""):
    """Send a photo to Telegram via sendPhoto API."""
    if not photo_path or not os.path.exists(photo_path):
        print(f"[{AGENT}] Photo not found: {photo_path}")
        return False
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendPhoto"
    try:
        _ensure_session()
        with open(photo_path, "rb") as f:
            resp = _session.post(
                url,
                data={"chat_id": config.CHAT_ID, "caption": caption[:1024]},
                files={"photo": f},
                timeout=30,
            )
        ok = resp.json().get("ok", False)
        print(f"[{AGENT}] Photo sent: {ok} — {os.path.basename(photo_path)}")
        return ok
    except Exception as e:
        # Fallback: urllib multipart
        print(f"[{AGENT}] Photo send error (requests): {e}, trying urllib...")
        return _send_photo_urllib(photo_path, caption)


def _send_photo_urllib(photo_path, caption=""):
    """Fallback photo sender using urllib multipart."""
    import io
    try:
        boundary = "----NelsonBoundary"
        body = io.BytesIO()
        # chat_id field
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'.encode())
        body.write(f"{config.CHAT_ID}\r\n".encode())
        # caption field
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="caption"\r\n\r\n'.encode())
        body.write(f"{caption[:1024]}\r\n".encode())
        # photo file
        fname = os.path.basename(photo_path)
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="photo"; filename="{fname}"\r\n'.encode())
        body.write(f"Content-Type: image/png\r\n\r\n".encode())
        with open(photo_path, "rb") as f:
            body.write(f.read())
        body.write(f"\r\n--{boundary}--\r\n".encode())

        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendPhoto"
        import urllib.request
        req = urllib.request.Request(url, data=body.getvalue(), method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        resp = urllib.request.urlopen(req, timeout=30)
        import json
        return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        print(f"[{AGENT}] Photo urllib fallback error: {e}")
        return False


def send_test_report(test_results):
    """Send full test report with screenshots to Nelson Telegram."""
    # Build text summary
    lines = ["\U0001F9EA N\xd3I: N.E.L.S.O.N Test Report\n"]
    for r in test_results:
        icon = "\u2705" if r["verdict"] == "PASS" else "\u274C"
        lines.append(f"{icon} {r['test']}: {r['verdict']}")
        for check in r.get("checks", []):
            lines.append(f"  {check}")
        lines.append("")

    summary = "\n".join(lines)
    send(summary)

    # Send each screenshot
    sent = 0
    for r in test_results:
        sp = r.get("screenshot")
        if sp and os.path.exists(sp):
            caption = f"\U0001F4F8 {r['test']} \u2014 {r['verdict']}"
            if send_photo(sp, caption):
                sent += 1

    print(f"[{AGENT}] Test report sent: {len(test_results)} tests, {sent} screenshots")
    return True
