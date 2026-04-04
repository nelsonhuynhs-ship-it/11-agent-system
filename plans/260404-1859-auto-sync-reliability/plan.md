# Auto-Sync Reliability Plan
**Date:** 2026-04-04 | **Branch:** claude/magical-sutherland | **Status:** IMPLEMENTED

## Problem Statement
Hệ thống sync dữ liệu VPS hiện tại có nhiều single-point-of-failure:
- sync-data.yml chỉ chạy manual (workflow_dispatch)
- GH_DEPLOY_TOKEN có thể hết hạn bất kỳ lúc nào
- VPS rclone OneDrive chưa cài
- SQLite concurrent write gây race condition
- Email sync stalled (0 new events từ 15/03)

## Phases Overview

| Phase | Description | Priority | Status |
|-------|-------------|----------|--------|
| [Phase 1](phase-01-sync-data-cron.md) | VPS daily health check (was: sync-data) | P0 | ✅ REWORKED → health check |
| [Phase 2](phase-02-gh-token-audit.md) | GH_DEPLOY_TOKEN audit & long-lived PAT | P0 | ✅ SCRIPT + GUIDE |
| [Phase 3](phase-03-sqlite-wal.md) | Enable SQLite WAL mode | P1 | ✅ CODE DONE (13 files) |
| [Phase 4](phase-04-vps-rclone.md) | VPS rclone OneDrive setup guide | P1 | ✅ SCRIPT DONE |

## Dependencies
- Phase 1 ← Phase 2 (token phải valid trước khi cron chạy)
- Phase 3, 4: độc lập, có thể làm song song

## Key Files
| File | Purpose |
|------|---------|
| `.github/workflows/sync-data.yml` | Data sync workflow |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `shared/paths.py` | Central path resolver |
| `api/email_data/sync_state.json` | Email sync state |

## Success Criteria
- [x] sync-data.yml → renamed to VPS Health Check (data KHÔNG qua GitHub, chỉ OneDrive → rclone)
- [ ] GH_DEPLOY_TOKEN là PAT dài hạn — **Nelson cần tạo manual** (guide ready)
- [x] SQLite WAL mode enabled cho 13 files (shared/db_connect.py central)
- [x] VPS rclone guide + setup script ready (`deploy/vps-rclone-setup.sh`)
- [x] Health check có retry logic (3 attempts)

## Files Changed
| File | Change |
|------|--------|
| `.github/workflows/sync-data.yml` | REWORKED → VPS health check (rclone status, data freshness, API/WebApp, disk) |
| `shared/db_connect.py` | **NEW** — Central SQLite WAL connection factory |
| `email_engine/core/data_collector.py` | 3x sqlite3.connect → get_db() |
| `email_engine/core/nelson_briefing.py` | sqlite3.connect → get_db(readonly) |
| `email_engine/core/pst_importer.py` | sqlite3.connect → get_db() |
| `email_engine/test_pipeline.py` | sqlite3.connect → get_db(readonly) |
| `TelegramBot/database.py` | Centralized to shared.db_connect |
| `TelegramBot/kpi_store.py` | sqlite3.connect → get_db() |
| `TelegramBot/memory/oracle.py` | sqlite3.connect → get_db() |
| `TelegramBot/agents/sentinel.py` | 2x sqlite3.connect → get_db(readonly) |
| `ERP/intelligence/tracking_manager.py` | Centralized to shared.db_connect |
| `ERP/intelligence/spot_cache.py` | Centralized to shared.db_connect |
| `api/routers/hpl_router.py` | sqlite3.connect → get_db(readonly) |
| `intelligence/rag_engine.py` | sqlite3.connect → get_db(readonly) |
| `intelligence/email_intel.py` | sqlite3.connect → get_db(readonly) |
| `deploy/check-gh-token.sh` | **NEW** — Token health check script |
| `deploy/vps-rclone-setup.sh` | **NEW** — One-click VPS rclone setup |

## Pending (Nelson Manual)
1. **Create Fine-grained PAT** → https://github.com/settings/tokens?type=beta
2. **Update GH_DEPLOY_TOKEN** secret in repo settings
3. **SSH VPS** → run `deploy/vps-rclone-setup.sh`
4. **Fill** `/opt/nelson/sync/.env` with Telegram credentials
