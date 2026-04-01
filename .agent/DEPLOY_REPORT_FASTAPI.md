# 🚀 DEPLOY REPORT — FASTAPI → VPS

> **Deploy Date:** 2026-03-23 07:30 +07:00  
> **API URL:** http://14.225.207.145:8100  
> **STATUS:** 🟢 **ONLINE** (systemd service `nelson-api`)

---

## ENDPOINTS VERIFIED

| Endpoint | Status | Response | Notes |
|---|---|---|---|
| `/api/health` | ✅ OK | 200 — `{"status":"ok"}` | Instant |
| `/api/dashboard/charts` | ✅ OK | 200 — 384 bytes | ~30s first load (Parquet) |
| `/api/customers` | ✅ OK | 200 — 26 bytes | Instant |
| `/api/shipments` | ✅ OK | 200 — 26 bytes | Instant |
| `/api/quotes` | ✅ OK | 200 — 6,199 bytes | Instant |
| `/api/team` | ✅ OK | 200 — 24 bytes | Instant |
| `/api/carrier/freetime` | ✅ OK | 200 — 3,295 bytes | Instant |
| `/api/rates/stats` | ✅ OK | 200 — 88 bytes | OK after Parquet cache |
| `/api/rates/matrix` | ⚠ TIMEOUT | OOM risk | **VPS 1.9GB RAM limitation** |

## DEPLOYMENT DETAILS

| Item | Detail |
|---|---|
| **VPS** | 14.225.207.145 (Ubuntu, 1.9GB RAM, 33GB disk) |
| **Python** | 3.12.3 (venv at `/home/nelson/venv/`) |
| **Service** | systemd `nelson-api` — enabled, auto-restart |
| **Port** | 8100 (not conflicting with TraSuaPOS 3000/3001 or Next.js 3002) |
| **CORS** | Added `14.225.207.145:3002` + `:8100` |
| **Swap** | ✅ Created 2GB swapfile (persistent via fstab) |
| **Log files** | `/home/nelson/logs/api.log` + `api_error.log` |

## FILES DEPLOYED

```
/home/nelson/
├── api/                  # FastAPI application
│   ├── app.py            # Entry point v2.3.0
│   ├── config.py         # Fixed CORS (backup: config.py.bak)
│   ├── data_access.py    # Parquet loader
│   ├── routers/          # 12 router files
│   ├── middleware/        # CORS, rate limit, error handler
│   ├── workers/          # Email, intelligence, evaluator
│   ├── data/             # quotes.json, events.jsonl
│   └── ...
├── Pricing_Engine/data/
│   ├── Cleaned_Master_History.parquet  (12MB compressed)
│   └── carrier_rules.json             (12KB)
├── venv/                 # Python virtual environment
├── logs/                 # API logs
├── requirements_vps.txt  # Pip dependencies
└── swapfile              # 2GB swap (created for OOM prevention)
```

## ISSUES FOUND

### 🔴 `/api/rates/matrix` OOM / Timeout
- **Cause:** 10.2M-row Parquet expansion in memory exceeds 1.9GB RAM
- **Impact:** Pricing page matrix view won't load
- **Fix options:**
  1. **Pre-filter Parquet** on VPS — only keep last 60 days of rates (90% reduction)
  2. **Upgrade VPS RAM** to 4GB (~$5/mo extra)
  3. **Add column-level read** — only load needed columns (POL, POD, Carrier, Amount, Container_Type)
  4. **Lazy-load** — don't load full Parquet on first request, use chunked reading

### 🟡 First Request Slow (~30s)
- Dashboard/charts takes ~30s on first hit (cold Parquet load)
- Subsequent requests are instant (cached in memory)
- **Mitigation:** API workers pre-warm Parquet on startup

## SYSTEMD SERVICE

```ini
# /etc/systemd/system/nelson-api.service
[Service]
WorkingDirectory=/home/nelson/api
ExecStart=/home/nelson/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8100
Restart=always
RestartSec=10
```

**Commands:**
```bash
systemctl status nelson-api     # Check status
systemctl restart nelson-api    # Restart
journalctl -u nelson-api -f     # Live logs
tail -f /home/nelson/logs/api.log  # App logs
```

## NEXT STEPS

1. ✅ Open http://14.225.207.145:3002 → verify dashboard/quotes/shipments show data
2. 🟡 Fix `/api/rates/matrix` OOM → pre-filter Parquet to last 60 days
3. 🟡 Add Parquet pre-warm on startup (load in lifespan handler)
4. 🟢 Deploy bot_v5 to VPS (separate service)
