# Phase 2: GH_DEPLOY_TOKEN Audit & Long-Lived PAT

## Context
- [deploy.yml](.github/workflows/deploy.yml) dùng `secrets.GH_DEPLOY_TOKEN`
- [sync-data.yml](.github/workflows/sync-data.yml) dùng `secrets.GH_DEPLOY_TOKEN`
- Memory ghi: "đang dùng OAuth gho_ token (ngắn hạn) → cần tạo PAT lâu dài"

## Overview
- **Priority:** P0
- **Status:** ⬜ TODO
- **Description:** Audit token hiện tại, tạo Fine-grained PAT dài hạn, update GitHub secrets

## Key Insights
- OAuth `gho_` tokens (từ GitHub OAuth App) có expiry ngắn (thường 8h hoặc refresh)
- Fine-grained PAT có thể set expiry 90 days hoặc custom
- Classic PAT (ghp_) không hết hạn nhưng scope rộng hơn cần thiết
- Token cần quyền: `contents:read` trên repo FreightBrian (để download release assets)
- Deploy cần: `contents:read+write` (git pull private repo)

## Requirements

### Functional
- Tạo Fine-grained PAT với quyền tối thiểu
- Expiry: 90 days minimum (set reminder trước 1 tuần)
- Update `GH_DEPLOY_TOKEN` trong GitHub repo secrets
- Verify cả deploy.yml và sync-data.yml hoạt động với token mới

### Scope cần thiết cho PAT
| Permission | Level | Dùng cho |
|-----------|-------|----------|
| Contents | Read & Write | git clone/pull private repo |
| Actions | Read | Check workflow status (optional) |

### Repository scope
- Only: `nelsonhuynhs-ship-it/FrieghtBrian`

## Implementation Steps (Manual — Nelson thực hiện)

### Step 1: Tạo Fine-grained PAT
1. Vào https://github.com/settings/tokens?type=beta
2. "Generate new token"
3. Name: `nelson-freight-deploy`
4. Expiry: **90 days** (hoặc "Custom" → chọn xa nhất có thể)
5. Resource owner: `nelsonhuynhs-ship-it`
6. Repository access: "Only select repositories" → chọn `FrieghtBrian`
7. Permissions:
   - Contents: **Read and write**
   - (Mọi thứ khác: No access)
8. "Generate token" → Copy token

### Step 2: Update GitHub Secret
1. Vào repo Settings → Secrets and variables → Actions
2. Edit `GH_DEPLOY_TOKEN` → paste token mới
3. Verify: có `VPS_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` không?

### Step 3: Test
1. Trigger `sync-data.yml` manual → verify success
2. Push 1 commit nhỏ → verify deploy.yml triggers OK

### Step 4: Set Reminder
- Đặt reminder trước expiry 1 tuần
- Hoặc: tạo scheduled task trong Claude Code để check

## Todo
- [ ] Nelson tạo Fine-grained PAT trên GitHub
- [ ] Update GH_DEPLOY_TOKEN secret
- [ ] Test sync-data.yml manual trigger
- [ ] Test deploy.yml with dummy commit
- [ ] Set expiry reminder (Telegram hoặc calendar)

## Success Criteria
- Token mới là Fine-grained PAT (bắt đầu `github_pat_`)
- Cả sync-data.yml và deploy.yml pass với token mới
- Expiry >= 90 days

## Risk Assessment
- **Nếu quên renew:** sync + deploy đều chết → cần Telegram alert trước expiry
- **Repo rename:** Nếu rename `FrieghtBrian` → `FreightBrian`, PAT scope cần update
- **Token leak:** Fine-grained PAT chỉ access 1 repo → blast radius nhỏ

## Note
⚠ **Repo name typo:** Workflow files ghi `FrieghtBrian` (thiếu chữ `h`). Nếu anh rename repo trong tương lai, cần update cả workflow files.

## Next Steps
- Sau khi token valid → Phase 1 cron sẽ hoạt động ổn định
