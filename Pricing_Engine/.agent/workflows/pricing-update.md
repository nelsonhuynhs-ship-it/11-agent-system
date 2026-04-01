---
description: Daily pricing workflow - update pricing files, build parquet and MasterFullPricing
---

# Daily Pricing Update Workflow

## When new FAK/SCFI/Special Rate file arrives:

// turbo-all

### Step 1: Drop new file into `data/`
- FAK files → drop directly into `data/`
- SCFI raw → needs conversion first (Step 2a)
- Special Rate raw → needs conversion first (Step 2b)

### Step 2a: Convert SCFI (if raw format)
```
python run.py convert-scfi -i "data/Origin/HPL_SCFI_raw.xlsx"
```

### Step 2b: Convert Special Rate (if raw format)
```
python run.py convert-special -i "data/Origin/Fixed Rate Summary Table.xlsx"
```

### Step 3: Build parquet + MasterFullPricing
```
python run.py pricing
```

### Step 4: (Optional) Sync to ERP
```
python run.py full
```

### Step 5: Check status
```
python run.py status
```

---

## Weekly Custeam Update (Monday AM):

1. Drop `Product update WXX.docx` into `data/`
2. Run: `python run.py custeam`

## One-time Historical Load:

1. Drop historical FAK files into `data/raw/`
2. Run: `python run.py batch --dry-run` (preview)
3. Run: `python run.py batch` (execute)
