"""Market data providers.

Phase 1: US equities, daily OHLCV bars, multi-ticker universes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from collections.abc import Sequence

import pandas as pd

from quantframe.types import OHLCV_COLUMNS, BarsBySymbol


class DataProvider(ABC):
    """Abstract source of US equity daily bars.

    Implementations must return a DataFrame that:
    - is indexed by a tz-naive DatetimeIndex (one row per trading session)
    - is sorted ascending
    - contains columns: open, high, low, close, volume
    - includes both ``start`` and ``end`` when those sessions exist (inclusive)

    Prices are **adjusted** for splits/dividends when the source supports it
    (yfinance default uses ``auto_adjust=True``).
    """

    @abstractmethod
    def get_daily_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Fetch daily OHLCV for ``symbol`` from ``start`` through ``end`` (inclusive)."""

    def get_universe_bars(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> BarsBySymbol:
        """Fetch daily OHLCV for a universe. Default: one call per symbol.

        Keys are uppercase tickers. Subclasses may batch the request.
        """
        universe = _normalize_symbols(symbols)
        frames: BarsBySymbol = {}
        errors: list[str] = []
        for sym in universe:
            try:
                frames[sym] = self.get_daily_bars(sym, start, end)
            except (KeyError, ValueError) as exc:
                errors.append(f"{sym}: {exc}")
        if errors:
            raise ValueError("failed to load universe bars: " + "; ".join(errors))
        return frames


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


def align_universe(frames: BarsBySymbol, *, how: str = "inner") -> BarsBySymbol:
    """Align a universe onto one session index.

    ``how="inner"`` (Phase 1 default): keep sessions present for every name.
    """
    if not frames:
        raise ValueError("universe is empty")
    cleaned = {sym.upper(): _normalize_ohlcv(df) for sym, df in frames.items()}
    symbols = list(cleaned)
    index = cleaned[symbols[0]].index
    for sym in symbols[1:]:
        if how == "inner":
            index = index.intersection(cleaned[sym].index)
        elif how == "outer":
            index = index.union(cleaned[sym].index)
        else:
            raise ValueError("how must be 'inner' or 'outer'")
    index = index.sort_values()
    if len(index) == 0:
        raise ValueError("universe has no overlapping sessions")
    aligned: BarsBySymbol = {}
    for sym in symbols:
        piece = cleaned[sym].reindex(index) if how == "outer" else cleaned[sym].loc[index]
        if how == "outer":
            piece = piece.dropna(subset=["open", "high", "low", "close"])
        aligned[sym] = piece
    if how == "inner":
        return aligned
    # Outer join may drop to different lengths; re-inner the surviving dates.
    return align_universe(aligned, how="inner")


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    universe = [s.strip().upper() for s in symbols if str(s).strip()]
    if not universe:
        raise ValueError("universe is empty")
    # Preserve order, drop duplicates
    seen: set[str] = set()
    out: list[str] = []
    for s in universe:
        if s not in seen:
            seen.add(s)
            out.append(s)
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
