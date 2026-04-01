"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
  LineChart, Line,
} from "recharts";

/* ═══════════════════════════════════════════════════════════
   Reports — 6 tabs: Revenue, Carrier, Customer, Team KPI,
   Intelligence, Sales Report
   /dashboard/reports
   ═══════════════════════════════════════════════════════════ */

const TABS = [
  { key: "revenue", label: "Revenue Overview", icon: "📊" },
  { key: "carrier", label: "Carrier Performance", icon: "🚢" },
  { key: "customer", label: "Customer Analytics", icon: "👥" },
  { key: "team", label: "Team KPI", icon: "🎯" },
  { key: "intelligence", label: "Intelligence", icon: "🧠" },
  { key: "sales", label: "Sales Report", icon: "💰" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export default function ReportsPage() {
  const [tab, setTab] = useState<TabKey>("revenue");

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-text">Reports</h1>
        <p className="text-sm text-text-muted mt-0.5">Analytics & Performance Insights</p>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 p-1 bg-surface rounded-xl border border-border w-fit overflow-x-auto max-w-full">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
              tab === t.key
                ? "bg-white text-text shadow-sm border border-border"
                : "text-text-muted hover:text-text hover:bg-surface-hover"
            }`}
          >
            <span className="mr-1.5">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === "revenue" && <RevenueTab />}
      {tab === "carrier" && <CarrierTab />}
      {tab === "customer" && <CustomerTab />}
      {tab === "team" && <TeamKPITab />}
      {tab === "intelligence" && <IntelligenceTab />}
      {tab === "sales" && <SalesReportTab />}
    </div>
  );
}

/* ── Tab 1: Revenue Overview ──────────────────────────────── */
function RevenueTab() {
  const [data, setData] = useState<{
    revenue_timeline: { month: string; revenue: number; profit: number; shipments: number }[];
    region_summary: { name: string; min_price: number; avg_price: number; rates: number }[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/dashboard/charts`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!data?.revenue_timeline?.length) return <EmptyState text="No revenue data available" />;

  const timeline = data.revenue_timeline;
  const latest = timeline[timeline.length - 1] || { revenue: 0, profit: 0, shipments: 0 };
  const prev = timeline[timeline.length - 2] || { revenue: 0, profit: 0, shipments: 0 };
  const revChange = prev.revenue ? (((latest.revenue - prev.revenue) / prev.revenue) * 100).toFixed(1) : "0";
  const profitChange = prev.profit ? (((latest.profit - prev.profit) / prev.profit) * 100).toFixed(1) : "0";

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard label="Revenue (This Month)" value={`$${(latest.revenue / 1000).toFixed(1)}K`} change={`${Number(revChange) >= 0 ? "+" : ""}${revChange}%`} positive={Number(revChange) >= 0} />
        <KPICard label="Profit (This Month)" value={`$${(latest.profit / 1000).toFixed(1)}K`} change={`${Number(profitChange) >= 0 ? "+" : ""}${profitChange}%`} positive={Number(profitChange) >= 0} />
        <KPICard label="Shipments" value={String(latest.shipments)} change="This month" />
        <KPICard label="Active Routes" value={String(data.region_summary?.length || 0)} change="Regions" />
      </div>

      {/* Revenue Chart */}
      <div className="card">
        <h3 className="text-sm font-semibold text-text mb-4">Revenue & Profit Timeline</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={timeline} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
            <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
            <RTooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)", fontSize: 12 }} formatter={(v) => [`$${Number(v).toLocaleString()}`, ""]} />
            <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} name="Revenue" />
            <Bar dataKey="profit" fill="#10b981" radius={[4, 4, 0, 0]} name="Profit" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Top Routes */}
      {data.region_summary?.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-text mb-3">Top Routes by Rate Volume</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 text-text-muted font-medium">Region</th>
                <th className="text-right py-2 text-text-muted font-medium">Min Price</th>
                <th className="text-right py-2 text-text-muted font-medium">Avg Price</th>
                <th className="text-right py-2 text-text-muted font-medium">Rates</th>
              </tr>
            </thead>
            <tbody>
              {data.region_summary.slice(0, 10).map((r) => (
                <tr key={r.name} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                  <td className="py-2 font-medium text-text">{r.name}</td>
                  <td className="py-2 text-right text-text-secondary">${r.min_price.toLocaleString()}</td>
                  <td className="py-2 text-right text-text-secondary">${r.avg_price.toLocaleString()}</td>
                  <td className="py-2 text-right"><span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent font-semibold">{r.rates}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Tab 2: Carrier Performance ───────────────────────────── */
function CarrierTab() {
  const [data, setData] = useState<{
    carrier_grades: { carrier: string; score: number; grade: string; reliability: number }[];
    carrier_profit: { carrier: string; profit: number }[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/dashboard/charts`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!data?.carrier_grades?.length && !data?.carrier_profit?.length) return <EmptyState text="No carrier data available" />;

  const grades = data.carrier_grades || [];
  const profits = data.carrier_profit || [];
  const totalProfit = profits.reduce((s, c) => s + c.profit, 0);

  return (
    <div className="space-y-5">
      {/* Carrier Profit Chart */}
      {profits.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-text mb-4">Profit by Carrier</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={profits} layout="vertical" barSize={18}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" tick={{ fontSize: 11 }} stroke="var(--text-muted)" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
              <YAxis type="category" dataKey="carrier" tick={{ fontSize: 11 }} stroke="var(--text-muted)" width={50} />
              <RTooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)", fontSize: 12 }} formatter={(v) => [`$${Number(v).toLocaleString()}`, "Profit"]} />
              <Bar dataKey="profit" radius={[0, 4, 4, 0]}>
                {profits.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Carrier Grades Table */}
      {grades.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-text mb-3">Carrier Scorecard</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 text-text-muted font-medium">Carrier</th>
                <th className="text-center py-2 text-text-muted font-medium">Grade</th>
                <th className="text-right py-2 text-text-muted font-medium">Score</th>
                <th className="text-right py-2 text-text-muted font-medium">Reliability</th>
                <th className="text-right py-2 text-text-muted font-medium">Volume Share</th>
              </tr>
            </thead>
            <tbody>
              {grades.map((c) => {
                const share = totalProfit ? ((profits.find(p => p.carrier === c.carrier)?.profit || 0) / totalProfit * 100).toFixed(1) : "0";
                return (
                  <tr key={c.carrier} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                    <td className="py-2.5 font-semibold text-text">{c.carrier}</td>
                    <td className="py-2.5 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        c.grade === "A" ? "bg-success/10 text-success" :
                        c.grade === "B" ? "bg-accent/10 text-accent" :
                        c.grade === "C" ? "bg-warning/10 text-warning" : "bg-danger/10 text-danger"
                      }`}>{c.grade}</span>
                    </td>
                    <td className="py-2.5 text-right text-text-secondary">{c.score.toFixed(1)}</td>
                    <td className="py-2.5 text-right text-text-secondary">{(c.reliability * 100).toFixed(0)}%</td>
                    <td className="py-2.5 text-right"><span className="text-text-muted">{share}%</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Tab 3: Customer Analytics ────────────────────────────── */
function CustomerTab() {
  const [customers, setCustomers] = useState<{ customer: string; shipments: number }[]>([]);
  const [churn, setChurn] = useState<{ customer_code: string; risk: string; reason: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/dashboard/charts`).then(r => r.json()).catch(() => null),
      fetch(`${API_URL}/api/intelligence/churn`).then(r => r.json()).catch(() => null),
    ]).then(([chartData, churnData]) => {
      if (chartData?.customer_activity) setCustomers(chartData.customer_activity);
      if (churnData?.customers) setChurn(churnData.customers);
      else if (Array.isArray(churnData)) setChurn(churnData);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!customers.length && !churn.length) return <EmptyState text="No customer data available" />;

  const riskColor = (risk: string) => {
    const r = risk?.toLowerCase();
    if (r === "high" || r === "critical") return "bg-danger/10 text-danger";
    if (r === "medium" || r === "warning") return "bg-warning/10 text-warning";
    return "bg-success/10 text-success";
  };

  return (
    <div className="space-y-5">
      {/* Top Customers Chart */}
      {customers.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-text mb-4">Top Customers by Shipment Volume</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={customers.slice(0, 10)} barSize={24}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="customer" tick={{ fontSize: 10, angle: -30 }} stroke="var(--text-muted)" height={50} />
              <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
              <RTooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)", fontSize: 12 }} />
              <Bar dataKey="shipments" fill="#6366f1" radius={[4, 4, 0, 0]} name="Shipments">
                {customers.slice(0, 10).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Churn Risk Table */}
      {churn.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-text mb-3">Customer Churn Risk</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 text-text-muted font-medium">Customer</th>
                <th className="text-center py-2 text-text-muted font-medium">Risk Level</th>
                <th className="text-left py-2 text-text-muted font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {churn.map((c) => (
                <tr key={c.customer_code} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                  <td className="py-2.5 font-semibold text-text">{c.customer_code}</td>
                  <td className="py-2.5 text-center">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${riskColor(c.risk)}`}>{c.risk}</span>
                  </td>
                  <td className="py-2.5 text-text-secondary">{c.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Tab 4: Team KPI ──────────────────────────────────────── */
function TeamKPITab() {
  const [team, setTeam] = useState<{ name: string; role: string; active_quotes: number; won_quotes: number; active_shipments: number; revenue: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/team`)
      .then(r => r.json())
      .then(data => {
        if (data?.members) setTeam(data.members);
        else if (Array.isArray(data)) setTeam(data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!team.length) return <EmptyState text="No team data available" />;

  return (
    <div className="space-y-5">
      <div className="card">
        <h3 className="text-sm font-semibold text-text mb-3">Team Performance</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 text-text-muted font-medium">Member</th>
              <th className="text-left py-2 text-text-muted font-medium">Role</th>
              <th className="text-right py-2 text-text-muted font-medium">Active Quotes</th>
              <th className="text-right py-2 text-text-muted font-medium">Won</th>
              <th className="text-right py-2 text-text-muted font-medium">Shipments</th>
              <th className="text-right py-2 text-text-muted font-medium">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {team.map((m) => (
              <tr key={m.name} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                <td className="py-2.5 font-semibold text-text">{m.name}</td>
                <td className="py-2.5">
                  <span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px] font-medium">{m.role || "Member"}</span>
                </td>
                <td className="py-2.5 text-right text-text-secondary">{m.active_quotes ?? "—"}</td>
                <td className="py-2.5 text-right text-success font-semibold">{m.won_quotes ?? "—"}</td>
                <td className="py-2.5 text-right text-text-secondary">{m.active_shipments ?? "—"}</td>
                <td className="py-2.5 text-right font-semibold text-text">{m.revenue ? `$${m.revenue.toLocaleString()}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Shared Components ────────────────────────────────────── */
function KPICard({ label, value, change, positive }: { label: string; value: string; change: string; positive?: boolean }) {
  return (
    <div className="card !p-4">
      <p className="text-[11px] text-text-muted font-medium">{label}</p>
      <p className="text-2xl font-bold text-text mt-1 tracking-tight">{value}</p>
      <p className={`text-[11px] mt-1 font-medium ${positive === true ? "text-success" : positive === false ? "text-danger" : "text-text-muted"}`}>
        {change}
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card !p-4">
            <div className="h-3 w-20 bg-border rounded mb-2" />
            <div className="h-7 w-16 bg-border rounded" />
          </div>
        ))}
      </div>
      <div className="card h-80">
        <div className="h-4 w-32 bg-border rounded mb-4" />
        <div className="h-64 bg-border/50 rounded-lg" />
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="card !py-16 text-center">
      <p className="text-4xl mb-3">📭</p>
      <p className="text-sm text-text-muted">{text}</p>
    </div>
  );
}

/* ── Tab 5: Intelligence (Sprint 2 Skeleton) ──────────── */
function IntelligenceTab() {
  return (
    <div className="space-y-5">
      {/* Intro Banner */}
      <div className="card !p-4 bg-accent/5 border-accent/20">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🧠</span>
          <div>
            <p className="text-sm font-semibold text-text">Freight Intelligence Platform</p>
            <p className="text-xs text-text-muted mt-0.5">AI-powered rate analysis, anomaly detection, and market forecasting — powered by DuckDB</p>
          </div>
        </div>
      </div>

      {/* Section 1: Market Benchmark */}
      <div className="card overflow-hidden">
        <div className="p-5 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent" fill="none" stroke="currentColor" strokeWidth="1.75" viewBox="0 0 24 24">
                  <path d="M3 3v18h18" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M18 17V9" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M13 17V5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M8 17v-3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text">Market Benchmark</h3>
                <p className="text-xs text-text-muted mt-0.5">Rate envelope across carriers for your lanes</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filter Row (non-functional placeholder) */}
        <div className="p-4 bg-surface-hover/50 border-b border-border">
          <div className="flex flex-wrap gap-3">
            <div className="flex-1 min-w-[120px]">
              <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider block mb-1">POL</label>
              <select className="select !text-xs !py-1.5" disabled>
                <option>HPH</option>
                <option>HCM</option>
              </select>
            </div>
            <div className="flex-1 min-w-[120px]">
              <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider block mb-1">POD</label>
              <select className="select !text-xs !py-1.5" disabled>
                <option>All Destinations</option>
                <option>LAX</option>
                <option>NYC</option>
              </select>
            </div>
            <div className="flex-1 min-w-[120px]">
              <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider block mb-1">Container</label>
              <select className="select !text-xs !py-1.5" disabled>
                <option>40HQ</option>
                <option>20GP</option>
              </select>
            </div>
          </div>
        </div>

        {/* Placeholder Chart Area */}
        <div className="p-5">
          <div className="relative h-52 rounded-xl bg-gradient-to-br from-surface-hover to-border/30 flex flex-col items-center justify-center">
            <div className="animate-pulse space-y-3 w-full px-8">
              {/* Fake envelope bars */}
              <div className="flex items-end gap-1 justify-center h-24">
                {[35, 55, 75, 90, 100, 85, 70, 50, 40, 30, 25, 45, 65, 80].map((h, i) => (
                  <div key={i} className="w-6 rounded-t bg-accent/20" style={{ height: `${h}%` }} />
                ))}
              </div>
              {/* Labels */}
              <div className="flex justify-between px-4">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-success" />
                  <span className="text-[10px] text-text-muted">Low $1,843</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-accent" />
                  <span className="text-[10px] text-text-muted">Avg $4,893</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-danger" />
                  <span className="text-[10px] text-text-muted">High $7,448</span>
                </div>
              </div>
            </div>
            <p className="text-xs text-text-muted mt-3">Benchmark visualization loading...</p>
          </div>
        </div>
      </div>

      {/* Section 2: Carrier Scorecard */}
      <div className="card overflow-hidden relative">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-warning/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-warning" fill="none" stroke="currentColor" strokeWidth="1.75" viewBox="0 0 24 24">
                <path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-text">Carrier Scorecard</h3>
              <p className="text-xs text-text-muted mt-0.5">Compare carriers by cost, coverage, and consistency</p>
            </div>
          </div>
        </div>

        {/* Placeholder Table */}
        <div className="p-5">
          <div className="animate-pulse space-y-2">
            {/* Header Row */}
            <div className="grid grid-cols-5 gap-4 pb-2 border-b border-border">
              {["Carrier", "Cost Score", "Coverage", "Consistency", "Overall"].map((h) => (
                <div key={h} className="h-3 w-16 bg-border rounded" />
              ))}
            </div>
            {/* Data Rows */}
            {[...Array(6)].map((_, i) => (
              <div key={i} className="grid grid-cols-5 gap-4 py-2.5">
                <div className="h-3 w-12 bg-border/70 rounded" />
                <div className="h-3 w-10 bg-success/20 rounded" />
                <div className="h-3 w-14 bg-accent/20 rounded" />
                <div className="h-3 w-10 bg-warning/20 rounded" />
                <div className="h-3 w-8 bg-border/70 rounded" />
              </div>
            ))}
          </div>
        </div>

        {/* Coming Soon Overlay */}
        <div className="absolute inset-0 bg-surface/50 backdrop-blur-[1px] flex items-center justify-center">
          <span className="badge badge-info !text-xs !px-4 !py-1.5 shadow-md">
            🚧 Coming Soon — Sprint 2
          </span>
        </div>
      </div>

      {/* Section 3: Rate Forecast */}
      <div className="card overflow-hidden relative">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-success/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" strokeWidth="1.75" viewBox="0 0 24 24">
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points="16 7 22 7 22 13" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-text">Rate Forecast</h3>
              <p className="text-xs text-text-muted mt-0.5">4-week rate direction forecast by lane</p>
            </div>
          </div>
        </div>

        {/* Placeholder Chart */}
        <div className="p-5">
          <div className="animate-pulse h-48 rounded-xl bg-gradient-to-br from-surface-hover to-border/30 flex flex-col items-center justify-center">
            {/* Fake trend line */}
            <svg className="w-3/4 h-20 text-success/30" viewBox="0 0 200 60" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M0 45 C20 42 40 38 60 35 C80 32 100 40 120 28 C140 16 160 20 180 12 L200 8" />
              <path d="M0 45 C20 42 40 38 60 35 C80 32 100 40 120 28 C140 16 160 20 180 12 L200 8 L200 60 L0 60 Z" fill="currentColor" opacity="0.1" />
            </svg>
            <div className="flex gap-6 mt-3">
              <div className="flex items-center gap-1">
                <span className="w-6 h-0.5 bg-success rounded" />
                <span className="text-[10px] text-text-muted">Predicted</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-6 h-0.5 bg-border-strong rounded" style={{ borderTop: "1px dashed" }} />
                <span className="text-[10px] text-text-muted">Historical</span>
              </div>
            </div>
          </div>
        </div>

        {/* Coming Soon Overlay */}
        <div className="absolute inset-0 bg-surface/50 backdrop-blur-[1px] flex items-center justify-center">
          <span className="badge badge-info !text-xs !px-4 !py-1.5 shadow-md">
            🚧 Coming Soon — Sprint 3
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Tab 6: Sales Profit Monthly Report ───────────────────── */
function SalesReportTab() {
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return `${String(d.getFullYear()).slice(2)}${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [rows, setRows] = useState<SalesRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  // Generate last 12 months for dropdown
  const months = Array.from({ length: 12 }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - i);
    const yy = String(d.getFullYear()).slice(2);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const label = d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    return { value: `${yy}${mm}`, label };
  });

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/reports/monthly?month=${month}`)
      .then((r) => r.json())
      .then((data) => {
        setRows(data?.rows || (Array.isArray(data) ? data : []));
        setFetched(true);
      })
      .catch(() => { setRows([]); setFetched(true); })
      .finally(() => setLoading(false));
  }, [month]);

  const totals = rows.reduce(
    (acc, r) => ({
      buying: acc.buying + (r.buying || 0),
      selling: acc.selling + (r.selling || 0),
      profit_share: acc.profit_share + (r.profit_share || 0),
      carrier_kb: acc.carrier_kb + (r.carrier_kb || 0),
      tax: acc.tax + (r.tax || 0),
      net_profit: acc.net_profit + (r.net_profit || 0),
    }),
    { buying: 0, selling: 0, profit_share: 0, carrier_kb: 0, tax: 0, net_profit: 0 }
  );

  function exportCSV() {
    const headers = ["No", "Shipper", "POL", "POD", "Final Dest", "ETD", "ETA", "Carrier", "HBL", "Job No", "20'", "40'", "HC", "Buying", "Selling", "Profit Share", "Carrier KB", "Tax", "Net Profit"];
    const csvRows = [headers.join(",")];
    rows.forEach((r, i) => {
      csvRows.push([
        i + 1, `"${r.shipper || ""}"`, r.pol, r.pod, `"${r.final_dest || ""}"`,
        r.etd, r.eta, r.carrier, r.hbl || "", r.job_no || "",
        r.qty_20 || 0, r.qty_40 || 0, r.qty_hc || 0,
        r.buying?.toFixed(2) || "0", r.selling?.toFixed(2) || "0",
        r.profit_share?.toFixed(2) || "0", r.carrier_kb?.toFixed(2) || "0",
        r.tax?.toFixed(2) || "0", r.net_profit?.toFixed(2) || "0",
      ].join(","));
    });
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sales_report_${month}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <label className="block text-[10px] font-medium text-text-muted mb-1">Month</label>
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="select !text-xs !py-1.5 !w-40"
          >
            {months.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
        <button
          onClick={exportCSV}
          disabled={rows.length === 0}
          className="btn-primary !text-xs !py-1.5 !px-4 mt-4"
        >
          📥 Export CSV
        </button>
        <span className="text-xs text-text-muted mt-4">{rows.length} records</span>
      </div>

      {loading && <LoadingSkeleton />}

      {!loading && fetched && rows.length === 0 && (
        <EmptyState text={`No sales data for ${months.find(m => m.value === month)?.label || month}`} />
      )}

      {!loading && rows.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-xs min-w-[1200px]">
            <thead>
              <tr className="border-b border-border text-text-muted text-[10px] bg-surface-hover/50">
                <th className="text-left py-2 px-2 font-semibold w-8">#</th>
                <th className="text-left py-2 px-2 font-semibold">Shipper</th>
                <th className="text-left py-2 px-2 font-semibold">POL</th>
                <th className="text-left py-2 px-2 font-semibold">POD</th>
                <th className="text-left py-2 px-2 font-semibold">Final Dest</th>
                <th className="text-center py-2 px-2 font-semibold">ETD</th>
                <th className="text-center py-2 px-2 font-semibold">ETA</th>
                <th className="text-left py-2 px-2 font-semibold">Carrier</th>
                <th className="text-left py-2 px-2 font-semibold">HBL</th>
                <th className="text-left py-2 px-2 font-semibold">Job No</th>
                <th className="text-right py-2 px-2 font-semibold">20&apos;</th>
                <th className="text-right py-2 px-2 font-semibold">40&apos;</th>
                <th className="text-right py-2 px-2 font-semibold">HC</th>
                <th className="text-right py-2 px-2 font-semibold">Buying</th>
                <th className="text-right py-2 px-2 font-semibold">Selling</th>
                <th className="text-right py-2 px-2 font-semibold">P.Share</th>
                <th className="text-right py-2 px-2 font-semibold">Carr.KB</th>
                <th className="text-right py-2 px-2 font-semibold">Tax</th>
                <th className="text-right py-2 px-2 font-semibold">Net Profit</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.job_no || r.hbl || i}`} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                  <td className="py-2 px-2 text-text-muted">{i + 1}</td>
                  <td className="py-2 px-2 font-medium text-text truncate max-w-[120px]">{r.shipper || "—"}</td>
                  <td className="py-2 px-2 text-text-secondary">{r.pol || "—"}</td>
                  <td className="py-2 px-2 text-text-secondary">{r.pod || "—"}</td>
                  <td className="py-2 px-2 text-text-secondary truncate max-w-[100px]">{r.final_dest || "—"}</td>
                  <td className="py-2 px-2 text-center text-text-secondary whitespace-nowrap">{r.etd || "—"}</td>
                  <td className="py-2 px-2 text-center text-text-secondary whitespace-nowrap">{r.eta || "—"}</td>
                  <td className="py-2 px-2"><span className="badge badge-info !text-[9px]">{r.carrier || "—"}</span></td>
                  <td className="py-2 px-2 font-mono text-[10px] text-text-secondary">{r.hbl || "—"}</td>
                  <td className="py-2 px-2 font-mono text-[10px] text-text-secondary">{r.job_no || "—"}</td>
                  <td className="py-2 px-2 text-right text-text-secondary">{r.qty_20 || "—"}</td>
                  <td className="py-2 px-2 text-right text-text-secondary">{r.qty_40 || "—"}</td>
                  <td className="py-2 px-2 text-right text-text-secondary">{r.qty_hc || "—"}</td>
                  <td className="py-2 px-2 text-right font-mono">${(r.buying || 0).toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono">${(r.selling || 0).toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono text-text-secondary">${(r.profit_share || 0).toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono text-text-secondary">${(r.carrier_kb || 0).toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono text-danger/70">${(r.tax || 0).toLocaleString()}</td>
                  <td className={`py-2 px-2 text-right font-mono font-semibold ${(r.net_profit || 0) >= 0 ? "text-success" : "text-danger"}`}>
                    ${(r.net_profit || 0).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border bg-surface-hover/30 font-semibold">
                <td colSpan={13} className="py-2.5 px-2 text-right text-text-muted text-[10px] uppercase tracking-wider">Totals</td>
                <td className="py-2.5 px-2 text-right font-mono">${totals.buying.toLocaleString()}</td>
                <td className="py-2.5 px-2 text-right font-mono">${totals.selling.toLocaleString()}</td>
                <td className="py-2.5 px-2 text-right font-mono">${totals.profit_share.toLocaleString()}</td>
                <td className="py-2.5 px-2 text-right font-mono">${totals.carrier_kb.toLocaleString()}</td>
                <td className="py-2.5 px-2 text-right font-mono text-danger/70">${totals.tax.toLocaleString()}</td>
                <td className={`py-2.5 px-2 text-right font-mono font-bold text-sm ${totals.net_profit >= 0 ? "text-success" : "text-danger"}`}>
                  ${totals.net_profit.toLocaleString()}
                </td>
              </tr>
            </tfoot>
          </table>
          <div className="px-3 py-2 border-t border-border text-[10px] text-text-muted">
            Net Profit = Selling − Buying + Profit Share + Carrier KB − Tax (26.9%)
          </div>
        </div>
      )}
    </div>
  );
}

interface SalesRow {
  shipper: string;
  pol: string;
  pod: string;
  final_dest: string;
  etd: string;
  eta: string;
  carrier: string;
  hbl: string;
  job_no: string;
  qty_20: number;
  qty_40: number;
  qty_hc: number;
  buying: number;
  selling: number;
  profit_share: number;
  carrier_kb: number;
  tax: number;
  net_profit: number;
}
