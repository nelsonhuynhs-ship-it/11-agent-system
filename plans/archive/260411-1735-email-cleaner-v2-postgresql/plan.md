# Email Cleaner Tool v2 — PostgreSQL Data Source

> **Status**: 📋 Ready for Platform Team | **Created**: 2026-04-11 17:35 | **Target repo**: FrieghtBrian | **Owner task**: PLATFORM-LEAD
>
> **Supersedes**: `plans/260411-1709-email-cleaner-tool/` (PR #21, merged 2026-04-11). V1 assumed CSV input; Nelson clarified customer data lives in **PostgreSQL (FrieghtBrian DB)**. V1 directory is deleted in this PR.

## What changed vs v1

| Aspect | v1 (merged, deleted) | v2 (this plan) |
|---|---|---|
| Input | Raw CSV (`5,316 CNEE prospects`) | PostgreSQL table in FrieghtBrian DB |
| Phase 1 | Reacher Docker + init TS project | PG client + **schema discovery** (first!) |
| Cache layer | Separate PG DB, table `email_verification_cache` | **Same PG** as source, dedicated schema `email_cleaner` |
| Output | 3 CSV files | Write-back to PG + optional CSV export for review |
| Credentials | Not specified | `DATABASE_URL` via agent `other_config.env` — **never paste in chat** |
| Unresolved questions | 4 (CSV path, output dir, cron, notify) | 5 (source table, write-back mode, re-verify policy, scope, dry-run) |

Retained from v1: tool choice (`reacherhq/check-if-email-exists`), pre-filter strategy, status taxonomy (VALID/INVALID/DISPOSABLE/CATCH_ALL/NO_MX/UNKNOWN), p-limit(10) concurrency, 30-day cache TTL, AGPL-3.0 risk analysis.

## Goal

Build TypeScript tool that **reads customer emails directly from the FrieghtBrian PostgreSQL database**, verifies them via Reacher (MX/SMTP/disposable/catch-all), caches results in the same DB, and writes verification status back to the source table (or exports for review if dry-run).

## Critical security constraint — DATABASE_URL handling

> **Lead MUST NOT ask Nelson to paste `DATABASE_URL` in Telegram chat.** Leaked credentials in chat history = immediate rotation overhead.

**Correct flow**:
1. Nelson sets `DATABASE_URL` in the target agent's **`other_config.env`** via GoClaw UI (Agents → edit → Env section). Value format: `postgresql://user:pass@host:5432/freight_brian?sslmode=require`.
2. Agent process receives it as environment variable at spawn time (GoClaw injects `other_config.env` → sandbox env).
3. Tool code reads `process.env.DATABASE_URL`; throws fast if missing. Never logs the URL (log only `host:port/db` after parsing).
4. Agents working on this task: `platform-backend` needs it for read + cache write; `platform-devops` only for Phase 2 Docker Compose (reads URL to wire Reacher container env if needed); `platform-qa` does NOT get DB access (mocks only).
5. Lead coordinates: if an agent reports "missing DATABASE_URL", Lead replies "Nelson will configure it in your other_config.env — do not request it in chat". Lead then asks Nelson out-of-band (not through task comments).

**DB user privileges** (Nelson to set when creating the PG role):
- Phase 1 discovery: `GRANT USAGE ON SCHEMA public TO email_cleaner_ro; GRANT SELECT ON ALL TABLES IN SCHEMA public TO email_cleaner_ro;` (read-only).
- Phase 4 write-back: separate role `email_cleaner_rw` with `UPDATE` on the target column only, plus `CREATE/USAGE` on schema `email_cleaner`.
- Recommended: use **two DATABASE_URLs** (`DATABASE_URL_RO` for discovery/verify, `DATABASE_URL_RW` for write-back) so read-only phases cannot accidentally mutate data.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│ FrieghtBrian PostgreSQL (source of truth)                  │
│   schema public.<customer_table>  ← emails live here       │
│   schema email_cleaner.cache      ← results + TTL          │
│   schema email_cleaner.runs       ← run audit log          │
└──────────┬─────────────────────────────────────────────────┘
           │ SELECT (via pg client, DATABASE_URL_RO)
           ▼
┌────────────────────────────────────────────────────────────┐
│ Step 1: Fetch rows (src/db/fetch-emails.ts)                │
│   - Parameterized query (no string concat)                 │
│   - Batch cursor: 500 rows/page                            │
└──────────┬─────────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────────┐
│ Step 2: Pre-filter (fast, offline)                         │
│   - validator.isEmail()                                    │
│   - disposable-email-domains                               │
└──────────┬─────────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────────┐
│ Step 3: Cache lookup + Reacher verify                      │
│   - SELECT FROM email_cleaner.cache WHERE email=$1         │
│   - Cache MISS → POST localhost:8080/v0/check_email        │
│   - INSERT INTO email_cleaner.cache                        │
│   - p-limit(10), exponential backoff                       │
└──────────┬─────────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────────┐
│ Step 4: Write-back (src/db/writeback.ts)                   │
│   - Mode A: UPDATE public.<table>.email_status             │
│   - Mode B: INSERT INTO email_cleaner.results              │
│   - Mode C: dry-run → only CSV export, no DB write         │
│   - Wrapped in transaction; rollback on any failure        │
└────────────────────────────────────────────────────────────┘
```

## Deliverables

| # | File | Purpose |
|---|---|---|
| 1 | `tools/email-cleaner/docker-compose.yml` | Reacher backend |
| 2 | `tools/email-cleaner/src/db/client.ts` | `pg.Pool` factory, reads `DATABASE_URL` from env |
| 3 | `tools/email-cleaner/src/db/fetch-emails.ts` | Cursor-based batch fetch |
| 4 | `tools/email-cleaner/src/db/cache.ts` | `email_cleaner.cache` read/write |
| 5 | `tools/email-cleaner/src/db/writeback.ts` | Update source table OR insert into results |
| 6 | `tools/email-cleaner/src/verify/pre-filter.ts` | Syntax + disposable (no network) |
| 7 | `tools/email-cleaner/src/verify/reacher-client.ts` | HTTP client, p-limit, retry |
| 8 | `tools/email-cleaner/src/export.ts` | Optional CSV export for review |
| 9 | `tools/email-cleaner/src/cli.ts` | `node cli.ts --table customers --email-col email1 --mode writeback` |
| 10 | `tools/email-cleaner/migrations/001_email_cleaner_schema.sql` | CREATE SCHEMA + cache + runs tables |
| 11 | `tools/email-cleaner/migrations/002_add_email_status_column.sql` | Optional ALTER on source table (if Mode A) |
| 12 | `tools/email-cleaner/docs/schema-discovery.md` | Output of Phase 1 — tables/columns found |
| 13 | `tools/email-cleaner/tests/*.test.ts` | Unit + integration |
| 14 | `tools/email-cleaner/README.md` | Quick start + env var setup |

## Dependencies

```json
{
  "dependencies": {
    "pg": "^8",
    "validator": "^13",
    "disposable-email-domains": "^1",
    "commander": "^12",
    "pino": "^9",
    "p-limit": "^6",
    "csv-stringify": "^6"
  },
  "devDependencies": {
    "typescript": "^5",
    "tsx": "^4",
    "vitest": "^2",
    "@types/node": "^20",
    "@types/pg": "^8"
  }
}
```

`csv-parse` dropped (no CSV input). `csv-stringify` kept only for optional export.

## Implementation Steps (for Platform Team)

### Phase 1 — PG client + schema discovery (45 min) — platform-backend

**Goal**: connect to FrieghtBrian DB and understand the customer-email landscape **before writing any app code**. Produces `docs/schema-discovery.md` with findings Nelson reviews.

1. Init TS project: `tools/email-cleaner/`, `npm init -y`, `tsconfig.json` strict, install deps.
2. Write `src/db/client.ts`:
   - `function getPool(): pg.Pool` reading `process.env.DATABASE_URL` (or `DATABASE_URL_RO` if both set).
   - Throw clear error if missing: `"DATABASE_URL not set. Ask Nelson to configure it in this agent's other_config.env — do NOT paste in chat."`.
   - Log only `host:port/db` on connect, never full URL.
3. Write `scripts/discover-schema.ts`:
   - Query `information_schema.tables WHERE table_schema = 'public'`.
   - For each table, query `information_schema.columns` where column name matches `ILIKE '%email%'`.
   - For top 3 candidate tables: `SELECT COUNT(*)` and 5 sample rows (emails only, no PII).
4. Run discovery: `tsx scripts/discover-schema.ts > docs/schema-discovery.md`.
5. Output `docs/schema-discovery.md` must contain:
   - Candidate tables (name, row count, email column names, sample values masked)
   - Recommended target table + column
   - Any red flags (e.g., multiple email columns → need flatten, JSON arrays → need `jsonb_array_elements_text`)
6. **Stop for Nelson approval** of target table before Phase 2 (this is a gate).
7. Commit: `chore(email-cleaner): PG client + schema discovery`.

**Guardrails**: Phase 1 uses read-only connection. No migrations. No writes. If `DATABASE_URL` missing, phase fails fast with the message above — platform-backend does **not** ask Nelson for it in task comments.

### Phase 2 — Reacher backend + query layer (45 min) — platform-devops + platform-backend

1. `platform-devops`: write `tools/email-cleaner/docker-compose.yml` (Reacher backend, same as v1).
2. `platform-devops`: verify `docker compose up -d && curl localhost:8080/v0/check_email -d '{"to_email":"test@gmail.com"}'`.
3. `platform-backend`: write `src/db/fetch-emails.ts` based on Phase 1 findings:
   - Accept `{ table: string, emailColumn: string, where?: string, batchSize: number }`.
   - Use parameterized query via `pg.Pool.query('SELECT id, $1::text AS email FROM ...', [...])` — **never** concat user input into SQL.
   - Cursor-based: `DECLARE c CURSOR FOR ...; FETCH 500 FROM c` to avoid loading all rows.
4. Integration test: fetch first 10 rows from Nelson-approved table, assert shape.
5. Commit: `feat(email-cleaner): reacher compose + PG fetch layer`.

### Phase 3 — Pre-filter + verify + cache (1h) — platform-backend

1. `src/verify/pre-filter.ts`: syntax + disposable (same logic as v1).
2. `migrations/001_email_cleaner_schema.sql`:
   ```sql
   CREATE SCHEMA IF NOT EXISTS email_cleaner;
   CREATE TABLE IF NOT EXISTS email_cleaner.cache (
     email VARCHAR(320) PRIMARY KEY,
     status VARCHAR(16) NOT NULL,
     reacher_raw JSONB,
     verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
   );
   CREATE INDEX IF NOT EXISTS idx_cache_expires ON email_cleaner.cache(expires_at);
   CREATE TABLE IF NOT EXISTS email_cleaner.runs (
     run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     finished_at TIMESTAMPTZ,
     mode VARCHAR(16) NOT NULL,
     total_rows INT,
     cache_hits INT,
     stats JSONB
   );
   ```
3. `src/db/cache.ts`:
   - `getCached(email) → Result | null` (only non-expired rows).
   - `setCached(email, result)` with `ON CONFLICT (email) DO UPDATE`.
4. `src/verify/reacher-client.ts`: HTTP client with `p-limit(10)`, exponential backoff (3 retries: 1s/2s/4s). Map Reacher JSON → status taxonomy.
5. Main loop: `fetchEmails → preFilter → cacheGet → reacherVerify → cacheSet`.
6. Unit tests (vitest): mock `pg.Pool`, mock `fetch`. Cover 5 status mappings + cache hit/miss.
7. Commit: `feat(email-cleaner): pre-filter + reacher client + cache`.

### Phase 4 — Write-back + export (45 min) — platform-backend

1. `src/db/writeback.ts` supporting 3 modes (flag `--mode writeback|results-table|dry-run`):
   - **writeback**: `UPDATE <table> SET email_status = $1 WHERE id = $2` wrapped in `BEGIN/COMMIT`. Requires `DATABASE_URL_RW` + an `ALTER TABLE ... ADD COLUMN email_status VARCHAR(16)` migration (Phase 1 decides if column exists or needs adding).
   - **results-table**: `INSERT INTO email_cleaner.results (source_id, email, status, ...) VALUES ...` — non-destructive; original table untouched.
   - **dry-run**: no DB writes at all; only CSV export.
2. `src/export.ts` (optional, always available regardless of mode):
   - `clean-customers.csv`, `invalid-emails.csv`, `verification-report.json` — same schema as v1.
3. Transaction safety: any single row failure rolls back the whole batch; resumable via `runs` table (continue from last successful `source_id`).
4. Insert a row into `email_cleaner.runs` at start and update on finish with stats.
5. Commit: `feat(email-cleaner): write-back modes + CSV export`.

### Phase 5 — Tests + QA (45 min) — platform-backend + platform-qa

1. Unit tests (already started in Phase 3): extend to write-back paths with mocked `pg.Pool`.
2. Integration test (dry-run only on real DB): 10-row sample, verify no writes occur, CSV output matches expectations.
3. `platform-qa` review checklist:
   - [ ] No hardcoded credentials anywhere (grep `postgresql://`, `DATABASE_URL` string literals).
   - [ ] `DATABASE_URL` only accessed via `process.env`.
   - [ ] Log output never contains full connection string (redact test with fake URL).
   - [ ] All SQL is parameterized (grep for template literal SQL).
   - [ ] Write-back is transactional.
   - [ ] Dry-run mode confirmed non-destructive.
   - [ ] Coverage > 70% on `src/**`.
6. Commit: `test(email-cleaner): unit + integration + QA review`.

### Phase 6 — Docs + ship (30 min) — platform-lead + platform-devops

1. `README.md` with:
   - Quick start (3 commands + required env vars).
   - **Explicit instructions** to configure `DATABASE_URL` via agent `other_config.env` (NOT chat).
   - Mode descriptions + when to use each.
   - Rollback procedure (restore from `email_cleaner.runs` history).
2. `package.json` scripts: `clean-emails`, `discover-schema`, `migrate`.
3. Append lesson to `docs/lessons-learned.md` (create if missing): *"DATABASE_URL and similar secrets go through agent `other_config.env`, not chat — confirmed pattern from email-cleaner v2 2026-04-11."*
4. `platform-lead` final review → create PR → Nelson review + merge → auto-deploy.

## Success criteria

- [ ] Phase 1 `docs/schema-discovery.md` approved by Nelson before Phase 2 starts.
- [ ] `docker compose up` — Reacher backend healthy.
- [ ] `tsx src/cli.ts --mode dry-run` on 100 real rows completes in < 90s (cache warm).
- [ ] All 3 modes (`writeback`, `results-table`, `dry-run`) exercised in integration tests.
- [ ] QA checklist passes (no leaked credentials, parameterized SQL, transactional write-back).
- [ ] Coverage > 70%.
- [ ] README quick start < 3 minutes to read.
- [ ] PR merged to main, auto-deploy green.

## Risks

| Risk | Mitigation |
|---|---|
| `DATABASE_URL` leaked in chat or logs | Phase 1 fail-fast message; QA gate grep; log only `host:db`; Lead enforces "configure in other_config.env" rule. |
| Write-back corrupts source table | Dry-run default; transactional batches; `runs` audit table; separate `DATABASE_URL_RW` role scoped to single column. |
| Schema discovery finds no email columns | Phase 1 is a gate — stops for Nelson approval. Plan pivots if needed (JSON column, linked `contacts` table, etc.). |
| Long-running job times out mid-verify | Cursor-based fetch + `runs.cache_hits` counter + resumable from last `source_id`. |
| Port 25 blocked at VPS | Same as v1: pre-check `nc -zv mx.google.com 25`; fallback MX-only mode. |
| Reacher rate limit / blacklist | `p-limit(10)` + exponential backoff; throwaway `RCH_FROM_EMAIL`; cache heavily. |
| AGPL-3.0 viral license | Internal use only, no redistribution — unchanged from v1. |
| Cache staleness (30d TTL) | `--no-cache` flag for force re-verify; `expires_at` index for cleanup cron. |

## Out of scope

- Real-time verify API (batch only).
- SendGrid/Mailgun bounce webhook integration (Phase future).
- ML scoring (deterministic rules first).
- Web UI (CLI only).
- Automated cron scheduling (v1 on-demand; cron added later if requested).
- Multi-tenant support (single FrieghtBrian DB only).

## Unresolved questions — Nelson decides before Phase 2

1. **Which source table + email column(s)?** Phase 1 schema discovery will propose top candidates; Nelson picks. If multiple email columns (`email1`, `email2`, `email3`), write-back mode needs a composite key policy (e.g., pick first VALID, or store status per-column).
2. **Write-back mode**: `writeback` (update source), `results-table` (non-destructive), or `dry-run` (no writes, CSV only) for the first run? Recommended: start with `dry-run` on full set, review CSV, then switch to `results-table` or `writeback`.
3. **Re-verification policy**: skip emails already in cache with status VALID? Re-verify if > 30 days old? Force-refresh flag always available via `--no-cache`.
4. **Scope filter**: all rows or a `WHERE` clause (e.g., `status='prospect' AND created_at > '2025-01-01'`)? This affects Phase 2 query design.
5. **Schema for column addition**: if Mode A (`writeback`) selected, OK to `ALTER TABLE ADD COLUMN email_status VARCHAR(16)` on the source table, or create separate join table?

---

## Notes for platform-lead

- Read this plan end-to-end before dispatch.
- **DO NOT** ask Nelson for `DATABASE_URL` in Telegram chat. If an agent blocks on missing env var, reply to the agent with: *"Nelson will configure `DATABASE_URL` in your `other_config.env` out-of-band. Wait for confirmation before retrying."* Then ping Nelson separately asking him to set it via GoClaw UI.
- Phase 1 is a **hard gate** — do not dispatch Phase 2 until Nelson approves `docs/schema-discovery.md`.
- Phase 4 write-back operates on Nelson's real data — dry-run required before first writeback run.
- Use `team_tasks` to split Phase 1-5 into individual agent tasks. Phase 6 is lead + devops.
