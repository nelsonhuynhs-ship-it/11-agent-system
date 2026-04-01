"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Data Freshness Banner — shows alert if rate data is aging/stale
   Hidden when fresh. Yellow when aging. Red when stale.
   ═══════════════════════════════════════════════════════════ */

export default function DataFreshnessBanner() {
  const [data, setData] = useState<{ status: string; age_hours: number; last_modified: string } | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/health/data-freshness`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  // Don't show when fresh or loading
  if (!data || data.status === "fresh" || data.status === "error" || data.status === "unknown") return null;

  const isStale = data.status === "stale";
  const ageDays = Math.floor(data.age_hours / 24);

  return (
    <div className={`flex items-center justify-center gap-2 px-4 py-1.5 text-xs font-medium ${
      isStale
        ? "bg-danger/10 text-danger border-b border-danger/20"
        : "bg-warning/10 text-warning border-b border-warning/20"
    }`}>
      <span>{isStale ? "⚠️" : "🕐"}</span>
      <span>
        {isStale
          ? `Rate data outdated (${ageDays} days). Contact Nelson to update.`
          : `Rate data is ${ageDays} day${ageDays !== 1 ? "s" : ""} old`
        }
      </span>
    </div>
  );
}
