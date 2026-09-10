"""Phase-1 demo defaults (US equities, daily, portfolio)."""

from __future__ import annotations

from datetime import date

DEMO_UNIVERSE: tuple[str, ...] = ("SPY", "QQQ", "AAPL", "MSFT", "GOOGL")
DEMO_FAST = 20
DEMO_SLOW = 50
DEMO_CASH = 100_000.0
DEMO_COMMISSION_BPS = 5.0
DEMO_LOOKBACK_YEARS = 5


def lookback_window(end: date | None = None, years: int = DEMO_LOOKBACK_YEARS) -> tuple[date, date]:
    """Inclusive start/end covering about ``years`` calendar years ending at ``end``."""
    end = end or date.today()
    try:
        start = end.replace(year=end.year - years)
    except ValueError:
        # 29 Feb → 28 Feb in a non-leap start year
        start = end.replace(year=end.year - years, day=28)
    return start, end
