---
name: next-best-practices
description: >
  Next.js best practices — file conventions, RSC boundaries, data patterns, async APIs,
  metadata, error handling, route handlers, image/font optimization, bundling.
  TRIGGER khi: build WebApp Next.js cho Nelson dashboard, review Next.js code,
  hoặc sprint 13-14 WebApp implementation.
---

# Next.js Best Practices Skill

> **Source:** Vercel official next-best-practices skill (vercel-labs/next-skills)
> **Applied to:** Nelson WebApp Dashboard (Sprint 13-14)
> **Stack:** Next.js 14 App Router + Supabase + FastAPI

---

## 📁 File Conventions (App Router)

```
app/
├── layout.tsx         ← Root layout (providers, fonts)
├── page.tsx           ← Dashboard home
├── loading.tsx        ← Loading skeleton
├── error.tsx          ← Error boundary
├── not-found.tsx      ← 404 page
├── dashboard/
│   ├── page.tsx       ← KPI overview
│   ├── rates/
│   │   └── page.tsx   ← Rate lookup
│   └── quotes/
│       └── page.tsx   ← Quote management
└── api/
    └── rates/
        └── route.ts   ← API route (proxy to FastAPI)
```

---

## 🖥️ RSC Boundaries — Server vs Client

### Server Components (default — NO 'use client')
```typescript
// app/dashboard/page.tsx — Server Component
// ✅ Can: fetch data directly, access env vars, import server-only modules
// ❌ Cannot: useState, useEffect, event handlers, browser APIs

export default async function DashboardPage() {
  // Direct data fetch — no useEffect needed
  const kpi = await fetch(`${process.env.API_URL}/api/kpi/monthly`)
    .then(r => r.json())

  return <KPIOverview data={kpi} />
}
```

### Client Components ('use client' required)
```typescript
// components/RateSearch.tsx — Client Component
'use client'
// ✅ Can: useState, useEffect, event handlers, browser APIs
// ❌ Cannot: async/await at component level, direct DB access

export function RateSearch() {
  const [query, setQuery] = useState('')
  // ...
}
```

---

## 📡 Data Patterns cho Nelson WebApp

### Server Actions (mutations)
```typescript
// app/quotes/actions.ts
'use server'
import { revalidatePath } from 'next/cache'

export async function createQuote(formData: FormData) {
  const data = Object.fromEntries(formData)
  await fetch(`${process.env.API_URL}/api/quotes`, {
    method: 'POST',
    body: JSON.stringify(data)
  })
  revalidatePath('/quotes')  // Refresh quotes page
}
```

### Avoid data waterfalls — use Promise.all
```typescript
// ❌ BAD — waterfall (sequential)
const kpi = await fetchKPI()
const quotes = await fetchQuotes()

// ✅ GOOD — parallel
const [kpi, quotes] = await Promise.all([fetchKPI(), fetchQuotes()])
```

---

## ⚡ Async APIs (Next.js 15+)

```typescript
// ✅ Next.js 15+ — params is now async
export default async function Page({
  params,
  searchParams
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ [key: string]: string }>
}) {
  const { id } = await params
  const { filter } = await searchParams
  // ...
}
```

---

## 🖼️ Image Optimization

```typescript
// ✅ Always use next/image, never <img>
import Image from 'next/image'

<Image
  src="/logo.png"
  alt="Nelson Freight"
  width={200}
  height={60}
  priority  // For above-fold LCP images
/>
```

---

## 🚨 Error Handling

```typescript
// app/dashboard/error.tsx
'use client'
export default function Error({
  error,
  reset
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

---

## 🔐 Auth with Supabase (Nelson WebApp)

```typescript
// middleware.ts (runs on every request)
import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const supabase = createMiddlewareClient({ req, res })
  const { data: { session } } = await supabase.auth.getSession()

  // Redirect to login if not authenticated
  if (!session && req.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', req.url))
  }
  return res
}
```

---

## 🔗 References
- **Vercel source:** https://github.com/vercel-labs/next-skills
- **Next.js docs:** https://nextjs.org/docs (App Router)
- **Supabase + Next.js:** https://supabase.com/docs/guides/getting-started/quickstarts/nextjs
- **Nelson WebApp plan:** skill `webapp-scalable` → sub-skill `deployment`
