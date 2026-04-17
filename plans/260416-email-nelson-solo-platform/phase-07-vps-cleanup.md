# Phase 07 — VPS Cleanup (kill email routers)

**Priority:** LOW (tech debt, can parallel with others)
**Status:** Pending approval
**Slogan map:** Tech debt — cho codebase sạch, không distract

## Context

Đã quyết (2026-04-16): Kill VPS email hoàn toàn. Chỉ giữ VPS cho:
- Rate query (bot Telegram)
- GoClaw skills (Phase 05 intel-auto-reply)
- Intelligence/market public endpoint

Audit A1 xong. Danh sách file cần xử lý ở bên dưới.

## Key Insights

- Merge với Phase 05 cần: GoClaw cần access rate API → phải giữ `rate_router.py`
- Drop `email_queue` table destructive → backup first
- WebApp Next.js 3 pages (rate-send, email-campaign, email-log) — kill tất cả
- `queue_manager.py` auto-scheduler — kill luôn (Nelson không dùng đêm thông qua VPS nữa, GoClaw riêng)

## Requirements

**Must do (to not break VPS):**
1. Remove router includes trong `api/app.py`
2. Delete router files
3. Kill 3 WebApp pages + clean api.ts/useApi.ts
4. Drop `email_queue` table (backup first)
5. Update test + health check
6. Deploy + verify GoClaw bot vẫn query rate OK

**Must keep:**
- `rate_router.py`, `latest_rates_router.py`, `pricing_router.py`
- `intelligence_router.py`
- `auto_quote_router.py`
- `erp_router.py`, `hpl_router.py`, `sync_router.py`
- `dashboard_router.py` (generic data endpoints)
- `customer_check_router.py`
- `job_router.py`, `shipment_router.py`
- `data_router.py`, `health_router.py`
- `auth_router.py`, `worker_router.py`

## Architecture

```
BEFORE (VPS /api routes):
  /api/email-rate/*       ❌ KILL
  /api/email/queue/*      ❌ KILL
  /api/rates/*            ✅ KEEP
  /api/intelligence/*     ✅ KEEP
  /api/erp/*              ✅ KEEP
  /api/goclaw/*           ✅ ADD (Phase 05)

AFTER:
  Only non-email + rate + GoClaw skills
```

## Related Code Files

**Delete:**
- `api/routers/email_rate_router.py` (1,639 lines)
- `api/routers/email_queue_router.py` (248 lines)
- `api/pipeline/queue_manager.py` (auto-scheduler)
- `api/pipeline/template_engine.py` (if only used by queue_manager)
- `api/pipeline/blacklist.py` (if only used by queue_manager)
- `webapp/src/app/dashboard/rate-send/page.tsx` + folder
- `webapp/src/app/dashboard/email-campaign/page.tsx` + folder
- `webapp/src/app/dashboard/email-log/page.tsx` + folder

**Modify:**
- `api/app.py` — remove 3 import lines + 2 include_router lines
- `webapp/src/lib/api.ts` — remove email-rate methods (~15 functions)
- `webapp/src/hooks/useApi.ts` — remove email-rate hooks
- `webapp/src/app/dashboard/page.tsx` — remove menu links to 3 pages
- `api/tests/test_health.py` — remove email endpoint assertions
- `deploy/vps_deploy_full.sh` — remove email health check curl
- Update `CLAUDE.md` — note VPS email killed

**Database:**
- Backup: `pg_dump -t email_queue > backup-email-queue-20260416.sql`
- Then: `DROP TABLE email_queue CASCADE;`
- Migration file `003_email_platform.sql` — keep (history), maybe rename suffix `-deprecated`

**Env cleanup on VPS:**
- Remove: `SMTP_*`, `EMAIL_FROM`, related
- Keep: DB creds, Telegram token, rate API keys

## Implementation Steps

1. **Backup first:**
   - `pg_dump -h localhost -U nelson -t email_queue > backup.sql`
   - Git tag: `git tag pre-email-kill-2026-04-16 && git push --tags`

2. **WebApp cleanup (local):**
   - `rm -rf webapp/src/app/dashboard/{rate-send,email-campaign,email-log}`
   - Edit `webapp/src/lib/api.ts` — delete email-rate methods
   - Edit `webapp/src/hooks/useApi.ts` — delete email-rate hooks
   - Edit `webapp/src/app/dashboard/page.tsx` menu
   - Verify Next.js build: `npm run build` (no broken imports)

3. **Backend cleanup (local):**
   - `rm api/routers/{email_rate_router,email_queue_router}.py`
   - `rm api/pipeline/{queue_manager,template_engine,blacklist}.py` (verify unused)
   - Edit `api/app.py` — remove imports + includes
   - Edit `api/tests/test_health.py`
   - Edit `deploy/vps_deploy_full.sh`
   - Verify import tree: `python -c "from api.app import app"` passes

4. **Commit + deploy:**
   - `git add . && git commit -m "feat(email): kill VPS email stack — local-only from now"`
   - `git push` → GitHub Actions auto-deploys
   - Wait 3 min
   - Verify VPS: `curl http://14.225.207.145:8100/api/rates` still works

5. **DB cleanup (VPS, manual):**
   - SSH VPS
   - `pg_dump -t email_queue > ~/backup-email-queue.sql`
   - `psql -c "DROP TABLE email_queue CASCADE;"`
   - Verify GoClaw bot: Telegram `/rate HPH USLAX` still responds

6. **Update docs:**
   - `CLAUDE.md` — note VPS email killed, local-only
   - Memory: already has `project-email-stack-audit.md` + `nelson-slogan-and-focus.md`

## Todo List

- [ ] DB backup (pg_dump)
- [ ] Git tag pre-kill
- [ ] Delete 3 WebApp pages + lib/hooks methods
- [ ] Next.js build check
- [ ] Delete VPS routers + pipeline files
- [ ] Edit api/app.py imports
- [ ] Update tests + health check
- [ ] Commit + GitHub Actions deploy
- [ ] Verify rate API still OK on VPS
- [ ] Drop email_queue table
- [ ] Verify GoClaw bot rate query works
- [ ] Update CLAUDE.md

## Success Criteria

- VPS API boots without error
- `curl /api/email-rate/*` → 404 (killed)
- `curl /api/rates?pol=HPH&dest=USLAX` → 200 OK
- GoClaw Telegram `/rate HPH USLAX` → bot replies with rate
- Next.js WebApp builds + dashboard has no broken links
- Git commit clean, no orphaned imports

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| GoClaw depends on email router | Audit GoClaw code first; extract shared helpers before kill |
| Other tests depend on email endpoints | Run full test suite pre-kill; fix broken ones |
| Next.js build fails due to dangling imports | Build locally before commit |
| DROP TABLE loses data | Backup first + git tag |
| Scheduled jobs still try call email router | Check Task Scheduler / cron on VPS and laptop |

## Security Considerations

- Remove ENV SMTP creds on VPS — nếu leak cũng không dùng được
- Revoke any old SMTP app passwords (O365)
- Confirm no `.env` committed with creds

## Next Steps

After Phase 07:
- VPS surface smaller → attack surface giảm
- Codebase clear → developer (em) đỡ confuse
- Solo pipeline complete from user-facing perspective
