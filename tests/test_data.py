"""DataProvider contract on in-memory frames."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quantframe.data.provider import PandasDataProvider, _normalize_ohlcv
from tests.helpers import custom_ohlcv


def test_normalize_lowercases_and_sorts() -> None:
    idx = pd.to_datetime(["2020-01-03", "2020-01-02"])
    raw = pd.DataFrame(
        {
            "Open": [11.0, 10.0],
            "High": [11.2, 10.2],
            "Low": [10.8, 9.8],
            "Close": [11.0, 10.1],
            "Volume": [1.0, 2.0],
        },
        index=idx,
    )
    out = _normalize_ohlcv(raw)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index[0] < out.index[1]


def test_pandas_provider_inclusive_range() -> None:
    bars = custom_ohlcv(opens=[10, 10, 10], closes=[10, 11, 12])
    provider = PandasDataProvider({"aaa": bars})
    got = provider.get_daily_bars("AAA", start=date(2020, 1, 2), end=date(2020, 1, 3))
    assert len(got) == 2
    with pytest.raises(KeyError):
        provider.get_daily_bars("BBB", start=date(2020, 1, 2), end=date(2020, 1, 3))
