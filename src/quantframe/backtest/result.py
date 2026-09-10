"""Backtest result containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from quantframe.backtest.commission import Commission


@dataclass
class Fill:
    date: pd.Timestamp
    side: str  # "BUY" | "SELL"
    shares: int
    price: float
    commission: float
    cash_after: float
    shares_after: int


@dataclass
class RoundTrip:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp | None
    side: str  # "LONG"
    shares: int
    entry_price: float
    exit_price: float | None
    entry_commission: float
    exit_commission: float
    pnl: float | None
    return_pct: float | None
    open: bool = False

    def as_row(self) -> dict[str, Any]:
        return {
            "entry_date": self.entry_date.date().isoformat(),
            "exit_date": None if self.exit_date is None else self.exit_date.date().isoformat(),
            "side": self.side,
            "shares": self.shares,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_commission": self.entry_commission,
            "exit_commission": self.exit_commission,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "status": "open" if self.open else "closed",
        }


@dataclass
class BacktestResult:
    symbol: str
    start: date
    end: date
    strategy_name: str
    strategy_params: dict[str, Any]
    initial_cash: float
    commission: Commission
    bars: pd.DataFrame
    signals: pd.Series
    equity_curve: pd.Series
    fills: list[Fill]
    round_trips: list[RoundTrip]
    metrics: dict[str, float | int | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def ending_equity(self) -> float:
        if self.equity_curve.empty:
            return float(self.initial_cash)
        return float(self.equity_curve.iloc[-1])
