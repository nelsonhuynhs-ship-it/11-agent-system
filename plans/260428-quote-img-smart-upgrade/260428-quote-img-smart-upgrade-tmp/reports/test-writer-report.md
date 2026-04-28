# Test Writer Report — test_quote_img_smart.py

## File created
- **Path**: `D:\NELSON\2. Areas\Engine_test\tests\test_quote_img_smart.py`
- **LOC**: 204 lines (function 57 lines + 11 test cases 147 lines)

## pytest output
```
11 passed in 0.06s
```

| # | Test | Status |
|---|------|--------|
| 1 | `test_happy_single_quote` | PASS |
| 2 | `test_happy_group_3_rows` | PASS |
| 3 | `test_stop_at_different_customer` | PASS |
| 4 | `test_stop_at_different_date` | PASS |
| 5 | `test_prefer_group_id_over_customer` | PASS |
| 6 | `test_empty_sheet` | PASS |
| 7 | `test_single_match_then_gap` | PASS |
| 8 | `test_group_id_empty_falls_back_to_customer_date` | PASS |
| 9 | `test_mixed_group_then_customer_match` | PASS |
| 10 | `test_date_object_coercion` | PASS |
| 11 | `test_row_5_empty_quote_id_returns_empty` | PASS |

## Spec ambiguities encountered

### 1. group_id precedence over customer+date
Task spec case 5 phrased: "prefer_group_id → returns [5] only". Traced VBA source
(`erp-v14-ribbon-callbacks.bas` line 3399-3403) — the VBA logic is:

```vba
If refGid <> "" And gid = refGid Then
    match = True
ElseIf cust = refCust And dt = refDate Then
    match = True
End If
```

This is NOT exclusive. When `refGid` is non-empty but `gid` differs, the `ElseIf` still
fires for same customer+date. So the test corrected to match actual VBA behavior:
all rows sharing customer+date are included even if group_id differs.

### 2. date coercion
VBA `Format(date, "yyyy-mm-dd")` accepts both date objects and date serials.
Python implementation handles both `datetime.date` objects and ISO string
"yyyy-mm-dd" — test coverage added for both paths.

### 3. row 5 empty quote_id
VBA exits early when row 5 quote_id is empty (line 3379-3381). Python port mirrors
this: returns `[]` without crash.
