# Email Dashboard — Versioning Contract

**Last updated:** 2026-04-23
**Status:** ENFORCED (see `docs/SYSTEM_STANDARDS.md` RULE 8.3)

## TL;DR

Dashboard version (v6, v7, v8…) **KHÔNG BAO GIỜ** xuất hiện trong filename.
Filename cố định, version sống trong code + API + UI. Bump version = sửa 1 dòng.

## Why this exists

**Incident 2026-04-23:** Nelson mở Desktop shortcut, dashboard hiển thị "Nelson Email v6" với "Loading…" vĩnh viễn, KPI toàn dấu "—". Thực tế backend đã chạy v7 (master file `contact_unified_v7.xlsx`, 22,854 rows).

**Root cause:** 4 chỗ hardcode version cho dashboard:

| # | Chỗ | Vấn đề |
|---|-----|--------|
| 1 | Filename `email-dashboard-v6.html` | Phải rename mỗi lần bump |
| 2 | `start-dashboard-v4.bat` dòng 29 mở `plans\visuals\email-dashboard-v6.html` | Hardcode path |
| 3 | `web_server.py` route `/` candidates list `[v5, v4, legacy]` | Chưa thêm v6/v7 |
| 4 | Desktop `.lnk` trỏ `.bat` cũ | Quên update |

→ Shortcut mở file HTML v6 qua `file://` (bypass server) → API fetch bị CORS chặn → UI loading mãi.

Pattern này lặp lại 4 lần: v4→v5 (2026-04-18), v5→v6 (2026-04-22), v6→v7 (2026-04-23).

## Canonical paths (enforced)

| Role | Path |
|------|------|
| Dashboard HTML | `plans/visuals/email-dashboard.html` |
| Launcher script | `email_engine/start-dashboard.bat` |
| Desktop shortcut | `C:/Users/{USER}/OneDrive/Desktop/Nelson Email Dashboard.lnk` |
| Server URL | `http://localhost:8100/` |
| Version API | `http://localhost:8100/api/version` |
| Version constants | `email_engine/web_server.py` lines 11-14 |

**KHÔNG** tạo file có suffix `-v7`, `-v8`, `-v2`, `-final`, `-new`. Nếu cần backup khi bump, dùng `plans/visuals/archive-dashboard-old/` + đặt tên có date (`email-dashboard-20260423.html`).

## Version source of truth

`email_engine/web_server.py` (đầu file):

```python
# Single source of truth for dashboard version.
DASHBOARD_VERSION = "v7"
DASHBOARD_RELEASED = "2026-04-23"
DASHBOARD_MASTER_FILE = "contact_unified_v7.xlsx"
```

Endpoint:

```python
@app.get("/api/version")
def api_version():
    return {
        "version": DASHBOARD_VERSION,
        "released": DASHBOARD_RELEASED,
        "master_file": DASHBOARD_MASTER_FILE,
    }
```

UI fetch (cuối `email-dashboard.html`):

```javascript
if (window.location.protocol === 'file:') {
  document.getElementById('file-warning').style.display = 'block';
  document.title = 'Nelson Email · file:// mode';
  return;
}
fetch('/api/version').then(r => r.json()).then(v => {
  const tag = `${v.version} · ${v.released}`;
  document.getElementById('brand-version').textContent = `Email · ${tag}`;
  document.title = `Nelson Email ${v.version}`;
});
```

## How to bump version (v7 → v8)

1. Sửa 3 dòng trong `email_engine/web_server.py`:
   ```python
   DASHBOARD_VERSION = "v8"
   DASHBOARD_RELEASED = "2026-05-XX"
   DASHBOARD_MASTER_FILE = "contact_unified_v8.xlsx"   # nếu master file đổi
   ```
2. Restart server (`taskkill /F /PID <pid>` rồi `pythonw web_server.py`, hoặc click lại shortcut).
3. Reload browser — header + tab title auto-update.
4. Commit: `chore(dashboard): bump version v7 → v8`.

**KHÔNG** rename `.html`, `.bat`, `.lnk`. **KHÔNG** sửa route `/`.

## How to update dashboard UI (khác bump version)

Nếu chỉ sửa layout/logic:
1. Edit trực tiếp `plans/visuals/email-dashboard.html`.
2. Reload browser (hard reload `Ctrl+Shift+R` nếu cache).

Nếu rewrite lớn:
1. Vẫn edit in-place file `email-dashboard.html`.
2. Nếu cần giữ bản cũ để so sánh: copy → `archive-dashboard-old/email-dashboard-{YYYYMMDD}.html`.

## Guard: file:// detection

HTML có banner đỏ full-width (hidden by default) hiển thị khi `window.location.protocol === 'file:'`. Text:

> ⚠ Dashboard đang mở qua file:// — API không chạy. Hãy mở http://localhost:8100/ (dùng shortcut Nelson Email Dashboard).

Nếu Nelson thấy banner đỏ: đã mở sai cách (double-click file HTML trực tiếp). Phải dùng Desktop shortcut.

## Launcher script contract (`start-dashboard.bat`)

1. Kill process listening port 8100 (nếu có).
2. Start `pythonw web_server.py` hidden (background).
3. Poll `GET /api/version` mỗi giây, timeout 20s.
4. Nếu API ready → start `outlook_queue_worker.py --workers 3 --loop` hidden.
5. Nếu timeout → warn, skip worker (user vẫn có thể dùng dashboard read-only).
6. `start "" "http://localhost:8100/"` — mở browser qua URL (KHÔNG qua file://).

## Checklist khi merge PR chạm dashboard

- [ ] Không có filename mới chứa `-v\d+` (regex fail → reject)
- [ ] Không hardcode path `email-dashboard-v*.html` trong code
- [ ] Route `/` vẫn serve `email-dashboard.html` duy nhất
- [ ] `.bat` vẫn mở URL `http://localhost:8100/`
- [ ] Guard `file://` banner vẫn còn trong HTML
- [ ] Script fetch `/api/version` vẫn còn và đúng element IDs

## References

- Rule: `docs/SYSTEM_STANDARDS.md` Section 8, RULE 8.3
- Commit: `5944370` (2026-04-23)
- Memory: `feedback-no-version-in-filename.md`
- Related incident: v6→v7 migration 2026-04-23 session wrap
