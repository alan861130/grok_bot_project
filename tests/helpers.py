"""Shared synthetic fixtures for offline tests."""

from __future__ import annotations

import pandas as pd

from quantframe.strategy.base import Strategy
from quantframe.types import BarsBySymbol


class ScriptedStrategy(Strategy):
    """Emits a pre-baked boolean long set (dates × symbols)."""

    def __init__(self, membership: pd.DataFrame) -> None:
        self._membership = membership.astype(bool)

    @property
    def name(self) -> str:
        return "scripted"

    def params(self) -> dict:
        return {"symbols": list(self._membership.columns)}

    def generate_signals(self, bars: BarsBySymbol) -> pd.DataFrame:
        return self._membership


def trending_ohlcv(
    start: str = "2020-01-02",
    periods: int = 30,
    start_price: float = 10.0,
    step: float = 0.5,
) -> pd.DataFrame:
    """OHLC-consistent series whose close follows ``start_price + i * step``."""
    idx = pd.bdate_range(start=start, periods=periods)
    closes = [start_price + i * step for i in range(periods)]
    rows = []
    prev = closes[0]
    for c in closes:
        o = prev
        high = max(o, c) + 0.05
        low = min(o, c) - 0.05
        rows.append({"open": o, "high": high, "low": low, "close": c, "volume": 1_000.0})
        prev = c
    return pd.DataFrame(rows, index=idx)


def custom_ohlcv(
    opens: list[float],
    closes: list[float],
    start: str = "2020-01-02",
) -> pd.DataFrame:
    if len(opens) != len(closes):
        raise ValueError("opens and closes must be the same length")
    idx = pd.bdate_range(start=start, periods=len(closes))
    rows = []
    for o, c in zip(opens, closes, strict=True):
        rows.append(
            {
                "open": o,
                "high": max(o, c) + 0.01,
                "low": min(o, c) - 0.01,
                "close": c,
                "volume": 100.0,
            }
        )
    return pd.DataFrame(rows, index=idx)


def long_set(index: pd.DatetimeIndex, flags: dict[str, list[bool]]) -> pd.DataFrame:
    return pd.DataFrame(flags, index=index)
