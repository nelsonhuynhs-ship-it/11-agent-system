---
phase: 1
title: "Schema Audit — Inventory all schema definitions"
status: pending
priority: P1
effort: "1h"
dependencies: []
---

# Phase 1: Schema Audit

## Overview

Audit tất cả schema definitions hiện có trong docs/ + code để biết đã có gì, còn thiếu gì, và duplicate ở đâu.

## Requirements
- Functional: Tìm tất cả places định nghĩa schema (docs/*.md + code/*.py + YAML files)
- Non-functional: Không thay đổi gì, chỉ inventory

## Architecture

Audit 3 categories:

**Category A — Schema Definitions (docs/):**
- `MASTER_V7_SCHEMA.md` — CNEE column definitions (62 cols)
- `ARB_ORIGIN_MAPPING.md` — Country → POL + ARB rules
- `CHARGE_NAME_SOURCE_OF_TRUTH.md` — Rate charge names
- `rate-pipeline-contract.md` — Parquet rate schema

**Category B — Code Schema References (email_engine/):**
- `rule_engine.py:ARB_MAPPING` — Country → POL default + arb_key
- `rule_engine.py:VN_PORTS` → `load_vn_domestic_ports()` (YAML)
- `commodity_groups.yaml` — commodity_groups, pol_patterns, arb_origins, vn_domestic_ports
- `web_server.py:_get_cnee_df()` — DataFrame loading + column usage

**Category C — Code Schema References (ERP/):**
- VBA modules đọc cùng parquet columns
- ERP refresh scripts

## Implementation Steps

1. Đọc và extract key schema definitions từ docs/
2. Đọc và extract key schema từ code (ARB_MAPPING, commodity_groups.yaml)
3. List tất cả column names từ MASTER_V7_SCHEMA.md
4. List tất cả business rules từ ARB_ORIGIN_MAPPING.md
5. Identify duplicates (cùng 1 rule định nghĩa ở 2+ chỗ)
6. Viết audit report ngắn vào `plans/260503-shared-schema/reports/schema-audit.md`

## Success Criteria
- [ ] Audit report list đầy đủ schema definition locations
- [ ] Duplicate definitions được标记
- [ ] Missing documentation được noted

## Risk Assessment
- Risk: Có thể miss VBA schema definitions không đọc hết VBA code
- Mitigation: Chỉ audit Python code trước, VBA audit là Phase 2

---

**Output:** `plans/260503-shared-schema/reports/schema-audit.md`
