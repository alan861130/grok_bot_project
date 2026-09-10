"""SMA crossover signals use only closes through t (rolling windows)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantframe.strategy.sma import SMACrossoverStrategy
from tests.helpers import trending_ohlcv


def test_warmup_is_flat_then_long_on_uptrend() -> None:
    bars = trending_ohlcv(periods=20, start_price=10.0, step=1.0)
    strat = SMACrossoverStrategy(fast=3, slow=5)
    sig = strat.generate_signals(bars)
    assert len(sig) == len(bars)
    assert list(sig.index) == list(bars.index)
    # First slow-1 bars cannot have a full slow SMA.
    assert (sig.iloc[:4] == 0.0).all()
    # Strictly rising close → fast SMA > slow SMA once both exist.
    assert (sig.iloc[4:] == 1.0).all()


def test_fast_must_be_less_than_slow() -> None:
    with pytest.raises(ValueError):
        SMACrossoverStrategy(fast=50, slow=50)


def test_signal_independent_of_future_tail() -> None:
    bars = trending_ohlcv(periods=15, start_price=10.0, step=0.25)
    strat = SMACrossoverStrategy(fast=2, slow=4)
    full = strat.generate_signals(bars)
    prefix = strat.generate_signals(bars.iloc[:10])
    pd.testing.assert_series_equal(full.iloc[:10], prefix, check_names=True)


def test_downtrend_stays_flat_after_warmup() -> None:
    bars = trending_ohlcv(periods=12, start_price=50.0, step=-1.0)
    sig = SMACrossoverStrategy(fast=2, slow=4).generate_signals(bars)
    assert sig.iloc[3:].sum() == 0.0
    assert np.isfinite(sig).all()
