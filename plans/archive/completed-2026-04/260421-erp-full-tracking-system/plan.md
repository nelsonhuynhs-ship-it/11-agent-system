---
title: "ERP Full Tracking System — Booking Pool + 7-Stage Tooltip + 48h SI Alert"
description: "Complete booking lifecycle tracking: Keep Space + Direct flows, Booking Pool sheet, scanner auto-populate, MarkQuoteWin link mode, SI/CY/Payment metadata, 48h Telegram alerts"
status: completed
shipped: 2026-04-22
commits: [phase-1-5 ship, ab036ea si-alert-integration, 8682e0b si-merge]
priority: P1
effort: 10h
branch: main
tags: [erp-v14, vba, scanner, booking, si-alert, keep-space, tracking]
created: 2026-04-21
owner: Nelson
related: [260421-erp-tracking-auto-sync]
---

# Plan — ERP Full Tracking System

## Goal

Ship complete booking lifecycle tracking in ERP v14 covering BOTH flows:
- **Direct**: Nelson RQ with customer → Custeam booking → fwd customer → Docs → ATD → Delivered → Paid
- **Keep Space**: Nelson RQ internal "keep" → Custeam booking HOLDING → later link to customer after WIN → continue as Direct

Scanner auto-parses Custeam booking mails (format confirmed by Nelson), populates new `Booking Pool` sheet, enables MarkQuoteWin to LINK existing keep bookings. Active Jobs TRACKING tooltip upgrades to 7 stages + SI/CY/Payment metadata. Daily cron fires 48h SI warning to Nelson.

## Nelson-Confirmed Facts

1. **Subject patterns** (scanner parses both):
   - Direct: `SORACHI BKG SGNG83555500 // HCM-TACOMA, WA // 1X40HC // ETD 1May - ETA 24May // NELSON // ONE // YM TOPMOST 024E // PO# LP-95`
   - Keep Space: `[KEEP SPACE +SORACHI] | HCM-TACOMA, WA | 1X40HC | ONE | NELSON`
2. **SI/CY in body** (Custeam template):
   - `• S/I cut off time: 14:00 APR 21`
   - `• Deadline amendment: 11:00 APR 22`
3. **OPS asks for SI** (48h template):
   - `Pls kindly send your SI and VGM as soon as possible for our smoothly arrangement.`
4. **Release to customer** = Nelson reply mail Custeam OR new mail with same subject (remove "KEEP SPACE")
5. **1 keep booking = 1 customer** (no split logic needed)

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ EMAIL INBOX                                                    │
│ ├─ Custeam booking mail (Direct or Keep Space)                 │
│ ├─ Custeam SI/CY update                                        │
│ ├─ OPS SI request 48h template                                 │
│ └─ Nelson release forward to customer                          │
└─────────────────────┬─────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────────────────────┐
│ shipment_brain.py (fixed today — OneDrive config paths)       │
│ ├─ booking_parser.py (NEW) — regex 9 fields, both delimiters  │
│ ├─ Append booking_pool_state.jsonl                            │
│ └─ Hook events: release / SI_update / SI_48h_req              │
└─────────────────────┬─────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────────────────────┐
│ ERP xlsm                                                       │
│ ├─ Sheet "Booking Pool" (NEW)                                  │
│ │   BKG | Carrier | Customer | Route | CONT × QTY |           │
│ │   ETD | ETA | SI_CutOff | CY_Close | Vessel | PO# |         │
│ │   Status (HOLDING/ASSIGNED/EXPIRED) | Link_AJ | Created      │
│ │   VBA button "🔄 Sync Pool" flush jsonl                      │
│ │   VBA button "📥 New Keep Space" manual insert               │
│ ├─ Sheet "Active Jobs" (enhanced)                              │
│ │   MarkQuoteWin popup: "New" or "Link from Pool"              │
│ │   TRACKING tooltip: 7 stages + SI/CY/Payment metadata        │
│ │   Keep Space: CUSTOMER = "[KEEP SPACE SORACHI]" → after      │
│ │   release → "SORACHI"                                        │
│ └─ CustomUI: ribbon buttons grpBookingPool                     │
└─────────────────────┬─────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────────────────────┐
│ Daily cron 08:00 (si_48h_alert.py)                            │
│ └─ Scan Active Jobs → SI_CutOff − now < 48h AND Docs NOT done │
│    → Telegram: "SORACHI BKG X — SI còn 30h, check plan khách"  │
└───────────────────────────────────────────────────────────────┘
```

## 5 Phases

| # | Phase | Effort | Deliverable |
|---|-------|--------|-------------|
| 1 | Booking Parser + Pool Sheet | 3h | `booking_parser.py` + Pool schema + VBA "New Keep Space" button |
| 2 | Scanner Integration | 2.5h | shipment_brain hook: parse booking mails → Pool sidecar + release/SI events |
| 3 | MarkQuoteWin Link Mode | 2h | VBA popup "Use Pool BKG" + Pool→AJ transfer |
| 4 | TRACKING 7-stage Tooltip | 1.5h | New stage names + SI/CY/Payment metadata lines |
| 5 | 48h SI Alert Cron | 1h | `si_48h_alert.py` + Task Scheduler daily 08:00 + Telegram |

## 7 Tracking Stages (replace current 7)

| # | Stage | Trigger |
|---|-------|---------|
| 1 | **Request** | Nelson RQ email (keep or direct) |
| 2 | **Booked** | Custeam booking mail received |
| 3 | **To Customer** | Nelson forward to customer |
| 4 | **Docs** | SI cut + HBL issued + DN sent |
| 5 | **ATD** | Vessel departed |
| 6 | **ETA** | Arrival expected |
| 7 | **Delivered** | CNEE confirms receipt |

**Metadata lines** (below dots, not taking dot slot):
- 📅 **SI Cut Off** — date + countdown (red <48h, amber <72h)
- 📅 **CY Close** — date
- 💰 **Payment** — PENDING/PAID/OVERDUE + due date
- 📞 **PO#** — if present in subject

## Booking Pool Schema

```
Col A:  BKG_No           Primary key
Col B:  Carrier          ONE / HPL / ZIM / ...
Col C:  Customer         SORACHI / NELSON (keep) / [KEEP SPACE]
Col D:  POL              HCM / HPH
Col E:  POD              TACOMA / LAX
Col F:  Final_Dest       TACOMA, WA
Col G:  Container        40HC / 20DC / 40RF
Col H:  Qty              1 / 2 / 9
Col I:  ETD              date
Col J:  ETA              date
Col K:  SI_CutOff        datetime (from body regex)
Col L:  CY_Close         datetime (from body regex)
Col M:  Vessel           YM TOPMOST
Col N:  Voyage           024E
Col O:  PO_Number        LP-95 (optional)
Col P:  Status           HOLDING / ASSIGNED / EXPIRED / CANCELLED
Col Q:  Link_AJ_Row      link to Active Jobs row if assigned
Col R:  Date_Booked      when Custeam sent mail
Col S:  Source_Mail_ID   Outlook EntryID (audit)
Col T:  Notes            free text
```

## Keep Space CUSTOMER Display Convention

**While HOLDING:** Active Jobs CUSTOMER shows `"[KEEP SPACE SORACHI]"` → Nelson instantly sees it's hold-for-customer-X.
**After Release:** update to just `"SORACHI"`.

## Parser Regex Design

```python
# Accept both `|` and `//` as delimiters (auto-detect)
# Keep Space marker: starts with "[KEEP SPACE "
# Fields: customer, bkg, pol, pod, container_qty, etd, eta, sales, carrier, vessel_voyage, po

DELIM_RE = re.compile(r'\s*(?:\||//)\s*')  # | or // with optional whitespace

# BKG: alphanumeric 8-20 chars after "BKG "
BKG_RE = re.compile(r'BKG\s+([A-Z0-9]{8,20})', re.I)

# Route: POL-POD (possibly with state)
ROUTE_RE = re.compile(r'([A-Z]{3,4})\s*-\s*([A-Z]{3,6}(?:,\s*[A-Z]{2})?)')

# Container: 1X40HC, 2X40RF
CONTQTY_RE = re.compile(r'(\d+)\s*[Xx×]\s*(\d+(?:HC|DC|GP|RF|HQ|NOR))')

# ETD/ETA: "ETD 1May - ETA 24May" or "1May" solo
DATE_RE = re.compile(r'(?:ETD\s+)?(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', re.I)

# Vessel voyage: uppercase name + digits + optional E/W/N/S
VESSEL_RE = re.compile(r'\b([A-Z][A-Z\s]{3,25}?\s+\d{3,4}[EWNS]?)\b')

# SI cutoff body: "S/I cut off time: 14:00 APR 21"
SI_CUT_RE = re.compile(r'S/?I\s+cut\s*off\s+time:\s*(\d{1,2}:\d{2})\s+(\w{3}\s+\d{1,2})', re.I)

# CY close body: "Deadline amendment: 11:00 APR 22"
CY_CLOSE_RE = re.compile(r'(?:Deadline\s+amendment|CY\s+close?):\s*(\d{1,2}:\d{2})\s+(\w{3}\s+\d{1,2})', re.I)
```

## Files Touched

**NEW (4):**
- `Pricing_Engine/booking_parser.py` — regex module
- `email_engine/core/booking_pool_writer.py` — sidecar writer
- `scripts/si-48h-alert.py` — daily cron
- `tests/test_booking_parser.py`

**MODIFY (4):**
- `email_engine/core/shipment_brain.py` — add booking mail detection hook
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — MarkQuoteWin Link mode + tooltip
- `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` — tooltip 7-stage + metadata
- `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` — ribbon group "Booking Pool"

**NEW XLSM SHEET:**
- `Booking Pool` (20 cols, header row, hidden audit cols S/T optional)

## Risks + Mitigations

| Risk | Sev | Mitigation |
|------|-----|------------|
| Subject format variation (delimiter mix, missing fields) | Med | Parser returns partial dict + logs missing fields; Nelson reviews Pool row |
| Scanner runs outside window (07:30-18:00) miss evening mails | Low | OK — mail stays in Inbox, caught next morning run |
| Keep Space never matches customer (abandoned keep) | Med | Status EXPIRED after 30d; Telegram weekly summary |
| Duplicate BKG across Pool + AJ | Med | Pool writer dedup by BKG; VBA transfer sets Status=ASSIGNED preventing re-use |
| SI datetime parse fails (locale, year missing) | Med | Assume current year; if month already past today, assume next year |
| Nelson forgets to "Sync Pool" | Low | Auto-flush on Workbook_Open via VBA Workbook event |
| Telegram rate limit 48h alerts | Low | Dedup per BKG + per day |

## Success Criteria

- [ ] Parse 5 real emails (3 Direct + 2 Keep Space) → 90%+ field accuracy
- [ ] Booking Pool auto-populates within 30min of Custeam mail arrival
- [ ] MarkQuoteWin popup works for both modes (Pool & New)
- [ ] TRACKING tooltip shows 7 stages + 3 metadata lines
- [ ] 48h alert fires on 1 test booking (manual trigger OK for UAT)
- [ ] 1-week soak: ≥3 bookings pass through full lifecycle Request → Delivered

## Rollback Plan

- Pool sheet can be hidden/deleted without affecting existing AJ
- VBA changes: revert .bas from git, reimport modules
- Scanner hook: comment out `on_booking_detected` call in shipment_brain
- Parser module: orphan file, safe to delete
- 48h alert: disable Task Scheduler entry

## Out of Scope (YAGNI)

- Multi-customer split of single booking (Nelson rule: 1:1)
- Custeam API integration (email only)
- Mobile push notification (Telegram only)
- Historical backfill >30d (new bookings only)
- Auto-compose customer release email (Nelson writes manually)
