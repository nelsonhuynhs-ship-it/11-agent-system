"use client";

import { API_URL } from "@/lib/api";
import ActionNeeded from "@/components/dashboard/ActionNeeded";
import { DashboardSkeleton } from "@/components/ui/Skeleton";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  ResponsiveContainer, Cell,
} from "recharts";

/* ═══════════════════════════════════════════════════════════
   Dashboard Home — LIVE KPI + Charts + Intelligence
   /dashboard
   ═══════════════════════════════════════════════════════════ */

const COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];
const SENT_COLORS: Record<string, string> = {
  TIGHTENING: "#ef4444", NORMAL: "#10b981", LOOSENING: "#3b82f6", QUIET: "#9ca3af",
};

interface ChartData {
  revenue_timeline: { month: string; revenue: number; profit: number; shipments: number }[];
  carrier_profit: { carrier: string; profit: number }[];
  customer_activity: { customer: string; shipments: number }[];
  market_timeline: { period: string; total_shipments: number; total_profit: number; active_customers: number; sentiment: string }[];
  carrier_grades: { carrier: string; score: number; grade: string; reliability: number }[];
  intelligence_4c: {
    capacity: { active_carriers: number; active_routes: number; rising_demand_routes: number; troubled_carriers: number };
    costing: { total_profit: number; sentiment: string; profit_trend: string };
    challenge: { active_challenges: number };
    chances: { total_opportunities: number; by_type: Record<string, number> };
  };
  region_summary: { name: string; min_price: number; avg_price: number; rates: number }[];
}

export default function DashboardHome() {
  const { data: charts, isLoading } = useQuery<ChartData>({
    queryKey: ['dashboard', 'charts'],
    queryFn: () => fetch(`${API_URL}/api/dashboard/charts`).then(r => r.json()),
    staleTime: 60 * 1000,
  });

  if (isLoading) return <DashboardSkeleton />;

  const ic = charts?.intelligence_4c;
  const capacity = ic?.capacity;
  const costing = ic?.costing;
  const challenge = ic?.challenge;
  const chances = ic?.chances;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text">Dashboard</h1>
          <p className="text-sm text-text-muted mt-0.5">Nelson Freight Intelligence Overview</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-text-muted">Last updated: just now</span>
          <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
        </div>
      </div>

      {/* Action Needed Widget */}
      <ActionNeeded />

      {/* 4C Intelligence Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger-children">
        <C4Card icon="🚢" label="Capacity" accent
          value={`${capacity?.active_carriers ?? 0} carriers`}
          detail={`${capacity?.active_routes ?? 0} routes · ${capacity?.rising_demand_routes ?? 0} rising`} />
        <C4Card icon="💰" label="Costing"
          value={`$${(costing?.total_profit ?? 0).toLocaleString()}`}
          detail={`${costing?.sentiment ?? "—"} · Trend ${costing?.profit_trend ?? "—"}`}
          warn={costing?.sentiment === "TIGHTENING"} />
        <C4Card icon="⚠️" label="Challenge"
          value={`${challenge?.active_challenges ?? 0}`}
          detail="Active market challenges"
          warn={(challenge?.active_challenges ?? 0) > 0} />
        <C4Card icon="🎯" label="Chances" accent
          value={`${chances?.total_opportunities ?? 0}`}
          detail="Business opportunities detected" />
      </div>

      {/* Region Summary */}
      {charts?.region_summary && charts.region_summary.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {charts.region_summary.map(r => (
            <div key={r.name} className="card p-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-text-muted">{r.name}</span>
                <span className="text-[10px] text-text-muted">{r.rates} rates</span>
              </div>
              <p className="text-lg font-bold text-text mt-1">
                ${r.min_price?.toLocaleString() ?? "—"}
              </p>
              <p className="text-[10px] text-text-muted">
                avg ${r.avg_price?.toLocaleString() ?? "—"} (40HQ HPH)
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Revenue Timeline */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-text mb-3">Revenue & Profit</h2>
          {charts?.revenue_timeline && charts.revenue_timeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={charts.revenue_timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="var(--color-text-muted)" />
                <YAxis tick={{ fontSize: 10 }} stroke="var(--color-text-muted)"
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
                <RTooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--color-border)" }}
                  formatter={(v: any) => [`$${Number(v || 0).toLocaleString()}`, ""]} />
                <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} name="Revenue" />
                <Bar dataKey="profit" fill="#10b981" radius={[4, 4, 0, 0]} name="Profit" />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </div>

        {/* Customer Activity */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-text mb-3">Top Customers</h2>
          {charts?.customer_activity && charts.customer_activity.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={charts.customer_activity} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" tick={{ fontSize: 10 }} stroke="var(--color-text-muted)" />
                <YAxis type="category" dataKey="customer" tick={{ fontSize: 10 }} width={90}
                  stroke="var(--color-text-muted)" />
                <RTooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--color-border)" }} />
                <Bar dataKey="shipments" fill="#06b6d4" radius={[0, 4, 4, 0]} name="Shipments">
                  {charts.customer_activity.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Carrier Grades */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-text mb-3">Carrier Reliability Grades</h2>
          {charts?.carrier_grades && charts.carrier_grades.length > 0 ? (
            <div className="space-y-2">
              {charts.carrier_grades.map((c, i) => (
                <div key={c.carrier} className="flex items-center gap-3">
                  <span className="w-24 text-xs text-text-secondary truncate">{c.carrier}</span>
                  <div className="flex-1 h-5 bg-surface-hover rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all"
                      style={{
                        width: `${c.score}%`,
                        background: c.grade.startsWith("A") ? "#10b981"
                          : c.grade.startsWith("B") ? "#6366f1"
                          : c.grade.startsWith("C") ? "#f59e0b" : "#ef4444",
                      }} />
                  </div>
                  <span className={`text-xs font-bold w-8 text-center px-1 py-0.5 rounded ${
                    c.grade.startsWith("A") ? "bg-green-100 text-green-700"
                    : c.grade.startsWith("B") ? "bg-indigo-100 text-indigo-700"
                    : "bg-yellow-100 text-yellow-700"
                  }`}>{c.grade}</span>
                  <span className="text-xs font-mono text-text-muted w-10 text-right">{c.score.toFixed(0)}</span>
                </div>
              ))}
            </div>
          ) : <Empty />}
        </div>

        {/* Market Sentiment */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-text mb-3">Market Sentiment (12 Months)</h2>
          {charts?.market_timeline && charts.market_timeline.length > 0 ? (
            <div className="space-y-1.5">
              {charts.market_timeline.map(m => (
                <div key={m.period} className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-text-muted w-14">{m.period}</span>
                  <span className="w-2 h-2 rounded-full" style={{ background: SENT_COLORS[m.sentiment] || "#9ca3af" }} />
                  <span className="text-[10px] w-20" style={{ color: SENT_COLORS[m.sentiment] || "#9ca3af" }}>
                    {m.sentiment}
                  </span>
                  <div className="flex-1 h-3 bg-surface-hover rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-400 rounded-full"
                      style={{ width: `${Math.min(100, (m.total_shipments / 25) * 100)}%` }} />
                  </div>
                  <span className="text-[10px] text-text-muted w-16 text-right">
                    {m.total_shipments} ships
                  </span>
                  <span className="text-[10px] font-mono text-text-muted w-16 text-right">
                    ${m.total_profit?.toLocaleString() ?? 0}
                  </span>
                </div>
              ))}
            </div>
          ) : <Empty />}
        </div>
      </div>

      {/* Carrier Profit */}
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-text mb-3">Profit by Carrier</h2>
        {charts?.carrier_profit && charts.carrier_profit.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={charts.carrier_profit}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="carrier" tick={{ fontSize: 10 }} stroke="var(--color-text-muted)" />
              <YAxis tick={{ fontSize: 10 }} stroke="var(--color-text-muted)"
                tickFormatter={(v: number) => `$${v.toLocaleString()}`} />
              <RTooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--color-border)" }}
                formatter={(v: any) => [`$${Number(v || 0).toLocaleString()}`, "Profit"]} />
              <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                {charts.carrier_profit.map((entry, i) => (
                  <Cell key={i} fill={entry.profit >= 0 ? "#10b981" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : <Empty />}
      </div>
    </div>
  );
}

function C4Card({ icon, label, value, detail, accent, warn }: {
  icon: string; label: string; value: string; detail: string; accent?: boolean; warn?: boolean;
}) {
  return (
    <div className={`card p-3 ${warn ? "border-l-2 border-l-red-400" : accent ? "border-l-2 border-l-accent" : ""}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-sm">{icon}</span>
        <p className="text-[11px] text-text-muted font-semibold">{label}</p>
      </div>
      <p className={`text-xl font-bold ${warn ? "text-red-500" : accent ? "text-accent" : "text-text"}`}>
        {value}
      </p>
      <p className="text-[10px] text-text-muted mt-0.5">{detail}</p>
    </div>
  );
}

function Empty() {
  return (
    <div className="h-[200px] flex items-center justify-center text-text-muted text-sm">
      Waiting for data...
    </div>
  );
}
