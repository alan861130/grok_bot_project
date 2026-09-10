"""SMA crossover long-set signals use only closes through t (rolling windows)."""

from __future__ import annotations

import pandas as pd
import pytest

from quantframe.strategy.sma import SMACrossoverStrategy
from quantframe.strategy.weights import equal_weight_long_set
from tests.helpers import trending_ohlcv


def test_warmup_is_flat_then_long_on_uptrend() -> None:
    bars = trending_ohlcv(periods=20, start_price=10.0, step=1.0)
    strat = SMACrossoverStrategy(fast=3, slow=5)
    sig = strat.generate_signals({"AAA": bars})
    assert list(sig.index) == list(bars.index)
    assert list(sig.columns) == ["AAA"]
    assert (sig.iloc[:4, 0] == False).all()  # noqa: E712
    assert (sig.iloc[4:, 0] == True).all()  # noqa: E712


def test_multi_asset_independent_signals() -> None:
    up = trending_ohlcv(periods=12, start_price=10.0, step=1.0)
    down = trending_ohlcv(periods=12, start_price=50.0, step=-1.0)
    strat = SMACrossoverStrategy(fast=2, slow=4)
    sig = strat.generate_signals({"UP": up, "DOWN": down})
    assert (sig.iloc[3:]["UP"] == True).all()  # noqa: E712
    assert (sig.iloc[3:]["DOWN"] == False).all()  # noqa: E712
    weights = strat.generate_target_weights({"UP": up, "DOWN": down})
    # Only UP is long after warmup → 100% UP, 0% DOWN
    assert weights.iloc[-1]["UP"] == pytest.approx(1.0)
    assert weights.iloc[-1]["DOWN"] == pytest.approx(0.0)


def test_equal_weight_helper() -> None:
    idx = pd.bdate_range("2020-01-02", periods=2)
    signals = pd.DataFrame({"A": [True, False], "B": [True, True], "C": [False, True]}, index=idx)
    w = equal_weight_long_set(signals)
    assert w.iloc[0]["A"] == pytest.approx(0.5)
    assert w.iloc[0]["B"] == pytest.approx(0.5)
    assert w.iloc[0]["C"] == pytest.approx(0.0)
    assert w.iloc[1]["B"] == pytest.approx(0.5)
    assert w.iloc[1]["C"] == pytest.approx(0.5)
    assert w.iloc[1].sum() == pytest.approx(1.0)


def test_fast_must_be_less_than_slow() -> None:
    with pytest.raises(ValueError):
        SMACrossoverStrategy(fast=20, slow=20)


def test_signal_independent_of_future_tail() -> None:
    bars = trending_ohlcv(periods=15, start_price=10.0, step=0.25)
    strat = SMACrossoverStrategy(fast=2, slow=4)
    full = strat.generate_signals({"AAA": bars})
    prefix = strat.generate_signals({"AAA": bars.iloc[:10]})
    pd.testing.assert_frame_equal(full.iloc[:10], prefix)
