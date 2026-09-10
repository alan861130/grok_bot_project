"""Multi-asset SMA crossover: golden cross includes a name, death cross drops it."""

from __future__ import annotations

from typing import Any

import pandas as pd

from quantframe.defaults import DEMO_FAST, DEMO_SLOW
from quantframe.strategy.base import Strategy
from quantframe.types import BarsBySymbol


class SMACrossoverStrategy(Strategy):
    """Per-symbol SMA: long when fast SMA > slow SMA (else flat in that name).

    Golden cross (fast crosses above slow) → include in the portfolio long set.
    Death cross (fast crosses below slow) → remove. Equivalent to holding the
    name while the fast average is strictly above the slow average.

    Signals use **closes through bar t**. Warm-up (slow window not full) is False.
    The engine equal-weights names that are in the long set that session.
    """

    def __init__(self, fast: int = DEMO_FAST, slow: int = DEMO_SLOW) -> None:
        if fast < 1 or slow < 2:
            raise ValueError("fast must be >= 1 and slow must be >= 2")
        if fast >= slow:
            raise ValueError("fast period must be strictly less than slow period")
        self.fast = int(fast)
        self.slow = int(slow)

    @property
    def name(self) -> str:
        return "sma_crossover"

    def params(self) -> dict[str, Any]:
        return {"fast": self.fast, "slow": self.slow}

    def generate_signals(self, bars: BarsBySymbol) -> pd.DataFrame:
        if not bars:
            raise ValueError("bars is empty")
        cols: dict[str, pd.Series] = {}
        for symbol, frame in bars.items():
            close = frame["close"].astype(float)
            fast_sma = close.rolling(self.fast, min_periods=self.fast).mean()
            slow_sma = close.rolling(self.slow, min_periods=self.slow).mean()
            valid = fast_sma.notna() & slow_sma.notna()
            long = pd.Series(False, index=frame.index)
            long.loc[valid] = fast_sma.loc[valid] > slow_sma.loc[valid]
            cols[symbol] = long
        signals = pd.DataFrame(cols)
        return signals.fillna(False).astype(bool)
