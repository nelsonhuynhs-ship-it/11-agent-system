---
phase: 2
title: "Consolidate into SHARED_SCHEMA.md"
status: pending
priority: P1
effort: "2h"
dependencies: [1]
---

# Phase 2: Consolidate into SHARED_SCHEMA.md

## Overview

Tạo `docs/SHARED_SCHEMA.md` — một file duy nhất chứa tất cả schema definitions + business rules, có reference/link đến source documents gốc (không duplicate).

## Requirements
- Functional: File cuối cùng đọc được bởi bất kỳ Claude CLI nào, hiểu đầy đủ data contract
- Non-functional: Không duplicate nội dung từ docs gốc — chỉ reference + summary

## Architecture

```
docs/SHARED_SCHEMA.md
├── 1. CNEE Master Schema (62 cols)
│   └── Link: [MASTER_V7_SCHEMA.md](MASTER_V7_SCHEMA.md) — full column index
├── 2. Commodity Groups (8 canonical groups)
│   └── Link: [commodity_groups.yaml](../email_engine/config/commodity_groups.yaml)
├── 3. Country → POL Default Rules
│   └── Summary: VN→HCM/HPH, MY→PKG, TH→BKK, CN→SHA/NGB, KH→HCM+ARB
├── 4. ARB Origin Mapping (6 origins)
│   └── Link: [ARB_ORIGIN_MAPPING.md](ARB_ORIGIN_MAPPING.md) — full rules
├── 5. Parquet Rate Schema
│   └── Link: [rate-pipeline-contract.md](rate-pipeline-contract.md)
├── 6. VN Domestic Ports (13 ports)
│   └── Source: commodity_groups.yaml → vn_domestic_ports
└── 7. Key Business Rules
    └── VN direct (no ARB) vs MY/TH/CN/KH transit (ARB surcharge)
```

## Implementation Steps

1. Tạo `docs/SHARED_SCHEMA.md` với structure trên
2. Mỗi section có: brief summary (2-3 dòng) + link đến source document
3. Critical rules (Country→POL mapping) viết trực tiếp vào file — không cần click link để hiểu
4. Add frontmatter: `last_updated`, `status: SOLE_SOURCE`

## Related Code Files
- Create: `docs/SHARED_SCHEMA.md`
- Modify: None
- Reference: `docs/MASTER_V7_SCHEMA.md`, `docs/ARB_ORIGIN_MAPPING.md`, `email_engine/config/commodity_groups.yaml`

## Success Criteria
- [ ] SHARED_SCHEMA.md tồn tại tại docs/
- [ ] 3 CLI đều đọc được file này khi start session
- [ ] Không duplicate content — chỉ reference + brief summaries
- [ ] Critical rules viết trực tiếp (để Claude đọc không cần click link)

## Risk Assessment
- Risk: Duplicate content với ARB_ORIGIN_MAPPING.md
- Mitigation: Chỉ viết summary ngắn + link, không copy toàn bộ

---

**Output:** `docs/SHARED_SCHEMA.md`
