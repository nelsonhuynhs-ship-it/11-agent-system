"use client";

import { useState, useEffect, useCallback } from "react";
import { campaignApi, dataApi, CampaignProspect } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────
type Step = 1 | 2 | 3 | 4;

interface QueueResult {
  queued: number;
  message: string;
}

const STEP_LABELS = ["Select Campaign", "Select Batch", "Preview Email", "Approve & Queue"];

// ═══════════════════════════════════════════════════════════════
export default function EmailCampaignPage() {
  const [step, setStep] = useState<Step>(1);

  // Step 1
  const [campaigns, setCampaigns] = useState<string[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [loadingCampaigns, setLoadingCampaigns] = useState(true);

  // Step 2
  const [prospects, setProspects] = useState<CampaignProspect[]>([]);
  const [loadingProspects, setLoadingProspects] = useState(false);
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());
  const [totalProspects, setTotalProspects] = useState(0);

  // Step 3
  const [previewHtml, setPreviewHtml] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState("");

  // Step 4
  const [queueResult, setQueueResult] = useState<QueueResult | null>(null);
  const [queueing, setQueueing] = useState(false);
  const [queueError, setQueueError] = useState("");

  // Load campaigns list on mount
  useEffect(() => {
    campaignApi.stats().then(res => {
      setCampaigns(Object.keys(res.campaigns));
      setLoadingCampaigns(false);
    }).catch(() => setLoadingCampaigns(false));
  }, []);

  // Step 1 → 2: load prospects for campaign
  const handleSelectCampaign = useCallback(async () => {
    if (!selectedCampaign) return;
    setLoadingProspects(true);
    setSelectedEmails(new Set());
    try {
      const res = await campaignApi.prospects({
        campaign: selectedCampaign,
        sent_status: "not_sent",
        page_size: 200,
      });
      setProspects(res.prospects);
      setTotalProspects(res.total);
      setStep(2);
    } catch {
      // stay on step 1
    } finally {
      setLoadingProspects(false);
    }
  }, [selectedCampaign]);

  // Toggle selection
  const toggleEmail = (email: string) => {
    setSelectedEmails(prev => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else if (next.size < 50) next.add(email);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedEmails.size === Math.min(prospects.length, 50)) {
      setSelectedEmails(new Set());
    } else {
      setSelectedEmails(new Set(prospects.slice(0, 50).map(p => p.email)));
    }
  };

  // Step 2 → 3: load preview
  const handlePreview = useCallback(async () => {
    if (selectedEmails.size === 0) return;
    setLoadingPreview(true);
    setPreviewError("");
    const first = prospects.find(p => selectedEmails.has(p.email));
    if (!first) return;
    try {
      const res = await campaignApi.preview({
        email: first.email,
        company: first.company,
        pic: first.pic,
        pol: first.pol,
        destinations: first.destination,
        markup: 0,
        intro: "",
        closing: "",
        subject: "",
        template: "professional",
      });
      setPreviewHtml(res.html);
      setStep(3);
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoadingPreview(false);
    }
  }, [selectedEmails, prospects]);

  // Step 3 → 4: queue emails
  const handleQueue = useCallback(async () => {
    setQueueing(true);
    setQueueError("");
    try {
      const res = await dataApi.queueEmails({
        emails: Array.from(selectedEmails),
        campaign_id: selectedCampaign,
        markup: 0,
        template: "professional",
      });
      setQueueResult(res);
      setStep(4);
    } catch (e) {
      setQueueError(e instanceof Error ? e.message : "Queue failed");
    } finally {
      setQueueing(false);
    }
  }, [selectedEmails, selectedCampaign]);

  const resetWizard = () => {
    setStep(1);
    setSelectedCampaign("");
    setProspects([]);
    setSelectedEmails(new Set());
    setPreviewHtml("");
    setQueueResult(null);
    setQueueError("");
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-text">Email Campaign</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Chọn campaign → chọn batch → preview → queue gửi
        </p>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center gap-0">
        {STEP_LABELS.map((label, idx) => {
          const s = (idx + 1) as Step;
          const isActive = step === s;
          const isDone = step > s;
          return (
            <div key={s} className="flex items-center flex-1 last:flex-none">
              <div className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  isDone ? "bg-green-500 text-white" :
                  isActive ? "bg-accent text-white" :
                  "bg-surface border border-border text-text-muted"
                }`}>
                  {isDone ? "✓" : s}
                </div>
                <span className={`text-xs font-medium hidden sm:block ${isActive ? "text-text" : "text-text-muted"}`}>
                  {label}
                </span>
              </div>
              {idx < STEP_LABELS.length - 1 && (
                <div className={`flex-1 h-px mx-2 ${isDone ? "bg-green-500" : "bg-border"}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step 1: Select Campaign */}
      {step === 1 && (
        <div className="rounded-xl border border-border bg-surface p-6 space-y-4">
          <h2 className="font-semibold text-text">Chọn Campaign</h2>
          {loadingCampaigns ? (
            <p className="text-sm text-text-muted">Loading campaigns...</p>
          ) : (
            <div className="space-y-3">
              <select
                value={selectedCampaign}
                onChange={e => setSelectedCampaign(e.target.value)}
                className="w-full max-w-sm px-3 py-2 rounded-lg bg-background border border-border text-sm text-text focus:outline-none focus:border-accent"
              >
                <option value="">-- Select campaign --</option>
                {campaigns.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <button
                onClick={handleSelectCampaign}
                disabled={!selectedCampaign || loadingProspects}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
              >
                {loadingProspects ? "Loading..." : "Load CNEEs →"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Select Batch */}
      {step === 2 && (
        <div className="rounded-xl border border-border bg-surface space-y-0">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div>
              <h2 className="font-semibold text-text">{selectedCampaign} — Chọn batch</h2>
              <p className="text-xs text-text-muted mt-0.5">
                {totalProspects} CNEEs chưa gửi • Đã chọn: {selectedEmails.size}/50
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(1)} className="px-3 py-1.5 text-sm rounded-lg border border-border text-text-muted hover:text-text transition-colors">← Back</button>
              <button
                onClick={handlePreview}
                disabled={selectedEmails.size === 0 || loadingPreview}
                className="px-4 py-1.5 text-sm rounded-lg bg-primary text-white font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
              >
                {loadingPreview ? "Loading..." : `Preview (${selectedEmails.size}) →`}
              </button>
            </div>
          </div>
          {previewError && (
            <div className="px-4 py-2 bg-red-500/10 text-red-400 text-sm border-b border-border">{previewError}</div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-hover">
                  <th className="px-3 py-2.5 w-10">
                    <input
                      type="checkbox"
                      checked={selectedEmails.size === Math.min(prospects.length, 50)}
                      onChange={toggleAll}
                      className="rounded"
                    />
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide">Company</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide">Email</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide">Tier</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-text-muted uppercase tracking-wide">PIC</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map(p => {
                  const checked = selectedEmails.has(p.email);
                  const disabled = !checked && selectedEmails.size >= 50;
                  return (
                    <tr
                      key={p.email}
                      onClick={() => !disabled && toggleEmail(p.email)}
                      className={`border-b border-border/50 cursor-pointer transition-colors ${
                        checked ? "bg-accent/5" : disabled ? "opacity-40" : "hover:bg-surface-hover"
                      }`}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleEmail(p.email)}
                          onClick={e => e.stopPropagation()}
                          className="rounded"
                        />
                      </td>
                      <td className="px-3 py-2 font-medium text-text">{p.company}</td>
                      <td className="px-3 py-2 text-text-muted">{p.email}</td>
                      <td className="px-3 py-2">
                        <span className="text-xs font-medium text-accent">{p.tier}</span>
                      </td>
                      <td className="px-3 py-2 text-text-muted">{p.pic}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Step 3: Preview Email */}
      {step === 3 && (
        <div className="rounded-xl border border-border bg-surface space-y-0">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div>
              <h2 className="font-semibold text-text">Preview Email</h2>
              <p className="text-xs text-text-muted mt-0.5">Preview mẫu cho CNEE đầu tiên</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(2)} className="px-3 py-1.5 text-sm rounded-lg border border-border text-text-muted hover:text-text transition-colors">← Back</button>
              <button
                onClick={() => setStep(4)}
                className="px-4 py-1.5 text-sm rounded-lg bg-primary text-white font-medium hover:bg-primary/90 transition-colors"
              >
                Approve →
              </button>
            </div>
          </div>
          <div className="p-4">
            <div
              className="rounded-lg border border-border bg-white text-gray-900 p-4 text-sm overflow-auto max-h-[500px]"
              dangerouslySetInnerHTML={{ __html: previewHtml || "<p class='text-gray-400'>No preview available.</p>" }}
            />
          </div>
        </div>
      )}

      {/* Step 4: Approve & Queue */}
      {step === 4 && (
        <div className="rounded-xl border border-border bg-surface p-6 space-y-4">
          <h2 className="font-semibold text-text">Queue Emails</h2>
          {!queueResult ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-surface-hover border border-border p-4 space-y-2">
                <p className="text-sm text-text"><span className="text-text-muted">Campaign:</span> <strong>{selectedCampaign}</strong></p>
                <p className="text-sm text-text"><span className="text-text-muted">Emails selected:</span> <strong>{selectedEmails.size}</strong></p>
                <p className="text-sm text-text"><span className="text-text-muted">Template:</span> <strong>Professional</strong></p>
              </div>
              {queueError && (
                <p className="text-sm text-red-400">{queueError}</p>
              )}
              <div className="flex gap-2">
                <button onClick={() => setStep(3)} className="px-3 py-2 text-sm rounded-lg border border-border text-text-muted hover:text-text transition-colors">← Back</button>
                <button
                  onClick={handleQueue}
                  disabled={queueing}
                  className="px-5 py-2 text-sm rounded-lg bg-accent text-white font-semibold disabled:opacity-50 hover:bg-accent/90 transition-colors"
                >
                  {queueing ? "Queueing..." : `Queue ${selectedEmails.size} emails`}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg bg-green-500/10 border border-green-500/30 p-5 text-center space-y-2">
                <div className="text-3xl font-bold text-green-400">{queueResult.queued}</div>
                <p className="font-semibold text-text">emails queued</p>
                <p className="text-sm text-text-muted">{queueResult.message || "Worker will send them shortly."}</p>
              </div>
              <button
                onClick={resetWizard}
                className="px-4 py-2 rounded-lg bg-surface border border-border text-sm text-text hover:bg-surface-hover transition-colors"
              >
                Start new campaign
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
