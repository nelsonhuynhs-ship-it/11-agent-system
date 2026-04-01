"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Quotes — Multi-Carrier/Container Builder + Intelligence
   ═══════════════════════════════════════════════════════════ */

// ── Types ────────────────────────────────────────────────
interface ContainerPrice {
  ocean_freight: number;
  markup: number;
  sell_rate: number;
}

interface CarrierEntry {
  carrier: string;
  badge: string;
  containers: Record<string, ContainerPrice>;
}

interface OptionalCharge {
  description: string;
  amount: number;
  currency: string;
}

interface Quote {
  quote_id: string;
  customer: string;
  service_type: string;
  pol: string;
  pod: string;
  place: string;
  routing: string;
  carriers: CarrierEntry[];
  markup_mode: string;
  global_markup: number;
  optional_charges: OptionalCharge[];
  charges_total: number;
  transit: string;
  freetime: string;
  validity: string;
  status: string;
  version: number;
  parent_quote_id: string | null;
  win_probability: number | null;
  price_alerts: string[];
  best_sell_rate: number;
  best_buy_rate: number;
  carrier_count: number;
  container_count: number;
  created_at: string;
  updated_at: string;
  converted_shipment_id: string | null;
}

interface QuoteStats {
  total: number;
  draft: number;
  sent: number;
  accepted: number;
  rejected: number;
  converted: number;
}

interface BestCarrier {
  carrier: string;
  ocean_freight: number;
  badge: string;
  transit: string;
  freetime: string;
  pod: string;
  place: string;
}

const STATUS_BADGE: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  SENT: "bg-blue-100 text-blue-700",
  ACCEPTED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  CONVERTED: "bg-purple-100 text-purple-700",
};

const SERVICE_TYPES = ["CY-CY", "CY-DOOR", "DOOR-DOOR"];
const CONTAINER_TYPES = ["20GP", "40GP", "40HQ", "45HQ"];

function fmtDate(iso: string) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }); }
  catch { return iso; }
}

// ── Inner Component ──────────────────────────────────────
function QuotesInner() {
  const searchParams = useSearchParams();
  const [view, setView] = useState<"list" | "builder" | "preview">("list");
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [stats, setStats] = useState<QuoteStats>({ total: 0, draft: 0, sent: 0, accepted: 0, rejected: 0, converted: 0 });
  const [customers, setCustomers] = useState<{ name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [convertDialog, setConvertDialog] = useState<Quote | null>(null);

  // ═══════ INTELLIGENCE STATE ═══════
  interface Alert { type: string; severity: string; quote_id: string; customer: string; message: string; action: string; data?: Record<string, unknown>; }
  interface PriceChange { quote_id: string; carrier: string; container: string; route: string; quoted_rate: number; current_rate: number; diff: number; direction: string; action: string; }
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [priceChanges, setPriceChanges] = useState<PriceChange[]>([]);
  const [winMap, setWinMap] = useState<Record<string, { wp: number; priority: string }>>({});
  const [opps, setOpps] = useState({ price_drops: 0, high_win: 0, expiring: 0, stale: 0 });

  // ═══════ BUILDER STATE ═══════
  const [pol, setPol] = useState("HPH");
  const [pod, setPod] = useState("");
  const [place, setPlace] = useState("");
  const [customer, setCustomer] = useState("");
  const [serviceType, setServiceType] = useState("CY-CY");
  const [transit, setTransit] = useState("");
  const [freetime, setFreetime] = useState("");
  const [validity, setValidity] = useState("");
  const [routing, setRouting] = useState("");

  // Multi-container
  const [selectedContainers, setSelectedContainers] = useState<string[]>(["40HQ"]);

  // Multi-carrier: carrier_name → { containers: { ct: {ocean_freight, markup} } }
  const [carrierRows, setCarrierRows] = useState<
    { carrier: string; badge: string; containers: Record<string, { ocean_freight: number; markup: number }> }[]
  >([]);

  // Markup
  const [markupMode, setMarkupMode] = useState<"global" | "per_carrier">("global");
  const [globalMarkup, setGlobalMarkup] = useState(0);

  // Optional charges
  const [charges, setCharges] = useState<OptionalCharge[]>([]);

  // Best carriers cache
  const [bestCarriers, setBestCarriers] = useState<Record<string, BestCarrier[]>>({});
  const [loadingBest, setLoadingBest] = useState(false);

  // Preview
  const [lastSaved, setLastSaved] = useState<Quote | null>(null);

  // ═══════ DATA LOADERS ═══════
  const loadQuotes = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/quotes`);
      const data = await res.json();
      setQuotes(data.quotes || []);
      setStats(data.stats || { total: 0, draft: 0, sent: 0, accepted: 0, rejected: 0, converted: 0 });
    } catch { /* skip */ }
  }, []);

  const loadIntelligence = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/quotes/intelligence`);
      const data = await res.json();
      if (data.alerts) setAlerts(data.alerts);
      if (data.price_changes) setPriceChanges(data.price_changes);
      if (data.opportunities) setOpps(data.opportunities);
      // Build win probability map
      const wm: Record<string, { wp: number; priority: string }> = {};
      for (const q of (data.quotes || [])) {
        if (q.win_probability != null) wm[q.quote_id] = { wp: q.win_probability, priority: q.win_priority || "LOW" };
      }
      setWinMap(wm);
    } catch { /* skip */ }
  }, []);

  useEffect(() => {
    Promise.all([
      loadQuotes(),
      fetch(`${API_URL}/api/customers`).then(r => r.json()).catch(() => ({ customers: [] })),
      loadIntelligence(),
    ]).then(([, cusData]) => {
      setCustomers((cusData as { customers: { name: string }[] }).customers || []);
    }).finally(() => setLoading(false));
  }, [loadQuotes, loadIntelligence]);

  // Auto-open builder from Pricing
  useEffect(() => {
    if (searchParams.get("build") === "true") {
      const p = searchParams;
      setPol(p.get("pol") || "HPH");
      setPod(p.get("pod") || "");
      setPlace(p.get("place") || "");
      setRouting(p.get("routing") || "");
      setFreetime(p.get("freetime") || "");
      setValidity(p.get("validity") || "");
      const ct = p.get("container") || "40HQ";
      setSelectedContainers([ct]);

      const carrier = p.get("carrier") || "";
      const of = parseFloat(p.get("ocean_freight") || "0") || 0;
      const badge = p.get("badge") || "";
      if (carrier && of) {
        setCarrierRows([{
          carrier, badge,
          containers: { [ct]: { ocean_freight: of, markup: 0 } },
        }]);
      }

      setView("builder");
      window.history.replaceState({}, "", "/dashboard/quotes");
    }
  }, [searchParams]);

  // Fetch best carriers when route/containers change
  const fetchBest = useCallback(async () => {
    if (!pol || (!pod && !place) || selectedContainers.length === 0) return;
    setLoadingBest(true);
    try {
      const params = new URLSearchParams({
        pol, containers: selectedContainers.join(","),
        ...(pod && { pod }), ...(place && { place }),
      });
      const res = await fetch(`${API_URL}/api/rates/best?${params}`);
      const data = await res.json();
      setBestCarriers(data.best || {});
    } catch { /* skip */ }
    setLoadingBest(false);
  }, [pol, pod, place, selectedContainers]);

  // ═══════ BUILDER ACTIONS ═══════
  function toggleContainer(ct: string) {
    setSelectedContainers(prev => {
      const next = prev.includes(ct) ? prev.filter(c => c !== ct) : [...prev, ct];
      // Update carrier rows to include/remove container
      setCarrierRows(rows => rows.map(r => {
        const newContainers = { ...r.containers };
        if (!prev.includes(ct) && !newContainers[ct]) {
          // Find best rate for this carrier/container
          const best = bestCarriers[ct]?.find(b => b.carrier === r.carrier);
          newContainers[ct] = { ocean_freight: best?.ocean_freight || 0, markup: 0 };
        } else if (prev.includes(ct) && next.length < prev.length) {
          delete newContainers[ct];
        }
        return { ...r, containers: newContainers };
      }));
      return next;
    });
  }

  function addCarrierFromBest(ct: string, best: BestCarrier) {
    // Check if carrier already exists
    const existing = carrierRows.find(r => r.carrier === best.carrier);
    if (existing) {
      // Just add this container to existing carrier
      setCarrierRows(prev => prev.map(r => {
        if (r.carrier !== best.carrier) return r;
        return {
          ...r,
          containers: {
            ...r.containers,
            [ct]: { ocean_freight: best.ocean_freight, markup: 0 },
          },
        };
      }));
    } else {
      // Add new carrier row
      const containers: Record<string, { ocean_freight: number; markup: number }> = {};
      // Fill all selected containers with best prices if available
      for (const c of selectedContainers) {
        const b = bestCarriers[c]?.find(x => x.carrier === best.carrier);
        containers[c] = { ocean_freight: b?.ocean_freight || 0, markup: 0 };
      }
      containers[ct] = { ocean_freight: best.ocean_freight, markup: 0 };
      setCarrierRows(prev => [...prev, { carrier: best.carrier, badge: best.badge, containers }]);
    }
  }

  function removeCarrier(idx: number) {
    setCarrierRows(prev => prev.filter((_, i) => i !== idx));
  }

  function updateCarrierPrice(carrierIdx: number, ct: string, field: "ocean_freight" | "markup", value: number) {
    setCarrierRows(prev => prev.map((r, i) => {
      if (i !== carrierIdx) return r;
      return {
        ...r,
        containers: {
          ...r.containers,
          [ct]: { ...r.containers[ct], [field]: value },
        },
      };
    }));
  }

  // Calculate totals
  const getCarrierSellRate = (row: typeof carrierRows[0], ct: string) => {
    const p = row.containers[ct];
    if (!p) return 0;
    const mk = markupMode === "global" ? globalMarkup : p.markup;
    return p.ocean_freight + mk;
  };

  const chargesTotal = charges.reduce((s, c) => s + c.amount, 0);

  async function handleSaveQuote() {
    setSaving(true);
    try {
      const carriersPayload = carrierRows.map(r => ({
        carrier: r.carrier,
        badge: r.badge,
        containers: Object.fromEntries(
          Object.entries(r.containers).map(([ct, p]) => [ct, {
            ocean_freight: p.ocean_freight,
            markup: markupMode === "global" ? globalMarkup : p.markup,
          }])
        ),
      }));

      const res = await fetch(`${API_URL}/api/quotes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pol, pod, place, routing, customer, service_type: serviceType,
          transit, freetime, validity,
          carriers: carriersPayload,
          markup_mode: markupMode,
          global_markup: globalMarkup,
          optional_charges: charges,
        }),
      });
      const data = await res.json();
      if (data.success && data.quote) {
        setLastSaved(data.quote);
        setView("preview");
        await loadQuotes();
      }
    } catch { /* skip */ }
    setSaving(false);
  }

  async function handleStatusChange(quoteId: string, newStatus: string) {
    await fetch(`${API_URL}/api/quotes/${quoteId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    }).catch(() => {});
    await loadQuotes();
  }

  async function handleConvert(quoteId: string, winningCarrier: string) {
    const res = await fetch(`${API_URL}/api/quotes/${quoteId}/convert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ winning_carrier: winningCarrier }),
    }).catch(() => null);
    if (res) {
      const data = await res.json();
      if (data.success) {
        await loadQuotes();
        setConvertDialog(null);
        window.location.href = "/dashboard/shipments";
      }
    }
  }

  async function handleRequote(quoteId: string) {
    const res = await fetch(`${API_URL}/api/quotes/${quoteId}/requote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }).catch(() => null);
    if (res) {
      await loadQuotes();
      await loadIntelligence();
    }
  }

  function resetBuilder() {
    setPol("HPH"); setPod(""); setPlace(""); setCustomer("");
    setServiceType("CY-CY"); setTransit(""); setFreetime(""); setValidity(""); setRouting("");
    setSelectedContainers(["40HQ"]); setCarrierRows([]);
    setMarkupMode("global"); setGlobalMarkup(0); setCharges([]);
    setLastSaved(null); setBestCarriers({});
  }

  const filteredQuotes = statusFilter === "ALL"
    ? quotes : quotes.filter(q => q.status === statusFilter);

  if (loading) return <div className="p-12 text-center text-text-muted">Loading quotes...</div>;

  // ═══════════════════════════════════════════════════════
  // QUOTE BUILDER
  // ═══════════════════════════════════════════════════════
  if (view === "builder") {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-text">Quote Builder</h1>
            <p className="text-sm text-text-muted mt-0.5">
              Multi-carrier · Multi-container · <span className="text-accent font-medium">Auto-fill</span>
            </p>
          </div>
          <button onClick={() => { setView("list"); resetBuilder(); }}
            className="text-xs text-text-secondary hover:text-text cursor-pointer">← Back to Quotes</button>
        </div>

        {/* Row 1: Route + Customer */}
        <div className="card p-4">
          <h2 className="text-xs font-semibold text-text-muted mb-3">📍 Route & Customer</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Fld label="POL" val={pol} set={setPol} />
            <Fld label="POD" val={pod} set={setPod} />
            <Fld label="Place of Delivery" val={place} set={setPlace} />
            <Fld label="Routing" val={routing} set={setRouting} />
            <div>
              <label className="block text-[11px] font-medium text-text-muted mb-1">Customer</label>
              <select value={customer} onChange={e => setCustomer(e.target.value)} className="select">
                <option value="">— Select —</option>
                {customers.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-text-muted mb-1">Service Type</label>
              <select value={serviceType} onChange={e => setServiceType(e.target.value)} className="select">
                {SERVICE_TYPES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <Fld label="Transit" val={transit} set={setTransit} />
            <Fld label="Validity" val={validity} set={setValidity} />
          </div>
        </div>

        {/* Row 2: Container Selection */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-text-muted">📦 Container Selection</h2>
            <button onClick={fetchBest} disabled={loadingBest}
              className="text-[10px] font-semibold text-accent hover:underline cursor-pointer">
              {loadingBest ? "Loading..." : "🔍 Find Best Rates"}
            </button>
          </div>
          <div className="flex gap-2">
            {CONTAINER_TYPES.map(ct => (
              <button key={ct} onClick={() => toggleContainer(ct)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors border ${
                  selectedContainers.includes(ct)
                    ? "bg-accent text-white border-accent"
                    : "bg-surface-hover text-text-secondary border-border hover:border-accent/50"
                }`}>{ct}</button>
            ))}
          </div>
        </div>

        {/* Row 3: Best Carrier Suggestions */}
        {Object.keys(bestCarriers).length > 0 && (
          <div className="card p-4">
            <h2 className="text-xs font-semibold text-text-muted mb-3">⚡ Best Carriers (click to add)</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {selectedContainers.map(ct => (
                <div key={ct}>
                  <p className="text-[10px] font-bold text-text-muted mb-1">{ct}</p>
                  <div className="flex flex-wrap gap-1">
                    {(bestCarriers[ct] || []).map((b, i) => {
                      const already = carrierRows.some(r => r.carrier === b.carrier);
                      return (
                        <button key={i} onClick={() => !already && addCarrierFromBest(ct, b)}
                          disabled={already}
                          className={`text-[10px] px-2 py-1 rounded border cursor-pointer transition-all ${
                            already
                              ? "bg-emerald-50 border-emerald-200 text-emerald-600"
                              : "bg-surface-hover border-border text-text-secondary hover:border-accent hover:text-accent"
                          }`}>
                          {b.carrier} {b.badge && `(${b.badge})`} — ${b.ocean_freight.toLocaleString()}
                          {already && " ✓"}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Row 4: Markup Mode */}
        <div className="card p-4">
          <div className="flex items-center gap-4 mb-3">
            <h2 className="text-xs font-semibold text-text-muted">💰 Markup</h2>
            <div className="flex gap-1">
              <button onClick={() => setMarkupMode("global")}
                className={`text-[10px] px-2 py-1 rounded cursor-pointer ${
                  markupMode === "global" ? "bg-accent text-white" : "bg-surface-hover text-text-secondary"
                }`}>Global Markup</button>
              <button onClick={() => setMarkupMode("per_carrier")}
                className={`text-[10px] px-2 py-1 rounded cursor-pointer ${
                  markupMode === "per_carrier" ? "bg-accent text-white" : "bg-surface-hover text-text-secondary"
                }`}>Per-Carrier</button>
            </div>
          </div>
          {markupMode === "global" && (
            <div className="w-40">
              <label className="text-[10px] text-text-muted">Markup (USD)</label>
              <input type="number" className="input font-mono !text-xs" value={globalMarkup}
                onChange={e => setGlobalMarkup(parseFloat(e.target.value) || 0)} />
            </div>
          )}
        </div>

        {/* Row 5: Carrier × Container Matrix */}
        {carrierRows.length > 0 && (
          <div className="card overflow-x-auto">
            <table className="w-full text-xs min-w-[600px]">
              <thead>
                <tr className="border-b border-border text-text-muted text-[10px] bg-surface-hover/50">
                  <th className="text-left py-2 px-3 font-semibold">Carrier</th>
                  {selectedContainers.map(ct => (
                    <th key={ct} className="text-center py-2 px-3 font-semibold" colSpan={markupMode === "per_carrier" ? 3 : 2}>
                      {ct}
                    </th>
                  ))}
                  <th className="text-center py-2 px-3">✕</th>
                </tr>
                <tr className="border-b border-border/50 text-[9px] text-text-muted">
                  <th></th>
                  {selectedContainers.map(ct => (
                    markupMode === "per_carrier" ? (
                      <><th key={`${ct}-of`} className="text-center px-1">O/F</th>
                      <th key={`${ct}-mk`} className="text-center px-1">Markup</th>
                      <th key={`${ct}-sell`} className="text-center px-1">Sell</th></>
                    ) : (
                      <><th key={`${ct}-of`} className="text-center px-1">O/F</th>
                      <th key={`${ct}-sell`} className="text-center px-1">Sell</th></>
                    )
                  ))}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {carrierRows.map((row, ri) => (
                  <tr key={ri} className="border-b border-border/30 hover:bg-surface-hover/30">
                    <td className="py-2 px-3 font-semibold text-text">
                      {row.carrier}
                      {row.badge && <span className="ml-1 text-[8px] px-1 py-0.5 rounded bg-blue-50 text-blue-600">{row.badge}</span>}
                    </td>
                    {selectedContainers.map(ct => {
                      const p = row.containers[ct] || { ocean_freight: 0, markup: 0 };
                      const sell = getCarrierSellRate(row, ct);
                      return markupMode === "per_carrier" ? (
                        <>
                          <td key={`${ct}-of`} className="px-1 py-1">
                            <input type="number" className="input !text-xs !py-1 font-mono w-20 text-center"
                              value={p.ocean_freight || ""} onChange={e => updateCarrierPrice(ri, ct, "ocean_freight", parseFloat(e.target.value) || 0)} />
                          </td>
                          <td key={`${ct}-mk`} className="px-1 py-1">
                            <input type="number" className="input !text-xs !py-1 font-mono w-16 text-center"
                              value={p.markup || ""} onChange={e => updateCarrierPrice(ri, ct, "markup", parseFloat(e.target.value) || 0)} />
                          </td>
                          <td key={`${ct}-sell`} className="px-1 py-1 text-center font-mono font-bold text-accent">
                            ${sell.toLocaleString()}
                          </td>
                        </>
                      ) : (
                        <>
                          <td key={`${ct}-of`} className="px-1 py-1">
                            <input type="number" className="input !text-xs !py-1 font-mono w-20 text-center"
                              value={p.ocean_freight || ""} onChange={e => updateCarrierPrice(ri, ct, "ocean_freight", parseFloat(e.target.value) || 0)} />
                          </td>
                          <td key={`${ct}-sell`} className="px-1 py-1 text-center font-mono font-bold text-accent">
                            ${sell.toLocaleString()}
                          </td>
                        </>
                      );
                    })}
                    <td className="px-2 py-1 text-center">
                      <button onClick={() => removeCarrier(ri)} className="text-red-400 hover:text-red-600 cursor-pointer">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Row 6: Optional Charges */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-text-muted">📋 Optional Charges</h2>
            <button onClick={() => setCharges(prev => [...prev, { description: "", amount: 0, currency: "USD" }])}
              className="text-[10px] font-semibold text-accent hover:underline cursor-pointer">+ Add</button>
          </div>
          {charges.length === 0 ? (
            <p className="text-[10px] text-text-muted">Trucking, DDP, Custom Clearance, Handling…</p>
          ) : (
            <div className="space-y-2">
              {charges.map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input type="text" placeholder="Description" className="input flex-1 !text-xs"
                    value={c.description} onChange={e => setCharges(p => p.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
                  <input type="number" placeholder="Amount" className="input w-24 !text-xs font-mono"
                    value={c.amount || ""} onChange={e => setCharges(p => p.map((x, j) => j === i ? { ...x, amount: parseFloat(e.target.value) || 0 } : x))} />
                  <select className="select w-20 !text-xs" value={c.currency}
                    onChange={e => setCharges(p => p.map((x, j) => j === i ? { ...x, currency: e.target.value } : x))}>
                    <option>USD</option><option>VND</option>
                  </select>
                  <button onClick={() => setCharges(p => p.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600 text-sm cursor-pointer">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Row 7: Summary + Generate */}
        <div className="card p-4 border-l-2 border-l-accent">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] text-text-muted">Summary</p>
              <p className="text-lg font-bold text-text">
                {carrierRows.length} carrier{carrierRows.length !== 1 ? "s" : ""} × {selectedContainers.length} container{selectedContainers.length !== 1 ? "s" : ""}
              </p>
              {chargesTotal > 0 && <p className="text-[10px] text-text-muted">+ ${chargesTotal.toLocaleString()} charges</p>}
            </div>
            <button onClick={handleSaveQuote} disabled={saving || carrierRows.length === 0}
              className="btn-primary !py-2.5 !px-6 text-sm font-semibold">
              {saving ? "Saving..." : "🧾 Generate Quote"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════
  // QUOTE PREVIEW
  // ═══════════════════════════════════════════════════════
  if (view === "preview" && lastSaved) {
    const q = lastSaved;
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-text">Quote Generated ✅</h1>
            <p className="text-sm text-text-muted mt-0.5">
              <span className="font-mono text-accent font-semibold">{q.quote_id}</span> · v{q.version}
            </p>
          </div>
          <button onClick={() => { setView("list"); resetBuilder(); }}
            className="text-xs text-text-secondary hover:text-text cursor-pointer">← Back</button>
        </div>

        <div className="card p-5">
          <div className="border-b border-border pb-3 mb-4 flex items-center justify-between">
            <div>
              <p className="text-lg font-bold text-text">Quotation — {q.quote_id}</p>
              <p className="text-xs text-text-muted">{q.customer || "—"} · {q.service_type} · {fmtDate(q.created_at)}</p>
            </div>
            <span className={`text-[10px] font-bold px-2 py-1 rounded ${STATUS_BADGE[q.status]}`}>{q.status}</span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-sm mb-4">
            <Info label="Route" value={`${q.pol} → ${q.place || q.pod}`} />
            <Info label="Validity" value={q.validity || "—"} />
            <Info label="Markup Mode" value={q.markup_mode === "global" ? `Global $${q.global_markup}` : "Per-Carrier"} />
          </div>

          {/* Carrier × Container table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="text-left py-2 px-2">Carrier</th>
                  {Array.from(new Set(q.carriers.flatMap(c => Object.keys(c.containers)))).map(ct => (
                    <th key={ct} className="text-center py-2 px-2">{ct}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {q.carriers.map((c, i) => (
                  <tr key={i} className="border-b border-border/30">
                    <td className="py-2 px-2 font-semibold">
                      {c.carrier} {c.badge && <span className="text-[8px] px-1 py-0.5 rounded bg-blue-50 text-blue-600">{c.badge}</span>}
                    </td>
                    {Array.from(new Set(q.carriers.flatMap(x => Object.keys(x.containers)))).map(ct => {
                      const p = c.containers[ct];
                      return (
                        <td key={ct} className="py-2 px-2 text-center">
                          {p ? (
                            <div>
                              <span className="font-mono font-bold text-accent">${p.sell_rate.toLocaleString()}</span>
                              <span className="block text-[9px] text-text-muted">O/F ${p.ocean_freight.toLocaleString()} + ${p.markup}</span>
                            </div>
                          ) : <span className="text-text-muted">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {q.optional_charges.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50">
              <p className="text-[10px] text-text-muted mb-1">Optional Charges</p>
              {q.optional_charges.map((c, i) => (
                <div key={i} className="flex justify-between text-xs py-0.5">
                  <span className="text-text-secondary">{c.description}</span>
                  <span className="font-mono">{c.currency} {c.amount.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button onClick={() => { setView("builder"); resetBuilder(); }} className="btn-primary !py-2">+ New Quote</button>
          <button onClick={() => { setView("list"); resetBuilder(); }}
            className="px-4 py-2 rounded-lg bg-surface-hover text-text-secondary text-sm font-medium hover:bg-border cursor-pointer transition-colors">
            View All Quotes
          </button>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════
  // QUOTE LIST (Default)
  // ═══════════════════════════════════════════════════════
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text">Quotes</h1>
          <p className="text-sm text-text-muted mt-0.5">{stats.total} quotes · <span className="text-accent font-medium">Pipeline</span></p>
        </div>
        <button onClick={() => { resetBuilder(); setView("builder"); }} className="btn-primary !py-2 !text-xs">+ New Quote</button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {[
          { label: "Total", val: stats.total, cls: "border-l-2 border-l-accent", color: "text-accent" },
          { label: "Draft", val: stats.draft, cls: "", color: "text-text" },
          { label: "Sent", val: stats.sent, cls: "", color: "text-blue-600" },
          { label: "Accepted", val: stats.accepted, cls: "border-l-2 border-l-emerald-400", color: "text-emerald-600" },
          { label: "Rejected", val: stats.rejected, cls: "", color: "text-red-500" },
          { label: "Converted", val: stats.converted, cls: "", color: "text-purple-600" },
        ].map(k => (
          <div key={k.label} className={`card p-3 ${k.cls}`}>
            <p className="text-[10px] text-text-muted">{k.label}</p>
            <p className={`text-xl font-bold ${k.color}`}>{k.val}</p>
          </div>
        ))}
      </div>

      {/* Sales Intelligence Cards */}
      {(opps.price_drops > 0 || opps.high_win > 0 || opps.expiring > 0 || alerts.length > 0) && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-text-muted">🧠 Sales Intelligence</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {opps.price_drops > 0 && (
              <div className="card p-3 border-l-2 border-l-emerald-400">
                <p className="text-[10px] text-text-muted">📉 Price Drops</p>
                <p className="text-lg font-bold text-emerald-600">{opps.price_drops}</p>
                <p className="text-[9px] text-text-muted">Re-quote opportunities</p>
              </div>
            )}
            {opps.high_win > 0 && (
              <div className="card p-3 border-l-2 border-l-accent">
                <p className="text-[10px] text-text-muted">🎯 High Win</p>
                <p className="text-lg font-bold text-accent">{opps.high_win}</p>
                <p className="text-[9px] text-text-muted">Priority follow-up</p>
              </div>
            )}
            {opps.expiring > 0 && (
              <div className="card p-3 border-l-2 border-l-amber-400">
                <p className="text-[10px] text-text-muted">⏰ Expiring</p>
                <p className="text-lg font-bold text-amber-600">{opps.expiring}</p>
                <p className="text-[9px] text-text-muted">Rate validity ending</p>
              </div>
            )}
            {opps.stale > 0 && (
              <div className="card p-3">
                <p className="text-[10px] text-text-muted">📋 Stale</p>
                <p className="text-lg font-bold text-text-muted">{opps.stale}</p>
                <p className="text-[9px] text-text-muted">Need follow-up</p>
              </div>
            )}
          </div>

          {/* Price Change Alerts */}
          {priceChanges.length > 0 && (
            <div className="card p-3">
              <p className="text-[10px] font-semibold text-text-muted mb-2">📊 Price Alerts</p>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {priceChanges.slice(0, 5).map((pc, i) => (
                  <div key={i} className={`flex items-center justify-between text-[10px] px-2 py-1 rounded ${
                    pc.direction === "DROP" ? "bg-emerald-50" : "bg-red-50"
                  }`}>
                    <span className="text-text-secondary">
                      {pc.direction === "DROP" ? "📉" : "📈"} {pc.carrier} {pc.container} · {pc.route}
                    </span>
                    <span className={`font-mono font-bold ${pc.direction === "DROP" ? "text-emerald-600" : "text-red-600"}`}>
                      ${Math.abs(pc.diff).toLocaleString()} {pc.direction.toLowerCase()}
                    </span>
                    <button onClick={() => handleRequote(pc.quote_id)}
                      className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-accent/10 text-accent hover:bg-accent/20 cursor-pointer ml-1">
                      Requote
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1">
        {["ALL", "DRAFT", "SENT", "ACCEPTED", "REJECTED", "CONVERTED"].map(s => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
              statusFilter === s ? "bg-accent text-white" : "bg-surface-hover text-text-secondary hover:text-text"
            }`}>{s === "ALL" ? "All" : s.charAt(0) + s.slice(1).toLowerCase()}</button>
        ))}
      </div>

      {/* Quote Table */}
      {filteredQuotes.length === 0 ? (
        <div className="card p-8 text-center text-text-muted text-sm">
          {quotes.length === 0 ? "No quotes yet. Build from Pricing!" : "No quotes match filter."}
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm min-w-[950px]">
            <thead>
              <tr className="border-b border-border text-text-muted text-[10px] bg-surface-hover/50">
                <th className="text-left py-2 px-3 font-semibold" style={{ minWidth: 100 }}>Quote ID</th>
                <th className="text-left py-2 px-3 font-semibold" style={{ minWidth: 80 }}>Customer</th>
                <th className="text-left py-2 px-3 font-semibold" style={{ minWidth: 110 }}>Route</th>
                <th className="text-center py-2 px-3 font-semibold">Carriers</th>
                <th className="text-center py-2 px-3 font-semibold">Containers</th>
                <th className="text-right py-2 px-3 font-semibold">Best Rate</th>
                <th className="text-center py-2 px-3 font-semibold">Win %</th>
                <th className="text-center py-2 px-3 font-semibold">Ver</th>
                <th className="text-center py-2 px-3 font-semibold" style={{ minWidth: 70 }}>Status</th>
                <th className="text-center py-2 px-3 font-semibold">Created</th>
                <th className="text-center py-2 px-3 font-semibold" style={{ minWidth: 140 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuotes.map(q => (
                <tr key={q.quote_id} className="table-row border-b border-border/30">
                  <td className="py-2 px-3">
                    <span className="font-mono text-[11px] font-semibold text-text">{q.quote_id}</span>
                  </td>
                  <td className="py-2 px-3 text-xs text-text">{q.customer || "—"}</td>
                  <td className="py-2 px-3 text-xs text-text-secondary truncate max-w-[120px]">
                    {q.pol} → {q.place || q.pod}
                  </td>
                  <td className="py-2 px-3 text-center">
                    <div className="flex flex-wrap gap-0.5 justify-center">
                      {q.carriers?.map((c, i) => (
                        <span key={i} className="badge badge-info text-[8px]">{c.carrier}</span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <div className="flex flex-wrap gap-0.5 justify-center">
                      {Array.from(new Set(q.carriers?.flatMap(c => Object.keys(c.containers)) || [])).map(ct => (
                        <span key={ct} className="badge badge-neutral text-[8px]">{ct}</span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-xs font-semibold text-accent">
                    ${q.best_sell_rate?.toLocaleString() || "—"}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {(() => {
                      const w = winMap[q.quote_id];
                      if (!w) return <span className="text-[9px] text-text-muted">—</span>;
                      const colors = w.priority === "HIGH" ? "bg-emerald-100 text-emerald-700" : w.priority === "MEDIUM" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500";
                      const dots = w.priority === "HIGH" ? "🟢" : w.priority === "MEDIUM" ? "🟡" : "⚪";
                      return <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${colors}`}>{dots} {w.wp}%</span>;
                    })()}
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className="text-[9px] font-mono text-text-muted">v{q.version || 1}</span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={`text-[9px] font-bold px-2 py-0.5 rounded ${STATUS_BADGE[q.status] || ""}`}>
                      {q.status}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center text-[10px] text-text-muted">{fmtDate(q.created_at)}</td>
                  <td className="py-2 px-3 text-center">
                    <div className="flex items-center justify-center gap-1 flex-wrap">
                      <button onClick={() => setExpandedId(expandedId === q.quote_id ? null : q.quote_id)}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-surface-hover text-text-secondary hover:text-text cursor-pointer">👁</button>

                      {q.status === "DRAFT" && (
                        <button onClick={() => handleStatusChange(q.quote_id, "SENT")}
                          className="text-[9px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold hover:bg-blue-100 cursor-pointer">Send</button>
                      )}
                      {q.status === "SENT" && (
                        <>
                          <button onClick={() => handleStatusChange(q.quote_id, "ACCEPTED")}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold hover:bg-emerald-100 cursor-pointer">Accept</button>
                          <button onClick={() => handleStatusChange(q.quote_id, "REJECTED")}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-red-50 text-red-700 font-semibold hover:bg-red-100 cursor-pointer">Reject</button>
                        </>
                      )}
                      {q.status === "ACCEPTED" && !q.converted_shipment_id && (
                        <button onClick={() => setConvertDialog(q)}
                          className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-bold hover:bg-accent/20 cursor-pointer">🚢 Convert</button>
                      )}
                      {q.converted_shipment_id && (
                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 font-mono">→ {q.converted_shipment_id}</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Expanded Detail */}
          {expandedId && (() => {
            const q = filteredQuotes.find(x => x.quote_id === expandedId);
            if (!q) return null;
            const allCts = Array.from(new Set(q.carriers?.flatMap(c => Object.keys(c.containers)) || []));
            return (
              <div className="border-t border-accent/20 bg-accent/5 px-4 py-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs mb-2">
                    <thead>
                      <tr className="text-text-muted text-[9px]">
                        <th className="text-left py-1 px-2">Carrier</th>
                        {allCts.map(ct => <th key={ct} className="text-center py-1 px-2">{ct} (O/F → Sell)</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {q.carriers?.map((c, i) => (
                        <tr key={i}>
                          <td className="py-1 px-2 font-semibold">{c.carrier} {c.badge && <span className="text-[8px] text-blue-600">({c.badge})</span>}</td>
                          {allCts.map(ct => {
                            const p = c.containers[ct];
                            return <td key={ct} className="py-1 px-2 text-center font-mono">
                              {p ? <span>${p.ocean_freight.toLocaleString()} → <span className="font-bold text-accent">${p.sell_rate.toLocaleString()}</span></span> : "—"}
                            </td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {q.optional_charges?.length > 0 && (
                  <div className="text-[10px] text-text-muted">
                    Charges: {q.optional_charges.map(c => `${c.description} $${c.amount}`).join(" · ")}
                  </div>
                )}
              </div>
            );
          })()}

          <div className="px-4 py-2 border-t border-border text-[10px] text-text-muted flex items-center gap-4">
            <span>{filteredQuotes.length} of {quotes.length} quotes</span>
            <span className="ml-auto">Pipeline: {stats.draft} draft · {stats.sent} sent · {stats.accepted} accepted · {stats.converted} converted</span>
          </div>
        </div>
      )}

      {/* Convert Dialog */}
      {convertDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setConvertDialog(null)}>
          <div className="bg-surface rounded-xl p-5 shadow-2xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-text mb-3">🚢 Convert to Shipment</h3>
            <p className="text-xs text-text-muted mb-4">Select the winning carrier for <span className="font-mono font-bold">{convertDialog.quote_id}</span>:</p>
            <div className="space-y-2">
              {convertDialog.carriers?.map((c, i) => (
                <button key={i} onClick={() => handleConvert(convertDialog.quote_id, c.carrier)}
                  className="w-full text-left px-3 py-2 rounded-lg border border-border hover:border-accent hover:bg-accent/5 cursor-pointer transition-all">
                  <span className="font-semibold text-text text-sm">{c.carrier}</span>
                  {c.badge && <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-blue-50 text-blue-600">{c.badge}</span>}
                  <div className="flex gap-3 mt-1">
                    {Object.entries(c.containers).map(([ct, p]) => (
                      <span key={ct} className="text-[10px] text-text-muted">
                        {ct}: <span className="font-mono text-accent font-bold">${p.sell_rate.toLocaleString()}</span>
                      </span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
            <button onClick={() => setConvertDialog(null)}
              className="mt-3 w-full text-xs text-text-muted hover:text-text text-center py-2 cursor-pointer">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Field helper ─────────────────────────────────────────
function Fld({ label, val, set }: { label: string; val: string; set: (v: string) => void }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-text-muted mb-1">{label}</label>
      <input type="text" className="input !text-xs" value={val} onChange={e => set(e.target.value)} />
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><p className="text-[10px] text-text-muted">{label}</p><p className="text-text font-medium">{value}</p></div>;
}

// ── Export ────────────────────────────────────────────────
export default function QuotesPage() {
  return (
    <Suspense fallback={<div className="p-12 text-center text-text-muted">Loading...</div>}>
      <QuotesInner />
    </Suspense>
  );
}
