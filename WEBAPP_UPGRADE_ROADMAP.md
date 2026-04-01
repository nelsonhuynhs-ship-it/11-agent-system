# Nelson Freight WebApp Upgrade Roadmap
## Build Once, Serve Both: Desktop + Telegram Mini App

> **Date:** 2026-03-23
> **Author:** Claude (Architect/Reviewer)
> **Executor:** Antigravity
> **Stack:** Next.js (port 3002) + FastAPI (port 8100) + Telegram Bot

---

## Executive Summary

Nâng cấp WebApp từ 7/8 pages thành nền móng cho Telegram Mini App. Chiến lược "build once, serve both" — shared component library, dual auth, responsive-first. 5 workstreams, 6 sprints, ưu tiên security trước rồi mới tính feature.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Next.js Shared Codebase             │
│                                                  │
│  ┌──────────────┐    ┌─────────────────────┐    │
│  │ Desktop Shell │    │ Telegram Mini App   │    │
│  │ Port 3002     │    │ TWA SDK + compact   │    │
│  └──────┬───────┘    └──────────┬──────────┘    │
│         │                       │                │
│  ┌──────┴───────────────────────┴──────────┐    │
│  │      Shared Component Library            │    │
│  │   Cards, Tables, Charts, Forms           │    │
│  │   responsive: compact | full variant     │    │
│  └──────────────────┬──────────────────────┘    │
│                     │                            │
│  ┌──────────────────┴──────────────────────┐    │
│  │      Auth Middleware Layer               │    │
│  │   Desktop: JWT + credentials             │    │
│  │   Telegram: initData HMAC validation     │    │
│  │   Roles: admin | mentee | viewer         │    │
│  └──────────────────┬──────────────────────┘    │
│                     │                            │
│  ┌──────────────────┴──────────────────────┐    │
│  │      API Client Layer (typed fetch)      │    │
│  │      → FastAPI :8100                     │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  8 Pages: Dashboard | Pricing | Shipments |      │
│  Customers | Quotes | Team | AI Copilot |        │
│  Reports (NEW)                                   │
└─────────────────────────────────────────────────┘
```

---

## Sprint Plan

| Sprint | Workstream | Duration | Deliverable |
|--------|-----------|----------|-------------|
| S1 | Auth + Security | 3 days | Login page, JWT, middleware guard |
| S2 | Reports Page | 3 days | 4-tab reports, 8/8 pages complete |
| S3 | UX Upgrades | 4 days | Action widget, compare mode, quick actions |
| S4 | Mobile Responsive | 3 days | All pages responsive, compact variants |
| S5 | Data Freshness | 2 days | Cron sync, health endpoint, alerts |
| S6 | Telegram Mini App | 4 days | TWA integration, TG auth, bottom nav |

**Total:** ~19 days (phụ thuộc tốc độ Antigravity)

---

## SPRINT 1: Auth + Security (P1)

### Mục tiêu
Port 3002 đang exposed. Thêm auth layer bảo vệ tất cả routes.

### Files cần tạo/sửa

```
webapp/
├── app/login/page.tsx          ← NEW: Login page
├── lib/auth.ts                 ← NEW: JWT sign/verify utilities
├── middleware.ts                ← NEW: Route protection
├── app/api/auth/login/route.ts ← NEW: Login API route
└── .env.local                  ← NEW: AUTH_SECRET, ADMIN_USER, ADMIN_PASS
```

### Design Decisions

**Tại sao không dùng NextAuth/Supabase:**
- VPS chỉ 1.9GB RAM, không nên chạy thêm external auth
- Chỉ có ~5 users (Nelson + mentees), không cần OAuth phức tạp
- JWT đơn giản, lightweight, zero external dependency

**User management:**
- Hardcode trong `.env`: `USERS=nelson:admin,mentee1:mentee,mentee2:mentee`
- Hoặc JSON file: `webapp/users.json` (gitignored)
- Sau này scale lên SQLite nếu cần

**Role permissions matrix:**

| Page | admin | mentee | viewer |
|------|-------|--------|--------|
| Dashboard | ✅ Full | ✅ No P&L | ✅ Read-only |
| Pricing | ✅ + margin | ✅ No margin | ❌ |
| Shipments | ✅ | ✅ | ✅ Read-only |
| Customers | ✅ | ✅ Limited | ❌ |
| Quotes | ✅ | ✅ Own quotes | ❌ |
| Team | ✅ | ❌ | ❌ |
| AI Copilot | ✅ | ✅ | ❌ |
| Reports | ✅ | ❌ | ❌ |

### Prompt cho Antigravity — Sprint 1

```
## Task: Implement Auth for Nelson Freight WebApp

### Context
- WebApp: Next.js at ~/webapp on VPS 14.225.207.145
- Port 3002 currently has NO authentication
- Need lightweight JWT auth, no external services
- VPS has 1.9GB RAM total, keep it simple

### Step 1: Create auth utilities
File: webapp/lib/auth.ts

```typescript
import { SignJWT, jwtVerify } from 'jose'

const secret = new TextEncoder().encode(process.env.AUTH_SECRET)

export interface UserPayload {
  username: string
  role: 'admin' | 'mentee' | 'viewer'
}

export async function signToken(payload: UserPayload): Promise<string> {
  return new SignJWT(payload as any)
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('7d')
    .sign(secret)
}

export async function verifyToken(token: string): Promise<UserPayload | null> {
  try {
    const { payload } = await jwtVerify(token, secret)
    return payload as unknown as UserPayload
  } catch {
    return null
  }
}
```

### Step 2: Create login API route
File: webapp/app/api/auth/login/route.ts
- Accept POST { username, password }
- Validate against USERS env var (format: "nelson:pass1:admin,mentee1:pass2:mentee")
- Return JWT in httpOnly cookie, expires 7 days
- Return 401 on invalid credentials

### Step 3: Create middleware
File: webapp/middleware.ts
- Check for auth cookie on every route EXCEPT /login and /api/auth/*
- Verify JWT, extract role
- Redirect to /login if invalid/missing
- Pass user info via headers to pages

### Step 4: Create login page
File: webapp/app/login/page.tsx
- Simple form: username + password + submit button
- Nelson Freight branding (logo, dark theme)
- Error message on invalid credentials
- Redirect to /dashboard on success

### Step 5: Add .env.local
```
AUTH_SECRET=<generate 64 char random string>
USERS=nelson:<password>:admin,mentee1:<password>:mentee
```

### Step 6: Install dependency
```bash
cd ~/webapp && npm install jose
```

### Step 7: Test
- Visit :3002 → should redirect to /login
- Login with correct credentials → redirect to /dashboard
- Login with wrong credentials → error message
- Try accessing /pricing without cookie → redirect to /login

### IMPORTANT
- DO NOT touch ports 3000/3001 (TraSuaPOS)
- DO NOT restart any service except webapp
- Commit message: "feat: add JWT auth + login page"
```

---

## SPRINT 2: Reports Page (P1)

### Mục tiêu
Hoàn thiện page 8/8. Reports page với 4 tabs, tận dụng API đã live.

### Files cần tạo

```
webapp/
├── app/reports/page.tsx           ← NEW: Reports page (Server Component)
├── components/reports/
│   ├── RevenueTab.tsx             ← NEW: Revenue by route/carrier/customer
│   ├── CarrierTab.tsx             ← NEW: Carrier performance metrics
│   ├── CustomerTab.tsx            ← NEW: Customer analytics + churn
│   ├── TeamKPITab.tsx             ← NEW: Mentee performance
│   ├── ReportExport.tsx           ← NEW: PDF/Excel export button
│   └── DateRangeFilter.tsx        ← NEW: Shared date filter
api/
├── routers/report_router.py       ← NEW: Aggregate endpoints
```

### API Design cho Reports

Backend cần 1 router mới aggregate data từ existing endpoints:

```python
# api/routers/report_router.py
# Prefix: /api/reports

GET /api/reports/revenue
  ?period=weekly|monthly
  &start_date=2026-03-01
  &end_date=2026-03-23
  → Returns: revenue by route, carrier, customer (aggregate from rates + quotes)

GET /api/reports/carrier-performance
  ?period=monthly
  → Returns: volume share %, avg rate trend, freetime compliance
  (aggregate from /api/intelligence/carriers + /api/shipments)

GET /api/reports/customer-analytics
  → Returns: top 10 revenue, churn risk list, 4C scores
  (aggregate from /api/intelligence/churn + /api/intelligence/4C)

GET /api/reports/team-kpi
  ?period=weekly
  → Returns: mentee metrics (quote count, accuracy, response time)
  (aggregate from /api/team + /api/quotes stats)

GET /api/reports/export
  ?type=pdf|excel
  &report=revenue|carrier|customer|team
  → Returns: downloadable file
```

### Prompt cho Antigravity — Sprint 2

```
## Task: Build Reports Page + API Router

### Context
- WebApp needs page 8/8: Reports
- FastAPI already has these endpoints live:
  - /api/intelligence/carriers
  - /api/intelligence/churn
  - /api/intelligence/opportunities
  - /api/intelligence/4C
  - /api/dashboard/charts
  - /api/shipments
  - /api/quotes
  - /api/team
- Need new report_router.py that aggregates these
- Need Next.js Reports page with 4 tabs

### Step 1: Create report_router.py
File: api/routers/report_router.py
- Import and call existing service functions internally (don't HTTP call self)
- 4 GET endpoints: /revenue, /carrier-performance, /customer-analytics, /team-kpi
- 1 export endpoint: /export?type=pdf|excel&report=<name>
- IMPORTANT: Parquet queries MUST filter 30 days: filters=[('Eff', '>=', cutoff)]
- Register router in api/app.py

### Step 2: Create Reports page
File: webapp/app/reports/page.tsx
- Tab navigation: Revenue | Carrier | Customer | Team KPI
- Date range filter (shared across tabs)
- Charts using recharts or chart.js (whichever is already installed)
- Tables with sorting
- Export button per tab

### Step 3: Create tab components
- RevenueTab: bar chart by route, line chart trend, table top routes
- CarrierTab: pie chart volume share, line chart rate trend
- CustomerTab: table top 10, churn risk badges (red/yellow/green)
- TeamKPITab: table mentee metrics, sparkline trends

### Step 4: Add navigation
- Add "Reports" link to sidebar/nav (should be last item)
- Route: /reports

### Step 5: Test
- All 4 tabs render with data
- Date filter changes data range
- Export downloads file
- Page accessible only with admin role

### IMPORTANT
- DO NOT load full Parquet — always 30 day filter
- Commit: "feat: reports page + report_router — 8/8 pages complete"
```

---

## SPRINT 3: UX Upgrades

### 3A: Dashboard "Action Needed" Widget

```
## Prompt cho Antigravity — Action Needed Widget

### Task: Add Action Needed widget to Dashboard

### Design
Top of Dashboard page, above existing charts. 3 sections:
1. URGENT (red): Shipments with freetime deadline < 3 days
   - API: GET /api/shipments?freetime_warning=true
2. WARNING (amber): Quotes pending reply > 24h
   - API: GET /api/quotes?status=pending&older_than=24h
3. INFO (blue): Customers flagged churn risk
   - API: GET /api/intelligence/churn?risk=high

Each item is clickable → navigates to detail page.

### Files to modify
- webapp/components/dashboard/ActionNeeded.tsx ← NEW
- webapp/app/dashboard/page.tsx ← ADD ActionNeeded component at top

### API additions needed
- Add query param to /api/shipments: freetime_warning=true
- Add query param to /api/quotes: status=pending, older_than=24h
```

### 3B: Pricing Compare Mode

```
## Prompt cho Antigravity — Pricing Compare Mode

### Task: Add carrier compare mode to Pricing page

### Design
- Toggle button "Compare mode" on Pricing page
- User selects 2 carriers from dropdown
- Side-by-side table: Route | Carrier A Rate | Carrier B Rate | Diff | % Diff
- Highlight: green if A cheaper, red if A more expensive
- API: GET /api/rates/compare?carrier1=HPL&carrier2=ONE&pol=HCM

### Files
- webapp/components/pricing/CompareMode.tsx ← NEW
- webapp/app/pricing/page.tsx ← ADD toggle + CompareMode
- api/routers/rate_router.py ← ADD /api/rates/compare endpoint
```

### 3C: Quote Quick Actions

```
## Prompt cho Antigravity — Quote Quick Actions

### Task: Add quick actions to Quotes page

### Design
- Each quote row gets action buttons: Duplicate | Resend | Won | Lost
- "Create from Pricing" button on Pricing page → pre-fills quote form
- Quote timeline view: Draft → Sent → Replied → Won/Lost/Expired

### Files
- webapp/components/quotes/QuoteActions.tsx ← NEW
- webapp/components/quotes/QuoteTimeline.tsx ← NEW
- webapp/app/pricing/page.tsx ← ADD "Create Quote" button per rate row
```

### 3D: Rate Freshness Badges

```
## Prompt cho Antigravity — Rate Freshness Badges

### Task: Add data freshness indicators to Pricing page

### Design
- Badge next to each rate: "Updated 2h ago" (green) / "3 days old" (yellow) / "Stale" (red)
- Based on Eff date from Parquet data
- Top of page: "Rate data last synced: March 23, 2026 06:00 AM"

### API
- GET /api/health/data-freshness → { last_updated, age_hours, status }
- Existing /api/rates/matrix already returns Eff date per rate
```

---

## SPRINT 4: Mobile Responsive

### Shared Hook for Platform Detection

```typescript
// webapp/hooks/useViewport.ts
'use client'
import { useState, useEffect } from 'react'

interface ViewportInfo {
  width: number
  isCompact: boolean      // < 480px OR Telegram
  isTelegram: boolean     // Telegram Mini App
  isDesktop: boolean      // >= 1024px
  platform: 'desktop' | 'tablet' | 'mobile' | 'telegram'
}

export function useViewport(): ViewportInfo {
  const [info, setInfo] = useState<ViewportInfo>({
    width: 1024, isCompact: false, isTelegram: false,
    isDesktop: true, platform: 'desktop'
  })

  useEffect(() => {
    const tg = typeof window !== 'undefined' && (window as any).Telegram?.WebApp
    const update = () => {
      const w = window.innerWidth
      const isTG = !!tg
      setInfo({
        width: w,
        isCompact: w < 480 || isTG,
        isTelegram: isTG,
        isDesktop: w >= 1024 && !isTG,
        platform: isTG ? 'telegram' : w < 480 ? 'mobile' : w < 1024 ? 'tablet' : 'desktop'
      })
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return info
}
```

### Component Pattern: Desktop + Compact

```typescript
// Example: ShipmentCard with both variants
export function ShipmentCard({ shipment }: Props) {
  const { isCompact } = useViewport()

  if (isCompact) {
    return (
      <div className="p-3 border-b">
        <div className="flex justify-between">
          <span className="font-medium">{shipment.bl_number}</span>
          <FreetimeBadge days={shipment.freetime_remaining} />
        </div>
        <div className="text-sm text-gray-500 mt-1">
          {shipment.pol} → {shipment.pod}
        </div>
      </div>
    )
  }

  return (
    <tr>
      <td>{shipment.bl_number}</td>
      <td>{shipment.pol}</td>
      <td>{shipment.pod}</td>
      <td>{shipment.carrier}</td>
      <td><FreetimeBadge days={shipment.freetime_remaining} /></td>
      <td>{shipment.status}</td>
    </tr>
  )
}
```

### Prompt cho Antigravity — Sprint 4

```
## Task: Make all 8 pages mobile responsive

### Context
- All components need compact variant for mobile + Telegram Mini App
- Breakpoint: 480px (below = compact, above = full)
- Priority pages for mobile: Dashboard, Shipments, Pricing, Quotes

### Approach
1. Create useViewport hook (code above)
2. For each page, create compact variant:
   - Dashboard: stack KPI cards vertical, charts full-width
   - Pricing: card layout instead of wide table
   - Shipments: list view instead of table
   - Quotes: card view with swipe actions
   - Reports: tab becomes vertical accordion on mobile
   - Team/Customers/AI: simple responsive with Tailwind

### Test at
- 375px (iPhone SE)
- 390px (iPhone 14)
- 768px (iPad)
- 1024px+ (Desktop)

### Commit: "feat: mobile responsive all 8 pages"
```

---

## SPRINT 5: Data Freshness + Auto-sync

### Prompt cho Antigravity — Sprint 5

```
## Task: Implement Parquet auto-sync + freshness monitoring

### Step 1: Health endpoint
File: api/routers/health_router.py (existing, add endpoint)

GET /api/health/data-freshness
→ Returns:
{
  "last_modified": "2026-03-23T06:00:00Z",
  "age_hours": 8,
  "status": "fresh" | "aging" | "stale",
  "record_count": 10200000,
  "date_range": { "min": "2026-02-21", "max": "2026-03-23" }
}

Logic:
- Read Parquet file modification time
- Query max(Eff) from last 30 day filter
- fresh: < 24h, aging: 24-72h, stale: > 72h

### Step 2: Cron job
File: /home/nelson/scripts/sync_rates.sh

#!/bin/bash
# Runs daily at 6AM Vietnam time (UTC+7 = 23:00 UTC previous day)
cd /home/nelson/api
source /home/nelson/venv/bin/activate
python -c "from services.rate_sync import sync_daily; sync_daily()"

# Alert if failed
if [ $? -ne 0 ]; then
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
         -d "chat_id=${NELSON_CHAT_ID}&text=⚠️ Rate sync failed at $(date)"
fi

Crontab:
0 23 * * * /home/nelson/scripts/sync_rates.sh >> /home/nelson/logs/sync.log 2>&1

### Step 3: Sync service
File: api/services/rate_sync.py
- Read from rate source (manual upload dir or email parse)
- Validate: columns match schema, dates make sense
- Append to Parquet (don't replace — append new rows)
- Log: rows added, new date range

### Step 4: Stale data alert
- If /api/health/data-freshness returns "stale"
- NÓI agent sends Telegram message to Nelson
- WebApp shows banner: "Rate data may be outdated (last updated X days ago)"

### IMPORTANT
- NEVER load full Parquet — always 30 day filter
- Backup Parquet before any write operation
- Commit: "feat: data freshness monitoring + auto-sync cron"
```

---

## SPRINT 6: Telegram Mini App Integration

### Prerequisites
- Sprints 1-5 complete
- All pages responsive
- Auth supports both JWT and Telegram initData

### Telegram WebApp SDK Integration

```typescript
// webapp/lib/telegram.ts
export function initTelegramWebApp() {
  if (typeof window === 'undefined') return null

  const tg = (window as any).Telegram?.WebApp
  if (!tg) return null

  tg.ready()
  tg.expand() // Full height

  return {
    user: tg.initDataUnsafe?.user,
    initData: tg.initData, // For auth validation
    colorScheme: tg.colorScheme,
    headerColor: tg.headerColor,
    close: () => tg.close(),
    mainButton: tg.MainButton,
    backButton: tg.BackButton,
    hapticFeedback: tg.HapticFeedback,
  }
}
```

### Auth Flow for Telegram

```typescript
// webapp/app/api/auth/telegram/route.ts
import { createHmac } from 'crypto'

export async function POST(req: Request) {
  const { initData } = await req.json()

  // Validate HMAC using bot token
  const params = new URLSearchParams(initData)
  const hash = params.get('hash')
  params.delete('hash')
  const dataCheckString = [...params.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join('\n')

  const secretKey = createHmac('sha256', 'WebAppData')
    .update(process.env.BOT_TOKEN!)
    .digest()
  const expectedHash = createHmac('sha256', secretKey)
    .update(dataCheckString)
    .digest('hex')

  if (hash !== expectedHash) {
    return Response.json({ error: 'Invalid initData' }, { status: 401 })
  }

  // Map TG user to role
  const user = JSON.parse(params.get('user') || '{}')
  const role = mapTelegramUserToRole(user.id)

  // Issue JWT same as desktop
  const token = await signToken({ username: user.first_name, role })
  // Set cookie and return
}

function mapTelegramUserToRole(telegramId: number): string {
  const roleMap: Record<number, string> = {
    [Number(process.env.NELSON_TG_ID)]: 'admin',
    // Add mentee TG IDs here
  }
  return roleMap[telegramId] || 'viewer'
}
```

### Navigation for Telegram Mini App

```typescript
// webapp/components/TelegramNav.tsx
// Bottom tab bar: 4 main pages
// Dashboard | Pricing | Quotes | Shipments
// Hamburger menu for: Reports, Team, AI, Customers

export function TelegramBottomNav() {
  const tabs = [
    { icon: 'home', label: 'Home', path: '/dashboard' },
    { icon: 'dollar', label: 'Rates', path: '/pricing' },
    { icon: 'file', label: 'Quotes', path: '/quotes' },
    { icon: 'ship', label: 'Ships', path: '/shipments' },
  ]
  // ... render bottom tab bar
}
```

### Bot Integration

```python
# bot/handlers/webapp_handler.py
# Add inline button to open Mini App

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

def get_webapp_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📊 Open Dashboard",
            web_app=WebAppInfo(url="https://your-domain.com/dashboard")
        )
    ]])
```

### Prompt cho Antigravity — Sprint 6

```
## Task: Integrate Telegram Mini App

### Prerequisites
- WebApp fully responsive (Sprint 4 done)
- Auth supports JWT (Sprint 1 done)

### Step 1: Add Telegram WebApp SDK
File: webapp/app/layout.tsx
- Add <script src="https://telegram.org/js/telegram-web-app.js"/> to head
- Create lib/telegram.ts helper

### Step 2: Add Telegram auth endpoint
File: webapp/app/api/auth/telegram/route.ts
- Validate initData HMAC with bot token
- Map TG user ID to role
- Issue JWT cookie same as desktop flow

### Step 3: Update middleware
File: webapp/middleware.ts
- If Telegram initData present in request → use TG auth flow
- Otherwise → use existing JWT cookie flow

### Step 4: Add bottom nav for Telegram
File: webapp/components/TelegramNav.tsx
- Render only when isTelegram = true
- 4 tabs: Dashboard, Pricing, Quotes, Shipments
- More menu for other pages

### Step 5: Add webapp button to bot
File: bot/handlers/webapp_handler.py
- /webapp command opens inline keyboard with Mini App button
- URL: https://<domain>/dashboard

### Step 6: Configure BotFather
- Set Menu Button → Mini App URL
- Set webapp domain in BotFather settings

### IMPORTANT
- Mini App needs HTTPS — VPS needs reverse proxy (nginx) with SSL
- Or use ngrok/cloudflare tunnel for testing
- Commit: "feat: Telegram Mini App integration"
```

---

## RAM Budget Check

| Service | Current | After Upgrade |
|---------|---------|---------------|
| FastAPI | ~83MB | ~90MB (+report router) |
| Bot + NÃO | ~717MB | ~720MB (+webapp handler) |
| WebApp Next.js | ~150MB | ~180MB (+auth, reports, responsive) |
| **Total** | ~950MB | ~990MB |
| **Available** | 1.9GB + 2GB swap | Still safe |

**Verdict:** All upgrades fit within RAM budget. No additional services needed.

---

## Risk Flags

1. **SSL/HTTPS for Mini App**: Telegram requires HTTPS for Mini Apps. VPS cần nginx reverse proxy + Let's Encrypt. Antigravity cần setup trước Sprint 6.

2. **Parquet write concurrency**: Cron job writes to Parquet while API reads from it. Need file lock hoặc write to temp file → atomic rename.

3. **Rate source automation**: Sprint 5 cron expects a rate source. Nếu rates vẫn manual update qua Zalo → cron chỉ check freshness, không auto-pull. Full automation cần HPL API live (P2 backlog).

4. **Testing on real Telegram**: Mini App testing cần BotFather setup + HTTPS domain. Suggest: dùng ngrok tunnel cho testing trước khi setup production nginx.

---

## Post-Upgrade Backlog Updates

After all 6 sprints complete, CLAUDE.md backlog should update:

| Priority | Task | Status |
|----------|------|--------|
| ~~P1~~ | ~~WebApp login/auth~~ | ✅ Done (Sprint 1) |
| ~~P1~~ | ~~Reports page (page 8)~~ | ✅ Done (Sprint 2) |
| ~~P1~~ | ~~Parquet auto-sync~~ | ✅ Done (Sprint 5) |
| P2 | HPL API live → enable full rate auto-sync | Unblocked by S5 |
| P2 | Verification gate | Still TODO |
| **NEW** | Telegram Mini App v2 — push notifications | After S6 |
| **NEW** | Mini App payments integration | After S6 |
| **NEW** | Offline mode + PWA | After responsive |

---

## How to Use This Document

1. **Anh Nelson** đọc overview, confirm priority order
2. **Feed từng Sprint prompt** cho Antigravity, theo thứ tự S1→S6
3. **Sau mỗi Sprint**, báo Claude review kết quả
4. Claude sẽ check: code quality, security, RAM usage, data rules compliance
5. Iterate nếu cần fix

> **Next step:** Confirm thứ tự sprint, rồi em sẽ refine Sprint 1 prompt chi tiết hơn cho Antigravity bắt đầu.
