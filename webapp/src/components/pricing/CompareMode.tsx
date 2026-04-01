"use client";

import { useState, useCallback } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Carrier Compare Mode — side-by-side rate comparison
   Select 2 carriers → fetch rates → show diff table
   ═══════════════════════════════════════════════════════════ */

const CARRIERS = [
  "CMA", "ONE", "MSK", "YML", "ZIM", "OOCL", "WHL", "HMM",
  "PIL", "TSL", "ESL", "MCK", "APL", "HPL", "COSCO",
];

interface CompareRow {
  route: string;
  pod: string;
  place: string;
  priceA: number | null;
  priceB: number | null;
  diff: number | null;
}

interface Props {
  pol: string;
  mode: "DRY" | "REEFER";
}

export default function CompareMode({ pol, mode }: Props) {
  const [open, setOpen] = useState(false);
  const [carrierA, setCarrierA] = useState("");
  const [carrierB, setCarrierB] = useState("");
  const [rows, setRows] = useState<CompareRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const container = mode === "DRY" ? "40HQ" : "40RF";

  const compare = useCallback(async () => {
    if (!carrierA || !carrierB || carrierA === carrierB) return;
    setLoading(true);
    setSearched(false);

    try {
      const [resA, resB] = await Promise.all([
        fetch(`${API_URL}/api/rates/matrix?pol=${pol}&mode=${mode}&sort_by=${container}&carrier=${carrierA}`).then(r => r.json()),
        fetch(`${API_URL}/api/rates/matrix?pol=${pol}&mode=${mode}&sort_by=${container}&carrier=${carrierB}`).then(r => r.json()),
      ]);

      const rowsA = (resA.rows || []) as { pod: string; place: string; routing: string; prices: Record<string, number> }[];
      const rowsB = (resB.rows || []) as { pod: string; place: string; routing: string; prices: Record<string, number> }[];

      // Index B by POD+Place
      const bMap = new Map<string, number>();
      rowsB.forEach(r => {
        const key = `${r.pod}::${r.place}`;
        bMap.set(key, r.prices[container] ?? null as unknown as number);
      });

      // Build combined rows
      const combined = new Map<string, CompareRow>();

      rowsA.forEach(r => {
        const key = `${r.pod}::${r.place}`;
        const pA = r.prices[container] ?? null;
        const pB = bMap.get(key) ?? null;
        combined.set(key, {
          route: r.routing || `${r.pod} → ${r.place}`,
          pod: r.pod,
          place: r.place,
          priceA: pA,
          priceB: pB,
          diff: pA != null && pB != null ? pA - pB : null,
        });
      });

      // Add B-only routes
      rowsB.forEach(r => {
        const key = `${r.pod}::${r.place}`;
        if (!combined.has(key)) {
          combined.set(key, {
            route: r.routing || `${r.pod} → ${r.place}`,
            pod: r.pod,
            place: r.place,
            priceA: null,
            priceB: r.prices[container] ?? null,
            diff: null,
          });
        }
      });

      setRows(Array.from(combined.values()).sort((a, b) => {
        if (a.diff != null && b.diff != null) return a.diff - b.diff;
        return 0;
      }));
      setSearched(true);
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, [pol, mode, container, carrierA, carrierB]);

  return (
    <div>
      {/* Toggle */}
      <button
        onClick={() => setOpen(!open)}
        className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
          open
            ? "bg-accent text-white border-accent"
            : "bg-white text-text-secondary border-border hover:border-accent/50"
        }`}
      >
        ⚖️ Compare
      </button>

      {/* Compare Panel */}
      {open && (
        <div className="card mt-3 p-4 space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">Carrier A</label>
              <select value={carrierA} onChange={e => setCarrierA(e.target.value)} className="select !text-xs !py-1.5 !w-32">
                <option value="">Select...</option>
                {CARRIERS.filter(c => c !== carrierB).map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <span className="text-text-muted text-lg mt-4">vs</span>
            <div>
              <label className="block text-[10px] font-medium text-text-muted mb-1">Carrier B</label>
              <select value={carrierB} onChange={e => setCarrierB(e.target.value)} className="select !text-xs !py-1.5 !w-32">
                <option value="">Select...</option>
                {CARRIERS.filter(c => c !== carrierA).map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <button
              onClick={compare}
              disabled={!carrierA || !carrierB || carrierA === carrierB || loading}
              className="btn-primary !text-xs !py-1.5 !px-4 mt-4"
            >
              {loading ? "Comparing..." : "Compare Rates"}
            </button>
          </div>

          {/* Results Table */}
          {searched && (
            rows.length === 0 ? (
              <p className="text-xs text-text-muted text-center py-4">No matching routes found for comparison.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-text-muted">
                      <th className="text-left py-2 px-3 font-semibold">Route</th>
                      <th className="text-right py-2 px-3 font-semibold">{carrierA} ({container})</th>
                      <th className="text-right py-2 px-3 font-semibold">{carrierB} ({container})</th>
                      <th className="text-right py-2 px-3 font-semibold">Difference</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={`${r.pod}-${r.place}`} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                        <td className="py-2 px-3 font-medium text-text">{r.route}</td>
                        <td className={`py-2 px-3 text-right font-mono ${r.diff != null && r.diff < 0 ? "text-success font-semibold" : "text-text-secondary"}`}>
                          {r.priceA != null ? `$${r.priceA.toLocaleString()}` : "—"}
                        </td>
                        <td className={`py-2 px-3 text-right font-mono ${r.diff != null && r.diff > 0 ? "text-success font-semibold" : "text-text-secondary"}`}>
                          {r.priceB != null ? `$${r.priceB.toLocaleString()}` : "—"}
                        </td>
                        <td className="py-2 px-3 text-right">
                          {r.diff != null ? (
                            <span className={`font-mono font-semibold px-1.5 py-0.5 rounded ${
                              r.diff < 0 ? "bg-success/10 text-success" :
                              r.diff > 0 ? "bg-danger/10 text-danger" :
                              "text-text-muted"
                            }`}>
                              {r.diff > 0 ? "+" : ""}{r.diff === 0 ? "=" : `$${r.diff.toLocaleString()}`}
                            </span>
                          ) : <span className="text-text-muted">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="pt-2 text-[10px] text-text-muted flex gap-4">
                  <span><span className="inline-block w-2.5 h-2.5 rounded bg-success/10 border border-success/30 mr-1 align-middle" />Cheaper</span>
                  <span><span className="inline-block w-2.5 h-2.5 rounded bg-danger/10 border border-danger/30 mr-1 align-middle" />More expensive</span>
                  <span className="ml-auto">{rows.length} routes compared</span>
                </div>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
