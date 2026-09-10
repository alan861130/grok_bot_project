"""Shared column names and small type aliases."""

from __future__ import annotations

from typing import Final

import pandas as pd

OHLCV_COLUMNS: Final[tuple[str, ...]] = ("open", "high", "low", "close", "volume")

BAR_COLUMNS_DOC = "open, high, low, close, volume"

BarsBySymbol = dict[str, pd.DataFrame]
