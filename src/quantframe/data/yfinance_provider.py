"""Default DataProvider: Yahoo Finance via yfinance (US daily bars)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from quantframe.data.provider import DataProvider, _normalize_ohlcv


class YFinanceDataProvider(DataProvider):
    """Download US equity daily OHLCV from Yahoo Finance.

    Uses adjusted prices (``auto_adjust=True``) so splits/dividends are
    reflected in the OHLC series used by the backtester.
    """

    def get_daily_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if end < start:
            raise ValueError(f"end {end} is before start {start}")

        # yfinance ``end`` is exclusive; add one day so the caller's end is inclusive.
        yf_end = end + timedelta(days=1)
        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            start=start.isoformat(),
            end=yf_end.isoformat(),
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        if raw is None or raw.empty:
            raw = yf.download(
                symbol,
                start=start.isoformat(),
                end=yf_end.isoformat(),
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        if raw is None or raw.empty:
            raise ValueError(f"yfinance returned no daily bars for {symbol} in [{start}, {end}]")

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [str(c[0]).strip().lower() for c in raw.columns]

        return _normalize_ohlcv(raw)
