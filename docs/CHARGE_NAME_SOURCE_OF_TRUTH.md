# Charge Name — Source of Truth

**Last updated:** 2026-04-17
**Status:** 🔒 AUTHORITATIVE — mọi loader/consumer PHẢI tuân theo.

---

## ONE rule

Giá báo khách (all-in) trong Parquet luôn nằm ở:

```
Charge_Name = 'Total Ocean Freight'
```

**Không dùng** `BASIC O/F`, `Base Ocean Freight`, `HLCU Basic Cost` — đây là giá basic/net, **không phải** giá báo khách.

---

## So sánh 3 loại rate

| Rate Type | File | Sheet | Cột Excel = all-in | Cột Excel = basic | Cột chuẩn hoá vào Parquet |
|-----------|------|-------|--------------------|-------------------|--------------------------|
| **FAK** | `FAK_*.xlsx` | default | `ALL IN COST` (M-Q) | `BASIC O/F` (R-V) | `Total Ocean Freight` |
| **SCFI** (HPL only) | `SCFI_*.xlsx` | `RATE TABLE` | **`BASE O/F`** (H-J) ⚠ | `HLCU Offer` (K-M) | `Total Ocean Freight` |
| **FIX COC** | `FIX_*.xlsx` | `COC` | `Base Ocean Freight` (M-Q) | — | `Total Ocean Freight` |
| **FIX SOC HPL** | `FIX_*.xlsx` | `SOC HPL` | `TOTAL O/F` (G-I) | `BASIC O/F` (J-L) | `Total Ocean Freight` |

⚠ **SCFI khác FAK**: trong SCFI, `BASE O/F` đã là all-in (bao gồm DLF+ISPS+EMF+COMMISSION). Trong FAK, `BASIC O/F` là raw basic, phải dùng `ALL IN COST` mới là all-in.

---

## Source of truth

- **JSON:** `D:/OneDrive/NelsonData/pricing/mapping/CARRIER_RATE_MAPPING.json`
- **Helper:** `Pricing_Engine/charge_normalizer.py` — `normalize_charge_name(source, rate_type)`
- **Loaders:** `scripts/master_loader_v2.py` + `Pricing_Engine/rate_importer.py` đều gọi helper (không hardcode)
- **Validator:** `python Pricing_Engine/charge_normalizer.py validate` — chạy sau mỗi import; fail nếu Parquet chứa charge name cấm (`BASE O/F`, `HLCU Offer`)

---

## Incident 2026-04-17 — đã fix

**Triệu chứng:** Nelson báo giá thấp cho khách, đặc biệt inland route (Saint Louis, Memphis, Nashville). Sai đến -$1,561/40HQ trên HPL SCFI Norfolk → Saint Louis.

**Root cause:** Mapping cũ (`scripts/master_loader_v2.py` + `rate_importer.py`) hard-code ngược cho HPL SCFI:
```python
"BASE O/F":   "BASIC O/F"            # ❌ BASE O/F thực tế là ALL-IN
"HLCU Offer": "Total Ocean Freight"  # ❌ HLCU là basic cost, không phải all-in
```

Hậu quả: mọi consumer filter `Charge_Name LIKE '%TOTAL%'` lấy giá HLCU ($2,939) thay vì BASE O/F ($4,500) — under-quote khách $1,561.

**Fix:**
1. Đổi mapping `BASE O/F → Total Ocean Freight` và `HLCU Offer → HLCU Basic Cost`
2. Purge stale SCFI rows khỏi Parquet + re-import
3. Tạo `CARRIER_RATE_MAPPING.json` làm source of truth
4. Viết helper `charge_normalizer.py` + wire 2 loaders đọc JSON
5. Validator check forbidden stale names sau import

---

## Thêm rate type / carrier mới — Checklist

1. Mở `CARRIER_RATE_MAPPING.json`
2. Thêm block vào `rate_types.{NEW_TYPE}` với `file_pattern`, `sheets`, `charge_mapping.all_in`, `charge_mapping.basic`
3. Thêm entry tương ứng vào `charge_normalize_table.{NEW_TYPE}` và `charge_normalize_flat`
4. Chạy `python Pricing_Engine/charge_normalizer.py` để smoke-test
5. Import file mẫu → chạy validator → đảm bảo không có row với Charge_Name lạ

**Không được:** hardcode mapping trong code Python. Mọi mapping đi qua JSON.

---

## Related

- Pipeline email: `docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md`
- ERP v14: `docs/erp-v14-source-of-truth.md`
- ERP refresh rate: `D:/OneDrive/NelsonData/erp/refresh-v14.py`
