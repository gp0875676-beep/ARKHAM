# tracking/filters.py — value threshold + dedup + spam filters.
"""Pure functions that decide whether a TxEvent should produce an alert."""
from chains.base import TxEvent


def passes_threshold(event: TxEvent, min_usd: float) -> bool:
    """True only if USD value is known AND >= threshold. None USD = drop (no fabrication)."""
    return event.usd_value is not None and event.usd_value >= min_usd
