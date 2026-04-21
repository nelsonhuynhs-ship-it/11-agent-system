---
name: Auto CNEE Milestone Notify (MVP v2)
created: 2026-04-20
updated: 2026-04-20 (post red-team)
status: implemented-pending-soak
blockedBy: []
blocks: []
related: [260418-shipment-brain, 260416-email-nelson-solo-platform]
effort: ~4h (1 session, security-hardened MVP)
owner: Nelson
version: v2 (rewrite after red-team)
---

# Plan — Auto CNEE Milestone Notify (MVP v2)

**Created:** 2026-04-20
**Rewritten:** 2026-04-20 after red-team (see [red-team-findings.md](red-team-findings.md))
**Brainstorm:** [brainstorm-summary.md](brainstorm-summary.md)
**Old plan v1:** [archive-v1/](archive-v1/) (6 phase over-engineered design)

## Goal

Khi mail OPS Pudong báo ATD (real, verified) hoặc ETA còn 7 ngày → compose Outlook Draft EN cho CNEE → Nelson review + Send.

## What Changed vs v1

Red-team phát hiện v1 over-engineer + thiếu security. v2:

- **6 phases → 3 phases** (schema audit · MVP implementation · test+monitor)
- **Multiple modules → 1 file** `cnee_milestone.py` ~200 LOC
- **Dataclass/Enum → plain dict** (YAGNI)
- **Buffer pattern → inline list** (YAGNI)
- **schedule_override framework → separate Task Scheduler entry** (YAGNI)
- **+ Auth-Results header check** (reject spoofed mail)
- **+ OPS allowlist explicit** (not domain-wide)
- **+ Placeholder sanitization** (prevent BEC injection)
- **+ Rate limit + kill switch** (MAX_DRAFTS_PER_RUN=5, DAY=20)
- **+ JSON sidecar state** (no xlsm write from scanner — avoid race)
- **+ Check ActiveInspector** (don't steal Nelson's Outlook session)
- **+ Boolean dedup cols** (not substring match)

## Architecture

```
Scanner 30p/lần (existing NelsonUnifiedScanner)
    ↓
shipment_brain.py scan_and_update (existing) — at END of per-email loop:
    ↓
🆕 cnee_milestone.on_atd_detected(mail_item, stages, identifiers):
    • Auth-Results check (SPF/DKIM/DMARC pass)
    • OPS allowlist (explicit senders, not domain)
    • Blacklist keywords (VESSEL CHANGE, RVS ETD)
    • Rate limit check (MAX_DRAFTS_PER_RUN)
    • Kill switch file check
    • Extract ATD date (regex + cross-check with ReceivedTime)
    • Match Bkg → Active Jobs (recency filter ETD > today-60d)
    • Customer cross-check (mail context vs Active Jobs row)
    • Check CRM.AUTO_NOTIFY for customer
    • Sanitize all placeholders
    • Lookup CNEE email (CRM → Active Jobs fallback, support list)
    • Check Outlook.ActiveInspector → defer if busy
    • Compose draft (subject prefix [AUTO])
    • Write to milestone_state.jsonl sidecar (NOT xlsm)
    • Append Telegram summary list

Separate Task Scheduler entry 08:00 daily:
    python -m email_engine.core.cnee_milestone eta-reminder
    ↓
🆕 run_eta_reminder():
    • Loop Active Jobs
    • ETA in [today+1, today+8] window (not exact =7)
    • Same pipeline as above

End of scan → Flush Telegram list (1 consolidated message)

VBA "Sync milestones" button on ERP ribbon:
    • Read milestone_state.jsonl
    • Write ATD/NOTIFIED_ATD/NOTIFIED_ETA7 back to Active Jobs
    • Clear processed entries
```

## Phases

| # | File | Effort | Purpose | Status |
|---|------|--------|---------|--------|
| 01 | [Schema audit + minimal changes](phase-01-schema-audit.md) | 1h | Dump headers · add cols safely · backup | DONE 2026-04-20 |
| 02 | [MVP implementation (1 file)](phase-02-mvp-implementation.md) | 2h | cnee_milestone.py + tests + wire in | DONE 2026-04-20 |
| 03 | [Test + verify + monitor](phase-03-test-verify.md) | 1h | 6 smoke tests + 1 week soak | PARTIAL — pytest+smoke done, soak PENDING |

**Total: ~4h** (realistic, includes security)

## Files Touched

**New (3):**
- `email_engine/core/cnee_milestone.py` (~200 LOC, single file)
- `tests/test_cnee_milestone.py` (~60 LOC)
- `email_engine/data/milestone_state.jsonl` (runtime)

**Modified (3):**
- `email_engine/core/shipment_brain.py` — 5-line hook call at end of scan loop
- ERP_Master_v14.xlsm — CRM AUTO_NOTIFY col · Active Jobs 4 cols · VBA sync button
- Windows Task Scheduler — new entry 08:00 daily

**Unchanged (respect YAGNI):**
- `scanner_rules.json` (no new job entry needed)
- `outlook_scanner.py` (no new handler)
- Archive sheet

## Security Controls (baked in)

| Control | Implementation |
|---------|----------------|
| Mail auth | `PropertyAccessor` reads `Authentication-Results` header; require SPF+DKIM+DMARC=pass |
| Sender allowlist | Explicit SMTP list `{ops@pudongprime.vn, ...}` — NOT domain-wide |
| Placeholder sanitize | Strip `\n\r\t` · length cap per field · regex whitelist for HBL/Bkg format |
| Rate limit | MAX_DRAFTS_PER_RUN=5, MAX_DRAFTS_PER_DAY=20 |
| Kill switch | File `email_engine/data/AUTO_NOTIFY_DISABLED` → abort if exists |
| Blacklist | Regex `VESSEL CHANGE\|RVS ETD\|REVISED ETD\|CHANGE VESSEL\|NEW ETD` |
| Bulk detect | Reject mail with >3 Bkg (bulk sheet) |
| Date sanity | ATD ∈ [ReceivedTime - 30d, ReceivedTime + 1d] |
| Customer match | Cross-check mail sender context vs Active Jobs CUSTOMER |
| Recency filter | Only match Active Jobs rows with ETD > today - 60d |
| Outlook polite | Check `ActiveInspector()` — defer if Nelson composing |
| Subject visibility | Prefix `[AUTO]` so Nelson always notices |

## Data Changes (minimal)

**CRM sheet** (add 1 col):
- `AUTO_NOTIFY` (Y/N, default N)

**Active Jobs** (add 4 cols):
- `ATD_DATE` — JSON sidecar source of truth, copied in via VBA Sync button
- `ETA_DATE` — Nelson manual
- `NOTIFIED_ATD` — boolean
- `NOTIFIED_ETA7` — boolean

**Archive:** NO changes (dropped from v1 scope)

## Success Criteria (measurable)

- [ ] Week 1: Nelson actually Sends ≥5 auto-drafts (not deletes them)
- [ ] Week 1: Zero drafts with wrong customer or wrong Bkg (manual audit)
- [ ] Week 1: Zero xlsm corruption, zero Outlook freeze
- [ ] Week 1: Auth-Results filter rejects ≥1 test spoof mail

## Out of Scope (explicit YAGNI)

- Email history integrity check (v2 feature)
- Telegram token rotation (operations concern)
- Multi-language templates
- Draft send analytics / reply tracking
- Web UI for config
- Mobile app

## Risks (post red-team mitigation)

| Risk | Mitigation |
|------|-----------|
| OPS allowlist thiếu → miss legit mail | Weekly Telegram digest of rejected mails → review + add |
| Auth-Results header absent (internal mail) | Fallback: require allowlist SMTP match explicit |
| JSON sidecar → xlsm sync lag | VBA Workbook_Open auto-flush on ERP open |
| Date `.` separator miss | Unit test covers 5 formats |
| Nelson forgets kill switch exists | Doc in SYSTEM_STANDARDS + Telegram `/status` command |

## Red Team Review

### Session — 2026-04-20
**Findings:** 40 raw → 15 dedup (5 Security · 5 Correctness · 5 YAGNI) — all accepted
**Severity breakdown:** 7 Critical · 5 High · 3 Medium
**Action:** Full plan rewrite v1 → v2 (this document)
**Full report:** [red-team-findings.md](red-team-findings.md)

| # | Finding | Severity | Disposition | Applied |
|---|---------|----------|-------------|---------|
| A1 | Sender spoof | Critical | Accept | Phase 02 — Auth-Results check |
| A2 | Bkg trust boundary | Critical | Accept | Phase 02 — bulk detect + customer cross-check |
| A3 | Placeholder injection | Critical | Accept | Phase 02 — sanitize |
| A4 | No rate limit | Critical | Accept | Phase 02 — MAX_DRAFTS + kill switch |
| A5 | Self-send filter narrow | High | Accept | Phase 02 — explicit allowlist |
| B1 | Hook point missing | Critical | Accept | Phase 02 — verify actual shipment_brain API first |
| B2 | xlsm write race | Critical | Accept | Phase 02 — JSON sidecar, NO xlsm write from scanner |
| B3 | Outlook COM steal session | High | Accept | Phase 02 — ActiveInspector check |
| B4 | Date regex ambiguity | High | Accept | Phase 02 — ReceivedTime cross-check |
| B5 | Substring dedup | High | Accept | Phase 01 — boolean cols |
| C1 | Over-structured | Critical | Accept | Full rewrite to 1 file |
| C2 | Buffer/flush pattern | High | Accept | Delete — inline list |
| C3 | Schedule framework | High | Accept | Delete — separate Task Scheduler |
| C4 | Archive schema | Medium | Accept | Delete from scope |
| C5 | Effort understated | High | Accept | Re-estimated 4h realistic |
| D1 | Manual test only | Medium | Accept | Phase 03 — add pytest file |
| D2 | Rollback data loss | Medium | Accept | Phase 01 — COPY test + CSV export |
| D3 | Unmeasurable metrics | Medium | Accept | Binary "Send ≥5 drafts" criterion |
