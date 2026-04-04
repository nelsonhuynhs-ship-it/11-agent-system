# Phase 1: Auto Sync-Data Workflow (Cron Schedule)

## Context
- [sync-data.yml](.github/workflows/sync-data.yml) — hiện chỉ `workflow_dispatch`
- [deploy.yml](.github/workflows/deploy.yml) — reference architecture

## Overview
- **Priority:** P0
- **Status:** ⬜ TODO
- **Description:** Thêm cron schedule vào sync-data.yml để tự động sync data từ GitHub Release → VPS mỗi ngày

## Key Insights
- Workflow hiện tại hoạt động đúng khi trigger manual
- Logic download assets theo file type (parquet, cnee, shipper) đã OK
- Health check cuối workflow đã có
- Thiếu: retry logic, error notification, scheduled trigger

## Requirements

### Functional
- Cron chạy 1 lần/ngày (6:00 AM VN = 23:00 UTC-1 = `0 23 * * *` UTC)
- Giữ `workflow_dispatch` để có thể trigger manual
- Telegram notification khi sync fail
- Retry download tối đa 3 lần mỗi asset

### Non-functional
- Không ảnh hưởng deploy.yml
- Backward compatible với manual trigger

## Architecture
```
GitHub Release (data-sync-v1)
    ↓ cron daily 6:00 VN
sync-data.yml
    ↓ SSH VPS
Download assets → /opt/nelson/data/
    ↓
Restart API container
    ↓
Health check + Telegram notify
```

## Related Code Files
- **Modify:** `.github/workflows/sync-data.yml`
- **No new files needed**

## Implementation Steps
1. Thêm `schedule` trigger vào `on:` block
2. Thêm retry logic cho curl download (3 attempts)
3. Thêm Telegram notification (success + failure)
4. Thêm checksum verification sau download
5. Test bằng `workflow_dispatch` trước

## Changes to sync-data.yml

```yaml
on:
  schedule:
    - cron: '0 23 * * *'  # 6:00 AM Vietnam time (UTC+7)
  workflow_dispatch:       # Keep manual trigger
```

Add retry + notification steps.

## Todo
- [ ] Add cron schedule trigger
- [ ] Add retry logic (3 attempts per asset)
- [ ] Add Telegram notification
- [ ] Add file size validation post-download
- [ ] Test via manual dispatch
- [ ] Verify cron fires next day

## Success Criteria
- sync-data.yml triggers automatically daily
- Failed downloads retry up to 3 times
- Nelson receives Telegram notification on success/failure

## Risk Assessment
- **Cron timezone:** GitHub Actions cron uses UTC — `0 23 * * *` = 6:00 AM VN (UTC+7)
- **Token expiry:** Depends on Phase 2 (PAT audit)
- **VPS downtime:** If VPS unreachable, SSH step fails → notification sent

## Next Steps
- Phase 2: Verify GH_DEPLOY_TOKEN validity
