"""Dataclass schemas for the 4C Market Report system.

Four streams: Costing (parquet), Capacity (manual), Catalyst (crawl), Forecast (scenarios).
Keep enums as Literals for static analysis without runtime dep on `enum`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Literal, Optional

Lane = Literal["WC", "EC", "GULF", "ALL"]
RateType = Literal["FIX", "FAK", "SCFI", "SPOT", "BULLET", "NAC"]
Status = Literal["OPEN", "TIGHT", "FULL", "ROLLING"]
Dimension = Literal["space", "equipment", "booking_policy"]
CatalystSource = Literal[
    "Panjiva", "JOC", "Xeneta", "CarrierNotice", "GoogleAlert", "Manual"
]
Category = Literal[
    "surcharge", "capacity", "geopolitical", "fuel", "labor", "policy", "weather"
]
Direction = Literal["UP", "DOWN", "FLAT", "VOLATILE"]
Magnitude = Literal["LOW", "MED", "HIGH", "CRITICAL"]


@dataclass
class CostingItem:
    """One best-rate row surfaced from parquet for the weekly costing section."""
    lane: Lane
    carrier: str
    rate_type: RateType
    container: str                 # e.g. "40HC", "20DC"
    price: float
    valid_from: Optional[date]
    valid_to: Optional[date]
    is_pudong_best: bool = False
    spread_vs_lane_avg: float = 0.0  # price - lane_avg (negative = cheaper than avg)
    source_parquet_row: int = -1

    def to_dict(self) -> dict:
        d = asdict(self)
        # Serialize dates to ISO strings for json/yaml compatibility
        for k in ("valid_from", "valid_to"):
            if d[k] is not None:
                d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else str(d[k])
        return d


@dataclass
class CapacitySignal:
    """Manually entered capacity status from CS team."""
    week: str                       # "2026-W15"
    carrier: str
    lane: Lane
    dimension: Dimension
    status: Status
    score: int                      # 1..5 (1=critical-tight, 5=abundant)
    notes: str = ""
    entered_by: str = ""
    entered_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not (1 <= self.score <= 5):
            raise ValueError(
                f"CapacitySignal.score must be 1..5, got {self.score}"
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.entered_at is not None:
            d["entered_at"] = self.entered_at.isoformat()
        return d


@dataclass
class Catalyst:
    """News / market event extracted from crawler or manual input."""
    source: CatalystSource
    category: Category
    headline: str
    body: str
    impact_direction: Direction
    impact_magnitude: Magnitude
    affected_lanes: list[str] = field(default_factory=list)
    affected_carriers: list[str] = field(default_factory=list)
    effective_date: Optional[date] = None
    confidence: float = 0.5
    url: Optional[str] = None
    raw_text: str = ""
    ingested_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Catalyst.confidence must be 0..1, got {self.confidence}"
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.effective_date is not None:
            d["effective_date"] = self.effective_date.isoformat()
        if self.ingested_at is not None:
            d["ingested_at"] = self.ingested_at.isoformat()
        return d


@dataclass
class ForecastScenario:
    """Low/base/high scenarios for next-week rate per lane."""
    lane: Lane
    week: str                       # target week "2026-W16"
    container: str
    base_case: float
    low_case: float
    high_case: float
    confidence: float = 0.5
    trigger_catalyst_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    model_version: str = "baseline-v1"

    def __post_init__(self) -> None:
        if not (self.low_case <= self.base_case <= self.high_case):
            raise ValueError(
                f"ForecastScenario must satisfy low<=base<=high, got "
                f"low={self.low_case} base={self.base_case} high={self.high_case}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"ForecastScenario.confidence must be 0..1, got {self.confidence}"
            )

    def to_dict(self) -> dict:
        return asdict(self)
