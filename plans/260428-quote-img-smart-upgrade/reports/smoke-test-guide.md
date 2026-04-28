# Hướng dẫn kiểm thử nâng cấp Quote Img — 28/04/2026

> **File này dùng cho Sếp tự kiểm tra sau khi code mới được deploy lên ERP_Master_v14.xlsm.**
> Đọc xong → làm theo 5 bước bên dưới → biết feature work hay không, không cần em hỗ trợ realtime.

---

## Trước khi test (chỉ làm 1 lần)

**Bước 1 — Đóng Excel hoàn toàn**
- Kiểm tra Task Manager không còn `EXCEL.EXE` nào đang chạy
- Nếu còn → kill hết rồi mới tiếp tục

**Bước 2 — (Khuyến nghị) Tắt Break-on-All-Errors trong VBE**
Bước này giúp tránh bị "stuck" như lần trước — không bắt buộc nhưng nên làm:
- Mở Excel bất kỳ file nào
- Bấm **Alt + F11** (mở VBE)
- Menu trên cùng → **Tools** → **Options** → tab **General**
- Mục **"Error Trapping"** → chọn **"Break on Unhandled Errors"** (KHÔNG chọn "Break on All Errors")
- Bấm **OK**
- Đóng VBE → đóng Excel

**Bước 3 — Mở file test**
- Mở `ERP_Master_v14.xlsm` bình thường

---

## Test 1 — Báo giá 1 cảng nhanh

**Anh đang đứng đâu**: phòng khách hỏi giá HPH → USLAX gấp

**Các bước thực hiện**:
1. Sang sheet **Pricing Dry**
2. Trong ribbon: chọn **POL = HPH**, **POD = USLAX**
3. Click vào 1 dòng giá bất kỳ → điền margin
4. Bấm nút **QUOTE** → hiện hộp thoại "Quote ... created"
5. **Vẫn ở sheet Pricing** (không sang sheet Quotes) → bấm nút **📷 Quote Img**

**Kết quả mong đợi**:
- ✅ Tự nhảy sang sheet **Quotes**
- ✅ Browser hoặc email mở ra ảnh báo giá vừa tạo
- ✅ Ảnh hiển thị đúng 1 dòng HPH → USLAX

**Nếu sai**: chụp màn hình → nhắn cho em biết ở bước nào sai

---

## Test 2 — Báo giá nhiều cảng (multi-port)

**Anh đang đứng đâu**: khách hỏi báo giá cùng lúc 5 cảng USLAX, USLGB, NYC, ATL, SAV

**Các bước thực hiện**:
1. Vẫn ở sheet **Pricing Dry**
2. Lần lượt với mỗi cảng:
   - Chọn **POD = USLAX** → click rate → điền margin → bấm **QUOTE**
   - Chọn **POD = USLGB** → click rate → điền margin → bấm **QUOTE**
   - Chọn **POD = NYC** → click rate → điền margin → bấm **QUOTE**
   - Chọn **POD = ATL** → click rate → điền margin → bấm **QUOTE**
   - Chọn **POD = SAV** → click rate → điền margin → bấm **QUOTE**
3. Sau 5 lần **vẫn ở sheet Pricing** → bấm **📷 Quote Img** **chỉ 1 lần duy nhất**

**Kết quả mong đợi**:
- ✅ Tự nhảy sang sheet **Quotes**
- ✅ Browser/email mở ra ảnh chứa **nhóm 5 cảng** vừa báo
- ✅ Không cần kéo chọn dòng nào trước khi bấm

**Nếu sai**: chụp màn hình → nhắn em ở bước nào sai

---

## Test 3 — Render lại quote cũ (chọn dòng cụ thể)

**Anh đang đứng đâu**: muốn render lại ảnh quote từ tuần trước

**Các bước thực hiện**:
1. Sang sheet **Quotes**
2. Tìm và **click chọn 1 dòng** quote cũ (hoặc kéo chọn N dòng)
3. Bấm **📷 Quote Img**

**Kết quả mong đợi**:
- ✅ Render đúng **N dòng anh đã chọn**
- ✅ Không tự nhảy sang dòng khác

**Nếu sai**: báo em biết đã chọn mấy dòng mà ra kết quả sai

---

## Test 4 — Quay lại Pricing thì bảng giá không bị "trắng"

**Anh đang đứng đâu**: đang xem giá HPH → USLAX ARB, đã filter sẵn

**Các bước thực hiện**:
1. Đang ở sheet **Pricing Dry** — bảng giá đang hiện HPH → USLAX
2. Sang sheet **Quotes** (bấm tab Quotes)
3. **Quay lại** sheet **Pricing Dry** (bấm lại tab Pricing)
4. Nhìn bảng giá → kiểm tra

**Kết quả mong đợi**:
- ✅ Bảng giá **vẫn hiện y nguyên** HPH → USLAX
- ✅ Không bị "trắng" như trước
- ✅ **Không cần gõ lại** ô tìm kiếm

**Nếu sai**: báo em "lọc bị reset ở bước X" kèm chụp màn hình

---

## Test 5 — Chưa có quote nào mà bấm Quote Img

**Anh đang đứng đâu**: sheet **Quotes đang trống** (chưa báo giá gì hôm nay)

**Các bước thực hiện**:
1. Sang sheet **Quotes**
2. Xác nhận bảng **trống** (không có dòng nào)
3. **Không chọn dòng nào** → bấm **📷 Quote Img**

**Kết quả mong đợi**:
- ✅ Hiện hộp thoại thông báo **"Chưa có quote nào hôm nay"** (hoặc tương tự)
- ✅ Excel **không crash**, không bị lỗi

**Nếu sai**: báo em "bấm Quote Img lúc trống → bị lỗi X"

---

## Nếu CÓ TEST FAIL → Rollback (5 phút)

Nếu có bất kỳ test nào fail, anh làm theo các bước sau để quay về bản cũ:

**Bước 1 — Đóng Excel**
- Đóng `ERP_Master_v14.xlsm` hoàn toàn
- Kiểm tra Task Manager không còn `EXCEL.EXE`

**Bước 2 — Copy 4 file backup từ OneDrive**
- Copy từ `D:/OneDrive/NelsonData/erp/backup/` về đè vào thư mục `ERP/`:
  - `erp-v14-ribbon-callbacks.bas.bak` → `erp-v14-ribbon-callbacks.bas`
  - `erp-v14-thisworkbook.bas.bak` → `erp-v14-thisworkbook.bas`
  - `erp-v14-QuoteImage.bas.bak` → `erp-v14-QuoteImage.bas`
  - `erp-v14-main.bas.bak` → `erp-v14-main.bas`

**Bước 3 — Reimport VBA modules**
- Chạy file `reimport-erp-vba-modules.py` (trong thư mục `scripts/`)
- **Lưu ý quan trọng**: Excel phải đóng hoàn toàn trước khi chạy script này

**Bước 4 — Mở lại Excel**
- Mở `ERP_Master_v14.xlsm` → verify nút **📷 Quote Img** trở lại hành vi cũ

---

## Báo cáo cho em sau khi test xong

| Test | Kết quả | Ghi chú |
|------|---------|---------|
| Test 1 (1 cảng) | ✅ Pass / ❌ Fail | |
| Test 2 (5 cảng) | ✅ Pass / ❌ Fail | |
| Test 3 (chọn dòng cũ) | ✅ Pass / ❌ Fail | |
| Test 4 (filter restore) | ✅ Pass / ❌ Fail | |
| Test 5 (empty edge) | ✅ Pass / ❌ Fail | |

**Nếu PASS hết 5 test**: nhắn em **"OK ngon, commit đi"** → em commit + push code.

**Nếu có FAIL**: chụp màn hình → gửi cho em → em vào fix rồi thông báo lại.