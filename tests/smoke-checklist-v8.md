# Smoke Checklist V8 — Sếp manual verify sau mỗi sprint

**Mục đích:** Bảo vệ 9 view web + backend ẩn V7 không bị vỡ khi V8 nâng cấp. 5 phút click qua, tick từng ô. Ô nào ✕ → rollback `.bak.{sprint-tag}` hoặc `git checkout v7-stable-20260429 -- <file>`.

**Rollback targets:**
- Per-file backup: `cp web_server.py.bak.20260429-graph web_server.py` (rollback Sprint 1)
- Full rollback: `git checkout v7-stable-20260429` (rollback toàn repo về point ổn định 2026-04-29)

**Khi chạy:** Sau mỗi sprint M2.7 ship xong, trước khi ship sprint kế tiếp.

**Pre-req:** `python email_engine/web_server.py` chạy port 8231.

---

## Web Dashboard — 9 view (mở `http://localhost:8231/`)

- [ ] **1. Quick Send** mặc định active. KPI row "Sent Apr 2026 / Opened / Open Rate" hiển thị số (không phải `—`).
- [ ] **2. Priority** — click sidebar. Bảng prospects hiện ≥10 row, không "Loading..." kẹt.
- [ ] **3. Inbox** — click sidebar. Recent replies render (có thể empty nếu không có reply gần — OK miễn không error).
- [ ] **4. Insights** — campaign-stats hiện. **PLYWOOD reply rate ≈ 32.5%** (verify metric không bị reset/clear).
- [ ] **5. AI Model** — view render. Train/predict button click không 500.
- [ ] **6. Alerts** — `/api/email-events/alerts/count` không lỗi 500. View render.
- [ ] **7. Open Tracker** — `/api/opens/feed` trả JSON. Pixel `/t/o/{job_id}.gif` còn endpoint.
- [ ] **8. Follow-up Queue** — `/api/sequence/due` trả JSON, view render.
- [ ] **9. Settings** — Suppression list load. `/api/config` trả 200.

## Backend ẩn — endpoint smoke (curl/browser)

- [ ] **10. Daily rotation** — `/api/email-rate/batch/progress` trả JSON có field `total_sent`, `target`.
- [ ] **11. Sent scan** — `/api/sent-scan/pending` trả JSON (có thể `[]` nếu không có pending — OK).
- [ ] **12. Bounce KB** — `/api/bounce-kb/summary` trả JSON với `learned_count`, `dead_domains`.
- [ ] **13. Suppression** — `/api/suppression/list` trả JSON list.
- [ ] **14. WhatsApp** — `/api/whatsapp/status` trả 200 (không cần connected, chỉ cần endpoint sống).
- [ ] **15. Panjiva** — `/api/panjiva/history` trả JSON.
- [ ] **16. Smart draft AI** — `/api/draft/smart` POST với body test → trả 200/400 (không 500).
- [ ] **17. Send-time AI** — `/api/send-time/state-breakdown` trả JSON.
- [ ] **18. CNEE memory** — `/api/cnee/memory/test@example.com` trả JSON (rỗng OK).
- [ ] **19. Patterns** — `/api/patterns/top-templates` trả ≥1 template.

## Send flow (live, 1 email test) — RUN sau khi Sprint 1 ship

- [ ] **20. Bấm Smart Send** → flow Confirm modal mở.
- [ ] **21. Send 1 test email** tới chính mình → trong 30s dashboard hiện ✅ + msg_id (Sprint 1 verified badge).
- [ ] **22. Outlook Sent folder** → email tồn tại với subject + recipient đúng.
- [ ] **23. `email_log.csv`** → row mới có cột `backend=graph`, `graph_msg_id=AAMkA...`, `verified=yes`.

---

## Cách dùng

1. Sau M2.7 báo "Sprint X done", Sếp mở file này (`tests/smoke-checklist-v8.md`).
2. Restart `email_engine/web_server.py`.
3. Tick từ ô 1 → 19 (mỗi ô ~10s click). Tổng ~5 phút.
4. Sprint 1 ship xong: tick thêm ô 20-23 (live send test).
5. Ô nào ✕:
   - Sprint 1 fail → `cp web_server.py.bak.20260429-graph web_server.py` (rollback chỉ Sprint 1)
   - Vỡ nặng diện rộng → `git checkout v7-stable-20260429` (rollback toàn repo)
6. Báo em ô nào fail + log error → em diagnose.

---

## Tag history

| Tag | Date | Sprint shipped before tag |
|---|---|---|
| `v7-stable-20260429` | 2026-04-29 | (none — V7 baseline) |
| `v8-sprint1-green` | TBD | Sprint 1 graph-send-reliability |
| `v8-sprint2-green` | TBD | Sprint 2 error-detection |
