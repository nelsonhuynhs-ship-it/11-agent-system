# ?? ACTIVE CONTEXT ? SESSION TRACKER

## ?? Session Hi?n T?i
- **Date:** 30/03/2026 (Laptop VP ? k?t th?c 17:35)
- **Status:** Sprint 12 ? Email Pipeline Recovery + Customer Ownership ?

---

## ? ?? Ho?n Th?nh (30/03/2026 ? Laptop VP)

### 1. Audit H? Th?ng Task Scheduler
- Ki?m tra 6 task ?ang ??ng k? trong Windows Task Scheduler
- X?c nh?n `NelsonUnifiedScanner` l? task ch?nh (30 ph?t/l?n, 4 jobs)
- Ph?t hi?n 2 l?i blocking pipeline t? ng?y 26/03

### 2. Fix l?i Mentee Classification (rules.json)
- **L?i:** `_mark_transferred` l? string n?m trong dict `members` ? crash `.get()`
- **Fix:** Chuy?n ra `_notes` section + fix BOM encoding (UTF-8 with BOM ? UTF-8 clean)
- **K?t qu?:** Test live ? 43 emails routed th?nh c?ng v?o ??ng folder mentee

### 3. Fix l?i Pricing Import (master_loader_v2.py)
- **L?i:** `sys.stdout.buffer` crash khi ch?y b?ng `pythonw.exe` (Task Scheduler)
- **Fix:** Th?m try/except guard, fallback khi stdout = None
- **K?t qu?:** Test live ? 3 files imported, 22,314 net new rates, Parquet 6.6M rows

### 4. D?n d?p Scheduler Scripts
- Archive `setup_task_scheduler.ps1` + `setup_brain_scheduler.ps1` ? `_archived_schedulers/`
- Gi? l?i `setup_unified_scheduler.ps1` l? workflow ch?nh duy nh?t

### 5. Si?t Rules Kh?ch H?ng (Customer Ownership)
- **customer_rules.json:** Th?m WEST FOOD (Direct), th?m field `owner` cho t?t c? 9 kh?ch Nelson
- **org_rules.json:** Th?m WEST FOOD v?o known_customers
- **ALPHA + MP GLOBAL:** ??i owner sang `mentee:johnny` (kh?ch c?a mentee, kh?ng ph?i Nelson)
- **Logic m?i:** Match t?n kh?ch ? lu?n = Nelson (d? mentee c? CC c?ng kh?ng ??i)

### 6. Upgrade Shipment Brain ? Owner Detection
- K?ch ho?t h?m `detect_mentee_pic()` (t?n t?i nh?ng ch?a bao gi? ???c g?i)
- Th?m `get_all_participants()` ? l?y sender + To + CC
- Th?m `determine_owner()` ? ph?n bi?t kh?ch Nelson vs mentee
- `detect_customer()` gi? tr? v? 3 gi? tr?: (name, type, owner)
- Migration 37 l? hi?n c?: 34 nelson, 2 mentee:blue, 1 mentee:lina

### 7. Fix Backup Parquet Rotation
- **Tr??c:** 13 file backup ? 10.5MB = 136 MB r?c n?m tr?n trong `data/`
- **Sau:** Backup v?o `data/_backup/`, ch? gi? 1 b?n m?i nh?t, t? x?a c?
- D?n s?ch 12 file c?, gi?i ph?ng ~125 MB

---

## ?? Files Changed (?? push GitHub)

### Commit 1: `c5abcc0` ? fix: email pipeline + customer ownership rules
```
email_engine/core/rules.json          ? Fix _mark_transferred + BOM
email_engine/core/shipment_brain.py   ? Owner detection activated
email_engine/core/org_rules.json      ? +WEST FOOD known_customers  
email_engine/data/customer_rules.json ? +WEST FOOD, +owner field
Pricing_Engine/scripts/master_loader_v2.py ? Fix pythonw.exe stdout crash
```

### Commit 2: `3f71ce8` ? fix: backup rotation
```
Pricing_Engine/rate_importer.py ? Backup ? _backup/, keep 1 only
```

---

## ?? System Status

```
[NelsonUnifiedScanner] ? 30min cycle ? all 4 jobs OK
[Mentee Classification] ? 43 emails routed
[Pricing Import]       ? 6,642,291 rows in Parquet
[Shipment Brain]       ? 37 shipments, all have owner
[Backup Rotation]      ? Auto-cleanup, 1 backup only
[Bot v5]               ? LIVE
[ERP]                  ? LIVE  
[WebApp]               ? Sprint 13-14
```

---

## ?? C?n Sync Cloud ? PC Home
- `email_engine/data/shipment_state.json` (37 l? ?? g?n owner)
- `email_engine/data/*.xlsx` (master files)
- `Pricing_Engine/data/Cleaned_Master_History.parquet` (6.6M rows, ~10.5MB)
- `Pricing_Engine/data/_backup/` (1 backup file)

## ?? PC Home ch? c?n
```bash
git pull origin main
```
R?i sync data t? cloud v?o ??ng folder.

---

## ?? NEXT ACTION

### PC Home ? Sprint 12 cont.
1. Review 22 l? UNKNOWN ? g?n ??ng customer name (d?a v?o email subject)
2. Test full unified scanner cycle t?i PC Home
3. Xem x?t th?m c?c kh?ch h?ng mentee v?o customer_rules.json (Blue, Jun, Otis, Jennie, Johnny c? kh?ch ri?ng n?o?)
4. Auto Quote email pipeline (from conversation 3926bd52)

### Sprint 13-14
- FastAPI backend
- Supabase + PostgreSQL migration
- WebApp real data integration
