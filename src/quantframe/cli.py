"""CLI: run a daily US equity *portfolio* backtest and write Markdown + HTML reports."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from quantframe import __version__
from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.data.yfinance_provider import YFinanceDataProvider
from quantframe.defaults import (
    DEMO_CASH,
    DEMO_COMMISSION_BPS,
    DEMO_FAST,
    DEMO_LOOKBACK_YEARS,
    DEMO_SLOW,
    DEMO_UNIVERSE,
    lookback_window,
)
from quantframe.report.render import write_reports
from quantframe.strategy.sma import SMACrossoverStrategy


def main(argv: list[str] | None = None) -> int:
    default_start, default_end = lookback_window()
    parser = argparse.ArgumentParser(
        prog="quantframe",
        description="Phase-1 US equities quant framework (daily portfolio backtests + reports).",
    )
    parser.add_argument("--version", action="version", version=f"quantframe {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser(
        "run-sample",
        help=(
            "Run the bundled multi-asset SMA 20/50 portfolio backtest "
            f"({', '.join(DEMO_UNIVERSE)}, last ~{DEMO_LOOKBACK_YEARS} years) and write reports."
        ),
    )
    p_sample.add_argument("--output-dir", default="outputs", help="Report directory (default: outputs)")

    p_bt = sub.add_parser("backtest", help="Run a daily SMA crossover portfolio backtest.")
    p_bt.add_argument(
        "--universe",
        default=",".join(DEMO_UNIVERSE),
        help="Comma-separated tickers (default: SPY,QQQ,AAPL,MSFT,GOOGL)",
    )
    p_bt.add_argument("--start", default=default_start.isoformat(), help="Inclusive start date YYYY-MM-DD")
    p_bt.add_argument("--end", default=default_end.isoformat(), help="Inclusive end date YYYY-MM-DD")
    p_bt.add_argument("--fast", type=int, default=DEMO_FAST)
    p_bt.add_argument("--slow", type=int, default=DEMO_SLOW)
    p_bt.add_argument("--cash", type=float, default=DEMO_CASH)
    p_bt.add_argument(
        "--commission-bps",
        type=float,
        default=None,
        help=f"Commission in bps of notional (default {DEMO_COMMISSION_BPS}).",
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
        start, end = lookback_window()
        return _run(
            universe=list(DEMO_UNIVERSE),
            start=start,
            end=end,
            fast=DEMO_FAST,
            slow=DEMO_SLOW,
            cash=DEMO_CASH,
            commission=Commission(kind="bps", value=DEMO_COMMISSION_BPS),
            output_dir=args.output_dir,
        )
    if args.cmd == "backtest":
        start = _parse_date(args.start)
        end = _parse_date(args.end)
        if args.commission_fixed is not None:
            commission = Commission(kind="fixed", value=args.commission_fixed)
        else:
            bps = DEMO_COMMISSION_BPS if args.commission_bps is None else args.commission_bps
            commission = Commission(kind="bps", value=bps)
        return _run(
            universe=_parse_universe(args.universe),
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
    universe: list[str],
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
        universe=universe,
        start=start,
        end=end,
    )
    md_path, html_path = write_reports(result, Path(output_dir))
    print(f"universe={result.universe_label}  sessions={len(result.equity_curve)}  {result.start} → {result.end}")
    print(f"strategy={result.strategy_name}  params={result.strategy_params}")
    print(f"ending_equity={result.ending_equity:,.2f}  total_return={result.metrics.get('total_return')}")
    print(f"wrote {md_path}")
    print(f"wrote {html_path}")
    return 0


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_universe(value: str) -> list[str]:
    names = [part.strip().upper() for part in value.split(",") if part.strip()]
    if not names:
        raise SystemExit("universe is empty")
    return names
