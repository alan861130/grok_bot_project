"""Metrics on synthetic equity curves — no network."""

from __future__ import annotations

import pandas as pd
import pytest

from quantframe.backtest.result import RoundTrip
from quantframe.metrics.calc import compute_metrics, max_drawdown


def _equity(values: list[float], start: str = "2020-01-02") -> pd.Series:
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, name="equity")


def test_total_return_and_trade_stats() -> None:
    eq = _equity([100.0, 110.0, 105.0])
    trips = [
        RoundTrip(
            entry_date=eq.index[0],
            exit_date=eq.index[1],
            side="LONG",
            shares=1,
            entry_price=100.0,
            exit_price=110.0,
            entry_commission=0.0,
            exit_commission=0.0,
            pnl=10.0,
            return_pct=0.10,
            open=False,
        ),
        RoundTrip(
            entry_date=eq.index[1],
            exit_date=eq.index[2],
            side="LONG",
            shares=1,
            entry_price=110.0,
            exit_price=105.0,
            entry_commission=0.0,
            exit_commission=0.0,
            pnl=-5.0,
            return_pct=-5 / 110,
            open=False,
        ),
    ]
    m = compute_metrics(eq, initial_cash=100.0, round_trips=trips)
    assert m["total_return"] == pytest.approx(0.05)
    assert m["ending_equity"] == pytest.approx(105.0)
    assert m["trade_count"] == 2
    assert m["win_rate"] == pytest.approx(0.5)
    assert m["avg_win"] == pytest.approx(10.0)
    assert m["avg_loss"] == pytest.approx(-5.0)
    assert m["profit_factor"] == pytest.approx(10.0 / 5.0)


def test_max_drawdown() -> None:
    eq = _equity([100.0, 120.0, 90.0, 95.0])
    dd, peak, trough = max_drawdown(eq)
    assert dd == pytest.approx((90.0 / 120.0) - 1.0)
    assert peak == eq.index[1].date().isoformat()
    assert trough == eq.index[2].date().isoformat()


def test_sharpe_none_when_flat() -> None:
    eq = _equity([100.0, 100.0, 100.0, 100.0])
    m = compute_metrics(eq, initial_cash=100.0, round_trips=[])
    assert m["sharpe"] is None
    assert m["volatility"] == pytest.approx(0.0)
    assert m["win_rate"] is None
    assert m["trade_count"] == 0


def test_cagr_positive_on_up_trend() -> None:
    # ~1y of business days, 100 → 200
    idx = pd.bdate_range("2020-01-02", periods=253)
    eq = pd.Series([100.0 + i * (100.0 / 252) for i in range(253)], index=idx)
    m = compute_metrics(eq, initial_cash=100.0, round_trips=[])
    assert m["cagr"] is not None and m["cagr"] > 0
    assert m["total_return"] == pytest.approx(eq.iloc[-1] / 100.0 - 1.0)
    assert m["sharpe"] is not None and m["sharpe"] > 0
