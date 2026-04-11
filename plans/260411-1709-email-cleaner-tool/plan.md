# Email Cleaner Tool — Customer Data Validation

> **Status**: 📋 Ready for Platform Team | **Created**: 2026-04-11 17:09 | **Target repo**: FrieghtBrian | **Owner task**: PLATFORM-LEAD

## Goal

Build TypeScript tool clean raw customer CSV (5,316 CNEE prospects) — verify emails qua MX/SMTP/disposable/catch-all checks, output clean data ready for email campaigns.

## Input / Output

### Input
```csv
pol,pod,company,email1,email2,email3
Ho Chi Minh,Hanoi,ABC Corp,contact@abc.com,sales@abc.com,
Da Nang,HCMC,XYZ Ltd,info@xyz.com,admin@tempmail.com,test@
TPHCM,Hanoi,123 Co,valid@company.com,,
```

### Output
- `clean-customers.csv` — chỉ email VALID + CATCH_ALL
- `invalid-emails.csv` — email rejected (review trước delete)
- `verification-report.json` — stats tổng hợp
- `parsed-customers.json` — intermediate raw parsed

## Tool Selection — Research Results

### Candidates evaluated

| Tool | Stars | Lang | Status | Score | Note |
|------|-------|------|--------|-------|------|
| **reacherhq/check-if-email-exists** | 8.6K | Rust | ✅ Active (2026-03) | **🥇** | Docker backend, AGPL-3.0, full checks |
| AfterShip/email-verifier | 1.5K | Go | ✅ Active (2026-02) | 🥈 | Library only, MIT |
| truemail-rb/truemail-go | 131 | Go | ✅ Active (2026-04) | 🥉 | Config flexible |
| getpingback/ping-email | 87 | Node.js | ✅ Active | — | SMTP only |
| trumail/trumail | 1.1K | Go | ❌ Archived 2018 | ❌ | Dead |
| debeka/debitis | — | — | ❌ NOT FOUND | ❌ | Plan v2 sai tên repo |

### 🏆 Decision: **reacherhq/check-if-email-exists** (Docker HTTP backend)

**Lý do chọn**:
1. **8.6K stars, most popular** — community trusted
2. **Active maintenance** (last push 2026-03)
3. **Full checks**: syntax + MX + SMTP + disposable + catch-all + role + Gravatar + HIBP breach
4. **Docker ready**: `docker run -p 8080:8080 reacherhq/backend:latest`
5. **AGPL-3.0 free** cho internal use (Nelson không distribute binary → OK)
6. **HTTP API** — TypeScript orchestrator POST `/v0/check_email` → JSON response
7. **Rate limit tự do** khi self-host (không phải SaaS)

**Rủi ro + mitigation**:
- AGPL-3.0 viral license → em research: chỉ affect nếu **distribute modified binary**. Self-host internal (không redistribute) → không trigger. Nelson dùng cho internal cleaning — **safe**.
- Cần outbound port 25 (SMTP verify) → VPS Nelson đã có (đã deploy production)
- Có thể bị blacklist nếu verify quá nhiều → cache results + rate limit phía client

## Architecture

```
┌──────────────────────────────────────────────────┐
│ Input CSV (raw customer data, 5,316 rows)       │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 1: Parse + Flatten (TypeScript)            │
│ - csv-parse npm                                  │
│ - Detect email* columns                          │
│ - Output: parsed-customers.json                  │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 2: Pre-filter (fast, no network)           │
│ - Syntax check (validator npm)                   │
│ - Disposable check (disposable-email-domains)    │
│ - Reject obvious invalid ngay                    │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 3: Batch verify qua Reacher Docker         │
│ POST localhost:8080/v0/check_email               │
│ { "to_email": "x@y.com" }                        │
│ ← response JSON với full checks                  │
│ - Rate limit: 10 req/s (tránh SMTP block)        │
│ - Cache: PostgreSQL (email → result, 30 ngày)    │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 4: Classify + Export                       │
│ Status: VALID / INVALID / DISPOSABLE /           │
│         CATCH_ALL / NO_MX / UNKNOWN              │
│ - Output: clean-customers.csv                    │
│ - Output: invalid-emails.csv                     │
│ - Output: verification-report.json               │
└──────────────────────────────────────────────────┘
```

## Deliverables

| # | File | Purpose |
|---|------|---------|
| 1 | `tools/email-cleaner/docker-compose.yml` | Reacher backend spin-up |
| 2 | `tools/email-cleaner/src/parse.ts` | CSV parse + flatten |
| 3 | `tools/email-cleaner/src/verify.ts` | Call Reacher API + classify |
| 4 | `tools/email-cleaner/src/export.ts` | Write 3 output files |
| 5 | `tools/email-cleaner/src/cache.ts` | PostgreSQL cache layer |
| 6 | `tools/email-cleaner/src/cli.ts` | CLI entry: `node cli.ts --input raw.csv --output clean/` |
| 7 | `tools/email-cleaner/package.json` | Dependencies |
| 8 | `tools/email-cleaner/README.md` | Usage docs |
| 9 | `tools/email-cleaner/migrations/001_cache_table.sql` | DB schema cho cache |
| 10 | `tools/email-cleaner/tests/verify.test.ts` | Unit tests |

## Dependencies

```json
{
  "dependencies": {
    "csv-parse": "^5",
    "csv-stringify": "^6",
    "validator": "^13",
    "disposable-email-domains": "^1",
    "commander": "^12",
    "pino": "^9",
    "pg": "^8",
    "p-limit": "^6"
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

## Implementation Steps (for Platform Team)

### Phase 1 — Setup (30 min) — platform-devops

1. Tạo thư mục `tools/email-cleaner/` trong repo FrieghtBrian
2. Init TypeScript project: `npm init -y && npm i -D typescript tsx @types/node`
3. `tsconfig.json` strict mode
4. Write `docker-compose.yml` cho Reacher backend:
   ```yaml
   services:
     reacher:
       image: reacherhq/backend:latest
       ports: ["8080:8080"]
       environment:
         - RCH_HTTP_HOST=0.0.0.0
         - RCH_FROM_EMAIL=nelson@pudongprime.vn
         - RCH_HELLO_NAME=pudongprime.vn
       restart: unless-stopped
   ```
5. Test: `docker compose up -d && curl localhost:8080/v0/check_email -d '{"to_email":"test@gmail.com"}'`
6. Commit: `ci(email-cleaner): add reacher docker setup`

### Phase 2 — Parse + Pre-filter (45 min) — platform-backend

1. Write `src/parse.ts`:
   - Read CSV via `csv-parse/sync`
   - Detect columns matching `^email\d*$`
   - Flatten thành array `{ pol, pod, company, emails: string[] }`
   - Output `parsed-customers.json`
2. Write `src/pre-filter.ts`:
   - Syntax check mỗi email (`validator.isEmail()`)
   - Disposable check (local DB, no network)
   - Return `{ valid_syntax: [], disposable: [], malformed: [] }`
3. Test: `tsx src/parse.ts --input test.csv`
4. Commit: `feat(email-cleaner): CSV parse + syntax pre-filter`

### Phase 3 — Verify loop (1h) — platform-backend

1. Write `src/verify.ts`:
   - `async function verifyEmail(email: string): Promise<Result>`
   - POST `http://localhost:8080/v0/check_email` với body `{"to_email": email}`
   - Parse response JSON → extract: `is_reachable`, `misc.is_disposable`, `mx.accepts_mail`, `smtp.can_connect_smtp`, `smtp.is_catch_all`
   - Map to status: VALID / INVALID / DISPOSABLE / CATCH_ALL / NO_MX / UNKNOWN
2. Batch loop với `p-limit(10)` (10 concurrent)
3. Cache:
   - Check `email_verification_cache` table trước khi call API
   - Cache TTL 30 days
   - Insert result sau khi verify
4. Log: pino structured logs (success, fail, cached hits)
5. Test: `tsx src/verify.ts --emails test@gmail.com,fake@fake.fake`
6. Commit: `feat(email-cleaner): reacher API client + cache layer`

### Phase 4 — Export (30 min) — platform-backend

1. Write `src/export.ts`:
   - Read verification results
   - Filter: `VALID` + `CATCH_ALL` (uncertain nhưng vẫn keep) → `clean-customers.csv`
   - Filter: `INVALID` + `DISPOSABLE` + `NO_MX` → `invalid-emails.csv`
   - Aggregate stats → `verification-report.json`:
     ```json
     {
       "total_emails": 10632,
       "by_status": { "VALID": 5200, "INVALID": 1500, ... },
       "top_disposable_domains": [...],
       "duration_seconds": 450
     }
     ```
2. CLI entry `src/cli.ts` với commander:
   ```
   node cli.ts --input raw.csv --output ./clean-data/
   ```
3. Commit: `feat(email-cleaner): CSV/JSON export + CLI entry`

### Phase 5 — Cache + Tests (45 min) — platform-backend + platform-qa

1. `src/cache.ts`:
   - PostgreSQL table `email_verification_cache`:
     ```sql
     CREATE TABLE email_verification_cache (
       email VARCHAR(320) PRIMARY KEY,
       status VARCHAR(16) NOT NULL,
       reacher_raw JSONB,
       verified_at TIMESTAMPTZ DEFAULT NOW(),
       expires_at TIMESTAMPTZ
     );
     CREATE INDEX idx_expires ON email_verification_cache(expires_at);
     ```
2. Migration file: `migrations/001_cache_table.sql`
3. Unit tests `tests/verify.test.ts`:
   - Mock Reacher responses
   - Test status mapping (5 cases)
   - Test cache hit/miss
4. Integration test: run real cleanup trên 10-row sample CSV
5. platform-qa review: coverage > 70%
6. Commit: `feat(email-cleaner): PostgreSQL cache + unit tests`

### Phase 6 — Docs + Ship (30 min) — platform-lead + platform-devops

1. Write `tools/email-cleaner/README.md`:
   - Quick start (3 commands)
   - Config env vars
   - Troubleshooting (port 25 blocked, rate limit, false positives)
2. Add script to `package.json`:
   ```json
   "scripts": {
     "clean-emails": "tsx src/cli.ts"
   }
   ```
3. Lead review toàn bộ PR
4. Create PR: `feat(email-cleaner): customer data validation tool`
5. Nelson review + merge
6. Auto-deploy qua GitHub Actions (deploy.yml đã fix)

## Success Criteria

- [ ] `docker compose up` — Reacher backend healthy
- [ ] `node cli.ts --input sample.csv --output out/` — produces 3 output files
- [ ] Sample 100 emails verify trong < 60s với cache warm
- [ ] Report JSON có `total`, `by_status`, `duration`
- [ ] Unit tests pass (coverage > 70%)
- [ ] QA approve: no hardcoded secrets, no `console.log` in src
- [ ] Docs README có quick start < 3 phút đọc
- [ ] PR merged main, auto-deploy success

## Risks

| Risk | Mitigation |
|------|-----------|
| Port 25 blocked tại VPS outbound | Check `nc -zv mx.google.com 25` first; fallback to SMTP verify disabled, chỉ MX check |
| Reacher rate limit khi spam quá nhanh | `p-limit(10)` + retry with exponential backoff |
| Email server Nelson bị blacklist | Dùng throwaway sender domain cho verify, không phải `@pudongprime.vn` |
| Cache staleness (email existed 30 days ago, giờ invalid) | TTL 30 days + optional force re-verify flag `--no-cache` |
| AGPL-3.0 viral license | Internal use only, không redistribute Reacher binary → không trigger |

## Out of Scope

- ❌ Real-time email verify API (chỉ batch)
- ❌ Integration với SendGrid/Mailgun bounce webhooks (Phase sau)
- ❌ ML-based scoring (dùng deterministic rules trước)
- ❌ Web UI (CLI only cho v1)

## Unresolved Questions

1. **Input CSV location**: File raw ở `/opt/nelson/data/email/` hay Nelson upload qua WebApp? → platform-lead hỏi Nelson trước khi start
2. **Output destination**: Clean CSV save ở đâu? `/opt/nelson/data/email/cleaned/{date}/`? → platform-devops config
3. **Scheduling**: Chạy on-demand hay weekly cron? → v1 on-demand, v2 add cron
4. **Notification**: Sau clean xong, Telegram alert Nelson? → optional Phase 7
