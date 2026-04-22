# F8 YML Email Scan — Research Notes
**Date:** 2026-04-14 | **Feature:** Active Jobs v4 — Feature 8

## YML Email Template Assumed

Yang Ming Line does not publish a fixed email template publicly.
Based on typical NVOCC carrier notification patterns observed for HPL/ONE/YML,
the scanner assumes:

### Pattern A — Container event line
```
Container YMLU1234567 gated in at HCMC on 2026-04-10
Container YMLU7654321 arrived at Los Angeles on 2026-05-06
```

### Pattern B — Vessel departure line
```
Vessel YM WARRANTY departed Hai Phong on 2026-04-12 ETA Los Angeles 2026-05-05
Vessel YM UNICORN sailed from HPH on 2026-04-15
```

### Pattern C — ETA notification
```
ETA Los Angeles 2026-05-05
ETA: 12/05/2026
```

## Fields Extracted

| Field | Regex / Logic |
|-------|---------------|
| Container no. | `[A-Z]{4}\d{7}` — ISO 6346 pattern |
| Event type | Keyword heuristics → DCSA milestone (GTIN/VD/VA/LOAD/DISC) |
| Timestamp | ISO `YYYY-MM-DD` or `DD/MM/YYYY` on same line |
| Location | Text after "at" or "in" before "on" or digit |
| Vessel name | After "Vessel" or "M/V" keyword |
| Booking ref | `YM[-\s]?\d{5,10}` pattern in subject or body |

## Active Jobs Match Strategy

1. Extract booking ref from email subject + body via `_RE_BKG`
2. Exact match against `Bkg_No` (col 4) in Active Jobs, uppercase both sides
3. Fallback: match against `HBL_NO` (col 30)
4. Multi-match: pick row with latest `ETD` (col 5)

## Update Logic per Event

| DCSA code | Action |
|-----------|--------|
| GTIN | Append `[YML stamp] Gate-in CONT at LOC on DATE` to Notes (col 24) |
| VD | Set Status (col 16) = "In Transit", append ATD note |
| VA | Set ATA (col 7) = parsed date (only if not already set), append arrival note |
| ETA_INFO | Append ETA update note only — no field overwrite |
| LOAD/DISC | Append milestone note only |

## Edge Cases Handled

- **No match found**: print warning, skip (no write)
- **ATA already set**: VA event appends note but does not overwrite ATA
- **Multi-container email**: parser tracks current container per line
- **Date format DD/MM/YYYY**: normalised to YYYY-MM-DD before storage
- **Outlook unavailable**: graceful exit 0 with "Outlook not available — skip"
- **ERP file missing**: dry-run fallback, print warning

## Limitations / Known Gaps

- Booking ref extraction from email body assumes YML uses `YM-XXXXXXX` format.
  If YML uses a different booking number format, `_RE_BKG` will not match and
  the email will be printed as "No match" — no data is corrupted.
- Vessel name regex captures up to 30 chars; very long names may truncate.
- Location extraction is best-effort; some port names with special chars may not
  be captured cleanly.
- The scanner does not de-duplicate events across multiple runs on the same email.
  Re-running on the same period will append duplicate notes. Recommend adding
  a processed-email log (email Message-ID tracking) in a future iteration.
