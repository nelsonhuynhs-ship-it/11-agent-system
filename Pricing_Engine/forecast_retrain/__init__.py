"""Forecast retrain orchestration.

Decides when the Nelson market forecaster needs retraining based on
multi-signal triggers:
  (A) imports_since_train  >= N_IMPORTS_THRESHOLD
  (B) rows_delta           >= N_ROWS_THRESHOLD
  (C) days_since_train     >= N_DAYS_THRESHOLD
  (D) last_accuracy_error  >= N_ACCURACY_THRESHOLD

Retrain fires if ANY signal trips. State persisted to OneDrive so all
machines share the same view.
"""
from .state import (
    RetrainState,
    load_state,
    save_state,
    bump_import_counter,
)
from .check_retrain import should_retrain, run_check

__all__ = [
    "RetrainState",
    "load_state",
    "save_state",
    "bump_import_counter",
    "should_retrain",
    "run_check",
]
