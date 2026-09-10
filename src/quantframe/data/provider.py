"""Market data providers.

Phase 1: US equities, daily OHLCV bars.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from quantframe.types import OHLCV_COLUMNS


class DataProvider(ABC):
    """Abstract source of US equity daily bars.

    Implementations must return a DataFrame that:
    - is indexed by a tz-naive DatetimeIndex (one row per trading session)
    - is sorted ascending
    - contains columns: open, high, low, close, volume
    - includes both ``start`` and ``end`` when those sessions exist (inclusive)
    """

    @abstractmethod
    def get_daily_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Fetch daily OHLCV for ``symbol`` from ``start`` through ``end`` (inclusive)."""


class PandasDataProvider(DataProvider):
    """In-memory provider used by tests and offline runs. No network."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = {sym.upper(): _normalize_ohlcv(df) for sym, df in frames.items()}

    def get_daily_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        key = symbol.upper()
        if key not in self._frames:
            raise KeyError(f"No bars loaded for symbol {symbol!r}")
        df = self._frames[key]
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        out = df.loc[(df.index >= start_ts) & (df.index <= end_ts)].copy()
        if out.empty:
            raise ValueError(f"No bars for {symbol} in [{start}, {end}]")
        return out


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw frame into the Phase-1 OHLCV contract."""
    if df.empty:
        raise ValueError("OHLCV frame is empty")

    work = df.copy()
    work.columns = [str(c).strip().lower() for c in work.columns]
    rename = {}
    for col in work.columns:
        if col in OHLCV_COLUMNS:
            continue
        # yfinance / CSV variants
        mapping = {
            "adj close": "close",
            "adj_close": "close",
            "adjclose": "close",
        }
        if col in mapping:
            rename[col] = mapping[col]
    if rename:
        work = work.rename(columns=rename)

    missing = [c for c in OHLCV_COLUMNS if c not in work.columns]
    if missing:
        raise ValueError(f"OHLCV frame missing columns {missing}; have {list(work.columns)}")

    work = work.loc[:, list(OHLCV_COLUMNS)].astype(float)
    idx = pd.to_datetime(work.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    work.index = pd.DatetimeIndex(idx).normalize()
    work = work[~work.index.duplicated(keep="last")].sort_index()
    work = work.dropna(subset=["open", "high", "low", "close"])
    if work.empty:
        raise ValueError("OHLCV frame has no usable rows after cleaning")
    _validate_ohlc(work)
    return work


def _validate_ohlc(df: pd.DataFrame) -> None:
    bad_high = df["high"] < df[["open", "close", "low"]].max(axis=1)
    bad_low = df["low"] > df[["open", "close", "high"]].min(axis=1)
    if bool(bad_high.any() or bad_low.any()):
        raise ValueError("OHLC consistency check failed (high/low vs open/close)")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Prices must be positive")
    if (df["volume"] < 0).any():
        raise ValueError("Volume cannot be negative")
