# Plan: Code/Data Separation — Nelson Freight System
**Date:** 2026-04-02 | **Status:** IMPLEMENTED

## Overview
Tách biệt source code (GitHub) và data files (OneDrive) để:
- Deploy code = git push only, không ảnh hưởng data
- Data sync giữa PC Home ↔ Laptop VP qua OneDrive
- VPS data sync qua rclone mỗi 15 phút
- Session awareness: hệ thống tự biết đang chạy trên máy nào

## Architecture

```
PC Home / Laptop VP:
  [OneDrive]\NelsonData\     ← data (auto-sync)
  [Home]\NelsonLocal\        ← logs + runtime (local only)
  D:\NELSON\..\Engine_test\  ← code (git)

VPS:
  /opt/nelson/code/          ← git clone (CI/CD)
  /opt/nelson/data/          ← rclone from OneDrive
  /opt/nelson/local/         ← VPS runtime
```

## Key Component: `shared/paths.py`
Central path resolver. 3 env vars: `NELSON_DATA_DIR`, `NELSON_LOCAL_DIR`, `NELSON_CODE_DIR`.
Machine detection via hostname + `NELSON_MACHINE` override.

## Changes Made
- [x] Phase 1: Created OneDrive NelsonData structure (39 data files copied)
- [x] Phase 2: Created `shared/paths.py` with machine detection
- [x] Phase 3: Updated 15+ code files to use `shared.paths`
- [x] Phase 4: Cleaned .gitignore, untracked 31 data files
- [x] Phase 5: Created rclone script, updated deploy.yml, .env.example

## Pending (manual on VPS)
- [ ] Install rclone on VPS, configure OneDrive remote
- [ ] Create /opt/nelson/{code,data,local,sync} directories
- [ ] Copy rclone-data.sh to /opt/nelson/sync/
- [ ] Add cron job: `*/15 * * * * /opt/nelson/sync/rclone-data.sh`
- [ ] Update systemd EnvironmentFile to include new env vars
- [ ] Setup same OneDrive structure on PC Home (if different machine)
