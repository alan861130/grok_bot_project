"""Portfolio backtester: same-close fills, equal-weight, commissions (no network)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.data.provider import PandasDataProvider
from tests.helpers import ScriptedStrategy, custom_ohlcv, long_set


def _two_names():
    aaa = custom_ohlcv(opens=[9, 9, 9, 9], closes=[10, 10, 12, 12])
    bbb = custom_ohlcv(opens=[19, 19, 19, 19], closes=[20, 20, 20, 20])
    return aaa, bbb


def test_fill_at_same_session_close_not_open_or_next_close() -> None:
    aaa = custom_ohlcv(opens=[8, 8, 8], closes=[10, 11, 50])
    membership = long_set(aaa.index, {"AAA": [True, True, False]})
    engine = Backtester(initial_cash=1000.0, commission=Commission(kind="bps", value=0.0))
    result = engine.run_bars(bars={"AAA": aaa}, strategy=ScriptedStrategy(membership))

    assert len(result.fills) == 2
    buy, sell = result.fills
    assert buy.side == "BUY" and buy.symbol == "AAA"
    assert buy.date == aaa.index[0]
    assert buy.price == pytest.approx(10.0)  # same-day close, not open 8
    assert sell.date == aaa.index[2]
    assert sell.price == pytest.approx(50.0)  # flatten at that close, not a later bar
    assert buy.shares == 100  # 1000 // 10


def test_equal_weight_two_names() -> None:
    aaa, bbb = _two_names()
    membership = long_set(aaa.index, {"AAA": [True] * 4, "BBB": [True] * 4})
    engine = Backtester(initial_cash=1000.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(
        bars={"AAA": aaa, "BBB": bbb},
        strategy=ScriptedStrategy(membership),
    )
    # One rebalance on day 0: 50% / 50% at closes 10 and 20.
    buys = [f for f in result.fills if f.side == "BUY"]
    assert {f.symbol: f.shares for f in buys} == {"AAA": 50, "BBB": 25}
    assert all(f.date == aaa.index[0] for f in buys)
    # Hold while membership unchanged — no churn.
    assert len(result.fills) == 2
    # Mark-to-market day 2 close: 50*12 + 25*20 = 1100
    assert result.equity_curve.iloc[2] == pytest.approx(1100.0)
    assert result.exposure.iloc[0] == pytest.approx(1.0)


def test_flat_when_long_set_empty() -> None:
    aaa, bbb = _two_names()
    membership = long_set(aaa.index, {"AAA": [False] * 4, "BBB": [False] * 4})
    engine = Backtester(initial_cash=1000.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(
        bars={"AAA": aaa, "BBB": bbb},
        strategy=ScriptedStrategy(membership),
    )
    assert result.fills == []
    assert (result.equity_curve == 1000.0).all()
    assert (result.exposure == 0.0).all()


def test_membership_change_rebalances_to_remaining_name() -> None:
    aaa, bbb = _two_names()
    # Both long d0-d1; only AAA on d2-d3.
    membership = long_set(
        aaa.index,
        {"AAA": [True, True, True, True], "BBB": [True, True, False, False]},
    )
    engine = Backtester(initial_cash=1000.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(
        bars={"AAA": aaa, "BBB": bbb},
        strategy=ScriptedStrategy(membership),
    )
    sell_bbb = [f for f in result.fills if f.symbol == "BBB" and f.side == "SELL"]
    assert len(sell_bbb) == 1
    assert sell_bbb[0].date == aaa.index[2]
    assert sell_bbb[0].price == pytest.approx(20.0)
    # After selling BBB, AAA should be sized toward 100% of equity at AAA close 12.
    aaa_pos = [f.position_after for f in result.fills if f.symbol == "AAA"]
    assert aaa_pos[-1] > 50


def test_bps_commission_charged_on_notional() -> None:
    aaa = custom_ohlcv(opens=[100, 100], closes=[100, 100])
    membership = long_set(aaa.index, {"AAA": [True, False]})
    engine = Backtester(initial_cash=10_000.0, commission=Commission(kind="bps", value=5.0))
    result = engine.run_bars(bars={"AAA": aaa}, strategy=ScriptedStrategy(membership))
    buy = result.fills[0]
    assert buy.commission == pytest.approx(buy.shares * 100 * 0.0005)
    assert buy.commission > 0
    assert result.equity_curve.iloc[-1] < 10_000.0


def test_provider_universe_slice() -> None:
    aaa, bbb = _two_names()
    provider = PandasDataProvider({"aaa": aaa, "bbb": bbb})
    membership = long_set(aaa.index, {"AAA": [True, False, False, False], "BBB": [False] * 4})
    engine = Backtester(initial_cash=500.0, commission=Commission("bps", 0.0))
    result = engine.run(
        provider=provider,
        strategy=ScriptedStrategy(membership),
        universe=["AAA", "BBB"],
        start=date(2020, 1, 2),
        end=date(2020, 1, 10),
    )
    assert result.universe == ["AAA", "BBB"]
    assert len(result.equity_curve) == 4


def test_rejects_empty_universe() -> None:
    engine = Backtester(initial_cash=100.0, commission=Commission("bps", 0.0))
    with pytest.raises(ValueError, match="empty"):
        engine.run_bars(bars={}, strategy=ScriptedStrategy(pd.DataFrame()))
