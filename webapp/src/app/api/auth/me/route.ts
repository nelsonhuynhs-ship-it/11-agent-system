/**
 * GET /api/auth/me
 * Returns current user from JWT cookie
 */
import { NextRequest, NextResponse } from 'next/server'
import { verifyToken, AUTH_COOKIE } from '@/lib/auth'

export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE)?.value

  if (!token) {
    return NextResponse.json(
      { error: 'Not authenticated' },
      { status: 401 }
    )
  }

  const user = await verifyToken(token)
  if (!user) {
    return NextResponse.json(
      { error: 'Invalid token' },
      { status: 401 }
    )
  }

  return NextResponse.json({
    username: user.username,
    role: user.role,
  })
}
