"use client";

import { useState, useEffect, useMemo } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Shipment Control Tower — 10 intelligence features
   /dashboard/shipments
   ═══════════════════════════════════════════════════════════ */

// ── Types ────────────────────────────────────────────────
interface Shipment {
  id: string; customer: string; type: string; stage: string;
  routing: string; carrier: string; container: string; quantity: number;
  etd: string; eta: string; ata: string;
  selling_rate: number; buying_rate: number; profit: number; profit_margin: string;
  delay_count: number; risk_level: string | null; risk_count: number;
  created_at: string; updated_at: string; source: string;
  stage_history: { stage: string; at: string; subject: string; source?: string }[];
  email_summary: string;
  email_alerts: { type: string; keyword: string; subject: string; timestamp: string }[];
}

interface CustomerInfo {
  name: string; risk: string; type: string; sla: string;
  shipment_count?: number; is_vip?: boolean;
}

interface CarrierFreetime {
  dry_total_days: number; reefer_total_days: number;
  power_free_days: number | null; power_free_hours: number | null;
  power_rate_usd_hour: number; dem_rate_vnd_day: number;
}

const REEFER_TYPES = ["20RF", "40RF", "RF", "REEFER"];
function isReefer(ct: string) { return REEFER_TYPES.some(r => ct.toUpperCase().includes(r)); }

// ── DEM/DET & Power Risk Calculator ───────────────────────
function calcCostRisks(s: { etd: string; carrier: string; container: string }, gateIn: string | null, rules: Record<string, CarrierFreetime>) {
  const risks: { type: string; detail: string; cls: string }[] = [];
  if (!gateIn || !s.etd) return risks;
  const cr = rules[s.carrier?.toUpperCase()] || rules[s.carrier];
  if (!cr) return risks;
  const giDate = new Date(gateIn);
  const etdDate = new Date(s.etd);
  const diffMs = etdDate.getTime() - giDate.getTime();
  const diffHours = Math.max(0, diffMs / 3600000);
  const diffDays = Math.max(0, Math.ceil(diffMs / 86400000));
  // DEM/DET
  const freeDays = isReefer(s.container) ? cr.reefer_total_days : cr.dry_total_days;
  if (diffDays > freeDays) {
    const over = diffDays - freeDays;
    const cost = over * cr.dem_rate_vnd_day;
    risks.push({ type: "DEM", detail: `DEM ${over}d × ${(cr.dem_rate_vnd_day/1000).toFixed(0)}k = ${(cost/1000).toFixed(0)}k VND`, cls: "text-red-600" });
  }
  // Power Charge (reefer)
  if (isReefer(s.container)) {
    const freeH = cr.power_free_hours ?? (cr.power_free_days ? cr.power_free_days * 24 : null);
    if (freeH != null && diffHours > freeH) {
      const overH = Math.ceil(diffHours - freeH);
      const cost = overH * cr.power_rate_usd_hour;
      risks.push({ type: "PWR", detail: `Power ${overH}h × $${cr.power_rate_usd_hour} = $${cost.toFixed(1)}`, cls: "text-orange-600" });
    }
  }
  return risks;
}

// ── Stage Config ─────────────────────────────────────────
const STAGES = [
  "BOOKING_CONFIRMED", "SI_SUBMITTED", "DRAFT_BL_ISSUED", "DRAFT_BL_CONFIRMED",
  "LOADED", "ATD", "ETA_UPDATE", "DN_SENT", "INVOICE_ISSUED", "PAYMENT_CONFIRMED",
];
const DISPLAY_STAGES = ["Booking", "Gate In", "Sailing", "Transit", "Arrival", "Delivered"];
const STAGE_MAP: Record<string, number> = {
  BOOKING_PENDING: 0, BOOKING_CONFIRMED: 0, SI_SUBMITTED: 1, DRAFT_BL_ISSUED: 1, DRAFT_BL_CONFIRMED: 1,
  LOADED: 2, ATD: 2, ETA_UPDATE: 3, DN_SENT: 4, INVOICE_ISSUED: 5, PAYMENT_CONFIRMED: 5,
};

// ── Helpers ──────────────────────────────────────────────
function daysBetween(from: string, to?: Date) {
  if (!from) return 0;
  return Math.floor(((to || new Date()).getTime() - new Date(from).getTime()) / 86400000);
}
function fmtDate(iso: string) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }); } catch { return iso; }
}

// ── Month Filter Helpers ─────────────────────────────────
const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function getMonthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(key: string) {
  if (key === "ALL") return "All";
  const [y, m] = key.split("-");
  return `${MONTH_NAMES[parseInt(m) - 1]} ${y}`;
}

function shipmentInMonth(s: { etd: string; ata: string }, monthKey: string): boolean {
  if (monthKey === "ALL") return true;
  // Shipment belongs to a month by sailing date: ETD or ATD (actual departure)
  for (const dateStr of [s.etd, s.ata]) {
    if (!dateStr) continue;
    try {
      const d = new Date(dateStr);
      if (getMonthKey(d) === monthKey) return true;
    } catch { /* skip */ }
  }
  return false;
}

function getAvailableMonths(shipments: { etd: string; ata: string }[]): string[] {
  const months = new Set<string>();
  for (const s of shipments) {
    for (const dateStr of [s.etd, s.ata]) {
      if (!dateStr) continue;
      try { months.add(getMonthKey(new Date(dateStr))); } catch { /* skip */ }
    }
  }
  return Array.from(months).sort().reverse(); // newest first
}

// ── Feature 1: Health Score ──────────────────────────────
function calcHealth(s: Shipment): number {
  let score = 0;
  // Profit (30pts)
  const margin = s.selling_rate > 0 ? (s.profit / s.selling_rate) * 100 : 0;
  if (margin >= 15) score += 30;
  else if (margin >= 5) score += 20;
  else if (margin >= 0) score += 10;
  // ETA Risk (25pts)
  const etaDays = s.eta ? daysBetween(new Date().toISOString().slice(0, 10), new Date(s.eta)) * -1 : 99;
  const daysToEta = s.eta ? Math.floor((new Date(s.eta).getTime() - Date.now()) / 86400000) : 99;
  if (daysToEta > 14) score += 25;
  else if (daysToEta > 7) score += 20;
  else if (daysToEta > 3) score += 12;
  else if (daysToEta > 0) score += 5;
  // Stage (25pts)
  const si = STAGES.indexOf(s.stage);
  if (si >= 0) score += Math.round(((si + 1) / STAGES.length) * 25);
  // Data completeness (20pts)
  let data = 20;
  if (!s.buying_rate) data -= 5;
  if (!s.selling_rate) data -= 5;
  if (!s.eta) data -= 5;
  if (!s.carrier) data -= 5;
  score += Math.max(0, data);
  return Math.min(100, Math.max(0, score));
}

function healthBadge(score: number) {
  if (score >= 80) return { emoji: "🟢", label: "Healthy", cls: "bg-emerald-50 text-emerald-700" };
  if (score >= 50) return { emoji: "🟡", label: "Monitor", cls: "bg-amber-50 text-amber-700" };
  return { emoji: "🔴", label: "Critical", cls: "bg-red-50 text-red-700" };
}

// ── Feature 3: ETA Intelligence ──────────────────────────
function etaStatus(s: Shipment) {
  if (s.ata) return { dot: "✅", label: "Delivered", cls: "text-gray-400", days: "" };
  if (!s.eta) return { dot: "❓", label: "No ETA", cls: "text-gray-400", days: "" };
  const d = Math.floor((new Date(s.eta).getTime() - Date.now()) / 86400000);
  if (d < 0) return { dot: "🔴", label: "Overdue", cls: "text-red-600 font-bold", days: `${d}d` };
  if (d <= 5) return { dot: "🔵", label: "Arriving", cls: "text-blue-600 font-semibold", days: `${d}d` };
  if (s.delay_count > 0) return { dot: "🟡", label: "At Risk", cls: "text-amber-600", days: `${d}d` };
  return { dot: "🟢", label: "On Track", cls: "text-emerald-600", days: `${d}d` };
}

// ── Feature 5: Profit Intelligence ───────────────────────
function profitSignal(profit: number, avgProfit: number) {
  if (profit < 0) return { icon: "🔴", label: "Loss", cls: "text-red-600 font-bold" };
  if (avgProfit > 0 && profit < avgProfit * 0.5) return { icon: "🟡", label: "Low", cls: "text-amber-600" };
  if (avgProfit > 0 && profit > avgProfit * 1.5) return { icon: "🟢", label: "High", cls: "text-emerald-600 font-semibold" };
  return { icon: "⚪", label: "Normal", cls: "text-text" };
}

// ── Feature 6: Customer Risk Badge ───────────────────────
function customerBadge(customer: string, cusMap: Record<string, CustomerInfo>) {
  const info = cusMap[customer.toUpperCase()] || cusMap[customer];
  if (!info) return { icon: "", cls: "" };
  if (info.is_vip || (info.shipment_count && info.shipment_count > 20)) return { icon: "⭐", cls: "text-yellow-500" };
  if (info.risk === "LOW") return { icon: "💚", cls: "" };
  if (info.risk === "MEDIUM") return { icon: "🟡", cls: "" };
  if (info.risk === "HIGH") return { icon: "🔴", cls: "" };
  return { icon: "💚", cls: "" };
}

// ── Feature 8: Aging ─────────────────────────────────────
function agingBadge(createdAt: string) {
  const d = daysBetween(createdAt);
  if (d <= 14) return { label: `${d}d`, cls: "text-emerald-600" };
  if (d <= 30) return { label: `${d}d`, cls: "text-text-muted" };
  if (d <= 45) return { label: `${d}d`, cls: "text-amber-600" };
  return { label: `${d}d`, cls: "text-red-600 font-bold animate-pulse" };
}

// ── Feature 9: Smart Suggestions ─────────────────────────
function getSuggestion(s: Shipment, avgProfit: number) {
  if (s.stage === "DN_SENT" && s.profit > 0) return { icon: "🧾", text: "Ready to invoice" };
  if (s.profit < 0) return { icon: "⚠️", text: "Review buy rate" };
  const eta_d = s.eta ? Math.floor((new Date(s.eta).getTime() - Date.now()) / 86400000) : 99;
  if (eta_d <= 3 && eta_d >= 0 && !s.ata) return { icon: "📦", text: "Prepare arrival" };
  const stageAge = s.updated_at ? daysBetween(s.updated_at) : 0;
  if (stageAge > 14 && s.stage !== "PAYMENT_CONFIRMED") return { icon: "🔒", text: `Follow up ${s.carrier}` };
  if (s.stage === "INVOICE_ISSUED" && daysBetween(s.created_at) > 30) return { icon: "💰", text: "Chase payment" };
  return null;
}

// ═══════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════
export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [customers, setCustomers] = useState<Record<string, CustomerInfo>>({});
  const [avgProfit, setAvgProfit] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState("health");
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [gateInData, setGateInData] = useState<Record<string, string>>({});
  const [freetimeRules, setFreetimeRules] = useState<Record<string, CarrierFreetime>>({});
  const [selectedMonth, setSelectedMonth] = useState(() => getMonthKey(new Date()));

  // Load data from 4 existing APIs
  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/shipments`).then(r => r.json()),
      fetch(`${API_URL}/api/customers`).then(r => r.json()).catch(() => ({ customers: [] })),
      fetch(`${API_URL}/api/dashboard/charts`).then(r => r.json()).catch(() => ({})),
      fetch(`${API_URL}/api/carrier/freetime`).then(r => r.json()).catch(() => ({ carriers: {} })),
    ]).then(([shipData, cusData, chartData, ftData]) => {
      setShipments(shipData.shipments || []);
      // Build customer lookup
      const cmap: Record<string, CustomerInfo> = {};
      for (const c of (cusData.customers || [])) {
        cmap[c.name?.toUpperCase()] = c;
        cmap[c.name] = c;
      }
      setCustomers(cmap);
      // Avg profit from chart data
      const cp = chartData.carrier_profit || [];
      if (cp.length > 0) {
        const total = cp.reduce((s: number, x: { profit: number }) => s + x.profit, 0);
        setAvgProfit(total / cp.length);
      }
      // Carrier freetime rules
      setFreetimeRules(ftData.carriers || {});
      // Load saved gate-in data from localStorage
      try {
        const saved = localStorage.getItem("shipment_gatein");
        if (saved) setGateInData(JSON.parse(saved));
      } catch { /* skip */ }
    }).finally(() => setLoading(false));
  }, []);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_URL}/api/shipments`).then(r => r.json())
        .then(data => { if (data.shipments) setShipments(data.shipments); })
        .catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Save gate-in to localStorage
  function setGateIn(shipId: string, value: string) {
    setGateInData(prev => {
      const next = { ...prev, [shipId]: value };
      try { localStorage.setItem("shipment_gatein", JSON.stringify(next)); } catch { /* skip */ }
      return next;
    });
  }

  // ── Computed ──────────────────────────────────────────
  const enriched = useMemo(() =>
    shipments.map(s => ({ ...s, health: calcHealth(s) })),
  [shipments]);

  // Month filter — applied BEFORE all other filters
  const availableMonths = useMemo(() => getAvailableMonths(shipments), [shipments]);
  const monthFiltered = useMemo(() =>
    enriched.filter(s => shipmentInMonth(s, selectedMonth)),
  [enriched, selectedMonth]);

  const active = monthFiltered.filter(s => s.stage !== "PAYMENT_CONFIRMED");
  const completed = monthFiltered.filter(s => s.stage === "PAYMENT_CONFIRMED");
  const critical = monthFiltered.filter(s => s.health < 50);
  const delayed = monthFiltered.filter(s => s.delay_count > 0);
  const totalProfit = monthFiltered.reduce((s, x) => s + (x.profit || 0), 0);
  const totalRevenue = monthFiltered.reduce((s, x) => s + (x.selling_rate || 0), 0);

  // Feature 2: Priority Actions
  const priorityActions = useMemo(() => {
    const actions: { icon: string; level: string; id: string; customer: string; msg: string }[] = [];
    for (const s of monthFiltered) {
      if (s.stage === "PAYMENT_CONFIRMED") continue;
      const etaD = s.eta ? Math.floor((new Date(s.eta).getTime() - Date.now()) / 86400000) : 99;
      if (etaD >= 0 && etaD <= 5 && !s.ata) actions.push({ icon: "⏰", level: "HIGH", id: s.id, customer: s.customer, msg: `ETA in ${etaD} days` });
      if (s.profit < 0) actions.push({ icon: "💸", level: "HIGH", id: s.id, customer: s.customer, msg: `Negative profit $${s.profit.toLocaleString()}` });
      if (!s.buying_rate) actions.push({ icon: "⚠️", level: "MED", id: s.id, customer: s.customer, msg: "Missing buy rate" });
      if (s.delay_count >= 2) actions.push({ icon: "🔴", level: "HIGH", id: s.id, customer: s.customer, msg: `Delayed ${s.delay_count}x` });
      const stageAge = s.updated_at ? daysBetween(s.updated_at) : 0;
      if (stageAge > 14) actions.push({ icon: "🔒", level: "MED", id: s.id, customer: s.customer, msg: `Stuck for ${stageAge}d` });
    }
    actions.sort((a, b) => (a.level === "HIGH" ? 0 : 1) - (b.level === "HIGH" ? 0 : 1));
    return actions.slice(0, 8);
  }, [monthFiltered]);

  // Feature 7: Route Heatmap
  const routeStats = useMemo(() => {
    const map: Record<string, { count: number; profit: number }> = {};
    for (const s of enriched) {
      const r = s.routing || "Unknown";
      if (!map[r]) map[r] = { count: 0, profit: 0 };
      map[r].count++;
      map[r].profit += s.profit || 0;
    }
    return Object.entries(map).map(([route, data]) => ({ route, ...data }))
      .sort((a, b) => b.count - a.count).slice(0, 5);
  }, [monthFiltered]);
  const maxRouteCount = routeStats[0]?.count || 1;

  // ── Filter & Sort ─────────────────────────────────────
  let filtered = monthFiltered;
  if (filter === "active") filtered = active;
  else if (filter === "critical") filtered = critical;
  else if (filter === "delayed") filtered = delayed;
  else if (filter === "completed") filtered = completed;
  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(s =>
      s.id.toLowerCase().includes(q) || s.customer.toLowerCase().includes(q) ||
      s.carrier.toLowerCase().includes(q) || s.routing.toLowerCase().includes(q)
    );
  }

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (sortCol) {
        case "health": va = a.health; vb = b.health; break;
        case "profit": va = a.profit; vb = b.profit; break;
        case "eta":
          va = a.eta ? new Date(a.eta).getTime() : 9e12;
          vb = b.eta ? new Date(b.eta).getTime() : 9e12; break;
        case "age":
          va = a.created_at ? new Date(a.created_at).getTime() : 9e12;
          vb = b.created_at ? new Date(b.created_at).getTime() : 9e12; break;
        default: va = a.health; vb = b.health;
      }
      return sortAsc ? va - vb : vb - va;
    });
    return arr;
  }, [filtered, sortCol, sortAsc]);

  function toggleSort(col: string) {
    if (sortCol === col) setSortAsc(!sortAsc);
    else { setSortCol(col); setSortAsc(col === "eta" || col === "age"); }
  }

  const sortIcon = (col: string) => sortCol === col ? (sortAsc ? " ▲" : " ▼") : "";

  if (loading) return <div className="p-12 text-center text-text-muted">Loading Control Tower...</div>;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-text">Shipment Control Tower</h1>
        <p className="text-sm text-text-muted mt-0.5">
          {enriched.length} total · {monthFiltered.length} in {monthLabel(selectedMonth)} ·{" "}
          <span className="text-accent font-medium">Logistics Intelligence</span>
        </p>
      </div>

      {/* Month Tabs */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {[getMonthKey(new Date()), ...availableMonths.filter(m => m !== getMonthKey(new Date())).slice(0, 5), "ALL"].filter(
          (v, i, arr) => arr.indexOf(v) === i
        ).map(m => (
          <button key={m} onClick={() => setSelectedMonth(m)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer whitespace-nowrap transition-colors ${
              selectedMonth === m
                ? "bg-accent text-white"
                : "bg-surface-hover text-text-secondary hover:text-text"
            }`}>
            {m === getMonthKey(new Date()) ? `📅 ${monthLabel(m)}` : monthLabel(m)}
          </button>
        ))}
      </div>

      {/* KPI Row — month-aware */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        <div className="card p-3 border-l-2 border-l-accent">
          <p className="text-[10px] text-text-muted">Shipments</p>
          <p className="text-2xl font-bold text-accent">{monthFiltered.length}</p>
        </div>
        <div className="card p-3">
          <p className="text-[10px] text-text-muted">Active</p>
          <p className="text-2xl font-bold text-text">{active.length}</p>
        </div>
        <div className="card p-3">
          <p className="text-[10px] text-text-muted">Completed</p>
          <p className="text-2xl font-bold text-emerald-600">{completed.length}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-red-400">
          <p className="text-[10px] text-text-muted">Delayed</p>
          <p className="text-2xl font-bold text-red-500">{delayed.length}</p>
        </div>
        <div className="card p-3">
          <p className="text-[10px] text-text-muted">Revenue</p>
          <p className="text-lg font-bold text-text">${totalRevenue.toLocaleString()}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-emerald-400">
          <p className="text-[10px] text-text-muted">Profit</p>
          <p className={`text-lg font-bold ${totalProfit >= 0 ? "text-emerald-600" : "text-red-500"}`}>${totalProfit.toLocaleString()}</p>
        </div>
      </div>

      {/* Feature 2: Priority Action Queue */}
      {priorityActions.length > 0 && (
        <div className="card overflow-hidden border-amber-200">
          <div className="p-2.5 bg-amber-50/60 flex items-center gap-2">
            <span className="text-sm">⚡</span>
            <h2 className="text-xs font-semibold text-amber-800">Priority Actions</h2>
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold">{priorityActions.length}</span>
          </div>
          <div className="divide-y divide-border max-h-40 overflow-y-auto">
            {priorityActions.map((a, i) => (
              <div key={`${a.id}-${i}`} className="px-3 py-1.5 flex items-center gap-2 text-xs hover:bg-surface-hover cursor-pointer"
                onClick={() => { setSearch(a.id); setFilter("all"); }}>
                <span>{a.icon}</span>
                <span className={`px-1 py-0.5 rounded text-[9px] font-bold ${a.level === "HIGH" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>{a.level}</span>
                <span className="font-mono text-[10px] text-text-muted">{a.id}</span>
                <span className="text-text-secondary">({a.customer})</span>
                <span className="text-text flex-1">{a.msg}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature 7: Route Heatmap */}
      <div className="card p-3">
        <h3 className="text-[10px] font-semibold text-text-muted mb-2">🗺️ Top Routes</h3>
        <div className="flex gap-3 overflow-x-auto">
          {routeStats.map(r => (
            <button key={r.route}
              className="flex items-center gap-2 min-w-0 cursor-pointer hover:bg-surface-hover rounded-lg px-2 py-1 transition-colors"
              onClick={() => { setSearch(r.route); setFilter("all"); }}>
              <div className="flex-shrink-0 w-20 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-accent/60 rounded-full" style={{ width: `${(r.count / maxRouteCount) * 100}%` }} />
              </div>
              <span className="text-[10px] text-text-secondary whitespace-nowrap truncate max-w-[120px]">{r.route}</span>
              <span className="text-[9px] font-mono text-text-muted">{r.count}</span>
              <span className={`text-[9px] font-mono ${r.profit >= 0 ? "text-emerald-600" : "text-red-500"}`}>${r.profit.toLocaleString()}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {[["all", "All"], ["active", "Active"], ["completed", "✅ Done"], ["delayed", "⚠️ Delayed"], ["critical", "🔴 Critical"]].map(([key, label]) => (
            <button key={key} onClick={() => setFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                filter === key ? "bg-accent text-white" : "bg-surface-hover text-text-secondary hover:text-text"
              }`}>{label}</button>
          ))}
        </div>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search HBL, customer, carrier, route..."
          className="input !py-1.5 !text-xs flex-1 max-w-xs" />
        {search && <button onClick={() => setSearch("")} className="text-xs text-accent cursor-pointer hover:underline">Clear</button>}
      </div>

      {/* Main Table */}
      {sorted.length === 0 ? (
        <div className="card p-8 text-center text-text-muted text-sm">No shipments match.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm min-w-[1300px]">
            <thead>
              <tr className="border-b border-border text-text-muted text-[10px] bg-surface-hover/50">
                <th className="text-center py-2 px-2 font-semibold cursor-pointer hover:text-accent" onClick={() => toggleSort("health")} style={{width:55}}>
                  Health{sortIcon("health")}
                </th>
                <th className="text-left py-2 px-2 font-semibold" style={{minWidth:90}}>HBL / BKG</th>
                <th className="text-left py-2 px-2 font-semibold" style={{minWidth:80}}>Customer</th>
                <th className="text-left py-2 px-2 font-semibold" style={{minWidth:90}}>Routing</th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:45}}>Carrier</th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:160}}>Progress</th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:55}}>ETD</th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:90}}>Gate-in</th>
                <th className="text-center py-2 px-2 font-semibold cursor-pointer hover:text-accent" onClick={() => toggleSort("eta")} style={{minWidth:90}}>
                  ETA{sortIcon("eta")}
                </th>
                <th className="text-right py-2 px-2 font-semibold cursor-pointer hover:text-accent" onClick={() => toggleSort("profit")} style={{minWidth:60}}>
                  Profit{sortIcon("profit")}
                </th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:110}}>Risk</th>
                <th className="text-center py-2 px-2 font-semibold" style={{minWidth:70}}>Action</th>
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 60).map(s => {
                const hb = healthBadge(s.health);
                const eta = etaStatus(s);
                const ps = profitSignal(s.profit, avgProfit);
                const cb = customerBadge(s.customer, customers);
                const ag = agingBadge(s.created_at);
                const sug = getSuggestion(s, avgProfit);
                const displayStageIdx = STAGE_MAP[s.stage] ?? -1;
                const isExpanded = expandedId === s.id;

                return (
                  <tr key={s.id}
                    className={`table-row ${s.health < 50 ? "bg-red-50/30" : ""}`}>
                    {/* Health Score */}
                    <td className="py-2 px-2 text-center">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${hb.cls}`}>
                        {hb.emoji} {s.health}
                      </span>
                    </td>

                    {/* HBL + Container */}
                    <td className="py-2 px-2">
                      <span className="font-mono text-[11px] font-semibold text-text">{s.id}</span>
                      <span className="badge badge-neutral text-[8px] ml-1">{s.container}</span>
                    </td>

                    {/* Customer + Risk Badge */}
                    <td className="py-2 px-2">
                      <span className="text-xs">{cb.icon} </span>
                      <span className="text-text font-medium text-xs">{s.customer}</span>
                    </td>

                    {/* Routing */}
                    <td className="py-2 px-2 text-xs text-text-secondary max-w-[110px] truncate">{s.routing}</td>

                    {/* Carrier */}
                    <td className="py-2 px-2 text-center">
                      <span className="badge badge-info text-[9px]">{s.carrier}</span>
                    </td>

                    {/* Feature 4: Progress Timeline */}
                    <td className="py-2 px-2">
                      <div className="flex items-center gap-0.5">
                        {DISPLAY_STAGES.map((label, idx) => {
                          const done = idx <= displayStageIdx;
                          const current = idx === displayStageIdx;
                          return (
                            <div key={label} className="flex items-center gap-0.5" title={label}>
                              <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center transition-colors ${
                                done ? (current ? "border-accent bg-accent" : "border-emerald-400 bg-emerald-400") : "border-gray-200 bg-white"
                              }`}>
                                {done && <span className="text-white text-[6px]">✓</span>}
                              </div>
                              {idx < DISPLAY_STAGES.length - 1 && (
                                <div className={`w-3 h-0.5 ${done ? "bg-emerald-400" : "bg-gray-200"}`} />
                              )}
                            </div>
                          );
                        })}
                        <span className="text-[8px] text-text-muted ml-1">
                          {DISPLAY_STAGES[displayStageIdx] || s.stage}
                        </span>
                      </div>
                    </td>

                    {/* ETD */}
                    <td className="py-2 px-2 text-center text-[11px] text-text-secondary">
                      {fmtDate(s.etd)}
                    </td>

                    {/* Gate-in (inline editable) */}
                    <td className="py-2 px-2 text-center">
                      <input
                        type={isReefer(s.container) ? "datetime-local" : "date"}
                        className="text-[10px] bg-transparent border border-border rounded px-1 py-0.5 w-full text-center focus:border-accent focus:outline-none cursor-text"
                        value={gateInData[s.id] || ""}
                        onChange={e => setGateIn(s.id, e.target.value)}
                        title={isReefer(s.container) ? "Reefer: enter date + time" : "Dry: enter date"}
                      />
                    </td>

                    {/* Smart ETA */}
                    <td className="py-2 px-2 text-center">
                      <div className={`text-[11px] ${eta.cls}`}>
                        <span className="mr-0.5">{eta.dot}</span>
                        {fmtDate(s.eta)}
                        {eta.days && <span className="text-[9px] ml-0.5">({eta.days})</span>}
                      </div>
                    </td>

                    {/* Feature 5: Profit Intelligence */}
                    <td className="py-2 px-2 text-right">
                      <div className={`font-mono text-xs ${ps.cls}`}>
                        <span className="mr-0.5 text-[9px]">{ps.icon}</span>
                        {s.profit ? `$${s.profit.toLocaleString()}` : "—"}
                      </div>
                    </td>

                    {/* DEM/DET & Power Charge Risk + Email Alerts */}
                    <td className="py-2 px-2 text-center">
                      {(() => {
                        const gi = gateInData[s.id];
                        const risks = calcCostRisks(s, gi || null, freetimeRules);
                        const emailAlerts = (s.email_alerts || []).slice(-2);
                        return (
                          <div className="space-y-0.5">
                            {!gi && emailAlerts.length === 0 && <span className="text-[9px] text-text-muted">—</span>}
                            {gi && risks.length === 0 && <span className="text-[9px] text-emerald-600 font-semibold">✅ OK</span>}
                            {risks.map(r => (
                              <div key={r.type} className={`text-[9px] font-semibold ${r.cls}`} title={r.type}>
                                ⚠️ {r.detail}
                              </div>
                            ))}
                            {emailAlerts.map((a, i) => (
                              <div key={`ea-${i}`} className="text-[9px] font-semibold text-orange-600" title={a.subject}>
                                📧 {a.keyword}
                              </div>
                            ))}
                          </div>
                        );
                      })()}
                    </td>

                    {/* Feature 9+10: Suggestions & Quick Actions */}
                    <td className="py-2 px-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {sug && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-surface-hover" title={sug.text}>
                            {sug.icon}
                          </span>
                        )}
                        <button className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-semibold hover:bg-accent/20 cursor-pointer"
                          onClick={() => {
                            const t = `${s.id} | ${s.customer} | ${s.routing} | ${s.carrier} | Sell: $${s.selling_rate} | Buy: $${s.buying_rate} | Profit: $${s.profit}`;
                            navigator.clipboard?.writeText(t);
                          }}
                          title="Copy shipment details">📋</button>
                        <button className="text-[9px] px-1.5 py-0.5 rounded bg-surface-hover text-text-secondary hover:text-text cursor-pointer"
                          onClick={() => setExpandedId(isExpanded ? null : s.id)}
                          title="View details">👁</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Expanded Detail Row */}
          {expandedId && (() => {
            const s = sorted.find(x => x.id === expandedId);
            if (!s) return null;
            return (
              <div className="border-t border-accent/20 bg-accent/5 px-4 py-3">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <p className="text-[10px] text-text-muted">Financial</p>
                    <p className="font-mono">Sell: ${s.selling_rate.toLocaleString()}</p>
                    <p className="font-mono">Buy: ${s.buying_rate.toLocaleString()}</p>
                    <p className={`font-mono font-semibold ${s.profit >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                      Profit: ${s.profit.toLocaleString()} ({s.profit_margin})
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Dates</p>
                    <p>ETD: {fmtDate(s.etd)}</p>
                    <p>ETA: {fmtDate(s.eta)}</p>
                    <p>ATA: {fmtDate(s.ata)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Details</p>
                    <p>{s.container} × {s.quantity}</p>
                    <p>Delays: {s.delay_count}</p>
                    <p>Source: {s.source}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted">Stage History</p>
                    {s.stage_history.slice(-4).map((h, i) => (
                      <p key={i} className="text-[10px] text-text-muted truncate" title={h.subject}>
                        {h.source === "email" ? "📧" : ""} {fmtDate(h.at)} — {h.stage}
                      </p>
                    ))}
                  </div>
                </div>
                {/* Email Summary */}
                {s.email_summary && (
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <p className="text-[10px] text-text-muted">📧 Latest Email Update</p>
                    <p className="text-xs text-text font-medium mt-0.5">{s.email_summary}</p>
                  </div>
                )}
                {/* Email Trouble Alerts */}
                {s.email_alerts && s.email_alerts.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <p className="text-[10px] text-text-muted">⚠️ Email Alerts</p>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {s.email_alerts.slice(-5).map((a, i) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-700 font-medium" title={a.subject}>
                          {a.keyword}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          <div className="px-4 py-2 border-t border-border text-[10px] text-text-muted flex items-center gap-4">
            <span>🟢 Healthy ≥80 · 🟡 Monitor 50–79 · 🔴 Critical &lt;50</span>
            <span className="ml-auto">{sorted.length} of {enriched.length} shipments</span>
          </div>
        </div>
      )}
    </div>
  );
}
