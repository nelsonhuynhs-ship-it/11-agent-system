"use client";

import { useState, useCallback, useMemo } from "react";
import { API_URL } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import RateFreshnessBadge from "@/components/pricing/RateFreshnessBadge";
import CompareMode from "@/components/pricing/CompareMode";

const PORTS = ["HPH", "HCM", "DAD"];
const RI: Record<string, string> = { WC: "🌊", EC: "🗽", GULF: "🏖️", IPI: "🚚" };
const RL: Record<string, string> = { WC: "West Coast", EC: "East Coast", GULF: "Gulf", IPI: "Inland" };
const BC: Record<string, string> = {
  SOC: "bg-emerald-100 text-emerald-700", FAK: "bg-sky-100 text-sky-700",
  FIX: "bg-violet-100 text-violet-700", FIXED: "bg-violet-100 text-violet-700",
  SCFI: "bg-amber-100 text-amber-700",
};

interface Row {
  carrier: string; badge: string; is_soc: boolean; routing: string;
  pod: string; place: string; prices: Record<string, number>;
  surcharges: Record<string, Record<string, number>>;
  valid: string; freetime: string; region: string;
}

interface Reg {
  count: number; best_carrier: string; min_price: number; avg_price: number;
  carriers: number; pods: number;
}

export default function PricingPage() {
  const [pol, setPol] = useState("HPH");
  const [pod, setPod] = useState("");
  const [place, setPlace] = useState("");
  const [mode, setMode] = useState<"DRY"|"REEFER">("DRY");
  const [sortBy, setSortBy] = useState("40HQ");
  const [rows, setRows] = useState<Row[]>([]);
  const [cts, setCts] = useState<string[]>([]);
  const [cheap, setCheap] = useState<Record<string, number|null>>({});
  // regs loaded via React Query below
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [hover, setHover] = useState<{r:number;c:string}|null>(null);

  const ct = mode === "DRY" ? "40HQ" : "20RF";
  const { data: regData } = useQuery({
    queryKey: ['rates', 'regions', pol, ct],
    queryFn: () => fetch(`${API_URL}/api/rates/regions?pol=${pol}&container=${ct}`).then(r => r.json()),
    staleTime: 60 * 1000,
  });

  const regs = regData?.regions || {};

  const search = useCallback(async () => {
    setLoading(true); setHover(null);
    try {
      const p = new URLSearchParams({ pol, mode, sort_by: sortBy });
      if (pod) p.set("pod", pod);
      if (place) p.set("place", place);
      const res = await fetch(`${API_URL}/api/rates/matrix?${p}`);
      const d = await res.json();
      setRows(d.rows||[]); setCts(d.containers||[]); setCheap(d.cheapest||{});
      setSearched(true);
    } catch { setRows([]); setCts([]); }
    setLoading(false);
  }, [pol, pod, place, mode, sortBy]);

  const sorted = useMemo(() =>
    [...rows].sort((a, b) => (a.prices[sortBy]??999999) - (b.prices[sortBy]??999999)),
  [rows, sortBy]);

  const nCarriers = new Set(sorted.map(r => r.carrier)).size;

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-text">Rate Explorer</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Freight Comparison Dashboard · <span className="text-accent font-medium">Live Market</span>
        </p>
      </div>

      {/* Rate Freshness Badge */}
      <RateFreshnessBadge />

      {/* Carrier Compare Mode */}
      <CompareMode pol={pol} mode={mode} />

      {/* Region Cards */}
      {Object.keys(regs).length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {(["WC","EC","GULF","IPI"] as const).map(r => {
            const d = regs[r];
            if (!d || d.count === 0) return (
              <div key={r} className="card p-3 opacity-40">
                <p className="text-[11px] font-semibold text-text-muted">{RI[r]} {RL[r]}</p>
                <p className="text-lg font-bold text-text-muted mt-1">—</p>
              </div>
            );
            return (
              <div key={r} className="card p-3.5 hover:border-accent/50 transition-colors">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[11px] font-semibold text-text-muted">{RI[r]} {RL[r]}</p>
                  <span className="text-[9px] text-text-muted">{d.count} rates</span>
                </div>
                <p className="text-xl font-bold text-text">${d.min_price?.toLocaleString()}</p>
                <div className="mt-1 space-y-0.5">
                  <p className="text-[10px] text-text-muted">Best: <span className="font-semibold text-accent">{d.best_carrier}</span></p>
                  <p className="text-[10px] text-text-muted">Range: ${d.min_price?.toLocaleString()} – ${Math.round(d.avg_price*1.15).toLocaleString()}</p>
                  <p className="text-[10px] text-text-muted">{d.carriers} carriers · {d.pods} PODs</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Filters */}
      <div className="card p-4">
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 items-end">
          <div>
            <label className="block text-[11px] font-medium text-text-muted mb-1">POL</label>
            <select value={pol} onChange={e => setPol(e.target.value)} className="select">
              {PORTS.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-medium text-text-muted mb-1">POD</label>
            <input type="text" value={pod} onChange={e => setPod(e.target.value)}
              placeholder="LAX, SAV, HOU..." className="input"
              onKeyDown={e => e.key === "Enter" && search()} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-[11px] font-medium text-text-muted mb-1">Place of Delivery</label>
            <input type="text" value={place} onChange={e => setPlace(e.target.value)}
              placeholder="Denver, Chicago, Atlanta..." className="input"
              onKeyDown={e => e.key === "Enter" && search()} />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-text-muted mb-1">Type</label>
            <div className="flex rounded-lg overflow-hidden border border-border h-[38px]">
              <button onClick={() => { setMode("DRY"); setSortBy("40HQ"); }}
                className={`flex-1 text-xs font-semibold cursor-pointer transition-colors ${
                  mode==="DRY" ? "bg-accent text-white" : "bg-surface-hover text-text-secondary"
                }`}>🏗️ DRY</button>
              <button onClick={() => { setMode("REEFER"); setSortBy("40RF"); }}
                className={`flex-1 text-xs font-semibold cursor-pointer transition-colors ${
                  mode==="REEFER" ? "bg-cyan-500 text-white" : "bg-surface-hover text-text-secondary"
                }`}>❄️ REEFER</button>
            </div>
          </div>
          <button onClick={search} disabled={loading}
            className="btn-primary flex items-center justify-center gap-2 !py-2 h-[38px]">
            {loading ? <Spin /> : <Srch />}
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {/* Matrix Results */}
      {searched && (
        <>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="badge badge-success">{sorted.length} rates</span>
            <span className="text-xs text-text-muted">{nCarriers} carriers</span>
            <span className="text-xs text-text-muted">Sorted: <span className="text-accent font-semibold">{sortBy}</span></span>
            {mode==="REEFER" && <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-700 font-bold">❄️ Reefer</span>}
          </div>

          {sorted.length === 0 ? (
            <div className="card p-12 text-center text-text-muted">No rates found.</div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm min-w-[800px]">
                <thead>
                  <tr className="border-b border-border text-text-muted text-[11px] bg-surface-hover/50">
                    <th className="text-left py-2.5 px-3 font-semibold sticky left-0 bg-surface-hover/50 z-10" style={{minWidth:130}}>Carrier</th>
                    <th className="text-left py-2.5 px-3 font-semibold" style={{minWidth:160}}>POD / VIA</th>
                    {cts.map(ct => (
                      <th key={ct} onClick={() => setSortBy(ct)}
                        className={`text-right py-2.5 px-3 font-semibold cursor-pointer hover:text-accent transition-colors ${sortBy===ct ? "text-accent bg-accent/5" : ""}`}
                        style={{minWidth:80}}>
                        {ct}{sortBy===ct && <span className="ml-0.5 text-[8px]">▼</span>}
                      </th>
                    ))}
                    <th className="text-center py-2.5 px-3 font-semibold" style={{minWidth:60}}>Free</th>
                    <th className="text-center py-2.5 px-3 font-semibold" style={{minWidth:90}}>Valid</th>
                    <th className="text-center py-2.5 px-3 font-semibold" style={{minWidth:60}}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((row, ri) => {
                    const grp = ri > 0 && sorted[ri-1].carrier === row.carrier;
                    return (
                      <tr key={`${row.carrier}-${row.badge}-${ri}`}
                        className={`table-row ${grp ? "border-t border-border/30" : "border-t border-border"}`}>
                        <td className="py-2.5 px-3 sticky left-0 bg-surface z-10">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`font-semibold ${grp ? "text-text-muted text-xs" : "text-text"}`}>
                              {grp ? "↳" : ""} {row.carrier}
                            </span>
                            {row.badge && (
                              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${BC[row.badge] || "bg-gray-100 text-gray-600"}`}>
                                {row.badge}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-xs text-text-secondary" title={`POD: ${row.pod}\nPlace: ${row.place}`}>
                          {row.routing}
                        </td>
                        {cts.map(ct => {
                          const price = row.prices[ct];
                          const best = price != null && cheap[ct] != null && price === cheap[ct];
                          const hasSur = row.surcharges[ct] && Object.keys(row.surcharges[ct]).length > 0;
                          const isH = hover?.r === ri && hover?.c === ct;
                          return (
                            <td key={ct} className={`py-2.5 px-3 text-right font-mono relative ${sortBy===ct ? "bg-accent/5" : ""}`}
                              onMouseEnter={() => hasSur && setHover({r:ri,c:ct})}
                              onMouseLeave={() => setHover(null)}>
                              {price != null ? (
                                <span className={`text-sm ${best ? "text-emerald-600 font-bold bg-emerald-50 px-1.5 py-0.5 rounded" : "text-text"} ${hasSur ? "cursor-help border-b border-dashed border-text-muted" : ""}`}>
                                  {price.toLocaleString()}
                                </span>
                              ) : <span className="text-text-muted text-xs">—</span>}
                              {isH && hasSur && (
                                <div className="absolute z-50 right-0 top-full mt-1 bg-white border border-border rounded-lg shadow-lg p-3 min-w-[200px]" style={{pointerEvents:"none"}}>
                                  <p className="text-[10px] font-semibold text-text mb-1.5">💰 Breakdown — {ct}</p>
                                  {Object.entries(row.surcharges[ct]).map(([n, a]) => (
                                    <div key={n} className="flex justify-between text-[10px] py-0.5">
                                      <span className="text-text-muted truncate mr-3">{n.length > 25 ? n.slice(0,25)+"…" : n}</span>
                                      <span className="font-mono text-text font-medium">${a.toLocaleString()}</span>
                                    </div>
                                  ))}
                                  <div className="flex justify-between text-[10px] py-0.5 mt-1 pt-1 border-t border-border">
                                    <span className="font-semibold text-accent">Total O/F</span>
                                    <span className="font-mono font-bold text-accent">${price?.toLocaleString()}</span>
                                  </div>
                                </div>
                              )}
                            </td>
                          );
                        })}
                        <td className="py-2.5 px-3 text-center text-xs text-text-secondary">{row.freetime || "—"}</td>
                        <td className="py-2.5 px-3 text-center text-[10px] text-text-muted whitespace-nowrap">{row.valid}</td>
                        <td className="py-2.5 px-3 text-center">
                          <button className="text-[10px] font-semibold text-accent hover:underline cursor-pointer whitespace-nowrap"
                            onClick={() => {
                              const params = new URLSearchParams({
                                build: "true",
                                pol: pol,
                                pod: row.pod || "",
                                place: row.place || "",
                                carrier: row.carrier || "",
                                badge: row.badge || "",
                                container: sortBy || "40HQ",
                                ocean_freight: String(row.prices[sortBy] || row.prices["40HQ"] || Object.values(row.prices)[0] || 0),
                                freetime: row.freetime || "",
                                validity: row.valid || "",
                                routing: row.routing || "",
                              });
                              window.location.href = `/dashboard/quotes?${params.toString()}`;
                            }}>
                            Build Quote →
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="px-4 py-2 border-t border-border text-[10px] text-text-muted flex items-center gap-4">
                <span><span className="inline-block w-3 h-3 rounded bg-emerald-50 border border-emerald-200 mr-1 align-middle"/>Best price</span>
                <span><span className="inline-block border-b border-dashed border-text-muted mr-1 w-3 align-middle"/>Hover for breakdown</span>
                <span className="ml-auto">{sorted.length} rates · {nCarriers} carriers</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Srch() {
  return (<svg className="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
  </svg>);
}
function Spin() {
  return (<svg className="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
  </svg>);
}
