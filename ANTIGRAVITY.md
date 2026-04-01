# ANTIGRAVITY.md — Agent Operating Manual
Last updated: 2026-03-31

## Role
Executor agent. Claude (Cowork) = Architect on PC Home.
Flow: Claude designs → Nelson feeds prompt → Antigravity executes
→ reports back → Claude reviews.

## Context Switch Protocol
- "home" = PC Home → ALL development (WebApp + API + email_engine)
- "vp"   = Laptop VP → Chatbot RUNTIME only (bot_v5, Telegram) — NO dev
- Always read .agent/handoff.md at session start

## IMPORTANT: Machine Policy (2026-03-31)
- PC Home is the ONLY machine where Claude/Cowork runs
- Laptop VP chỉ chạy bot — KHÔNG code, KHÔNG dùng Claude Code
- email_engine/ now tracked in Git (no longer .gitignore'd)
- Workspace root: C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\

## Session Start Checklist
1. Read CLAUDE.md
2. Read .agent/handoff.md
3. git pull origin main
4. Report current sprint status

## Execution Rules
- Backup before ANY file edit
- Never delete files — only add/modify
- Alert if code diff > 40%
- Test before commit: npm run build (webapp) / python -m py_compile (api)
- Commit format: "feat/fix/chore: [description]"
- Always report: ✅ DONE / ❌ BLOCKED / ⚠️ ISSUE

## Deploy Pipeline
git add . && git commit -m "..." && git push
→ SSH to VPS (nelson-vps) → git pull → restart services:
  - API:    sudo systemctl restart nelson-api
  - WebApp: cd webapp && npm run build && sudo systemctl restart nelson-webapp3003

## VP Domain Focus (Laptop VP) — RUNTIME ONLY
- bot_v5 Telegram: đang LIVE, không đụng code
- Unified Scanner: chạy tự động 4 jobs mỗi 30 phút
- Nếu bot lỗi: restart bằng systemctl trên VPS, KHÔNG sửa code tại Laptop VP

## Home Domain Focus (PC Home) — PRIORITY QUEUE
1. ⚡ VPS deploy Sprint 13:
   - git push → ssh nelson-vps → git pull
   - Thêm SMTP_USER + SMTP_PASS vào /api/.env trên VPS
   - sudo systemctl restart nelson-api
   - npm run build && sudo systemctl restart nelson-webapp3003
   - Test: curl http://14.225.207.145:8100/api/email-rate/customers
2. JWT middleware route protection (webapp + api)
3. Market Benchmark real data wiring
4. Mentee monitoring dashboard
5. Carrier Scorecard engine

## Sprint 13 — Đã hoàn thành (PC Home, 2026-03-31)
✅ email_rate_router.py — FastAPI, DuckDB, Office 365 SMTP
✅ webapp/rate-send/page.tsx — form + preview + send UI
✅ lib/api.ts — emailRateApi client
✅ Sidebar — thêm "Rate & Send"
✅ .gitignore — email_engine/ now tracked
✅ CLAUDE.md + ANTIGRAVITY.md updated
⏳ VPS deploy — chờ Nelson chạy git push + restart
