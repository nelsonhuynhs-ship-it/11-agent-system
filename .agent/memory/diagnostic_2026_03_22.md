# DIAGNOSTIC REPORT — 2026-03-22

> READ-ONLY scan. Nothing was modified.

---

## BOT STATUS

### Token Conflict Analysis

| Config File | Bot Token | Gemini API Key |
|---|---|---|
| `TelegramBot\config.py` | `8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys` | `AIzaSyA1gxWxufQeWmnlFSEz_0FNzC2pjG0xvUc` |
| `.agent\agents\config.py` | `8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys` | `AIzaSyCR0sqBU9TH6ApfWuAdoTEAPbPfmQ9CKQ8` |

> **Token conflict: NO** — Same bot token. But **different Gemini API keys**.
>
> ⚠️ This means if BOTH systems try to poll Telegram simultaneously, only ONE can connect (Telegram enforces single polling per token). They won't conflict on identity, but **they WILL conflict on polling**.

### Running Processes

| PID | Process | Memory |
|---|---|---|
| 10572 | python.exe | 9,840 KB |
| 11888 | python.exe | 7,744 KB |

> ⚠️ **2 python.exe processes** running. Cannot determine which script each is running from tasklist alone. Could be CTO agent + bot, or two unrelated scripts.

### Port 8100 (Dashboard API)

```
Port 8100: ❌ DEAD — not listening
Only PID 8080 listening on random ports (127.0.0.1:56452, 56453, 56974)
```

### start_bot.bat

```bat
@echo off
title Nelson Freight Bot
:loop
python bot_v4.py          ← ⚠️ RUNS bot_v4.py NOT bot_v5.py!
timeout /t 10 /nobreak
goto loop
```

> 🔴 **STALE:** `start_bot.bat` still launches **bot_v4.py**! If this is what the scheduled task runs, the bot is running v4, not v5.

---

## EMAIL ENGINE

### Scheduled Tasks

| Task Name | Status |
|---|---|
| `Nelson Freight Bot v4` | ✅ Found (but runs v4!) |
| `NelsonRateImporter` | ✅ Found (×2 entries) |
| `NelsonRateImporter_Monday` | ✅ Found |
| Email-related tasks | ❌ None found |

> **Email Engine scheduled: NO** — No scheduled task for email_engine

### Scheduler Scripts

| Script | Size |
|---|---|
| `setup_brain_scheduler.ps1` | 3.7 KB |
| `setup_task_scheduler.ps1` | 6.5 KB |

### run_all.py — 13 Pipeline Steps

| Mode | Command | Does |
|---|---|---|
| 0 | COLLECT | Process .msg files → SQLite |
| 1 | SCAN | Bounce scan + classify replies |
| 2 | CLASSIFY | Reply tier classifier |
| 3 | SEND | Send emails by CMD |
| 4 | FULL | Clean → Scan → Classify → Follow-up → Send |
| 5 | DASHBOARD | Generate email_master.xlsx |
| 6 | TIER SEND | Semi-auto send to hot prospects |
| 7 | FOLLOW-UP | Follow-up alert engine |
| 8 | INGEST | Process Panjiva files |
| 9 | SEQUENCE | Auto-advance email sequences |
| 10 | BRIEFING | Generate nelson_briefing.xlsx |
| 11 | PARQUET | Export SQLite → Parquet |
| 12 | PST IMPORT | Import backup.pst into DB |

---

## GOOGLE SHEETS

```
Existing integration: NO
URL found: 0 (only 1 false positive in a knowledge JSON file)
```

> No Google Sheets API, no spreadsheet IDs, no gspread or googleapis references anywhere in the codebase.

---

## BOT V5 FEATURES

### Registered Commands (30 total)

| Sprint | Commands | Purpose |
|---|---|---|
| **Core** | `/start` `/help` `/status` `/reload` | System basics |
| **Core** | `/quote` | Rate lookup (free-text + slash) |
| **Core** | `/remember` `/customer` `/customers` `/forget` | Customer memory |
| **Core** | `/com` | Commission tracking |
| **Core** | `/briefing` | Morning briefing |
| **Core** | `/savequote` `/quotes` `/wins` `/losses` | Quote management |
| **Sprint 7** | `/markup` | Markup engine display |
| **Sprint 8** | `/crm` `/jobs` `/history` `/win` | CRM + Job integration |
| **Sprint 9** | `/analyze` | Win/loss analysis |
| **Sprint 10** | `/report` `/setkpi` `/kpi` | Dashboard + KPI |
| **Sprint 10b** | `/forecast` `/pipeline` `/setleads` | Forecast + Pipeline |
| **Sprint 12** | `/guardian` `/intel` `/book` `/ask` | Rate guard + Intel + Booking |
| **Sprint 12.5** | `/sync` `/predict` `/whywon` `/reachout` `/risk` | AI Brain features |
| **Intelligence** | `/trouble` `/route` `/churn` `/intelligence` `/custintel` `/memory` `/news` `/carrier` `/4c` `/market` `/opps` | 11 intelligence commands |

### Scheduled Jobs (3)

| Time | Job | Purpose |
|---|---|---|
| 05:30 | ETL Sync | Refresh Data Lake |
| 06:00 | Rate Expiry Guardian | Check expiring rates |
| 07:30 | Morning Briefing | Send daily briefing |

### Intelligence Features Status (4/10 active)

| # | Feature | Status | Command |
|---|---|---|---|
| 1 | Churn Radar | ✅ Active | `/churn` |
| 2 | Response DNA | ⏳ Phase 3 | — |
| 3 | Carrier Trouble | ✅ Active | `/trouble` |
| 4 | Commitment Score | ⏳ Phase 3 | — |
| 5 | Route Health | ✅ Active | `/route` |
| 6 | Ghost Pipeline | ⏳ Phase 2 | — |
| 7 | Coaching Radar | ⏳ Phase 5 | — |
| 8 | Market Sentiment | ⏳ Phase 4 | — |
| 9 | Relationship Depth | ✅ Active | `/intel` |
| 10 | Autopilot Mode | ⏳ Phase 5 | — |

### Customer Profiles (3)

| Customer | Lanes | Commodity | Priority | Behavior |
|---|---|---|---|---|
| **HML** | Denver, El Paso, Kansas | Stone, Slabs | Direct | Hàng nặng, weight limit |
| **SIRI** | El Paso | Office Nails | Cheapest | Price sensitive, check nhiều |
| **PANDA** | LAX, Long Beach | Mixed | Direct | Prefer MSK, thua CMA |

---

## 🔴 CRITICAL FINDINGS

| # | Finding | Risk | Action |
|---|---|---|---|
| 1 | **`start_bot.bat` runs bot_v4.py** | Scheduled task runs wrong version | Update to `bot_v5.py` |
| 2 | **2 python.exe running** | Potential polling conflict | Check what each PID runs |
| 3 | **Port 8100 = dead** | Dashboard API not serving | Start API if needed |
| 4 | **Different Gemini API keys** | Agent uses different key than Bot | Align or keep separate |
| 5 | **No email engine scheduler** | Email pipeline only manual | Create scheduled task |
| 6 | **No Google Sheets integration** | Manual data transfer | Build if needed |
