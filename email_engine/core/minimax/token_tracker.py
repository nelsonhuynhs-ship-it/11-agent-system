import logging
from typing import Dict

log = logging.getLogger(__name__)

_TOKEN_COUNTER: Dict[str, Dict[str, int]] = {}

def track(model: str, tokens_in: int = 0, tokens_out: int = 0) -> None:
    if model not in _TOKEN_COUNTER:
        _TOKEN_COUNTER[model] = {"requests": 0, "tokens_in": 0, "tokens_out": 0}
    _TOKEN_COUNTER[model]["requests"] += 1
    _TOKEN_COUNTER[model]["tokens_in"] += tokens_in
    _TOKEN_COUNTER[model]["tokens_out"] += tokens_out

def get_usage() -> Dict[str, Dict[str, int]]:
    return dict(_TOKEN_COUNTER)

def reset() -> None:
    _TOKEN_COUNTER.clear()
