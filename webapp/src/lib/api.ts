/**
 * Nelson Freight System — API Client
 * Connects WebApp to Dashboard API (port 8100)
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://14.225.207.145:8100';

const API_BASE = API_URL;

// ── Fetch wrapper with error handling ─────────────────────
async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── API Client ────────────────────────────────────────────
export const api = {
  // Health & Status
  health: () => fetchAPI<{
    erp_exists: boolean;
    erp_size_mb: number;
    task_db: boolean;
    mailbox_db: boolean;
    lesson_md: boolean;
    backlog_md: boolean;
    agents_count: number;
  }>('/agent/health'),

  status: () => fetchAPI<{
    NÃO: string;
    ÉM: string;
    LÍNH: string;
    SOI: string;
    Ổ: string;
    NÓI: string;
    erp_version: string;
    listener: string;
  }>('/agent/status'),

  // Tasks
  tasks: () => fetchAPI<{ tasks: Array<{
    id: number;
    title: string;
    description: string;
    status: string;
    assigned_to: string;
    created_at: string;
    completed_at: string | null;
    result: string | null;
  }> }>('/agent/tasks'),

  createTask: (task: string) => fetchAPI<{ status: string; task: object }>(
    '/agent/task',
    {
      method: 'POST',
      body: JSON.stringify({ title: task, description: task }),
    }
  ),

  approveTask: (taskId: number) => fetchAPI<{ status: string }>(
    '/agent/approve',
    {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    }
  ),

  // Logs & Knowledge
  log: () => fetchAPI<{ lines: string[] }>('/agent/log'),
  lessons: () => fetchAPI<{ content: string }>('/agent/lessons'),
  backlog: () => fetchAPI<{ content: string }>('/agent/backlog'),
};

// ── Email Rate API (Sprint 13) ────────────────────────────
export interface CustomerInfo {
  name: string;
  pol: string;
  destinations: string;
  pic: string;
  email: string;
}

export interface PreviewRequest {
  customer: string;
  pic: string;
  pol: string;
  destinations: string;
  markup: number;
  intro: string;
  closing: string;
  subject: string;
}

export interface PreviewResponse {
  subject: string;
  html: string;
  row_count: number;
  is_blocked: boolean;
  warn_msg: string;
  pol_queried: string[];
  dests_found: number;
  days_used?: number;                    // 14A: fallback days (30/60/90)
  route_debug?: Record<string, string>;  // 14A: POD mapping debug info
}

export interface SendRequest extends PreviewRequest {
  to_email: string;
  cc_emails: string[];
}

export interface SendResponse {
  status: string;
  to: string;
  cc: string[];
  subject: string;
  rows_sent: number;
  timestamp: string;
}

export interface EmailRateConfig {
  default_pols: string[];
  default_destinations: string;
  subject_templates: string[];
  intro_default: string;
  closing_default: string;
  from_name: string;
  from_email: string;
}

export const emailRateApi = {
  customers: () =>
    fetchAPI<{ customers: CustomerInfo[]; total: number }>('/api/email-rate/customers'),

  config: () =>
    fetchAPI<EmailRateConfig>('/api/email-rate/config'),

  preview: (req: PreviewRequest) =>
    fetchAPI<PreviewResponse>('/api/email-rate/preview', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  send: (req: SendRequest) =>
    fetchAPI<SendResponse>('/api/email-rate/send', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

// ── Campaign API (Sprint 14) ─────────────────────────────────

export interface CampaignProspect {
  email: string;
  company: string;
  pic: string;
  greeting: string;
  pol: string;
  destination: string;
  carrier: string;
  total_shipment: number;
  campaign_id: string;
  already_sent: string;
  last_sent: string;
  email_quality: number;
  // v2 tier fields
  tier: string;
  action: string;
  priority_score: number;
  reply_status: string;
  send_count: number;
}

export interface CampaignProspectsResponse {
  prospects: CampaignProspect[];
  total: number;
  campaigns: string[];
  tiers: string[];
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TierStats {
  tiers: Record<string, number>;
  actions: Record<string, number>;
  reply_stats: Record<string, number>;
  total: number;
  send_now_ready: number;
}

export interface CampaignStats {
  total: number;
  sent: number;
  not_sent: number;
  campaigns: Record<string, { total: number; sent: number; not_sent: number }>;
}

export interface CampaignPreviewRequest {
  email: string;
  company: string;
  pic: string;
  pol: string;
  destinations: string;
  markup: number;
  intro: string;
  closing: string;
  subject: string;
  template: 'professional' | 'plain';
}

export interface CampaignSendRequest extends CampaignPreviewRequest {
  campaign_id: string;
  cc_emails: string[];
}

export interface CampaignSendResponse {
  status: string;
  to: string;
  company: string;
  cc: string[];
  subject: string;
  rows_sent: number;
  campaign_id: string;
  template: string;
  timestamp: string;
}

export interface CampaignBulkSendRequest {
  emails: string[];
  markup: number;
  template: 'professional' | 'plain';
  campaign_id?: string;
  cc_emails?: string[];
  subject?: string;
}

export interface CampaignBulkSendResult {
  email: string;
  company: string;
  subject?: string;
  status: string;
  error?: string;
}

export interface CampaignBulkSendResponse {
  sent: number;
  failed: number;
  results: CampaignBulkSendResult[];
  errors: CampaignBulkSendResult[];
  timestamp: string;
}

export const campaignApi = {
  prospects: (params: {
    campaign?: string;
    search?: string;
    sent_status?: string;
    tier?: string;
    page?: number;
    page_size?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.campaign) qs.set('campaign', params.campaign);
    if (params.search) qs.set('search', params.search);
    if (params.sent_status) qs.set('sent_status', params.sent_status);
    if (params.tier) qs.set('tier', params.tier);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    return fetchAPI<CampaignProspectsResponse>(`/api/email-rate/campaign/prospects?${qs}`);
  },

  stats: () =>
    fetchAPI<CampaignStats>('/api/email-rate/campaign/stats'),

  tierStats: () =>
    fetchAPI<TierStats>('/api/email-rate/campaign/tier-stats'),

  preview: (req: CampaignPreviewRequest) =>
    fetchAPI<PreviewResponse & { template: string }>('/api/email-rate/campaign/preview', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  send: (req: CampaignSendRequest) =>
    fetchAPI<CampaignSendResponse>('/api/email-rate/campaign/send', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  bulkSend: (req: CampaignBulkSendRequest) =>
    fetchAPI<CampaignBulkSendResponse>('/api/email-rate/campaign/bulk-send', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

export default api;
