# Security Audit Report

**Date**: 2026-05-03
**Auditor**: Security Auditor Agent
**Scope**: Engine_test (API + Email Engine + WebApp + ERP)
**Severity Summary**: Critical: 2 | High: 1 | Medium: 1 | Info: 4

> ⚠️ Report này chứa thông tin nhạy cảm — KHÔNG commit lên public repository

---

## 🚨 Critical Vulnerabilities

### SEC-001: Hardcoded JWT Secret Default
- **OWASP Category**: A07 — Auth & Session
- **File**: `webapp/src/lib/auth.ts:8`
- **Evidence**:
  ```typescript
  const secret = new TextEncoder().encode(
    process.env.AUTH_SECRET || 'nelson-freight-default-secret-change-me-in-production'
  )
  ```
- **Risk**: Nếu `AUTH_SECRET` env var không được set trong production, bất kỳ ai cũng có thể forge JWT token với role admin. Attackers có thể:
  1. Tạo token `{"username":"hacker","role":"admin"}`
  2. Sign với secret trên
  3. Truy cập toàn bộ API với quyền admin
- **Fix**: Đảm bảo `AUTH_SECRET` được set trong production. Fail-fast nếu không có secret:
  ```typescript
  if (!process.env.AUTH_SECRET) {
    throw new Error('AUTH_SECRET must be set in production')
  }
  ```

### SEC-002: API Bypass — Anonymous Users Get Admin Role
- **OWASP Category**: A01 — Broken Access Control
- **File**: `api/routers/auth_router.py:28`
- **Evidence**:
  ```python
  if not API_KEY:
      return {"user": "anonymous", "role": "admin"}  # no auth configured
  ```
- **Risk**: Khi `NELSON_API_KEY` không được set (dev mode), toàn bộ API trả về `role: "admin"` cho anonymous users. Điều này có nghĩa:
  - API hoàn toàn mở trong development
  - Nếu deploy mà quên set API key, hệ thống completely exposed
- **Fix**: Fail-closed thay vì fail-open:
  ```python
  if not API_KEY:
      raise HTTPException(status_code=401, detail="API not configured — set NELSON_API_KEY")
  ```

---

## 🔴 High

### SEC-003: CORS Allows `null` Origin
- **OWASP Category**: A05 — Security Misconfiguration
- **File**: `api/config.py:111`
- **Evidence**:
  ```python
  CORS_ORIGINS: list = field(default_factory=lambda: [
      ...
      "null",   # file:// origin — allows standalone HTML dashboards
  ])
  ```
- **Risk**: `null` origin cho phép request từ `file://` URLs. Attacker có thể:
  1. Tạo malicious HTML file
  2. Mở file đó trong browser
  3. Make requests đến API từ file:// origin
- **Fix**: Loại bỏ `"null"` khỏi CORS_ORIGINS. Nếu cần standalone HTML, dùng signed cookies thay vì allow all origins.

---

## 🟡 Medium

### SEC-004: Use of `exec()` for Local Variable Assignment
- **OWASP Category**: A03 — Injection
- **File**: `email_engine/ingest/combine_all.py:428`
- **Evidence**:
  ```python
  exec(f"{val_name} = ''")
  ```
- **Risk**: Dùng `exec()` để set local variables — không direct security risk vì input được control cứng, nhưng là code smell và có thể trở thành risk nếu code thay đổi.
- **Fix**: Dùng dictionary thay vì exec:
  ```python
  locals_cleaned = {val_name: '' for val_name in ["company", "name", ...]}
  ```

---

## ℹ️ Informational

### SEC-005: `eval()` with Restricted Builtins
- **File**: `scripts/erp-import-shipments.py:144`
- **Note**: `eval(s, {"__builtins__": {}})` đã được harden đúng cách — builtins bị remove, chỉ evaluate numeric expressions. Safe trong context này.

### SEC-006: `dangerouslySetInnerHTML` for CSS Animation
- **File**: `webapp/src/app/login/page.tsx:47`
- **Note**: Chỉ chứa CSS animation, không user input. Safe trong context này.

### SEC-007: Silent Exception in Startup
- **File**: `api/app.py:42,49,63,68,76`
- **Note**: Workers fail silently trong startup (try/except with pass). Đây là design decision cho dev flexibility, nhưng có thể mask production issues.
- **Recommendation**: Log warning khi worker fail, nhưng không block startup.

---

## ✅ Security Controls Đã Implement Tốt

| Control | Status | Evidence |
|---------|--------|----------|
| Rate Limiting | ✅ | `middleware/rate_limit.py` — per-IP với tiered limits |
| Error Handling | ✅ | Stack traces logged, not exposed to users |
| SQL Injection Prevention | ✅ | Parameterized queries throughout |
| Secret Management | ✅ | `.env` gitignored, `.env.example` không chứa secrets thật |
| Auth Middleware | ✅ | API key + JWT pattern rõ ràng |
| CORS Structure | ✅ | Middleware-based, configurable |
| Input Validation | ✅ | Pydantic schemas in API |
| Zod Validation (Web) | ✅ | `zod ^4.3.6` in webapp |
| Logging | ✅ | Structured logging throughout |
| Env Var Centralization | ✅ | `config.py` là single source of truth |

---

## 📋 Recommended Next Steps

### P0 — Fix Immediately Before Any Production Deploy:
1. **[SEC-001]** Set `AUTH_SECRET` env var in production — fail if not set
2. **[SEC-002]** Fix `auth_router.py:28` — fail-closed when API key not configured

### P1 — Fix Before V2 Launch:
3. **[SEC-003]** Remove `"null"` from `CORS_ORIGINS`
4. **[SEC-004]** Refactor `exec()` in `combine_all.py`

### P2 — Nice to Have:
5. Add startup health check to verify all required env vars are set
6. Add authentication status endpoint that clearly indicates security posture

---

## Architecture Robustness Assessment

### ✅ Strengths
| Area | Assessment |
|------|------------|
| **Modularity** | Router-based architecture, clear separation of concerns |
| **Scalability Path** | Rate limiting có Phase 2 Redis migration documented |
| **Error Handling** | Global exception handlers + structured errors |
| **Type Safety** | Pydantic v2 + Zod v4 — strong validation throughout |
| **Database** | DuckDB for analytics, PostgreSQL optional — appropriate choices |
| **Auth Pattern** | API key + JWT hybrid — sensible for current scale |
| **Config Management** | Centralized `config.py` — avoids env scattered |

### ⚠️ Areas to Monitor
| Area | Concern |
|------|---------|
| **Memory pressure** | In-memory rate limiting + bucket cleanup |
| **Worker resilience** | Workers fail silently in startup |
| **API key distribution** | Single API key for all ERP clients |

---

## Conclusion

**Hệ thống có nền tảng kiến trúc tốt** để phát triển lớn hơn. Tuy nhiên, **2 critical vulnerabilities (SEC-001, SEC-002) PHẢI fix trước production deploy** vì chúng cho phép complete authentication bypass.

Với việc fix SEC-001 + SEC-002, hệ thống đủ mạnh để scale vì:
- Strong typing (Pydantic/Zod)
- Good separation of concerns
- Clear scaling roadmap (Redis rate limiting, PostgreSQL)
- Rate limiting + error handling + logging infrastructure

**Khuyến nghị**: Sau khi fix 2 critical items, hệ thống sẵn sàng cho mở rộng.
