"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";
import Link from "next/link";

/* ═══════════════════════════════════════════════════════════
   Action Needed Widget — Dashboard top alert bar
   3 sections: URGENT (red), WARNING (yellow), INFO (blue)
   ═══════════════════════════════════════════════════════════ */

interface AlertSection {
  type: "urgent" | "warning" | "info";
  icon: string;
  label: string;
  count: number;
  message: string;
  href: string;
}

export default function ActionNeeded() {
  const [alerts, setAlerts] = useState<AlertSection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const results: AlertSection[] = [];

    Promise.all([
      // 1. Shipments: freetime < 3 days
      fetch(`${API_URL}/api/shipments`)
        .then(r => r.json())
        .then(data => {
          const shipments = data?.shipments || (Array.isArray(data) ? data : []);
          const now = Date.now();
          const urgent = shipments.filter((s: { eta: string; ata: string; freetime_days?: number }) => {
            if (s.ata) return false; // already arrived
            if (!s.eta) return false;
            const eta = new Date(s.eta).getTime();
            const daysLeft = Math.ceil((eta - now) / 86400000);
            return daysLeft >= 0 && daysLeft <= 3;
          });
          if (urgent.length > 0) {
            results.push({
              type: "urgent",
              icon: "🔴",
              label: "URGENT",
              count: urgent.length,
              message: `${urgent.length} shipment${urgent.length > 1 ? "s" : ""} arriving within 3 days`,
              href: "/dashboard/shipments",
            });
          }
        })
        .catch(() => {}),

      // 2. Quotes: pending > 24h
      fetch(`${API_URL}/api/quotes`)
        .then(r => r.json())
        .then(data => {
          const quotes = data?.quotes || (Array.isArray(data) ? data : []);
          const now = Date.now();
          const stale = quotes.filter((q: { status: string; created_at: string }) => {
            if (q.status?.toLowerCase() !== "pending" && q.status?.toLowerCase() !== "sent") return false;
            if (!q.created_at) return false;
            const age = now - new Date(q.created_at).getTime();
            return age > 86400000; // > 24 hours
          });
          if (stale.length > 0) {
            results.push({
              type: "warning",
              icon: "🟡",
              label: "FOLLOW UP",
              count: stale.length,
              message: `${stale.length} quote${stale.length > 1 ? "s" : ""} pending reply > 24h`,
              href: "/dashboard/quotes",
            });
          }
        })
        .catch(() => {}),

      // 3. Churn risk: high risk customers
      fetch(`${API_URL}/api/intelligence/churn`)
        .then(r => r.json())
        .then(data => {
          const customers = data?.customers || (Array.isArray(data) ? data : []);
          const high = customers.filter((c: { risk: string }) =>
            c.risk?.toLowerCase() === "high" || c.risk?.toLowerCase() === "critical"
          );
          if (high.length > 0) {
            results.push({
              type: "info",
              icon: "🔵",
              label: "WATCH",
              count: high.length,
              message: `${high.length} customer${high.length > 1 ? "s" : ""} with high churn risk`,
              href: "/dashboard/customers",
            });
          }
        })
        .catch(() => {}),
    ]).finally(() => {
      // Sort: urgent first, then warning, then info
      results.sort((a, b) => {
        const order = { urgent: 0, warning: 1, info: 2 };
        return order[a.type] - order[b.type];
      });
      setAlerts(results);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="card !p-3 animate-pulse">
        <div className="h-4 w-48 bg-border rounded" />
      </div>
    );
  }

  // All clear
  if (alerts.length === 0) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-success/5 border border-success/15">
        <span className="text-lg">✅</span>
        <p className="text-xs font-medium text-success">All clear — no action needed</p>
      </div>
    );
  }

  const styles = {
    urgent: { bg: "bg-danger/5", border: "border-danger/15", badge: "bg-danger text-white", text: "text-danger" },
    warning: { bg: "bg-warning/5", border: "border-warning/15", badge: "bg-warning text-white", text: "text-warning" },
    info:    { bg: "bg-accent/5", border: "border-accent/15", badge: "bg-accent text-white", text: "text-accent" },
  };

  return (
    <div className="space-y-2">
      {alerts.map((a) => {
        const s = styles[a.type];
        return (
          <Link
            key={a.type}
            href={a.href}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl ${s.bg} border ${s.border} hover:shadow-sm transition-all group cursor-pointer`}
          >
            <span className="text-base">{a.icon}</span>
            <span className={`text-[10px] font-bold tracking-wider ${s.text} uppercase`}>{a.label}</span>
            <p className="text-xs text-text flex-1">{a.message}</p>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${s.badge}`}>{a.count}</span>
            <svg className="w-3.5 h-3.5 text-text-muted group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </Link>
        );
      })}
    </div>
  );
}
