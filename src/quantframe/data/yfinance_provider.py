"""Default DataProvider: Yahoo Finance via yfinance (US daily bars, adjusted)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from quantframe.data.provider import (
    DataProvider,
    _normalize_ohlcv,
    _normalize_symbols,
)
from quantframe.types import BarsBySymbol


class YFinanceDataProvider(DataProvider):
    """Download US equity daily OHLCV from Yahoo Finance.

    Uses **adjusted** prices (``auto_adjust=True``) so splits/dividends are
    reflected in the OHLC series used by the backtester.
    """

    def get_daily_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        frames = self.get_universe_bars([symbol], start, end)
        return frames[_normalize_symbols([symbol])[0]]

    def get_universe_bars(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> BarsBySymbol:
        universe = _normalize_symbols(symbols)
        if end < start:
            raise ValueError(f"end {end} is before start {start}")

        # yfinance ``end`` is exclusive; add one day so the caller's end is inclusive.
        yf_end = end + timedelta(days=1)
        raw = yf.download(
            universe,
            start=start.isoformat(),
            end=yf_end.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
            group_by="ticker",
        )
        if raw is None or raw.empty:
            # Fallback: per-ticker history (sometimes more reliable for a single name).
            return {sym: self._history_one(sym, start, yf_end) for sym in universe}

        return _split_yf_download(raw, universe)

    def _history_one(self, symbol: str, start: date, yf_end: date) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            start=start.isoformat(),
            end=yf_end.isoformat(),
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        if raw is None or raw.empty:
            raise ValueError(f"yfinance returned no daily bars for {symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [str(c[0]).strip() for c in raw.columns]
        return _normalize_ohlcv(raw)


def _split_yf_download(raw: pd.DataFrame, universe: list[str]) -> BarsBySymbol:
    """Split a yfinance multi-ticker frame into per-symbol OHLCV."""
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(universe) == 1:
            return {universe[0]: _normalize_ohlcv(raw)}
        raise ValueError("yfinance returned a single-index frame for a multi-ticker universe")

    level0 = [str(x).upper() for x in raw.columns.get_level_values(0).unique()]
    tickers_in_lvl0 = set(universe).issubset(set(level0)) or any(t in level0 for t in universe)

    out: BarsBySymbol = {}
    missing: list[str] = []
    for sym in universe:
        try:
            if tickers_in_lvl0:
                piece = raw[sym]
            else:
                piece = raw.xs(sym, axis=1, level=1)
            if isinstance(piece, pd.Series):
                piece = piece.to_frame()
            out[sym] = _normalize_ohlcv(piece)
        except (KeyError, TypeError, ValueError):
            matched = _column_group(raw, sym)
            if matched is None:
                missing.append(sym)
            else:
                out[sym] = _normalize_ohlcv(matched)
    if missing:
        raise ValueError("yfinance missing bars: " + "; ".join(missing))
    return out


def _column_group(raw: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    target = symbol.upper()
    if not isinstance(raw.columns, pd.MultiIndex):
        return None
    for level in (0, 1):
        labels = raw.columns.get_level_values(level)
        if any(str(x).upper() == target for x in labels.unique()):
            try:
                if level == 0:
                    for key in raw.columns.get_level_values(0).unique():
                        if str(key).upper() == target:
                            return raw[key]
                return raw.xs(symbol, axis=1, level=level, drop_level=True)
            except KeyError:
                continue
    return None
