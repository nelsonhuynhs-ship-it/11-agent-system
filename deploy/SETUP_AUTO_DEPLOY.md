# Hướng dẫn Setup Auto-Deploy (làm 1 lần duy nhất)

Sau khi setup xong: **push code là tự deploy, không cần làm gì thêm**.

---

## Bước 1 — Lấy SSH Key của VPS

Mở PowerShell, chạy:
```powershell
Get-Content C:\Users\ADMIN\.ssh\id_nelson_vps
```

Copy toàn bộ nội dung từ `-----BEGIN OPENSSH PRIVATE KEY-----` đến `-----END OPENSSH PRIVATE KEY-----`.

---

## Bước 2 — Lấy Telegram Bot Token + Chat ID

Anh đã có từ bot Telegram đang chạy. Nếu quên:
- **Bot Token**: xem file `api/.env` → dòng `TELEGRAM_BOT_TOKEN=...`
- **Chat ID**: xem file `api/.env` → dòng `TELEGRAM_CHAT_ID=...`

---

## Bước 3 — Vào GitHub thêm Secrets

1. Mở trình duyệt → vào: **https://github.com/nelsonhuynhs-ship-it/FreightBrian/settings/secrets/actions**
2. Bấm **"New repository secret"** → thêm từng cái:

| Secret Name | Giá trị |
|-------------|---------|
| `VPS_SSH_KEY` | Nội dung SSH key từ Bước 1 |
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID của anh |

3. Mỗi cái: điền tên → paste giá trị → bấm **"Add secret"**

---

## Bước 4 — Setup thư mục trên VPS (1 lần)

Mở PowerShell, chạy:
```powershell
ssh -i C:\Users\ADMIN\.ssh\id_nelson_vps root@14.225.207.145
```

Trong VPS, chạy:
```bash
# Tạo thư mục staging cho git
mkdir -p /home/nelson/_repo_temp
cd /home/nelson/_repo_temp
git clone https://github.com/nelsonhuynhs-ship-it/FreightBrian.git .
echo "Done - VPS ready"
```

---

## Bước 5 — Push S14A lên GitHub (trigger deploy đầu tiên)

Từ PowerShell trên máy PC:
```powershell
cd "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
git push origin main
```

---

## Sau đó — Quy trình làm việc hàng ngày

```
Anh/Mentee sửa code
       ↓
git push origin main  (hoặc Cowork tự push)
       ↓
GitHub tự chạy test ~1 phút
       ↓
Nếu test PASS → tự deploy VPS
       ↓
Telegram báo anh: "Deploy xong!" hoặc "Deploy thất bại!"
       ↓
Anh không cần làm gì cả
```

---

## Kiểm tra trạng thái deploy

- **Xem live**: https://github.com/nelsonhuynhs-ship-it/FreightBrian/actions
- **Telegram**: anh nhận thông báo tự động sau mỗi deploy

---

## Nếu deploy fail

Telegram sẽ gửi link thẳng đến log. Anh bấm vào → xem dòng nào đỏ → báo em fix.
