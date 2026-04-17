/**
 * Nelson Freight System — API Client
 * Connects WebApp to Dashboard API (port 8100)
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://14.225.207.145:8100';

const API_BASE = API_URL;

// ── Fetch wrapper with error handling ─────────────────────
async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = 300_000; // 5 minutes — bulk-send renders 50 emails
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      const detail = body ? JSON.parse(body)?.detail || res.statusText : res.statusText;
      throw new Error(`API error: ${res.status} — ${detail}`);
    }
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timeout — server took too long (5min limit)');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
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

// ═══════════════════════════════════════════════════════════════════════════
// EMAIL SEND API REMOVED 2026-04-17
// Email send pipeline moved to email_engine/web_server.py (local PC + Outlook COM).
// See docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md
// Do NOT re-add emailRateApi or campaignApi here — they are DEAD paths.
// ═══════════════════════════════════════════════════════════════════════════

// ── Data Explorer API (S14B) ─────────────────────────────────

export interface CneeRow {
  email: string;
  company: string;
  pic: string;
  campaign_id: string;
  country: string;
  already_sent: string;
  last_sent: string | null;
  send_count: number;
  tier: string;
  email_quality: number;
}

export interface CneeListResponse {
  rows: CneeRow[];
  total: number;
  filtered: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface EmailLogRow {
  id: number;
  email: string;
  company: string;
  subject: string;
  campaign_id: string;
  status: 'pending' | 'sending' | 'sent' | 'failed';
  sent_at: string | null;
  error: string | null;
  created_at: string;
}

export interface EmailLogResponse {
  rows: EmailLogRow[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  stats: {
    total_sent: number;
    total_failed: number;
    total_pending: number;
    bounce_rate: number;
  };
}

export interface QueueResponse {
  sent: number;
  failed: number;
  results: Array<{ email: string; company: string; subject: string; status: string; queue_id: number }>;
  errors: Array<{ email: string; company: string; error: string }>;
  timestamp: string;
}

function scoreToTier(score: number): string {
  if (score >= 0.8) return 'VIP';
  if (score >= 0.6) return 'HOT';
  if (score >= 0.4) return 'WARM_A';
  if (score >= 0.2) return 'WARM_B';
  if (score > 0)    return 'COOL';
  return 'PARK';
}

export const dataApi = {
  cneeList: async (params: {
    page?: number;
    limit?: number;
    campaign?: string;
    status?: string;
    country?: string;
    search?: string;
  } = {}): Promise<CneeListResponse> => {
    const qs = new URLSearchParams();
    if (params.page) qs.set('page', String(params.page));
    if (params.limit) qs.set('page_size', String(params.limit));
    if (params.campaign) qs.set('campaign', params.campaign);
    if (params.status) qs.set('status', params.status);
    if (params.country) qs.set('country', params.country);
    // API doesn't support search filter yet — handled client-side
    const raw = await fetchAPI<{
      total: number; page: number; page_size: number; pages: number;
      items: Array<{
        id: number; company_name: string; contact_name: string; email: string;
        campaign: string; country: string; port: string; status: string;
        lead_score: number; last_contacted: string | null;
      }>;
    }>(`/api/data/cnee?${qs}`);

    const rows: CneeRow[] = (raw.items ?? []).map(r => ({
      email:        r.email ?? '',
      company:      r.company_name ?? '',
      pic:          r.contact_name ?? '',
      campaign_id:  r.campaign ?? '',
      country:      r.country ?? '',
      already_sent: r.last_contacted ? 'Y' : 'N',
      last_sent:    r.last_contacted ?? null,
      send_count:   0,
      tier:         scoreToTier(r.lead_score ?? 0),
      email_quality: Math.round((r.lead_score ?? 0) * 100),
    }));

    return {
      rows,
      total:       raw.total ?? 0,
      filtered:    raw.total ?? 0,
      page:        raw.page ?? 1,
      limit:       raw.page_size ?? 50,
      total_pages: raw.pages ?? 1,
    };
  },

  emailLog: (params: {
    page?: number;
    limit?: number;
    status?: string;
    campaign?: string;
    date_from?: string;
    date_to?: string;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.page) qs.set('page', String(params.page));
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.status) qs.set('status', params.status);
    if (params.campaign) qs.set('campaign', params.campaign);
    if (params.date_from) qs.set('date_from', params.date_from);
    if (params.date_to) qs.set('date_to', params.date_to);
    return fetchAPI<EmailLogResponse>(`/api/data/email-log?${qs}`);
  },

  queueEmails: (payload: {
    emails: string[];
    campaign_id: string;
    markup?: number;
    template?: string;
  }) =>
    fetchAPI<QueueResponse>('/api/email-rate/campaign/bulk-send', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export default api;
