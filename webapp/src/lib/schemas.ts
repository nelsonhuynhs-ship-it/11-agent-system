/**
 * Zod validation schemas for Nelson Freight forms
 */
import { z } from 'zod'

export const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

export type LoginForm = z.infer<typeof loginSchema>

export const emailPreviewSchema = z.object({
  customer: z.string().min(1, 'Select a customer'),
  pic: z.string().min(1, 'PIC is required'),
  pol: z.string().min(1, 'POL is required'),
  destinations: z.string().min(1, 'Destinations required'),
  markup: z.coerce.number().min(0, 'Markup must be >= 0'),
  intro: z.string(),
  closing: z.string(),
  subject: z.string().min(1, 'Subject is required'),
})

export type EmailPreviewForm = z.infer<typeof emailPreviewSchema>

export const emailSendSchema = emailPreviewSchema.extend({
  to_email: z.string().email('Invalid email'),
  cc_emails: z.array(z.string().email()).default([]),
})

export type EmailSendForm = z.infer<typeof emailSendSchema>

export const campaignBulkSendSchema = z.object({
  emails: z.array(z.string().email()).min(1, 'Select at least 1 prospect'),
  markup: z.coerce.number().min(0),
  template: z.enum(['professional', 'plain']),
  campaign_id: z.string().optional(),
  cc_emails: z.array(z.string().email()).optional(),
  subject: z.string().optional(),
})

export type CampaignBulkSendForm = z.infer<typeof campaignBulkSendSchema>
