---
title: "Email Dashboard v7 Hardening — Frontend + Backend Production Readiness"
description: ""
status: completed
priority: P2
branch: "main"
tags: []
blockedBy: []
blocks: []
created: "2026-05-03T02:21:29.680Z"
createdBy: "ck:plan"
source: skill
---

# Email Dashboard v7 Hardening — Frontend + Backend Production Readiness

## Overview

Address 5 critical and medium-risk areas across the Email Dashboard frontend (`email-dashboard.html`, 2198 lines) and backend (`web_server.py`, 4495 lines) to achieve production readiness.

**Scope:**
- Frontend: `plans/visuals/email-dashboard.html`
- Backend: `email_engine/web_server.py` + shared API routers

**Current score: 5.8/10** — Functional baseline exists but security (XSS, inline handlers), accessibility (WCAG AA), CSS architecture (duplication, BEM inconsistency), JS state management (memory leaks), and performance (table/virtual scroll) need hardening before multi-user production.

## Phases

| Phase | Name | Priority | Effort | Description |
|-------|------|----------|--------|-------------|
| 1 | [Security Fixes](./phase-01-security-fixes.md) | P1 | 2h | XSS fix, CSP, inline handler removal, error handling |
| 2 | [Accessibility](./phase-02-accessibility.md) | P1 | 2h | ARIA, keyboard nav, focus, reduced-motion, contrast |
| 3 | [Frontend Architecture](./phase-03-frontend-architecture.md) | P2 | 2h | CSS dedup, design tokens, KPI grid, button consistency |
| 4 | [Backend Hardening](./phase-04-backend-hardening.md) | P2 | 3h | State immutability, memory leaks, SendProgress dataclass |
| 5 | [Performance](./phase-05-performance.md) | P2 | 2h | Pagination, debounce, lazy-load, hover optimization |

**Total estimated: ~11h**

## Dependencies

<!-- None — plan is self-contained, no cross-plan dependencies -->

## Verification

After each phase, test:
1. Open `email-dashboard.html` in browser — tab through all interactive elements
2. Run `grep -n "onclick=\"\${" plans/visuals/email-dashboard.html` — expect 0 results (Phase 1)
3. Run `grep -n "prefers-reduced-motion" plans/visuals/email-dashboard.html` — expect >0 (Phase 2)
4. Verify contacts table shows pagination controls (Phase 5)
5. Run `cd email_engine && python -c "from web_server import app; print('OK')"` — verify no import errors (Phase 4)
