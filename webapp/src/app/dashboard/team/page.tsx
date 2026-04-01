"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════
   Team Performance — LIVE DATA from FastAPI
   /dashboard/team
   ═══════════════════════════════════════════════════════════ */

interface Member {
  email: string;
  name: string;
  role: string;
  folder: string;
  reports_to: string;
  required_cc: string[];
  skip: boolean;
}

const roleBadge: Record<string, string> = {
  Leader: "badge-warning",
  Mentor: "badge-info",
  "Mid-level": "badge-success",
  Mentee: "badge-neutral",
};

export default function TeamPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/team`)
      .then(r => r.json())
      .then(data => setMembers(data.members || []))
      .catch(e => setError(e.message || "Failed to load team data"))
      .finally(() => setLoading(false));
  }, []);

  const leaders = members.filter(m => m.role === "Leader");
  const mentors = members.filter(m => m.role === "Mentor");
  const midLevel = members.filter(m => m.role === "Mid-level");
  const mentees = members.filter(m => m.role === "Mentee");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-text">Team Performance</h1>
        <p className="text-sm text-text-muted mt-0.5">
          {members.length} members · Team Sunny · <span className="text-accent font-medium">Live Data</span>
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3 border-l-2 border-l-yellow-400">
          <p className="text-[11px] text-text-muted">Leaders</p>
          <p className="text-2xl font-bold text-text">{leaders.length}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-accent">
          <p className="text-[11px] text-text-muted">Mentors</p>
          <p className="text-2xl font-bold text-accent">{mentors.length}</p>
        </div>
        <div className="card p-3 border-l-2 border-l-green-400">
          <p className="text-[11px] text-text-muted">Mid-level</p>
          <p className="text-2xl font-bold text-text">{midLevel.length}</p>
        </div>
        <div className="card p-3">
          <p className="text-[11px] text-text-muted">Mentees</p>
          <p className="text-2xl font-bold text-text">{mentees.length}</p>
        </div>
      </div>

      {/* Org structure */}
      {loading ? (
        <div className="card p-8 text-center text-text-muted text-sm">Loading team data...</div>
      ) : (
        <div className="space-y-4">
          {/* Leadership */}
          <div className="card overflow-hidden">
            <div className="p-4 pb-2">
              <h2 className="text-sm font-semibold text-text">Leadership & Mentors</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 pt-2">
              {[...leaders, ...mentors].map(m => (
                <div key={m.email} className="border border-border rounded-lg p-3 hover:border-accent/30 transition-colors">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">
                      {m.name[0]}
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-text">{m.name}</p>
                      <span className={`badge ${roleBadge[m.role] || "badge-neutral"} text-[10px]`}>{m.role}</span>
                    </div>
                  </div>
                  <p className="text-[10px] text-text-muted">{m.email}</p>
                  {m.skip && <p className="text-[10px] text-accent mt-1">Self-managed routing</p>}
                </div>
              ))}
            </div>
          </div>

          {/* Team members table */}
          <div className="card overflow-hidden">
            <div className="p-4 pb-2">
              <h2 className="text-sm font-semibold text-text">
                Team Members
                <span className="text-text-muted font-normal ml-2">· {midLevel.length + mentees.length} members</span>
              </h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-border text-text-muted text-[11px]">
                  <th className="text-left py-2 px-4 font-medium">Name</th>
                  <th className="text-center py-2 px-3 font-medium">Role</th>
                  <th className="text-left py-2 px-3 font-medium">Reports To</th>
                  <th className="text-left py-2 px-3 font-medium">CC Compliance</th>
                  <th className="text-center py-2 px-3 font-medium">Folder</th>
                </tr>
              </thead>
              <tbody>
                {[...midLevel, ...mentees].map(m => {
                  const mgr = members.find(x => x.email === m.reports_to);
                  return (
                    <tr key={m.email} className="table-row">
                      <td className="py-2.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">
                            {m.name[0]}
                          </div>
                          <div>
                            <p className="font-semibold text-text">{m.name}</p>
                            <p className="text-[10px] text-text-muted">{m.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className={`badge ${roleBadge[m.role] || "badge-neutral"}`}>{m.role}</span>
                      </td>
                      <td className="py-2.5 px-3 text-text-secondary text-xs">
                        {mgr ? mgr.name : "—"}
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap gap-1">
                          {m.required_cc.length > 0 ? (
                            m.required_cc.map(cc => {
                              const ccMember = members.find(x => x.email === cc);
                              return (
                                <span key={cc} className="badge badge-neutral text-[10px]">
                                  {ccMember?.name || cc.split("@")[0]}
                                </span>
                              );
                            })
                          ) : (
                            <span className="text-[10px] text-text-muted">None required</span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="badge badge-info text-[10px]">{m.folder}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* CC Rules info */}
          <div className="card p-4 border-accent/20">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                <ShieldSm />
              </div>
              <div>
                <p className="text-sm font-semibold text-text">CC Compliance Intelligence</p>
                <p className="text-xs text-text-secondary mt-1">
                  Email Engine monitors CC compliance for {mentees.length + midLevel.length} team members.
                  Each outgoing email is checked against required CC rules.
                  Violations are logged and will appear here once dataset accumulates.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ShieldSm() {
  return (
    <svg className="w-4 h-4 text-accent" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}
