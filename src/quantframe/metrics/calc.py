"""Performance metrics from an equity curve and round-trip trades."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np
import pandas as pd

from quantframe.backtest.result import RoundTrip

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25


def compute_metrics(
    equity: pd.Series,
    initial_cash: float,
    round_trips: list[RoundTrip],
    *,
    risk_free_rate: float = 0.0,
) -> dict[str, float | int | None]:
    """Return the Phase-1 metric set (None = not defined)."""
    if equity.empty:
        raise ValueError("equity curve is empty")

    start_eq = float(initial_cash)
    end_eq = float(equity.iloc[-1])
    total_return = (end_eq / start_eq) - 1.0 if start_eq else None

    n_cal_days = max((equity.index[-1] - equity.index[0]).days, 0)
    years = n_cal_days / CALENDAR_DAYS_PER_YEAR if n_cal_days > 0 else 0.0
    if years > 0 and start_eq > 0 and end_eq > 0:
        cagr = (end_eq / start_eq) ** (1.0 / years) - 1.0
    else:
        cagr = None

    daily = equity.pct_change().dropna()
    vol = None
    sharpe = None
    if len(daily) >= 2 and float(daily.std(ddof=1)) > 0:
        vol = float(daily.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        excess = daily - (risk_free_rate / TRADING_DAYS_PER_YEAR)
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    elif len(daily) >= 2:
        vol = 0.0
        sharpe = None

    max_dd, max_dd_start, max_dd_end = max_drawdown(equity)

    closed = [t for t in round_trips if not t.open]
    wins = [t for t in closed if t.pnl is not None and t.pnl > 0]
    losses = [t for t in closed if t.pnl is not None and t.pnl <= 0]
    win_rate = (len(wins) / len(closed)) if closed else None
    avg_win = float(np.mean([t.pnl for t in wins])) if wins else None
    avg_loss = float(np.mean([t.pnl for t in losses])) if losses else None
    gross_profit = float(sum(t.pnl or 0.0 for t in wins))
    gross_loss = float(abs(sum(t.pnl or 0.0 for t in losses)))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    avg_trade = (
        float(np.mean([t.pnl for t in closed if t.pnl is not None])) if closed else None
    )

    time_in_market = _time_in_market(equity, round_trips)
    calmar = None
    if cagr is not None and max_dd is not None and max_dd < 0:
        calmar = cagr / abs(max_dd)

    return {
        "initial_cash": start_eq,
        "ending_equity": end_eq,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "volatility": vol,
        "max_drawdown": max_dd,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "calmar": calmar,
        "trade_count": len(closed),
        "open_trades": sum(1 for t in round_trips if t.open),
        "win_rate": win_rate,
        "avg_trade_pnl": avg_trade,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "time_in_market": time_in_market,
        "bar_count": int(len(equity)),
    }


def max_drawdown(equity: pd.Series) -> tuple[float | None, str | None, str | None]:
    """Peak-to-trough drawdown of the equity curve (negative fraction)."""
    if equity.empty:
        return None, None, None
    peak = equity.cummax()
    dd = equity / peak - 1.0
    trough_idx = dd.idxmin()
    max_dd = float(dd.loc[trough_idx])
    peak_idx = equity.loc[:trough_idx].idxmax()
    return (
        max_dd,
        pd.Timestamp(peak_idx).date().isoformat(),
        pd.Timestamp(trough_idx).date().isoformat(),
    )


def _time_in_market(equity: pd.Series, round_trips: list[RoundTrip]) -> float | None:
    if equity.empty or len(equity) < 2:
        return 0.0
    invested = pd.Series(0.0, index=equity.index)
    last = equity.index[-1]
    for trip in round_trips:
        end = last if trip.exit_date is None else trip.exit_date
        mask = (invested.index >= trip.entry_date) & (invested.index <= end)
        invested.loc[mask] = 1.0
    return float(invested.mean())


def format_metric(key: str, value: float | int | None | str) -> str:
    if value is None:
        return "n/a"
    pct_keys = {
        "total_return",
        "cagr",
        "max_drawdown",
        "win_rate",
        "volatility",
        "time_in_market",
        "return_pct",
    }
    money_keys = {
        "initial_cash",
        "ending_equity",
        "avg_trade_pnl",
        "avg_win",
        "avg_loss",
        "pnl",
    }
    if key in pct_keys:
        return f"{value:.2%}"
    if key in money_keys:
        return f"${value:,.2f}"
    if key in {"sharpe", "calmar", "profit_factor"}:
        return f"{value:.2f}"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


METRIC_LABELS: Mapping[str, str] = {
    "initial_cash": "Initial cash",
    "ending_equity": "Ending equity",
    "total_return": "Total return",
    "cagr": "CAGR",
    "sharpe": "Sharpe (rf=0, 252d)",
    "volatility": "Ann. volatility",
    "max_drawdown": "Max drawdown",
    "max_drawdown_start": "Max DD peak date",
    "max_drawdown_end": "Max DD trough date",
    "calmar": "Calmar",
    "trade_count": "Closed trades",
    "open_trades": "Open trades (end)",
    "win_rate": "Win rate",
    "avg_trade_pnl": "Avg trade PnL",
    "avg_win": "Avg win",
    "avg_loss": "Avg loss",
    "profit_factor": "Profit factor",
    "time_in_market": "Time in market",
    "bar_count": "Sessions",
}
