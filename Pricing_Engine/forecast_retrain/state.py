"""Persistent state for forecast retrain triggers.

State file lives on OneDrive so PC Home / Laptop VP / VPS share the
same view. Reads and writes are tolerant of missing files — first boot
returns a default state.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("nelson.forecast_retrain.state")

# Lazy import shared.paths so unit tests can monkey-patch.
import sys as _sys
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)
from shared import paths as _sp  # type: ignore  # noqa: E402

# State file on OneDrive next to the forecast assets.
STATE_DIR = _sp.PRICING_DATA / "forecast"
STATE_FILE = STATE_DIR / "retrain_state.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ImportDelta:
    at: str          # ISO-8601 UTC
    rows_added: int
    source: str      # "FAK" / "SCFI" / "FIX" / "MANUAL"


@dataclass
class AccuracySnapshot:
    week: str        # "2026-W14"
    avg_error_pct: float
    checked_at: str


@dataclass
class RetrainState:
    last_trained_at: Optional[str] = None         # ISO-8601 UTC
    last_train_parquet_rows: int = 0
    imports_since_train: int = 0
    data_deltas: list[ImportDelta] = field(default_factory=list)
    last_accuracy: Optional[AccuracySnapshot] = None

    # ── Serialization ────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RetrainState":
        deltas_raw = d.get("data_deltas") or []
        deltas = [ImportDelta(**x) for x in deltas_raw]
        acc_raw = d.get("last_accuracy")
        acc = AccuracySnapshot(**acc_raw) if acc_raw else None
        return cls(
            last_trained_at=d.get("last_trained_at"),
            last_train_parquet_rows=int(d.get("last_train_parquet_rows") or 0),
            imports_since_train=int(d.get("imports_since_train") or 0),
            data_deltas=deltas,
            last_accuracy=acc,
        )


def load_state(path: Path = STATE_FILE) -> RetrainState:
    """Load state or return a fresh default on first boot / corruption."""
    try:
        if not path.exists():
            return RetrainState()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return RetrainState.from_dict(raw)
    except Exception as e:
        log.warning("retrain state corrupt, starting fresh: %s", e)
        return RetrainState()


def save_state(state: RetrainState, path: Path = STATE_FILE) -> None:
    """Write state atomically via tmp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(state.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def bump_import_counter(
    rows_added: int,
    source: str,
    parquet_rows_after: Optional[int] = None,
    path: Path = STATE_FILE,
) -> RetrainState:
    """Called from rate_importer after a successful parquet write.

    Increments imports_since_train and appends a data_delta entry.
    Trimming: keep only last 50 deltas to bound file size.
    """
    state = load_state(path)
    state.imports_since_train += 1
    state.data_deltas.append(
        ImportDelta(at=_utcnow_iso(), rows_added=int(rows_added), source=source)
    )
    # Bound history to last 50 entries
    if len(state.data_deltas) > 50:
        state.data_deltas = state.data_deltas[-50:]
    save_state(state, path)
    log.info(
        "retrain-state: imports=%d, rows_added=%d, source=%s",
        state.imports_since_train,
        rows_added,
        source,
    )
    return state


def mark_trained(
    parquet_rows: int,
    path: Path = STATE_FILE,
) -> RetrainState:
    """Called after a successful retrain — resets counters."""
    state = load_state(path)
    state.last_trained_at = _utcnow_iso()
    state.last_train_parquet_rows = int(parquet_rows)
    state.imports_since_train = 0
    state.data_deltas = []
    save_state(state, path)
    log.info("retrain-state: marked trained at %s (rows=%d)", state.last_trained_at, parquet_rows)
    return state


def record_accuracy(
    week: str,
    avg_error_pct: float,
    path: Path = STATE_FILE,
) -> RetrainState:
    """Called by backtest job — updates the accuracy snapshot."""
    state = load_state(path)
    state.last_accuracy = AccuracySnapshot(
        week=week,
        avg_error_pct=float(avg_error_pct),
        checked_at=_utcnow_iso(),
    )
    save_state(state, path)
    return state
