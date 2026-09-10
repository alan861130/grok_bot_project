"""Backtester: next-open fills, no look-ahead, commissions, integer shares."""

from __future__ import annotations

from datetime import date

import pytest

from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.data.provider import PandasDataProvider
from tests.helpers import ScriptedStrategy, custom_ohlcv


def test_fill_at_next_open_not_same_bar_close() -> None:
    # Signal 1 on d1 close must buy at d2 open (11), not d1 close (11) or d2 close (12).
    bars = custom_ohlcv(
        opens=[10, 10, 11, 12, 11],
        closes=[10, 11, 12, 11, 10],
    )
    # weights at t = decision after that close
    weights = [0.0, 1.0, 1.0, 0.0, 0.0]
    engine = Backtester(initial_cash=1000.0, commission=Commission(kind="bps", value=0.0))
    result = engine.run_bars(bars=bars, strategy=ScriptedStrategy(weights), symbol="TEST")

    assert len(result.fills) == 2
    buy, sell = result.fills
    assert buy.side == "BUY"
    assert buy.date == bars.index[2]
    assert buy.price == pytest.approx(11.0)
    assert sell.side == "SELL"
    assert sell.date == bars.index[4]
    assert sell.price == pytest.approx(11.0)

    # Still cash through d1 close (index 1): no same-bar fill.
    assert result.equity_curve.iloc[0] == pytest.approx(1000.0)
    assert result.equity_curve.iloc[1] == pytest.approx(1000.0)

    shares = 1000 // 11  # 90
    assert buy.shares == shares
    # Mark-to-market at d2 close = leftover cash + 90 * 12
    leftover = 1000 - shares * 11
    assert result.equity_curve.iloc[2] == pytest.approx(leftover + shares * 12)


def test_does_not_use_future_open_for_earlier_fill() -> None:
    bars = custom_ohlcv(opens=[10, 20, 30], closes=[10, 20, 30])
    weights = [1.0, 1.0, 1.0]
    engine = Backtester(initial_cash=100.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(bars=bars, strategy=ScriptedStrategy(weights), symbol="TEST")
    # First fill is at bar 1 open (20), not bar 0 (would be look-ahead / same session).
    assert result.fills[0].date == bars.index[1]
    assert result.fills[0].price == pytest.approx(20.0)
    assert result.fills[0].shares == 5  # 100 // 20


def test_fixed_commission_reduces_cash() -> None:
    bars = custom_ohlcv(opens=[10, 10, 10, 10], closes=[10, 10, 10, 10])
    weights = [0.0, 1.0, 0.0, 0.0]
    engine = Backtester(initial_cash=1000.0, commission=Commission(kind="fixed", value=5.0))
    result = engine.run_bars(bars=bars, strategy=ScriptedStrategy(weights), symbol="TEST")
    buy = result.fills[0]
    sell = result.fills[1]
    assert buy.commission == pytest.approx(5.0)
    assert sell.commission == pytest.approx(5.0)
    # Buy at 10, fee 5 → 99 shares costs 990+5=995, cash 5; sell 99*10-5=985 → cash 990
    assert buy.shares == 99
    assert result.equity_curve.iloc[-1] == pytest.approx(990.0)


def test_bps_commission() -> None:
    bars = custom_ohlcv(opens=[100, 100, 100], closes=[100, 100, 100])
    weights = [1.0, 0.0, 0.0]
    engine = Backtester(initial_cash=10_000.0, commission=Commission(kind="bps", value=10.0))  # 0.10%
    result = engine.run_bars(bars=bars, strategy=ScriptedStrategy(weights), symbol="TEST")
    buy = result.fills[0]
    # 10 bps of 100*shares. shares chosen so equity - fee still fits.
    assert buy.commission == pytest.approx(buy.shares * 100 * 0.001)
    assert buy.commission > 0


def test_hold_does_not_churn_when_signal_stays_long() -> None:
    bars = custom_ohlcv(opens=[10, 11, 12, 13], closes=[10, 11, 12, 13])
    weights = [1.0, 1.0, 1.0, 1.0]
    engine = Backtester(initial_cash=1000.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(bars=bars, strategy=ScriptedStrategy(weights), symbol="TEST")
    assert len(result.fills) == 1
    assert result.fills[0].side == "BUY"
    assert result.round_trips[0].open is True


def test_provider_slice_and_symbol() -> None:
    bars = custom_ohlcv(opens=[10, 10, 10, 10, 10], closes=[10, 11, 12, 11, 10])
    provider = PandasDataProvider({"spy": bars})
    engine = Backtester(initial_cash=500.0, commission=Commission("bps", 0.0))
    strategy = ScriptedStrategy([0, 1, 1, 0, 0])
    result = engine.run(
        provider=provider,
        strategy=strategy,
        symbol="SPY",
        start=date(2020, 1, 2),
        end=date(2020, 1, 10),
    )
    assert result.symbol == "SPY"
    assert len(result.bars) == 5


def test_rejects_empty_or_single_bar() -> None:
    bars = custom_ohlcv(opens=[10], closes=[10])
    engine = Backtester(initial_cash=100.0, commission=Commission("bps", 0.0))
    with pytest.raises(ValueError, match="at least two"):
        engine.run_bars(bars=bars, strategy=ScriptedStrategy([0.0]), symbol="X")
