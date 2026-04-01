"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Rate Freshness Badge — shows how recent the rate data is
   Green: < 24h "Fresh"
   Yellow: 24-72h "Aging"
   Red: > 72h "Stale"
   ═══════════════════════════════════════════════════════════ */

interface FreshnessData {
  lastUpdated: string;
  ageHours: number;
  status: "fresh" | "aging" | "stale";
}

export default function RateFreshnessBadge() {
  const [data, setData] = useState<FreshnessData | null>(null);

  useEffect(() => {
    // Try the dedicated health endpoint first
    fetch(`${API_URL}/api/health/data-freshness`)
      .then(r => r.json())
      .then(d => {
        setData({
          lastUpdated: d.last_modified,
          ageHours: d.age_hours,
          status: d.status,
        });
      })
      .catch(() => {
        // Fallback: fetch rate matrix and extract max validity date
        fetch(`${API_URL}/api/rates/matrix?pol=HPH&mode=DRY&sort_by=40HQ`)
          .then(r => r.json())
          .then(d => {
            const rows = d.rows || [];
            if (rows.length === 0) return;
            const dates = rows
              .map((r: { valid: string }) => r.valid)
              .filter(Boolean)
              .map((v: string) => new Date(v).getTime())
              .filter((t: number) => !isNaN(t));
            if (dates.length === 0) return;
            const maxDate = new Date(Math.max(...dates));
            const ageHours = (Date.now() - maxDate.getTime()) / 3600000;
            setData({
              lastUpdated: maxDate.toISOString(),
              ageHours,
              status: ageHours < 24 ? "fresh" : ageHours < 72 ? "aging" : "stale",
            });
          })
          .catch(() => {});
      });
  }, []);

  if (!data) return null;

  const config = {
    fresh: { bg: "bg-success/8", border: "border-success/20", text: "text-success", icon: "🟢", label: "Fresh" },
    aging: { bg: "bg-warning/8", border: "border-warning/20", text: "text-warning", icon: "🟡", label: "Aging" },
    stale: { bg: "bg-danger/8", border: "border-danger/20", text: "text-danger", icon: "🔴", label: "Stale — rates may be outdated" },
  };

  const c = config[data.status];
  const dateStr = new Date(data.lastUpdated).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  return (
    <div className={`flex items-center gap-2.5 px-3.5 py-2 rounded-xl ${c.bg} border ${c.border}`}>
      <span className="text-xs">{c.icon}</span>
      <p className="text-[11px] font-medium text-text">
        Rate data last updated: <span className="font-semibold">{dateStr}</span>
      </p>
      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${c.bg} ${c.text} uppercase tracking-wider`}>
        {c.label}
      </span>
    </div>
  );
}
