"""Strategy interface.

Contract
--------
A strategy maps **price history that is already known** onto a **target
position** for the traded symbol.

Input
    ``bars``: daily OHLCV DataFrame (see ``DataProvider``). Sorted by date.
    Columns: open, high, low, close, volume.

Output
    ``pd.Series`` of target weights, **aligned to ``bars.index``**.
    The value at timestamp ``t`` is the desired weight in the symbol using
    **only information available at or before the close of bar ``t``**.

    Weight meaning (Phase 1, long-only / long-flat):
        1.0 = fully invested long
        0.0 = flat (100% cash)
        Values are clipped to [0, 1] by the engine.

Execution (engine, not strategy)
    The backtester fills the signal from bar ``t`` at the **open of bar t+1**.
    Same-bar fills on the close of ``t`` are intentionally not used, so a
    strategy cannot trade on information that would not have been available
    at the fill.

Look-ahead
    The engine does not peek at future bars when filling. Strategies **must
    not** use future rows when computing ``signal[t]``. Rolling windows that
    end at ``t`` (e.g. SMA) are valid; shifting indicators the wrong way is not.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class Strategy(ABC):
    """Price history → target weights. See module docstring for the contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable id used in reports and output filenames."""

    @abstractmethod
    def params(self) -> dict[str, Any]:
        """JSON-serializable parameters for the report."""

    @abstractmethod
    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        """Return target weights aligned with ``bars.index`` (see contract)."""
