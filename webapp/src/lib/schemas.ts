/**
 * Zod validation schemas for Nelson Freight forms
 */
import { z } from 'zod'

export const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

export type LoginForm = z.infer<typeof loginSchema>

// Email/Campaign schemas REMOVED 2026-04-17 — email send pipeline moved to
// email_engine/web_server.py (local PC). See docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md
