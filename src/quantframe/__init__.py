"""Phase-1 US equities quant framework: daily portfolio backtests, reports."""

from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.backtest.result import BacktestResult
from quantframe.backtest.slippage import Slippage, ZeroSlippage
from quantframe.data.provider import DataProvider, PandasDataProvider
from quantframe.data.yfinance_provider import YFinanceDataProvider
from quantframe.strategy.base import Strategy
from quantframe.strategy.sma import SMACrossoverStrategy

__version__ = "0.1.0"

__all__ = [
    "Backtester",
    "BacktestResult",
    "Commission",
    "DataProvider",
    "PandasDataProvider",
    "SMACrossoverStrategy",
    "Slippage",
    "Strategy",
    "YFinanceDataProvider",
    "ZeroSlippage",
    "__version__",
]
