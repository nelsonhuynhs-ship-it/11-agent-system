/**
 * Nelson Freight — Auth Utilities
 * Lightweight JWT auth using jose (Edge-compatible)
 */
import { SignJWT, jwtVerify } from 'jose'

const secret = new TextEncoder().encode(
  process.env.AUTH_SECRET || 'nelson-freight-default-secret-change-me-in-production'
)

export interface UserPayload {
  username: string
  role: 'admin' | 'mentee' | 'viewer'
}

/** Sign a JWT with 7-day expiry */
export async function signToken(payload: UserPayload): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('7d')
    .sign(secret)
}

/** Verify JWT and return payload, or null if invalid */
export async function verifyToken(token: string): Promise<UserPayload | null> {
  try {
    const { payload } = await jwtVerify(token, secret)
    return {
      username: payload.username as string,
      role: payload.role as UserPayload['role'],
    }
  } catch {
    return null
  }
}

/** Parse USERS env var: "name:pass:role,name2:pass2:role2" */
export function getUsers(): Array<{ username: string; password: string; role: UserPayload['role'] }> {
  const raw = process.env.USERS || ''
  if (!raw) return []
  return raw.split(',').map(entry => {
    const [username, password, role] = entry.trim().split(':')
    return { username, password, role: (role || 'viewer') as UserPayload['role'] }
  }).filter(u => u.username && u.password)
}

/** Validate credentials against USERS env var */
export function validateCredentials(
  username: string,
  password: string
): UserPayload | null {
  const users = getUsers()
  const user = users.find(
    u => u.username.toLowerCase() === username.toLowerCase() && u.password === password
  )
  if (!user) return null
  return { username: user.username, role: user.role }
}

export const AUTH_COOKIE = 'auth-token'
