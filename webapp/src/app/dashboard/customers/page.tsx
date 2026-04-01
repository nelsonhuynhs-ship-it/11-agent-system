"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Customers — LIVE DATA from FastAPI
   /dashboard/customers
   ═══════════════════════════════════════════════════════════ */

interface Customer {
  name: string;
  type: string;
  priority: string;
  sla_hours: number;
  routes: string[];
  carrier_affinity: string[];
  notes: string;
  total_shipments: number;
  active_shipments: number;
  risk_events: number;
  health: string;
}

const healthBadge: Record<string, string> = {
  active: "badge-success",
  watch: "badge-warning",
  new: "badge-neutral",
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/customers`)
      .then(r => r.json())
      .then(data => setCustomers(data.customers || []))
      .catch(e => setError(e.message || "Failed to load customers"))
      .finally(() => setLoading(false));
  }, []);

  const direct = customers.filter(c => c.type === "DIRECT");
  const fwd = customers.filter(c => c.type === "FWD");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-text">Customer Intelligence</h1>
        <p className="text-sm text-text-muted mt-0.5">
          {customers.length} customers tracked · <span className="text-accent font-medium">Live Data</span>
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3">
          <p className="text-[11px] text-text-muted">Total</p>
          <p className="text-2xl font-bold text-text">{customers.length}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-accent">
          <p className="text-[11px] text-text-muted">Direct</p>
          <p className="text-2xl font-bold text-accent">{direct.length}</p>
        </div>
        <div className="card p-3">
          <p className="text-[11px] text-text-muted">Forwarder</p>
          <p className="text-2xl font-bold text-text">{fwd.length}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-red-400">
          <p className="text-[11px] text-text-muted">Risk Events</p>
          <p className="text-2xl font-bold text-red-500">{customers.reduce((s, c) => s + c.risk_events, 0)}</p>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="p-4 pb-2">
          <h2 className="text-sm font-semibold text-text">All Customers</h2>
        </div>

        {loading ? (
          <div className="p-8 text-center text-text-muted text-sm">Loading...</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-border text-text-muted text-[11px]">
                <th className="text-left py-2 px-4 font-medium">Customer</th>
                <th className="text-center py-2 px-3 font-medium">Type</th>
                <th className="text-center py-2 px-3 font-medium">SLA</th>
                <th className="text-left py-2 px-3 font-medium">Routes</th>
                <th className="text-left py-2 px-3 font-medium">Carriers</th>
                <th className="text-center py-2 px-3 font-medium">Shipments</th>
                <th className="text-center py-2 px-3 font-medium">Active</th>
                <th className="text-center py-2 px-3 font-medium">Risks</th>
                <th className="text-center py-2 px-3 font-medium">Health</th>
              </tr>
            </thead>
            <tbody>
              {customers.map(c => (
                <tr key={c.name} className="table-row">
                  <td className="py-2.5 px-4">
                    <div>
                      <span className="font-semibold text-text">{c.name}</span>
                      {c.priority === "KEY" && <span className="ml-1.5 badge badge-warning">KEY</span>}
                    </div>
                    {c.notes && <p className="text-[10px] text-text-muted mt-0.5">{c.notes}</p>}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={`badge ${c.type === "DIRECT" ? "badge-info" : "badge-neutral"}`}>
                      {c.type}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-xs text-text-secondary">{c.sla_hours}h</td>
                  <td className="py-2.5 px-3">
                    <div className="flex flex-wrap gap-1">
                      {c.routes.map(r => (
                        <span key={r} className="badge badge-neutral text-[10px]">{r}</span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex flex-wrap gap-1">
                      {c.carrier_affinity.map(ca => (
                        <span key={ca} className="badge badge-info text-[10px]">{ca}</span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono text-xs">{c.total_shipments}</td>
                  <td className="py-2.5 px-3 text-center font-mono text-xs font-semibold">
                    {c.active_shipments}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {c.risk_events > 0 ? (
                      <span className="font-mono text-xs text-red-500 font-semibold">{c.risk_events}</span>
                    ) : (
                      <span className="text-xs text-text-muted">—</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={`badge ${healthBadge[c.health] || "badge-neutral"}`}>
                      {c.health}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
