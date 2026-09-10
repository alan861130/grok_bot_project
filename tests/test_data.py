"""DataProvider contract on in-memory frames."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quantframe.data.provider import PandasDataProvider, _normalize_ohlcv, align_universe
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


def test_pandas_provider_universe() -> None:
    a = custom_ohlcv(opens=[10, 10, 10], closes=[10, 11, 12])
    b = custom_ohlcv(opens=[20, 20, 20], closes=[20, 21, 22])
    provider = PandasDataProvider({"aaa": a, "bbb": b})
    uni = provider.get_universe_bars(["AAA", "BBB"], start=date(2020, 1, 2), end=date(2020, 1, 3))
    assert set(uni) == {"AAA", "BBB"}
    assert len(uni["AAA"]) == 2
    with pytest.raises(ValueError, match="CCC"):
        provider.get_universe_bars(["AAA", "BBB", "CCC"], start=date(2020, 1, 2), end=date(2020, 1, 3))


def test_align_universe_inner_join() -> None:
    a = custom_ohlcv(opens=[10, 10, 10], closes=[10, 11, 12])
    b = custom_ohlcv(opens=[20, 20], closes=[20, 21])
    aligned = align_universe({"AAA": a, "BBB": b}, how="inner")
    assert len(aligned["AAA"]) == 2
    assert list(aligned["AAA"].index) == list(aligned["BBB"].index)
