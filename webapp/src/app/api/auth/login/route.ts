/**
 * POST /api/auth/login
 * Validates credentials, returns JWT in httpOnly cookie
 */
import { NextRequest, NextResponse } from 'next/server'
import { validateCredentials, signToken, AUTH_COOKIE } from '@/lib/auth'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { username, password } = body

    if (!username || !password) {
      return NextResponse.json(
        { error: 'Username and password are required' },
        { status: 400 }
      )
    }

    const user = validateCredentials(username, password)
    if (!user) {
      return NextResponse.json(
        { error: 'Invalid credentials' },
        { status: 401 }
      )
    }

    const token = await signToken(user)

    const response = NextResponse.json({
      success: true,
      user: { username: user.username, role: user.role },
    })

    response.cookies.set(AUTH_COOKIE, token, {
      httpOnly: true,
      secure: false, // VPS serves over HTTP — set true when HTTPS is configured
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7, // 7 days
      path: '/',
    })

    return response
  } catch (err) {
    console.error('[LOGIN ERROR]', err)
    return NextResponse.json(
      { error: 'Internal server error', detail: String(err) },
      { status: 500 }
    )
  }
}
