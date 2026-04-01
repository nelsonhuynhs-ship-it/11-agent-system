"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  emailRateApi,
  campaignApi,
  CustomerInfo,
  PreviewResponse,
  EmailRateConfig,
  CampaignProspect,
  CampaignStats,
  CampaignBulkSendResponse,
} from "@/lib/api";

// ── Constants ────────────────────────────────────────────────────────────────
const DEFAULT_DESTS =
  "USLAX,USLGB,USTIW,CAVAN,USNYC,USEWR,USSAV,USCHS,CAHAL,USDAL,USDEN,USSEA,USCHI";

type TabType = "campaign" | "quick";

// ═══════════════════════════════════════════════════════════════════════════
export default function RateSendPage() {
  const [activeTab, setActiveTab] = useState<TabType>("campaign");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text">Rate & Send</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Query giá DuckDB → Preview email → Gửi Office 365
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-surface rounded-lg w-fit">
        <button
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            activeTab === "campaign"
              ? "bg-primary text-white shadow-sm"
              : "text-text-muted hover:text-text"
          }`}
          onClick={() => setActiveTab("campaign")}
        >
          Campaign CNEE
        </button>
        <button
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            activeTab === "quick"
              ? "bg-primary text-white shadow-sm"
              : "text-text-muted hover:text-text"
          }`}
          onClick={() => setActiveTab("quick")}
        >
          Quick Send
        </button>
      </div>

      {activeTab === "campaign" ? <CampaignTab /> : <QuickSendTab />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CAMPAIGN TAB
// ═══════════════════════════════════════════════════════════════════════════

function CampaignTab() {
  // State
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [prospects, setProspects] = useState<CampaignProspect[]>([]);
  const [campaigns, setCampaigns] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Filters
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sentFilter, setSentFilter] = useState("not_sent");
  const [currentPage, setCurrentPage] = useState(1);

  // Selected prospect for email compose (single)
  const [selected, setSelected] = useState<CampaignProspect | null>(null);

  // Multi-select for bulk send
  const [checkedEmails, setCheckedEmails] = useState<Set<string>>(new Set());
  const [bulkResult, setBulkResult] = useState<CampaignBulkSendResponse | null>(null);

  // Email compose
  const [template, setTemplate] = useState<"professional" | "plain">("professional");
  const [markup, setMarkup] = useState(20);
  const [customDests, setCustomDests] = useState("");
  const [subject, setSubject] = useState("");
  const [intro, setIntro] = useState("");
  const [closing, setClosing] = useState("");
  const [ccEmails, setCcEmails] = useState("");

  // Preview
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState<"list" | "preview" | "send" | "bulk" | null>(null);
  const [sendResult, setSendResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Debounce search
  const searchTimeout = useRef<NodeJS.Timeout>(null);

  // Load stats on mount
  useEffect(() => {
    campaignApi.stats().then(setStats).catch(() => {});
  }, []);

  // Load prospects
  const loadProspects = useCallback(async () => {
    setLoading("list");
    try {
      const res = await campaignApi.prospects({
        campaign: selectedCampaign,
        search: searchQuery,
        sent_status: sentFilter,
        page: currentPage,
        page_size: 50,
      });
      setProspects(res.prospects);
      setCampaigns(res.campaigns);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch {
      setProspects([]);
    } finally {
      setLoading(null);
    }
  }, [selectedCampaign, searchQuery, sentFilter, currentPage]);

  useEffect(() => { loadProspects(); }, [loadProspects]);

  // Search with debounce
  function handleSearch(value: string) {
    setSearchQuery(value);
    setCurrentPage(1);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {}, 300);
  }

  // Select prospect → auto-fill compose
  function selectProspect(p: CampaignProspect) {
    setSelected(p);
    setCustomDests(p.destination || DEFAULT_DESTS);
    setPreview(null);
    setSendResult(null);
    setError(null);
  }

  // Preview
  async function handlePreview() {
    if (!selected) { setError("Chưa chọn prospect"); return; }
    setError(null);
    setPreview(null);
    setSendResult(null);
    setLoading("preview");
    try {
      const res = await campaignApi.preview({
        email:        selected.email,
        company:      selected.company,
        pic:          selected.pic,
        pol:          selected.pol,
        destinations: customDests || DEFAULT_DESTS,
        markup,
        intro,
        closing,
        subject,
        template,
      });
      setPreview(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoading(null);
    }
  }

  // Send (single)
  async function handleSend() {
    if (!preview || preview.is_blocked || !selected) return;
    setError(null);
    setSendResult(null);
    setLoading("send");
    try {
      const ccList = ccEmails ? ccEmails.split(",").map(e => e.trim()).filter(Boolean) : [];
      await campaignApi.send({
        email:        selected.email,
        company:      selected.company,
        pic:          selected.pic,
        pol:          selected.pol,
        destinations: customDests || DEFAULT_DESTS,
        markup,
        intro,
        closing,
        subject,
        template,
        campaign_id:  selected.campaign_id,
        cc_emails:    ccList,
      });
      setSendResult({ ok: true, msg: `Sent to ${selected.email} (${selected.company})` });
      setPreview(null);
      loadProspects();
    } catch (e: unknown) {
      setSendResult({ ok: false, msg: e instanceof Error ? e.message : "Send failed" });
    } finally {
      setLoading(null);
    }
  }

  // Bulk send (selected checkboxes)
  async function handleBulkSend() {
    if (checkedEmails.size === 0) return;
    if (!confirm(`Gửi email đến ${checkedEmails.size} prospects?\n\nMarkup: $${markup} | Template: ${template}`)) return;
    setLoading("bulk");
    setBulkResult(null);
    setError(null);
    const ccList = ccEmails ? ccEmails.split(",").map(e => e.trim()).filter(Boolean) : [];
    try {
      const res = await campaignApi.bulkSend({
        emails:      Array.from(checkedEmails),
        markup,
        template,
        cc_emails:   ccList,
        subject,
      });
      setBulkResult(res);
      setCheckedEmails(new Set());
      loadProspects();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Bulk send failed");
    } finally {
      setLoading(null);
    }
  }

  // Toggle single checkbox
  function toggleCheck(email: string) {
    setCheckedEmails(prev => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else next.add(email);
      return next;
    });
  }

  // Select/deselect all on current page
  function toggleSelectAll() {
    const pageEmails = prospects.map(p => p.email);
    const allChecked = pageEmails.every(e => checkedEmails.has(e));
    setCheckedEmails(prev => {
      const next = new Set(prev);
      if (allChecked) { pageEmails.forEach(e => next.delete(e)); }
      else { pageEmails.forEach(e => next.add(e)); }
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {/* Stats Bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total CNEE" value={stats.total} color="blue" />
          <StatCard label="Already Sent" value={stats.sent} color="green" />
          <StatCard label="Not Sent" value={stats.not_sent} color="amber" />
          <StatCard label="Campaigns" value={Object.keys(stats.campaigns).length} color="purple" />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* ── LEFT: Prospect List (3 cols) ─────────────────────────── */}
        <div className="xl:col-span-3 space-y-3">
          {/* Filters */}
          <div className="card p-3">
            <div className="flex flex-wrap gap-2">
              {/* Campaign filter */}
              <select
                className="input text-sm py-1.5 w-40"
                value={selectedCampaign}
                onChange={(e) => { setSelectedCampaign(e.target.value); setCurrentPage(1); }}
              >
                <option value="">All Campaigns</option>
                {campaigns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>

              {/* Sent status */}
              <select
                className="input text-sm py-1.5 w-32"
                value={sentFilter}
                onChange={(e) => { setSentFilter(e.target.value); setCurrentPage(1); }}
              >
                <option value="all">All Status</option>
                <option value="not_sent">Not Sent</option>
                <option value="sent">Sent</option>
              </select>

              {/* Search */}
              <input
                className="input text-sm py-1.5 flex-1 min-w-[180px]"
                placeholder="Search company or email..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
              />

              <span className="text-xs text-text-muted self-center ml-auto">
                {total} prospects
              </span>
            </div>
          </div>

          {/* Bulk action toolbar */}
          {checkedEmails.size > 0 && (
            <div className="card p-2 flex items-center gap-3 bg-primary/5 border border-primary/20">
              <span className="text-xs font-semibold text-primary">{checkedEmails.size} selected</span>
              <div className="flex gap-2 ml-auto items-center">
                <label className="text-[11px] text-text-muted">Markup:</label>
                <input
                  type="number" min={0}
                  className="input w-16 text-xs py-1"
                  value={markup}
                  onChange={(e) => setMarkup(Number(e.target.value))}
                />
                <select
                  className="input text-xs py-1"
                  value={template}
                  onChange={(e) => setTemplate(e.target.value as "professional" | "plain")}
                >
                  <option value="professional">Professional</option>
                  <option value="plain">Plain</option>
                </select>
                <button
                  className="btn btn-primary text-xs px-3 py-1.5"
                  onClick={handleBulkSend}
                  disabled={loading === "bulk"}
                >
                  {loading === "bulk" ? (
                    <span className="flex items-center gap-1.5">
                      <SpinnerIcon className="w-3 h-3 animate-spin" /> Sending...
                    </span>
                  ) : (
                    `Send All (${checkedEmails.size})`
                  )}
                </button>
                <button
                  className="text-xs text-text-muted hover:text-text px-2"
                  onClick={() => setCheckedEmails(new Set())}
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Bulk result */}
          {bulkResult && (
            <div className={`card p-3 text-xs ${bulkResult.failed === 0 ? "bg-green-500/10 border border-green-500/30" : "bg-yellow-500/10 border border-yellow-500/30"}`}>
              <p className="font-semibold text-text">
                Bulk send: {bulkResult.sent} sent / {bulkResult.failed} failed
              </p>
              {bulkResult.errors.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-text-muted">
                  {bulkResult.errors.slice(0, 5).map((e, i) => (
                    <li key={i}>✗ {e.email} — {e.error}</li>
                  ))}
                  {bulkResult.errors.length > 5 && <li>...and {bulkResult.errors.length - 5} more</li>}
                </ul>
              )}
            </div>
          )}

          {/* Prospect Table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface border-b border-border">
                    <th className="px-3 py-2 w-8">
                      <input
                        type="checkbox"
                        className="cursor-pointer"
                        checked={prospects.length > 0 && prospects.every(p => checkedEmails.has(p.email))}
                        onChange={toggleSelectAll}
                        title="Select all on this page"
                      />
                    </th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-text-muted">Company</th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-text-muted">Email</th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-text-muted hidden sm:table-cell">Campaign</th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-text-muted hidden md:table-cell">Shipments</th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-text-muted">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {loading === "list" ? (
                    <tr><td colSpan={6} className="text-center py-8 text-text-muted text-sm">Loading...</td></tr>
                  ) : prospects.length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-text-muted text-sm">No prospects found</td></tr>
                  ) : (
                    prospects.map((p, i) => (
                      <tr
                        key={`${p.email}-${i}`}
                        className={`border-b border-border/50 transition-colors ${
                          selected?.email === p.email
                            ? "bg-primary/10 border-l-2 border-l-primary"
                            : checkedEmails.has(p.email)
                            ? "bg-primary/5"
                            : "hover:bg-surface-hover"
                        }`}
                      >
                        <td className="px-3 py-2 w-8" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            className="cursor-pointer"
                            checked={checkedEmails.has(p.email)}
                            onChange={() => toggleCheck(p.email)}
                          />
                        </td>
                        <td className="px-3 py-2 cursor-pointer" onClick={() => selectProspect(p)}>
                          <div className="font-medium text-text text-xs">{p.company}</div>
                          {p.pic && <div className="text-[11px] text-text-muted">{p.pic}</div>}
                        </td>
                        <td className="px-3 py-2 text-xs text-text-muted max-w-[200px] truncate cursor-pointer" onClick={() => selectProspect(p)}>{p.email}</td>
                        <td className="px-3 py-2 text-xs text-text-muted hidden sm:table-cell cursor-pointer" onClick={() => selectProspect(p)}>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface">
                            {p.campaign_id}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center text-xs text-text-muted hidden md:table-cell cursor-pointer" onClick={() => selectProspect(p)}>
                          {p.total_shipment}
                        </td>
                        <td className="px-3 py-2 text-center cursor-pointer" onClick={() => selectProspect(p)}>
                          {p.already_sent === "Y" ? (
                            <span className="inline-block w-2 h-2 rounded-full bg-green-400" title="Sent" />
                          ) : (
                            <span className="inline-block w-2 h-2 rounded-full bg-amber-400" title="Not sent" />
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-surface">
                <button
                  className="text-xs text-text-muted hover:text-text disabled:opacity-30"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage(p => p - 1)}
                >
                  Previous
                </button>
                <span className="text-xs text-text-muted">
                  Page {currentPage} / {totalPages}
                </span>
                <button
                  className="text-xs text-text-muted hover:text-text disabled:opacity-30"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage(p => p + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Compose + Preview (2 cols) ───────────────────── */}
        <div className="xl:col-span-2 space-y-3">
          {selected ? (
            <>
              {/* Selected prospect info */}
              <div className="card p-3 border-l-2 border-l-primary">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-text">{selected.company}</h3>
                    <p className="text-xs text-text-muted mt-0.5">{selected.email}</p>
                    {selected.pic && <p className="text-xs text-text-muted">PIC: {selected.pic}</p>}
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface font-medium text-text-muted">
                    {selected.campaign_id}
                  </span>
                </div>
              </div>

              {/* Compose */}
              <div className="card p-3 space-y-3">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Compose Email</h3>

                {/* Template + Markup */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] text-text-muted mb-1">Template</label>
                    <select
                      className="input w-full text-sm py-1.5"
                      value={template}
                      onChange={(e) => setTemplate(e.target.value as "professional" | "plain")}
                    >
                      <option value="professional">Professional</option>
                      <option value="plain">Plain Text</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] text-text-muted mb-1">Markup (USD)</label>
                    <input
                      className="input w-full text-sm py-1.5"
                      type="number"
                      min={0}
                      value={markup}
                      onChange={(e) => setMarkup(Number(e.target.value))}
                    />
                  </div>
                </div>

                {/* Destinations */}
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    Destinations (auto-filled from CNEE)
                  </label>
                  <textarea
                    className="input w-full h-14 resize-none font-mono text-[11px]"
                    value={customDests}
                    onChange={(e) => setCustomDests(e.target.value)}
                  />
                </div>

                {/* Subject */}
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">Subject (blank = auto)</label>
                  <input
                    className="input w-full text-sm py-1.5"
                    placeholder="Auto-generated from company name"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </div>

                {/* CC */}
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">CC (comma-separated)</label>
                  <input
                    className="input w-full text-sm py-1.5"
                    placeholder="cc@company.com"
                    value={ccEmails}
                    onChange={(e) => setCcEmails(e.target.value)}
                  />
                </div>

                {/* Intro / Closing (collapsible) */}
                <details className="group">
                  <summary className="text-[11px] text-text-muted cursor-pointer hover:text-text">
                    Customize intro & closing
                  </summary>
                  <div className="mt-2 space-y-2">
                    <textarea
                      className="input w-full h-16 resize-none text-xs"
                      placeholder="Custom intro (default: professional greeting)"
                      value={intro}
                      onChange={(e) => setIntro(e.target.value)}
                    />
                    <textarea
                      className="input w-full h-16 resize-none text-xs"
                      placeholder="Custom closing (default: professional sign-off)"
                      value={closing}
                      onChange={(e) => setClosing(e.target.value)}
                    />
                  </div>
                </details>

                {/* Action buttons */}
                <div className="flex gap-2 pt-1">
                  <button
                    className="btn btn-secondary flex-1 text-sm py-2"
                    onClick={handlePreview}
                    disabled={loading !== null}
                  >
                    {loading === "preview" ? (
                      <span className="flex items-center gap-2 justify-center">
                        <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> Querying...
                      </span>
                    ) : "Preview"}
                  </button>

                  <button
                    className={`btn flex-1 text-sm py-2 ${
                      preview && !preview.is_blocked
                        ? "btn-primary"
                        : "opacity-40 cursor-not-allowed bg-surface border border-border text-text-muted"
                    }`}
                    onClick={handleSend}
                    disabled={!preview || preview.is_blocked || loading !== null}
                  >
                    {loading === "send" ? (
                      <span className="flex items-center gap-2 justify-center">
                        <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> Sending...
                      </span>
                    ) : !preview ? "Preview first" : preview.is_blocked ? "Blocked" : "Approve & Send"}
                  </button>
                </div>

                {/* Error */}
                {error && (
                  <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">
                    {error}
                  </div>
                )}

                {/* Send result */}
                {sendResult && (
                  <div className={`rounded-lg px-3 py-2 text-xs ${
                    sendResult.ok
                      ? "bg-green-500/10 border border-green-500/30 text-green-400"
                      : "bg-red-500/10 border border-red-500/30 text-red-400"
                  }`}>
                    {sendResult.msg}
                  </div>
                )}
              </div>

              {/* Preview panel */}
              {preview && (
                <div className="card overflow-hidden">
                  {/* Status */}
                  {preview.is_blocked ? (
                    <div className="px-3 py-2 bg-red-500/15 border-b border-red-500/30">
                      <p className="text-xs font-semibold text-red-400">{preview.warn_msg}</p>
                    </div>
                  ) : preview.warn_msg ? (
                    <div className="px-3 py-2 bg-yellow-500/15 border-b border-yellow-500/30">
                      <p className="text-xs font-semibold text-yellow-400">{preview.warn_msg}</p>
                    </div>
                  ) : (
                    <div className="px-3 py-2 bg-green-500/10 border-b border-green-500/30">
                      <p className="text-xs text-green-400">
                        {preview.row_count} routes — {preview.dests_found} dests — POL: {preview.pol_queried.join(", ")}
                        {preview.days_used && preview.days_used > 30 && (
                          <span className="ml-2 text-amber-400 font-semibold">⚠ fallback {preview.days_used}d</span>
                        )}
                      </p>
                      {preview.route_debug && Object.keys(preview.route_debug).length > 0 && (
                        <details className="mt-1">
                          <summary className="text-[10px] text-green-600 cursor-pointer hover:text-green-400">
                            Route mapping debug ({Object.keys(preview.route_debug).length} routes)
                          </summary>
                          <div className="mt-1 space-y-0.5">
                            {Object.entries(preview.route_debug).map(([dest, info]) => (
                              <p key={dest} className="text-[10px] text-text-muted font-mono">{info}</p>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  )}

                  {/* Subject */}
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-[10px] text-text-muted">Subject</p>
                    <p className="text-xs font-medium text-text">{preview.subject}</p>
                  </div>

                  {/* HTML */}
                  <div className="overflow-auto max-h-[500px] p-2 bg-white">
                    <div
                      className="text-[12px]"
                      dangerouslySetInnerHTML={{ __html: preview.html }}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="card p-8 flex flex-col items-center justify-center text-center min-h-[300px]">
              <MailIcon className="w-10 h-10 text-text-muted mb-3 opacity-40" />
              <p className="text-sm text-text-muted">
                Select a prospect from the list to compose an email
              </p>
              <p className="text-xs text-text-muted mt-1">
                Click any row to begin
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// QUICK SEND TAB (Original Rate & Send)
// ═══════════════════════════════════════════════════════════════════════════

function QuickSendTab() {
  const [customers, setCustomers] = useState<CustomerInfo[]>([]);
  const [config, setConfig] = useState<EmailRateConfig | null>(null);
  const [form, setForm] = useState({
    customer: "",
    pic: "",
    pol: "",
    destinations: DEFAULT_DESTS,
    markup: 20,
    intro: "",
    closing: "",
    subject: "",
    toEmail: "",
    ccEmails: "",
  });

  const [customerSearch, setCustomerSearch] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState<"preview" | "send" | null>(null);
  const [sendResult, setSendResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    emailRateApi.customers().then((r) => setCustomers(r.customers)).catch(() => {});
    emailRateApi.config().then((c) => {
      setConfig(c);
      setForm((f) => ({
        ...f,
        intro: c.intro_default || f.intro,
        closing: c.closing_default || f.closing,
      }));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filteredCustomers = customers.filter((c) =>
    c.name.toLowerCase().includes(customerSearch.toLowerCase())
  );

  function selectCustomer(c: CustomerInfo) {
    setForm((f) => ({
      ...f,
      customer: c.name,
      pol: c.pol || "",
      destinations: c.destinations || DEFAULT_DESTS,
      pic: c.pic || f.pic,
      toEmail: c.email || f.toEmail,
    }));
    setCustomerSearch(c.name);
    setShowDropdown(false);
    setPreview(null);
    setSendResult(null);
  }

  async function handlePreview() {
    if (!form.customer) { setError("Chưa chọn khách hàng"); return; }
    setError(null);
    setPreview(null);
    setSendResult(null);
    setLoading("preview");
    try {
      const res = await emailRateApi.preview({
        customer: form.customer,
        pic: form.pic,
        pol: form.pol,
        destinations: form.destinations,
        markup: form.markup,
        intro: form.intro,
        closing: form.closing,
        subject: form.subject,
      });
      setPreview(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoading(null);
    }
  }

  async function handleSend() {
    if (!preview || preview.is_blocked) return;
    if (!form.toEmail) { setError("Chưa nhập email người nhận"); return; }
    setError(null);
    setSendResult(null);
    setLoading("send");
    try {
      const ccList = form.ccEmails
        ? form.ccEmails.split(",").map((e) => e.trim()).filter(Boolean)
        : [];
      await emailRateApi.send({
        customer: form.customer,
        pic: form.pic,
        pol: form.pol,
        destinations: form.destinations,
        markup: form.markup,
        intro: form.intro,
        closing: form.closing,
        subject: form.subject,
        to_email: form.toEmail,
        cc_emails: ccList,
      });
      setSendResult({ ok: true, msg: `Sent to ${form.toEmail}` });
      setPreview(null);
    } catch (e: unknown) {
      setSendResult({ ok: false, msg: e instanceof Error ? e.message : "Send failed" });
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
      {/* LEFT: Form */}
      <div className="space-y-4">
        <div className="card p-4 space-y-3">
          <h2 className="text-sm font-semibold text-text">Customer Info</h2>

          <div ref={dropdownRef} className="relative">
            <label className="block text-xs text-text-muted mb-1">Customer *</label>
            <input
              className="input w-full"
              placeholder="Search customer..."
              value={customerSearch}
              onChange={(e) => {
                setCustomerSearch(e.target.value);
                setShowDropdown(true);
                if (!e.target.value) setForm((f) => ({ ...f, customer: "" }));
              }}
              onFocus={() => setShowDropdown(true)}
            />
            {showDropdown && filteredCustomers.length > 0 && (
              <div className="absolute z-20 w-full mt-1 bg-sidebar border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {filteredCustomers.map((c) => (
                  <button
                    key={c.name}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-surface-hover flex justify-between items-center"
                    onMouseDown={() => selectCustomer(c)}
                  >
                    <span className="font-medium text-text">{c.name}</span>
                    <span className="text-xs text-text-muted">{c.pol || "HPH"}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">PIC</label>
            <input
              className="input w-full"
              placeholder="Contact person..."
              value={form.pic}
              onChange={(e) => setForm((f) => ({ ...f, pic: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-text-muted mb-1">To *</label>
              <input
                className="input w-full"
                placeholder="email@company.com"
                value={form.toEmail}
                onChange={(e) => setForm((f) => ({ ...f, toEmail: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">CC</label>
              <input
                className="input w-full"
                placeholder="cc1@..., cc2@..."
                value={form.ccEmails}
                onChange={(e) => setForm((f) => ({ ...f, ccEmails: e.target.value }))}
              />
            </div>
          </div>
        </div>

        <div className="card p-4 space-y-3">
          <h2 className="text-sm font-semibold text-text">Rate Config</h2>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-text-muted mb-1">POL (blank = HPH+HCM)</label>
              <input
                className="input w-full"
                placeholder="HPH / HCM"
                value={form.pol}
                onChange={(e) => setForm((f) => ({ ...f, pol: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Markup (USD/cont)</label>
              <input
                className="input w-full"
                type="number"
                min={0}
                value={form.markup}
                onChange={(e) => setForm((f) => ({ ...f, markup: Number(e.target.value) }))}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Destinations</label>
            <textarea
              className="input w-full h-16 resize-none font-mono text-xs"
              value={form.destinations}
              onChange={(e) => setForm((f) => ({ ...f, destinations: e.target.value }))}
            />
          </div>
        </div>

        <div className="card p-4 space-y-3">
          <h2 className="text-sm font-semibold text-text">Email Content</h2>

          <div>
            <label className="block text-xs text-text-muted mb-1">Subject</label>
            <input
              className="input w-full"
              placeholder="Auto: Rate Update Wxx — Customer"
              value={form.subject}
              onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Intro</label>
            <textarea
              className="input w-full h-20 resize-none text-xs"
              placeholder={config?.intro_default || "Opening message..."}
              value={form.intro}
              onChange={(e) => setForm((f) => ({ ...f, intro: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Closing</label>
            <textarea
              className="input w-full h-20 resize-none text-xs"
              placeholder={config?.closing_default || "Closing message..."}
              value={form.closing}
              onChange={(e) => setForm((f) => ({ ...f, closing: e.target.value }))}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <button className="btn btn-secondary flex-1" onClick={handlePreview} disabled={loading !== null}>
            {loading === "preview" ? (
              <span className="flex items-center gap-2 justify-center">
                <SpinnerIcon className="w-4 h-4 animate-spin" /> Querying...
              </span>
            ) : "Preview"}
          </button>
          <button
            className={`btn flex-1 ${
              preview && !preview.is_blocked
                ? "btn-primary"
                : "opacity-40 cursor-not-allowed bg-surface border border-border text-text-muted"
            }`}
            onClick={handleSend}
            disabled={!preview || preview.is_blocked || loading !== null}
          >
            {loading === "send" ? (
              <span className="flex items-center gap-2 justify-center">
                <SpinnerIcon className="w-4 h-4 animate-spin" /> Sending...
              </span>
            ) : !preview ? "Preview first" : preview.is_blocked ? "Blocked" : "Approve & Send"}
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-sm text-red-400">{error}</div>
        )}
        {sendResult && (
          <div className={`rounded-lg px-3 py-2 text-sm ${
            sendResult.ok ? "bg-green-500/10 border border-green-500/30 text-green-400" : "bg-red-500/10 border border-red-500/30 text-red-400"
          }`}>{sendResult.msg}</div>
        )}
      </div>

      {/* RIGHT: Preview */}
      <div className="space-y-3">
        {preview ? (
          <>
            {preview.is_blocked ? (
              <div className="rounded-lg bg-red-500/15 border border-red-500/40 px-4 py-3">
                <p className="text-sm font-semibold text-red-400">{preview.warn_msg}</p>
              </div>
            ) : preview.warn_msg ? (
              <div className="rounded-lg bg-yellow-500/15 border border-yellow-500/40 px-4 py-3">
                <p className="text-sm font-semibold text-yellow-400">{preview.warn_msg}</p>
              </div>
            ) : (
              <div className="rounded-lg bg-green-500/10 border border-green-500/30 px-4 py-2">
                <p className="text-sm text-green-400">
                  {preview.row_count} routes — {preview.dests_found} dests — POL: {preview.pol_queried.join(", ")}
                  {preview.days_used && preview.days_used > 30 && (
                    <span className="ml-2 text-amber-400 font-semibold text-xs">⚠ fallback {preview.days_used}d</span>
                  )}
                </p>
                {preview.route_debug && Object.keys(preview.route_debug).length > 0 && (
                  <details className="mt-1">
                    <summary className="text-xs text-green-600 cursor-pointer hover:text-green-400">
                      Route debug ({Object.keys(preview.route_debug).length} routes)
                    </summary>
                    <div className="mt-1 space-y-0.5">
                      {Object.entries(preview.route_debug).map(([dest, info]) => (
                        <p key={dest} className="text-[10px] text-text-muted font-mono">{info}</p>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}

            <div className="card p-3">
              <p className="text-xs text-text-muted mb-0.5">Subject</p>
              <p className="text-sm font-medium text-text">{preview.subject}</p>
            </div>

            <div className="card overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <span className="text-xs font-semibold text-text-muted">Email Preview</span>
                <span className="text-xs text-text-muted">{preview.row_count} rows</span>
              </div>
              <div className="overflow-auto max-h-[600px] p-3 bg-white">
                <div className="text-[13px]" dangerouslySetInnerHTML={{ __html: preview.html }} />
              </div>
            </div>
          </>
        ) : (
          <div className="card p-8 flex flex-col items-center justify-center text-center min-h-[300px]">
            <MailIcon className="w-10 h-10 text-text-muted mb-3 opacity-40" />
            <p className="text-sm text-text-muted">Select a customer and click Preview</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared Components
// ═══════════════════════════════════════════════════════════════════════════

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    blue:   "bg-blue-500/10 border-blue-500/20 text-blue-400",
    green:  "bg-green-500/10 border-green-500/20 text-green-400",
    amber:  "bg-amber-500/10 border-amber-500/20 text-amber-400",
    purple: "bg-purple-500/10 border-purple-500/20 text-purple-400",
  };

  return (
    <div className={`rounded-lg border px-3 py-2.5 ${colorMap[color] || colorMap.blue}`}>
      <p className="text-lg font-bold">{value.toLocaleString()}</p>
      <p className="text-[11px] opacity-70">{label}</p>
    </div>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function MailIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      viewBox="0 0 24 24">
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}
