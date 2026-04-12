"""Catalyst crawler — MVP fallback reads manual yaml seed file.

Gemini-based extraction from `knowledge/` email archive is deferred to avoid
heavy setup; when the yaml seed file exists it is preferred. The yaml format:

```yaml
- source: CarrierNotice
  category: surcharge
  headline: "HPL EFS $320/40HC from 23 Mar"
  body: "Hapag-Lloyd announces EFS on TP lanes..."
  impact_direction: UP
  impact_magnitude: MED
  affected_lanes: [WC, EC]
  affected_carriers: [HPL]
  effective_date: 2026-03-23
  confidence: 0.9
  url: null
```
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .paths import catalyst_seed_file
from .schemas import Catalyst

log = logging.getLogger(__name__)


def crawl_catalysts(week: str, seed_path: Optional[Path] = None) -> list[Catalyst]:
    """Load catalysts for the week.

    MVP behavior:
      1. Try manual yaml seed file at inputs/catalysts-{week}.yaml
      2. Return [] if missing (acceptable — report section simply shows empty)

    Future: integrate Gemini extraction from knowledge/ email archive.
    """
    seed_path = seed_path or catalyst_seed_file(week)
    if not seed_path.exists():
        log.info("No catalyst seed file for %s: %s", week, seed_path)
        return []

    try:
        import yaml  # type: ignore
    except ImportError:
        log.warning("PyYAML not installed; cannot load catalyst seeds")
        return []

    try:
        raw = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to parse %s: %s", seed_path, e)
        return []

    if not isinstance(raw, list):
        log.warning("Expected list at root of %s, got %s", seed_path, type(raw).__name__)
        return []

    catalysts: list[Catalyst] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        try:
            cat = _dict_to_catalyst(entry)
            catalysts.append(cat)
        except Exception as e:
            log.warning("Skipping catalyst #%d in %s: %s", i, seed_path.name, e)
            continue
    return catalysts


def _dict_to_catalyst(d: dict[str, Any]) -> Catalyst:
    """Build a Catalyst from a dict, applying sensible defaults."""
    effective_date = d.get("effective_date")
    if isinstance(effective_date, str):
        try:
            effective_date = date.fromisoformat(effective_date)
        except ValueError:
            effective_date = None
    elif not isinstance(effective_date, date):
        effective_date = None

    ingested_at = d.get("ingested_at")
    if isinstance(ingested_at, str):
        try:
            ingested_at = datetime.fromisoformat(ingested_at)
        except ValueError:
            ingested_at = datetime.now()
    elif not isinstance(ingested_at, datetime):
        ingested_at = datetime.now()

    affected_lanes = d.get("affected_lanes") or []
    if not isinstance(affected_lanes, list):
        affected_lanes = [str(affected_lanes)]
    affected_carriers = d.get("affected_carriers") or []
    if not isinstance(affected_carriers, list):
        affected_carriers = [str(affected_carriers)]

    return Catalyst(
        source=d.get("source", "Manual"),
        category=d.get("category", "policy"),
        headline=str(d.get("headline", "")).strip(),
        body=str(d.get("body", "")).strip(),
        impact_direction=d.get("impact_direction", "FLAT"),
        impact_magnitude=d.get("impact_magnitude", "LOW"),
        affected_lanes=[str(x).upper() for x in affected_lanes],
        affected_carriers=[str(x).upper() for x in affected_carriers],
        effective_date=effective_date,
        confidence=float(d.get("confidence", 0.5)),
        url=d.get("url"),
        raw_text=str(d.get("raw_text", d.get("body", ""))),
        ingested_at=ingested_at,
    )


# Impact ranking for sorting in the report
_MAGNITUDE_RANK = {"CRITICAL": 4, "HIGH": 3, "MED": 2, "LOW": 1}


def rank_catalysts(catalysts: list[Catalyst]) -> list[Catalyst]:
    """Sort catalysts by impact magnitude (CRITICAL first) then confidence."""
    return sorted(
        catalysts,
        key=lambda c: (_MAGNITUDE_RANK.get(c.impact_magnitude, 0), c.confidence),
        reverse=True,
    )
