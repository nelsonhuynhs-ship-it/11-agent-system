---
phase: 6
title: Sequence Engine COM Cleanup
effort_mm: 30 min
depends: []
blocks: []
---

# Phase 6 — Sequence Engine Cleanup

## Goal

Xoá hoàn toàn conditional COM block trong follow-up sequence path. Default đã dùng Graph, nhưng còn dead branch nếu env override.

## Files Modify

- `email_engine/web_server.py:1311` — xoá block `if EMAIL_SEND_BACKEND == "outlook":` trong `/api/sequence/send`
- `email_engine/core/sequence_engine.py` — bỏ `import win32com` (nếu có) + xóa COM dispatch path

## Diff Expected

**BEFORE** (web_server.py:1301-1330):
```python
def _send_followups():
    outlook = None
    if EMAIL_SEND_BACKEND == "outlook":
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception as e:
            log.error(f"Outlook unavailable for sequence send: {e}")
            return
    ...
    result = _send_email_html(to=c["email"], subject=c["subject"], html_body=body, outlook_app=outlook)
```

**AFTER**:
```python
def _send_followups():
    # Graph-only — Sprint 1 chốt graph_only, không fallback COM
    ...
    result = _send_email_html(to=c["email"], subject=c["subject"], html_body=body)
```

## Acceptance Criteria

- [ ] AC1: `grep -n "EMAIL_SEND_BACKEND.*outlook" email_engine/web_server.py` → 0 match
- [ ] AC2: `grep -rln "import win32com" email_engine/core/sequence_engine.py` → 0
- [ ] AC3: Follow-up send vẫn work qua Graph (smoke test 3 follow-up)
- [ ] AC4: bash syntax + python compile check pass

## Done When

- [ ] 4 AC pass
- [ ] Test follow-up cycle 3 contact
