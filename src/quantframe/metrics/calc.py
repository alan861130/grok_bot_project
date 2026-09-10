"""Performance metrics from an equity curve, exposure, and round-trip trades."""

from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from quantframe.backtest.result import RoundTrip

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25

# Locked Phase-1 set (report table). Extra keys may exist for drawdown dates.
LOCKED_METRIC_KEYS: tuple[str, ...] = (
    "ending_equity",
    "total_return",
    "cagr",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "trade_count",
    "time_in_market",
    "avg_exposure",
)


def compute_metrics(
    equity: pd.Series,
    initial_cash: float,
    round_trips: list[RoundTrip],
    *,
    exposure: pd.Series | None = None,
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
    sharpe = None
    if len(daily) >= 2 and float(daily.std(ddof=1)) > 0:
        excess = daily - (risk_free_rate / TRADING_DAYS_PER_YEAR)
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))

    max_dd, max_dd_start, max_dd_end = max_drawdown(equity)

    closed = [t for t in round_trips if not t.open]
    wins = [t for t in closed if t.pnl is not None and t.pnl > 0]
    win_rate = (len(wins) / len(closed)) if closed else None

    if exposure is None or exposure.empty:
        time_in_market, avg_exposure = _exposure_from_trips(equity, round_trips)
    else:
        exp = exposure.reindex(equity.index).fillna(0.0).astype(float)
        time_in_market = float((exp > 1e-9).mean())
        avg_exposure = float(exp.mean())

    return {
        "ending_equity": end_eq,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "trade_count": len(closed),
        "time_in_market": time_in_market,
        "avg_exposure": avg_exposure,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
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


def _exposure_from_trips(
    equity: pd.Series,
    round_trips: list[RoundTrip],
) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    invested = pd.Series(0.0, index=equity.index)
    last = equity.index[-1]
    for trip in round_trips:
        end = last if trip.exit_date is None else trip.exit_date
        mask = (invested.index >= trip.entry_date) & (invested.index <= end)
        invested.loc[mask] = 1.0
    return float(invested.mean()), float(invested.mean())


def format_metric(key: str, value: float | int | None | str) -> str:
    if value is None:
        return "n/a"
    pct_keys = {
        "total_return",
        "cagr",
        "max_drawdown",
        "win_rate",
        "time_in_market",
        "avg_exposure",
        "return_pct",
    }
    money_keys = {
        "ending_equity",
        "pnl",
    }
    if key in pct_keys:
        return f"{value:.2%}"
    if key in money_keys:
        return f"${value:,.2f}"
    if key in {"sharpe"}:
        return f"{value:.2f}"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


METRIC_LABELS: Mapping[str, str] = {
    "ending_equity": "Ending equity",
    "total_return": "Total return",
    "cagr": "CAGR",
    "sharpe": "Sharpe (rf=0, 252d)",
    "max_drawdown": "Max drawdown",
    "win_rate": "Win rate",
    "trade_count": "Trade count (closed round trips)",
    "time_in_market": "Time in market",
    "avg_exposure": "Avg exposure",
}
