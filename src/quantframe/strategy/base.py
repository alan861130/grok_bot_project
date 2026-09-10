"""Strategy interface.

Contract
--------
A Phase-1 strategy maps **already-known** daily bars for a **universe** onto
a **long set** (boolean membership). The engine then **equal-weights** names
that are in the long set that session and holds cash when the set is empty.

Input
    ``bars``: ``dict[symbol, DataFrame]`` of daily OHLCV (see ``DataProvider``).
    Frames share a session index after the engine aligns the universe
    (inner join of trading calendars).

Output of ``generate_signals``
    ``pd.DataFrame`` of booleans (or 0/1), **index = sessions**, **columns = symbols**.
    Value at ``(t, symbol)`` uses **only information through the close of bar t**
    for that symbol (rolling windows that end at ``t`` are valid).

    True / 1 = include in the long set that session.
    False / 0 = do not hold.

    Warm-up rows should be False.

Output of ``generate_target_weights`` (optional override)
    ``pd.DataFrame`` of non-negative weights, same shape. Each row should sum
    to at most 1.0; the remainder is cash. The **default implementation**
    equal-weights the long set from ``generate_signals``. Later strategies
    can override this method for non-equal target weights without changing
    the engine.

Execution (engine, not strategy)
    Phase 1 fills at the **same session close** as the signal (optimistic;
    you would not generally be able to transact at a close you just used
    to compute the signal). Documented in reports and the README.
    No shorting. Rebalance when the target-weight vector changes
    (membership change for equal-weight SMA).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from quantframe.strategy.weights import equal_weight_long_set
from quantframe.types import BarsBySymbol


class Strategy(ABC):
    """Universe bars → long set (and, by default, equal-weight targets)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable id used in reports and output filenames."""

    @abstractmethod
    def params(self) -> dict[str, Any]:
        """JSON-serializable parameters for the report."""

    @abstractmethod
    def generate_signals(self, bars: BarsBySymbol) -> pd.DataFrame:
        """Boolean long-set membership (dates × symbols). See module docstring."""

    def generate_target_weights(self, bars: BarsBySymbol) -> pd.DataFrame:
        """Target portfolio weights. Default: equal-weight the long set.

        Override in later phases for explicit target-weight strategies.
        """
        return equal_weight_long_set(self.generate_signals(bars))
