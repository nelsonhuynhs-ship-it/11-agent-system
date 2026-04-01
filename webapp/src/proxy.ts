/**
 * Nelson Freight — Route Protection Proxy
 * Next.js 16 proxy convention (replaces deprecated middleware.ts)
 * Redirects unauthenticated users to /login
 */
import { NextRequest, NextResponse } from 'next/server'
import { verifyToken, AUTH_COOKIE } from '@/lib/auth'

// Paths that don't require authentication
const PUBLIC_PATHS = ['/login', '/api/auth']

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(p => pathname.startsWith(p)) ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname === '/robots.txt'
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow public paths
  if (isPublicPath(pathname)) {
    // If logged in and accessing /login, redirect to dashboard
    if (pathname === '/login') {
      const token = request.cookies.get(AUTH_COOKIE)?.value
      if (token) {
        const user = await verifyToken(token)
        if (user) {
          return NextResponse.redirect(new URL('/dashboard', request.url))
        }
      }
    }
    return NextResponse.next()
  }

  // Root path: redirect to dashboard (authenticated) or login (not)
  if (pathname === '/') {
    const token = request.cookies.get(AUTH_COOKIE)?.value
    if (token) {
      const user = await verifyToken(token)
      if (user) return NextResponse.redirect(new URL('/dashboard', request.url))
    }
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Check auth cookie
  const token = request.cookies.get(AUTH_COOKIE)?.value
  if (!token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('from', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Verify JWT
  const user = await verifyToken(token)
  if (!user) {
    const response = NextResponse.redirect(new URL('/login', request.url))
    // Clear invalid cookie
    response.cookies.delete(AUTH_COOKIE)
    return response
  }

  // Pass user info to pages via headers
  const response = NextResponse.next()
  response.headers.set('x-user-name', user.username)
  response.headers.set('x-user-role', user.role)
  return response
}

export const config = {
  matcher: [
    /*
     * Match all paths except static files
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
}
