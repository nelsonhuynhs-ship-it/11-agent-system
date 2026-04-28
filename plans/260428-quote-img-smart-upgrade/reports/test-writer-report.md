

## Summary

**File created**: `D:\NELSON\2. Areas\Engine_test\tests\test_quote_img_smart.py` (204 LOC)
- Python reimplementation of `QuoteImage_CollectLatestGroup` (VBA `erp-v14-ribbon-callbacks.bas` ~line 3373)
- 11 test cases covering happy paths, edge cases, and spec ambiguities

**pytest result**: 11 passed in 0.06s

**Key spec ambiguity resolved**: Task case 5 said group_id "prefer" means "returns [5] only". Actual VBA logic uses `If ... ElseIf` (not exclusive `If/End If`), so customer+date fallback still fires when group_id differs. Test corrected to match actual VBA behavior.

**Report written to**: `D:\NELSON\2. Areas\Engine_test\plans\260428-quote-img-smart-upgrade/reports/test-writer-report.md`

```
TEST_RESULT: ALL_PASS
```
_coercion` | PASS |
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
