"use client";

import { useState, useRef, useEffect } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   AI Copilot — Chat interface with tool-assisted intelligence
   /dashboard/ai
   ═══════════════════════════════════════════════════════════ */

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  tool_used?: string;
}

const QUICK_PROMPTS = [
  { label: "Best rate HPH → Denver", icon: "💰" },
  { label: "Active shipments with risk", icon: "🚨" },
  { label: "Customer health overview", icon: "👥" },
  { label: "Team performance summary", icon: "📊" },
  { label: "Which customers are churn risk?", icon: "⚠️" },
  { label: "Compare carriers for LAX route", icon: "🚢" },
];

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "system", content: "Nelson Freight AI Copilot ready. I can look up rates, check shipments, analyze customers, and review team performance. Ask me anything!", timestamp: new Date().toISOString() },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(text?: string) {
    const q = text || input.trim();
    if (!q) return;
    setInput("");

    const userMsg: Message = { role: "user", content: q, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setThinking(true);

    try {
      const response = await processQuery(q);
      setMessages(prev => [...prev, response]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant", content: "Connection error. Make sure the API server is running on port 8000.",
        timestamp: new Date().toISOString()
      }]);
    }

    setThinking(false);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-text">AI Copilot</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Ask about rates, shipments, customers, and team performance
          </p>
        </div>
        <span className="badge badge-success">Online</span>
      </div>

      {/* Chat area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 pb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-2.5 ${
              m.role === "user"
                ? "bg-accent text-white"
                : m.role === "system"
                  ? "bg-accent/5 border border-accent/20 text-text"
                  : "card text-text"
            }`}>
              {m.tool_used && (
                <div className="flex items-center gap-1.5 mb-1.5 pb-1 border-b border-border/50">
                  <ToolIcon />
                  <span className="text-[10px] font-medium text-accent">{m.tool_used}</span>
                </div>
              )}
              <div className="text-sm whitespace-pre-wrap">{m.content}</div>
              <p className={`text-[10px] mt-1 ${m.role === "user" ? "text-white/60" : "text-text-muted"}`}>
                {new Date(m.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}

        {thinking && (
          <div className="flex justify-start">
            <div className="card px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-xs text-text-muted">Analyzing data...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick prompts */}
      {messages.length <= 1 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-3">
          {QUICK_PROMPTS.map(p => (
            <button key={p.label} onClick={() => handleSend(p.label)}
              className="card p-2.5 text-left hover:border-accent/30 transition-colors cursor-pointer group">
              <span className="text-base">{p.icon}</span>
              <p className="text-xs text-text-secondary mt-1 group-hover:text-text">{p.label}</p>
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="card p-2 flex items-center gap-2">
        <input
          type="text" value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask about rates, shipments, customers..."
          className="flex-1 px-3 py-2 text-sm bg-transparent outline-none text-text placeholder:text-text-muted"
          autoFocus
        />
        <button onClick={() => handleSend()} disabled={thinking || !input.trim()}
          className="btn-primary !py-2 !px-4 flex items-center gap-1.5">
          <SendIcon />
        </button>
      </div>
    </div>
  );
}

// ── AI Query Processor (local, tool-based) ───────────────────────
async function processQuery(query: string): Promise<Message> {
  const q = query.toLowerCase();
  const ts = new Date().toISOString();

  // Rate query
  if (q.includes("rate") || q.includes("price") || q.includes("giá") || q.includes("carrier") || q.includes("→") || q.includes("best")) {
    const placeMatch = q.match(/(?:to|→|den|for)\s+(\w+)/i);
    const place = placeMatch?.[1] || "Denver";
    const polMatch = q.match(/(?:from|hph|hcm|dad)/i);
    const pol = polMatch?.[0]?.toUpperCase() || "HPH";

    try {
      const res = await fetch(`${API_URL}/api/rates?pol=${pol}&place=${encodeURIComponent(place)}&container=40HQ&top=5`);
      const data = await res.json();
      if (data.rates.length === 0) {
        return { role: "assistant", content: `No rates found for ${pol} → ${place} (40HQ). Try a different destination.`, timestamp: ts, tool_used: "Rate Lookup" };
      }
      const lines = data.rates.map((r: Record<string, unknown>, i: number) =>
        `${i + 1}. ${(r.carrier as string).padEnd(6)} | $${(r.amount as number).toLocaleString()} | ${r.is_soc ? "SOC" : "COC"} | ${r.is_direct ? "DIRECT" : "T/S"}`
      );
      const cheapest = data.rates[0];
      return {
        role: "assistant", timestamp: ts, tool_used: "Rate Lookup",
        content: `📊 ${pol} → ${place} | 40HQ\n${"━".repeat(35)}\n${lines.join("\n")}\n\n💡 Best: ${cheapest.carrier} at $${cheapest.amount.toLocaleString()} (${cheapest.is_soc ? "SOC" : "COC"})\n📦 ${data.rates.length} options from Parquet database`,
      };
    } catch {
      return { role: "assistant", content: "Failed to query rates. Check if API server is running.", timestamp: ts };
    }
  }

  // Shipment query
  if (q.includes("shipment") || q.includes("lô") || q.includes("risk") || q.includes("active") || q.includes("track")) {
    try {
      const res = await fetch(`${API_URL}/api/shipments`);
      const data = await res.json();
      const shipments = data.shipments || [];
      if (shipments.length === 0) {
        return { role: "assistant", content: "No shipments tracked yet. Run shipment_brain.py to start tracking.", timestamp: ts, tool_used: "Shipment Tracker" };
      }
      const active = shipments.filter((s: Record<string, unknown>) => s.stage !== "PAYMENT_CONFIRMED");
      const risks = shipments.filter((s: Record<string, unknown>) => (s.risk_count as number) > 0);
      const lines = active.slice(0, 5).map((s: Record<string, unknown>) =>
        `  ${s.id} | ${(s.customer as string).padEnd(12)} | ${s.stage} ${(s.risk_count as number) > 0 ? `⚠ ${s.risk_level}` : "✅"}`
      );
      return {
        role: "assistant", timestamp: ts, tool_used: "Shipment Tracker",
        content: `🚢 Shipment Overview\n${"━".repeat(35)}\nTotal: ${shipments.length} | Active: ${active.length} | At Risk: ${risks.length}\n\n${lines.join("\n")}\n${active.length > 5 ? `\n... and ${active.length - 5} more` : ""}`,
      };
    } catch {
      return { role: "assistant", content: "Failed to load shipments.", timestamp: ts };
    }
  }

  // Customer query
  if (q.includes("customer") || q.includes("khách") || q.includes("churn") || q.includes("health")) {
    try {
      const res = await fetch(`${API_URL}/api/customers`);
      const data = await res.json();
      const customers = data.customers || [];
      const lines = customers.map((c: Record<string, unknown>) =>
        `  ${(c.name as string).padEnd(15)} | ${(c.type as string).padEnd(6)} | SLA: ${c.sla_hours}h | ${(c.routes as string[]).join(", ") || "—"} | ${(c.health as string).toUpperCase()}`
      );
      const watchList = customers.filter((c: Record<string, unknown>) => c.health === "watch" || c.health === "new");
      return {
        role: "assistant", timestamp: ts, tool_used: "Customer Intelligence",
        content: `👥 Customer Intelligence\n${"━".repeat(35)}\n${lines.join("\n")}\n\n${watchList.length > 0 ? `⚠️ Watch list: ${watchList.map((c: Record<string, unknown>) => c.name).join(", ")}` : "✅ All customers healthy"}`,
      };
    } catch {
      return { role: "assistant", content: "Failed to load customers.", timestamp: ts };
    }
  }

  // Team query
  if (q.includes("team") || q.includes("mentee") || q.includes("member") || q.includes("performance")) {
    try {
      const res = await fetch(`${API_URL}/api/team`);
      const data = await res.json();
      const members = data.members || [];
      const mentees = members.filter((m: Record<string, unknown>) => m.role === "Mentee");
      const lines = mentees.map((m: Record<string, unknown>) => {
        const mgr = members.find((x: Record<string, unknown>) => x.email === m.reports_to);
        return `  ${(m.name as string).padEnd(8)} | CC: ${(m.required_cc as string[]).length} rules | Reports to: ${(mgr as Record<string, unknown>)?.name || "—"}`;
      });
      return {
        role: "assistant", timestamp: ts, tool_used: "Team Analytics",
        content: `📊 Team Performance\n${"━".repeat(35)}\nTotal: ${members.length} members | Mentees: ${mentees.length}\n\n${lines.join("\n")}\n\n💡 CC compliance data will appear once email datasets accumulate.`,
      };
    } catch {
      return { role: "assistant", content: "Failed to load team data.", timestamp: ts };
    }
  }

  // Default
  return {
    role: "assistant", timestamp: ts,
    content: `I can help with:\n\n📊 **Rates** — "Best rate HPH to Denver", "Compare carriers for LAX"\n🚢 **Shipments** — "Active shipments", "Shipments with risk"\n👥 **Customers** — "Customer health", "Who is churn risk?"\n📋 **Team** — "Team performance", "Mentee overview"\n\nTry asking one of these!`,
  };
}

function SendIcon() {
  return (
    <svg className="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
      <path d="m21.854 2.147-10.94 10.939" />
    </svg>
  );
}

function ToolIcon() {
  return (
    <svg className="w-3 h-3 text-accent" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15.707 21.293a1 1 0 0 1-1.414 0l-1.586-1.586a1 1 0 0 1 0-1.414l5.586-5.586a1 1 0 0 1 1.414 0l1.586 1.586a1 1 0 0 1 0 1.414z" />
      <path d="m18 13-1.375-6.874a1 1 0 0 0-.746-.776L3.235 2.028a1 1 0 0 0-1.207 1.207L5.35 15.879a1 1 0 0 0 .776.746L13 18" />
      <path d="m2.3 2.3 7.286 7.286" /><circle cx="11" cy="11" r="2" />
    </svg>
  );
}
