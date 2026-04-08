"use client";

import { useState, useEffect, useCallback } from "react";
import { dataApi, CneeRow, CneeListResponse } from "@/lib/api";

// ── Constants ─────────────────────────────────────────────────
const PAGE_SIZE = 50;

type SortKey = keyof CneeRow;
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; width?: string }[] = [
  { key: "company", label: "Company", width: "min-w-[200px]" },
  { key: "email", label: "Email", width: "min-w-[200px]" },
  { key: "pic", label: "PIC", width: "min-w-[100px]" },
  { key: "campaign_id", label: "Campaign", width: "min-w-[120px]" },
  { key: "tier", label: "Tier", width: "min-w-[80px]" },
  { key: "already_sent", label: "Sent?", width: "min-w-[70px]" },
  { key: "send_count", label: "Sends", width: "min-w-[70px]" },
  { key: "email_quality", label: "Quality", width: "min-w-[80px]" },
  { key: "last_sent", label: "Last Sent", width: "min-w-[120px]" },
  { key: "country", label: "Country", width: "min-w-[90px]" },
];

const TIER_COLORS: Record<string, string> = {
  VIP: "bg-pink-500/15 text-pink-400",
  HOT: "bg-red-500/15 text-red-400",
  WARM_A: "bg-yellow-500/15 text-yellow-400",
  WARM_B: "bg-blue-500/15 text-blue-400",
  COOL: "bg-green-500/15 text-green-400",
  PARK: "bg-gray-500/15 text-gray-400",
};

// ═══════════════════════════════════════════════════════════════
export default function DataExplorerPage() {
  const [data, setData] = useState<CneeListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [campaign, setCampaign] = useState("");
  const [status, setStatus] = useState("");
  const [country, setCountry] = useState("");
  const [page, setPage] = useState(1);

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>("company");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dataApi.cneeList({
        page,
        limit: PAGE_SIZE,
        search: search || undefined,
        campaign: campaign || undefined,
        status: status || undefined,
        country: country || undefined,
      });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [page, search, campaign, status, country]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [search, campaign, status, country]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  // Client-side sort (server returns all rows for current page)
  const sortedRows = data?.rows
    ? [...data.rows].sort((a, b) => {
        const av = a[sortKey] ?? "";
        const bv = b[sortKey] ?? "";
        const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
        return sortDir === "asc" ? cmp : -cmp;
      })
    : [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-text">Data Explorer</h1>
          <p className="text-sm text-text-muted mt-0.5">
            {data ? `${data.filtered.toLocaleString()} / ${data.total.toLocaleString()} CNEEs` : "Loading..."}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-muted hover:text-text transition-colors"
        >
          <RefreshIcon className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Search company or email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
        <input
          type="text"
          placeholder="Campaign (e.g. CANDLE)"
          value={campaign}
          onChange={e => setCampaign(e.target.value.toUpperCase())}
          className="w-[180px] px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text focus:outline-none focus:border-accent"
        >
          <option value="">All Status</option>
          <option value="sent">Sent</option>
          <option value="not_sent">Not Sent</option>
        </select>
        <input
          type="text"
          placeholder="Country"
          value={country}
          onChange={e => setCountry(e.target.value)}
          className="w-[120px] px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-hover">
                {COLUMNS.map(col => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className={`px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide cursor-pointer hover:text-text transition-colors select-none ${col.width ?? ""}`}
                  >
                    <span className="flex items-center gap-1">
                      {col.label}
                      {sortKey === col.key && (
                        <span className="text-accent">{sortDir === "asc" ? "↑" : "↓"}</span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-3 py-8 text-center text-text-muted text-sm">
                    Loading...
                  </td>
                </tr>
              )}
              {error && !loading && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-3 py-8 text-center text-red-400 text-sm">
                    {error}
                  </td>
                </tr>
              )}
              {!loading && !error && sortedRows.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-3 py-8 text-center text-text-muted text-sm">
                    No results found.
                  </td>
                </tr>
              )}
              {!loading && sortedRows.map((row, i) => (
                <tr
                  key={`${row.email}-${i}`}
                  className="border-b border-border/50 hover:bg-surface-hover transition-colors"
                >
                  <td className="px-3 py-2 font-medium text-text truncate max-w-[220px]">{row.company}</td>
                  <td className="px-3 py-2 text-text-muted truncate max-w-[220px]">{row.email}</td>
                  <td className="px-3 py-2 text-text-muted">{row.pic}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs font-medium text-accent">{row.campaign_id}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded-md ${TIER_COLORS[row.tier] ?? "bg-gray-500/15 text-gray-400"}`}>
                      {row.tier}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`text-xs font-medium ${row.already_sent === "Y" ? "text-green-400" : "text-text-muted"}`}>
                      {row.already_sent === "Y" ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-text-muted text-center">{row.send_count}</td>
                  <td className="px-3 py-2 text-text-muted text-center">{row.email_quality}</td>
                  <td className="px-3 py-2 text-text-muted text-xs">{row.last_sent ?? "—"}</td>
                  <td className="px-3 py-2 text-text-muted">{row.country}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-text-muted">
              Page {data.page} of {data.total_pages}
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
