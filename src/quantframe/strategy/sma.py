"""Simple moving-average crossover (long / flat)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from quantframe.strategy.base import Strategy


class SMACrossoverStrategy(Strategy):
    """Long when fast SMA > slow SMA; otherwise flat.

    Signals are computed from **closes through bar t**. Warm-up bars (before
    the slow window is full) emit 0.0.
    """

    def __init__(self, fast: int = 50, slow: int = 200) -> None:
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

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"].astype(float)
        fast_sma = close.rolling(self.fast, min_periods=self.fast).mean()
        slow_sma = close.rolling(self.slow, min_periods=self.slow).mean()
        valid = fast_sma.notna() & slow_sma.notna()
        weights = pd.Series(0.0, index=bars.index, name="target_weight")
        weights.loc[valid] = (fast_sma.loc[valid] > slow_sma.loc[valid]).astype(float)
        return weights
