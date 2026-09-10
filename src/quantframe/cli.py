"""CLI: run a daily US equity backtest and write Markdown + HTML reports."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from quantframe import __version__
from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.data.yfinance_provider import YFinanceDataProvider
from quantframe.metrics.calc import compute_metrics
from quantframe.report.render import write_reports
from quantframe.strategy.sma import SMACrossoverStrategy

SAMPLE_SYMBOL = "SPY"
SAMPLE_START = date(2019, 1, 1)
SAMPLE_END = date(2024, 12, 31)
SAMPLE_FAST = 50
SAMPLE_SLOW = 200
SAMPLE_CASH = 100_000.0
SAMPLE_COMMISSION_BPS = 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantframe",
        description="Phase-1 US equities quant framework (daily backtests + reports).",
    )
    parser.add_argument("--version", action="version", version=f"quantframe {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser(
        "run-sample",
        help="Run the bundled SPY SMA 50/200 daily backtest and write reports.",
    )
    p_sample.add_argument("--output-dir", default="outputs", help="Report directory (default: outputs)")

    p_bt = sub.add_parser("backtest", help="Run a daily SMA crossover backtest.")
    p_bt.add_argument("--symbol", default=SAMPLE_SYMBOL)
    p_bt.add_argument("--start", default=SAMPLE_START.isoformat(), help="Inclusive start date YYYY-MM-DD")
    p_bt.add_argument("--end", default=SAMPLE_END.isoformat(), help="Inclusive end date YYYY-MM-DD")
    p_bt.add_argument("--fast", type=int, default=SAMPLE_FAST)
    p_bt.add_argument("--slow", type=int, default=SAMPLE_SLOW)
    p_bt.add_argument("--cash", type=float, default=SAMPLE_CASH)
    p_bt.add_argument(
        "--commission-bps",
        type=float,
        default=None,
        help="Commission in bps of notional (default 1). Mutually exclusive with --commission-fixed.",
    )
    p_bt.add_argument(
        "--commission-fixed",
        type=float,
        default=None,
        help="Commission in USD per fill. Overrides --commission-bps if both set.",
    )
    p_bt.add_argument("--output-dir", default="outputs")

    args = parser.parse_args(argv)
    if args.cmd == "run-sample":
        return _run(
            symbol=SAMPLE_SYMBOL,
            start=SAMPLE_START,
            end=SAMPLE_END,
            fast=SAMPLE_FAST,
            slow=SAMPLE_SLOW,
            cash=SAMPLE_CASH,
            commission=Commission(kind="bps", value=SAMPLE_COMMISSION_BPS),
            output_dir=args.output_dir,
        )
    if args.cmd == "backtest":
        start = _parse_date(args.start)
        end = _parse_date(args.end)
        if args.commission_fixed is not None:
            commission = Commission(kind="fixed", value=args.commission_fixed)
        else:
            bps = SAMPLE_COMMISSION_BPS if args.commission_bps is None else args.commission_bps
            commission = Commission(kind="bps", value=bps)
        return _run(
            symbol=args.symbol,
            start=start,
            end=end,
            fast=args.fast,
            slow=args.slow,
            cash=args.cash,
            commission=commission,
            output_dir=args.output_dir,
        )
    parser.error("unknown command")
    return 2


def _run(
    *,
    symbol: str,
    start: date,
    end: date,
    fast: int,
    slow: int,
    cash: float,
    commission: Commission,
    output_dir: str,
) -> int:
    strategy = SMACrossoverStrategy(fast=fast, slow=slow)
    engine = Backtester(initial_cash=cash, commission=commission)
    result = engine.run(
        provider=YFinanceDataProvider(),
        strategy=strategy,
        symbol=symbol,
        start=start,
        end=end,
    )
    result.metrics = compute_metrics(result.equity_curve, result.initial_cash, result.round_trips)
    md_path, html_path = write_reports(result, Path(output_dir))
    print(f"symbol={result.symbol}  bars={len(result.bars)}  {result.start} → {result.end}")
    print(f"strategy={result.strategy_name}  params={result.strategy_params}")
    print(f"ending_equity={result.ending_equity:,.2f}  total_return={result.metrics.get('total_return')}")
    print(f"wrote {md_path}")
    print(f"wrote {html_path}")
    return 0


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
