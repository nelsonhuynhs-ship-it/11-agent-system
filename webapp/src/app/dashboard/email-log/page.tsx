"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { dataApi, EmailLogRow, EmailLogResponse } from "@/lib/api";

// ── Constants ─────────────────────────────────────────────────
const PAGE_SIZE = 50;
const AUTO_REFRESH_MS = 10_000;

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-500/15 text-yellow-400",
  sending: "bg-blue-500/15 text-blue-400",
  sent: "bg-green-500/15 text-green-400",
  failed: "bg-red-500/15 text-red-400",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  sending: "Sending",
  sent: "Sent",
  failed: "Failed",
};

// ═══════════════════════════════════════════════════════════════
export default function EmailLogPage() {
  const [data, setData] = useState<EmailLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [campaignFilter, setCampaignFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await dataApi.emailLog({
        page,
        limit: PAGE_SIZE,
        status: statusFilter || undefined,
        campaign: campaignFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setData(res);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load email log");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [page, statusFilter, campaignFilter, dateFrom, dateTo]);

  // Initial + filter-driven fetch
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset page on filter change
  useEffect(() => {
    setPage(1);
  }, [statusFilter, campaignFilter, dateFrom, dateTo]);

  // Auto-refresh every 10s (silent — no loading spinner)
  useEffect(() => {
    intervalRef.current = setInterval(() => fetchData(true), AUTO_REFRESH_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  const stats = data?.stats;
  const rows = data?.rows ?? [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-text">Email Log</h1>
          <p className="text-sm text-text-muted mt-0.5">
            {lastRefresh
              ? `Auto-refresh mỗi 10s • Last: ${lastRefresh.toLocaleTimeString()}`
              : "Loading..."}
          </p>
        </div>
        <button
          onClick={() => fetchData()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-muted hover:text-text transition-colors"
        >
          <RefreshIcon className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total Sent" value={stats.total_sent} color="text-green-400" />
          <StatCard label="Failed" value={stats.total_failed} color="text-red-400" />
          <StatCard label="Pending" value={stats.total_pending} color="text-yellow-400" />
          <StatCard
            label="Bounce Rate"
            value={`${(stats.bounce_rate * 100).toFixed(1)}%`}
            color="text-text-muted"
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text focus:outline-none focus:border-accent"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="sending">Sending</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>
        <input
          type="text"
          placeholder="Campaign"
          value={campaignFilter}
          onChange={e => setCampaignFilter(e.target.value.toUpperCase())}
          className="w-[160px] px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text focus:outline-none focus:border-accent"
        />
        <input
          type="date"
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text focus:outline-none focus:border-accent"
        />
        {(statusFilter || campaignFilter || dateFrom || dateTo) && (
          <button
            onClick={() => {
              setStatusFilter("");
              setCampaignFilter("");
              setDateFrom("");
              setDateTo("");
            }}
            className="px-3 py-1.5 rounded-lg text-sm text-text-muted hover:text-text border border-border bg-surface transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        {error && (
          <div className="px-4 py-3 bg-red-500/10 text-red-400 text-sm border-b border-border">
            {error}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-hover">
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[160px]">Company</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[190px]">Email</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[250px]">Subject</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[110px]">Campaign</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[90px]">Status</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide min-w-[140px]">Sent At</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-text-muted text-sm">
                    Loading...
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-text-muted text-sm">
                    No emails found.
                  </td>
                </tr>
              )}
              {!loading && rows.map((row) => (
                <EmailLogRowItem key={row.id} row={row} />
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-text-muted">
              Page {data.page} of {data.total_pages} ({data.total.toLocaleString()} total)
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 rounded-lg text-sm bg-surface border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Prev
              </button>
              <button
                onClick={() => setPage(p => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="px-3 py-1 rounded-lg text-sm bg-surface border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-1">
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function EmailLogRowItem({ row }: { row: EmailLogRow }) {
  const statusStyle = STATUS_STYLES[row.status] ?? "bg-gray-500/15 text-gray-400";
  const statusLabel = STATUS_LABELS[row.status] ?? row.status;

  return (
    <tr className="border-b border-border/50 hover:bg-surface-hover transition-colors group">
      <td className="px-3 py-2 font-medium text-text">{row.company}</td>
      <td className="px-3 py-2 text-text-muted text-xs">{row.email}</td>
      <td className="px-3 py-2 text-text-muted truncate max-w-[250px]" title={row.subject}>
        {row.subject}
      </td>
      <td className="px-3 py-2">
        <span className="text-xs font-medium text-accent">{row.campaign_id}</span>
      </td>
      <td className="px-3 py-2">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyle}`}>
          {row.status === "sending" && <PulseIcon />}
          {statusLabel}
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-text-muted">
        {row.sent_at
          ? new Date(row.sent_at).toLocaleString()
          : row.status === "failed" && row.error
          ? <span className="text-red-400 truncate max-w-[130px] block" title={row.error}>{row.error}</span>
          : "—"}
      </td>
    </tr>
  );
}

// ── Icons ─────────────────────────────────────────────────────

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round"
      strokeLinejoin="round" className={className}>
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function PulseIcon() {
  return (
    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
  );
}
