# Domain: CODE — Path resolver + multi-machine + skill orchestration (rules-of-the-house)

## Tóm tắt
Code domain là các quy tắc giúp hệ thống hoạt động đúng trên máy anh (PC Home) và trên VPS. Nó bao gồm path resolver, multi-machine detection, và skill orchestration.

---

## Rule 1: Path resolver — shared/paths.py là SOT cho mọi path

### Anh thấy gì
Khi em làm việc với đường dẫn file (ví dụ: D:/OneDrive/NelsonData/...), em dùng shared/paths.py để resolve đúng đường dẫn trên máy anh.

### Quy định
- `shared/paths.py` = Single Source of Truth cho tất cả paths
- Tự động detect machine: PC Home / Laptop VP / VPS
- MACHINE detection: `shared.paths.MACHINE` → pc-home / laptop-vp / vps
- Đường dẫn OneDrive: `C:/Users/ADMIN/OneDrive/` (PC Home) hoặc `C:/Users/Nelson/OneDrive/` (Laptop VP)

### Khi sai → hậu quả
- Hardcoded path → không work trên machine khác
- File not found → em không tìm thấy data

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 4 rule chi tiết</summary>

- MACHINE auto-detect: pc-home / laptop-vp / vps
- OneDrive path: C:/Users/ADMIN/OneDrive/ (PC Home), C:/Users/Nelson/OneDrive/ (Laptop VP)
- GoClaw paths: D:/GoClaw/data/goclaw.db, D:/GoClaw/workspace/
- Bat tools: C:/Users/Nelson/5398948978/
</details>

---

## Rule 2: Multi-machine — code phải work trên 3 environments

### Anh thấy gì
Code của anh chạy trên 3 machine khác nhau:
- **PC Home**: Claude Code development + Email Dashboard
- **Laptop VP**: Telegram bot runtime (bot_v5)
- **VPS (14.225.207.145)**: API (port 8100) + WebApp (port 3003) + Telegram Bot

### Quy định
- SSH key PC Home: C:\Users\ADMIN\.ssh\id_nelson_vps
- SSH key Laptop VP: id_ed25519 (working as of 2026-03-24)
- Deploy script: Cowork deploy dùng PowerShell (không SSH trực tiếp)
- Port 3000/3001: TraSuaPOS Docker — KHÔNG BAO GIỜ chạm

### Khi sai → hậu quả
- Code chỉ work trên PC Home → fail trên VPS
- Port conflict → Docker services bị down

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 5 rule chi tiết</summary>

- VPS services: nelson-api (8100), nelson-webapp3003 (3003)
- Cowork deploy: powershell -ExecutionPolicy Bypass -File cowork_deploy.ps1
- Deploy log: deploy/deploy_log.txt
- OneDrive auto-detect: C:/Users/ADMIN/ (PC Home)
- Code/Data Separation: OneDrive data, shared/paths.py, rclone VPS sync
</details>

---

## Rule 3: Skill orchestration — 11-agent workflow v2.0

### Anh thấy gì
Khi anh yêu cầu một feature mới, em dùng 11-agent workflow:
- **Phase 1 — Design**: design-finder
- **Phase 2 — Review**: ux-reviewer, code-reviewer, security-auditor, perf-analyzer
- **Phase 3 — Execute**: master-executor
- **Phase 4 — Process**: test-writer, doc-writer, tech-debt-tracker
- **Phase 5 — Finalize**: git-commit

### Quy định
- **Trigger rules**:
  - "tính năng mới" / "UI mới" → design-finder → ... → git-commit
  - "fix bug" → code-reviewer → master-executor → test-writer → git-commit
  - "bảo mật" / "security audit" → security-auditor → perf-analyzer → ...
  - "viết test" → test-writer
  - "viết docs" → doc-writer
- **Report priority**: security-audit-report > code-review-report > ux-review-report > perf-analysis-report > design-inspiration
- **Never**: tự chạy git commit/push, npm publish, deploy commands

### Khi sai → hậu quả
- Feature không đúng spec → rework
- Security issue không được catch → production bug

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 5 rule chi tiết</summary>

- i18n-checker: KHÔNG dùng (Nelson Email chỉ gửi tiếng Anh)
- Skill map: backend-development, web-frameworks, ui-styling, devops, etc.
- Claude Code path: Engine_test/claudekit-skills/ (legacy), Engine_test/.claude/skills/ (current)
- Memory system: C:\Users\Nelson\.claude\projects\D--NELSON-2--Areas-Engine-test\memory\
- System Standards SOT: docs/SYSTEM_STANDARDS.md — validate trước khi commit
</details>

---

## Rule 4: System Standards validator — check trước khi commit

### Anh thấy gì
Trước khi commit bất kỳ thay đổi nào, em phải chạy validator:

```bash
python scripts/validate-system.py
```

### Quy định
- **Single Source of Truth**: `docs/SYSTEM_STANDARDS.md`
- Validator check tất cả rules trong file đó
- **Pass mới commit** — không được bypass

### Khi sai → hậu quả
- System drift → các phần không hoạt động đúng với nhau
- Data corruption → parquet không sync với ERP

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 2 rule chi tiết</summary>

- validate-system.py: reads SYSTEM_STANDARDS.md → check compliance
- 12 sections: canonical paths, charge name mapping, Active Jobs schema, VBA launch pattern, etc.
</details>

---

## Rule 5: COM threading — Outlook COM chỉ trên main thread

### Anh thấy gì
Khi code giao tiếp với Outlook (đọc email, tạo draft), phải chạy trên main thread.

### Quy định
- **FastAPI worker threads**: COM is NOT initialized
- **Main thread only**: Outlook COM calls phải từ main thread
- si_48h_alert merged INTO shipment_brain (2026-04-22)
- AutoSave OFF khi xlsm + OneDrive → VBA corruption

### Khi sai → hậu quả
- COM error → Outlook operations fail
- Crash → dashboard không respond được

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 3 rule chi tiết</summary>

- inbox_scanner.py: "IMPORTANT: When called from FastAPI worker thread, COM is NOT initialized"
- install_jobs_automation.py: "CRITICAL: Excel COM Save can silently drop customUI bindings"
- COM safety: only call from main thread
</details>

---

## Rule 6: Stale detection — file changed sau server start

### Anh thấy gì
Khi dashboard hiển thị banner "needs restart", có nghĩa là file đã được sửa sau khi server bắt đầu.

### Quy định
- `_CRITICAL_FILES` list compares `st_mtime` vs `SERVER_START_TS`
- Nelson sees "needs restart" banner if any critical file changed after server start
- Pre-warm: sau restart, curl 3 endpoints chậm (send-stats, rotation-today, analytics-overview)

### Khi sai → hậu quả
- Server không reload code mới → feature mới không hoạt động
- Dashboard dùng stale data

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 3 rule chi tiết</summary>

- _CRITICAL_FILES: st_mtime vs SERVER_START_TS comparison
- web_server.py: stale detection banner
- Pre-warm cache after restart: curl endpoints before use
</details>

---

## ✅ Anh đang làm tốt
- PC Home setup đang OPERATIONAL (Dashboard + web_server LIVE)
- OneDrive auto-detect hoạt động đúng (C:/Users/ADMIN/)
- Task Scheduler đã disable cho đến khi switch xong
- GoClaw Fox Spirit lead agent running daily email campaign