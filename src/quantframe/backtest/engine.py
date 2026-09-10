"""Long-only equal-weight portfolio backtester (daily bars, same-close fills)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np
import pandas as pd

from quantframe.backtest.commission import Commission
from quantframe.backtest.result import BacktestResult, Fill, RoundTrip
from quantframe.backtest.slippage import Slippage, ZeroSlippage
from quantframe.data.provider import DataProvider, align_universe
from quantframe.defaults import DEMO_CASH, DEMO_COMMISSION_BPS
from quantframe.metrics.calc import compute_metrics
from quantframe.strategy.base import Strategy
from quantframe.types import BarsBySymbol

_WEIGHT_ATOL = 1e-9


class Backtester:
    """Run a long-only / long-flat portfolio strategy over daily US equity bars.

    Target weights are taken from ``strategy.generate_target_weights`` (by
    default: equal-weight the long set). Fills occur at the **same session
    close**. Whole shares; leftover cash stays in the account. Positions are
    resized when the target-weight vector changes (not on daily price drift).
    """

    def __init__(
        self,
        initial_cash: float = DEMO_CASH,
        commission: Commission | None = None,
        slippage: Slippage | None = None,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.initial_cash = float(initial_cash)
        self.commission = commission or Commission(kind="bps", value=DEMO_COMMISSION_BPS)
        self.slippage = slippage or ZeroSlippage()

    def run(
        self,
        *,
        provider: DataProvider,
        strategy: Strategy,
        universe: Sequence[str],
        start: date,
        end: date,
    ) -> BacktestResult:
        bars = provider.get_universe_bars(universe, start, end)
        return self.run_bars(bars=bars, strategy=strategy)

    def run_bars(self, *, bars: BarsBySymbol, strategy: Strategy) -> BacktestResult:
        if not bars:
            raise ValueError("bars is empty")
        aligned = align_universe(bars, how="inner")
        symbols = list(aligned)
        calendar = aligned[symbols[0]].index
        if len(calendar) < 1:
            raise ValueError("need at least one daily bar")

        raw_signals = strategy.generate_signals(aligned)
        signals = _align_signals(raw_signals, calendar, symbols)
        weights = _align_weights(strategy.generate_target_weights(aligned), calendar, symbols)

        cash = self.initial_cash
        positions = {s: 0 for s in symbols}
        equity_vals: list[float] = []
        exposure_vals: list[float] = []
        fills: list[Fill] = []
        round_trips: list[RoundTrip] = []
        open_trips: dict[str, RoundTrip] = {}
        prev_w = pd.Series(0.0, index=symbols)

        for ts in calendar:
            px = {s: float(aligned[s].loc[ts, "close"]) for s in symbols}
            target = weights.loc[ts]
            if not np.allclose(target.to_numpy(dtype=float), prev_w.to_numpy(dtype=float), atol=_WEIGHT_ATOL):
                cash, day_fills, closed = self._rebalance(
                    ts=ts,
                    cash=cash,
                    positions=positions,
                    prices=px,
                    target=target,
                    open_trips=open_trips,
                )
                fills.extend(day_fills)
                round_trips.extend(closed)
                prev_w = target.astype(float)

            invested = sum(positions[s] * px[s] for s in symbols)
            equity = cash + invested
            equity_vals.append(equity)
            exposure_vals.append((invested / equity) if equity else 0.0)

        last_px = {s: float(aligned[s]["close"].iloc[-1]) for s in symbols}
        last_ts = calendar[-1]
        for trip in list(open_trips.values()):
            mark = last_px[trip.symbol]
            trip.exit_price = mark
            unreal = (mark - trip.entry_price) * trip.shares
            trip.pnl = (trip.pnl or 0.0) + unreal
            trip.return_pct = (trip.pnl / trip.buy_notional) if trip.buy_notional else None
            round_trips.append(trip)

        equity = pd.Series(equity_vals, index=calendar, name="equity")
        exposure = pd.Series(exposure_vals, index=calendar, name="exposure")
        notes = [
            "Phase 1: long-only / long-flat equal-weight portfolio, daily US equity bars.",
            "Adjusted prices (yfinance auto_adjust=True when using the default provider).",
            "Signal at close t is filled at the same close t (optimistic same-day execution).",
            "Equal-weight among names in the long set; 100% cash when the long set is empty.",
            "No shorting. Whole shares; leftover cash stays in the account.",
            "Rebalance when target weights change (membership change for equal-weight SMA); no daily drift rebalance.",
            "Commission on traded notional; no slippage model (hook is present, default is zero).",
        ]

        result = BacktestResult(
            universe=symbols,
            start=calendar[0].date(),
            end=calendar[-1].date(),
            strategy_name=strategy.name,
            strategy_params=strategy.params(),
            initial_cash=self.initial_cash,
            commission=self.commission,
            bars=aligned,
            signals=signals,
            weights=weights,
            equity_curve=equity,
            exposure=exposure,
            fills=fills,
            round_trips=round_trips,
            notes=notes,
        )
        result.metrics = compute_metrics(
            result.equity_curve,
            result.initial_cash,
            result.round_trips,
            exposure=result.exposure,
        )
        return result

    def _rebalance(
        self,
        *,
        ts: pd.Timestamp,
        cash: float,
        positions: dict[str, int],
        prices: dict[str, float],
        target: pd.Series,
        open_trips: dict[str, RoundTrip],
    ) -> tuple[float, list[Fill], list[RoundTrip]]:
        symbols = list(positions)
        equity = cash + sum(positions[s] * prices[s] for s in symbols)
        desired = {
            s: _shares_for_budget(equity * float(target.get(s, 0.0)), prices[s], self.commission)
            for s in symbols
        }

        fills: list[Fill] = []
        closed: list[RoundTrip] = []

        # Sells first so buys can reuse cash.
        for s in symbols:
            delta = desired[s] - positions[s]
            if delta < 0:
                cash, fill, done = self._execute(
                    ts=ts,
                    symbol=s,
                    side="SELL",
                    shares=-delta,
                    bar_price=prices[s],
                    cash=cash,
                    positions=positions,
                    open_trips=open_trips,
                )
                if fill is not None:
                    fills.append(fill)
                if done is not None:
                    closed.append(done)

        for s in symbols:
            delta = desired[s] - positions[s]
            if delta > 0:
                affordable = _max_shares_for_cash(cash, prices[s], self.commission)
                take = min(delta, affordable)
                if take <= 0:
                    continue
                cash, fill, done = self._execute(
                    ts=ts,
                    symbol=s,
                    side="BUY",
                    shares=take,
                    bar_price=prices[s],
                    cash=cash,
                    positions=positions,
                    open_trips=open_trips,
                )
                if fill is not None:
                    fills.append(fill)
                if done is not None:
                    closed.append(done)

        return cash, fills, closed

    def _execute(
        self,
        *,
        ts: pd.Timestamp,
        symbol: str,
        side: str,
        shares: int,
        bar_price: float,
        cash: float,
        positions: dict[str, int],
        open_trips: dict[str, RoundTrip],
    ) -> tuple[float, Fill | None, RoundTrip | None]:
        if shares <= 0:
            return cash, None, None
        price = self.slippage.on_fill(bar_price, side)
        notional = shares * price
        fee = self.commission.on_fill(notional)
        closed: RoundTrip | None = None

        if side == "BUY":
            cost = notional + fee
            if cost > cash + 1e-9:
                return cash, None, None
            cash -= cost
            positions[symbol] += shares
            _open_or_add(open_trips, symbol, ts, shares, price, fee)
        else:
            if shares > positions[symbol]:
                shares = positions[symbol]
                if shares <= 0:
                    return cash, None, None
                notional = shares * price
                fee = self.commission.on_fill(notional)
            cash += notional - fee
            positions[symbol] -= shares
            closed = _reduce_or_close(open_trips, symbol, ts, shares, price, fee)

        fill = Fill(
            date=ts,
            symbol=symbol,
            side=side,
            shares=shares,
            price=price,
            commission=fee,
            cash_after=cash,
            position_after=positions[symbol],
        )
        return cash, fill, closed


def _shares_for_budget(budget: float, price: float, commission: Commission) -> int:
    if budget <= 0 or price <= 0:
        return 0
    return _max_shares_for_cash(budget, price, commission)


def _max_shares_for_cash(cash: float, price: float, commission: Commission) -> int:
    if cash <= 0 or price <= 0:
        return 0
    lo, hi = 0, int(cash // price)
    ans = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid == 0:
            lo = 1
            continue
        fee = commission.on_fill(mid * price)
        if mid * price + fee <= cash + 1e-9:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ans


def _open_or_add(
    open_trips: dict[str, RoundTrip],
    symbol: str,
    ts: pd.Timestamp,
    shares: int,
    price: float,
    fee: float,
) -> None:
    trip = open_trips.get(symbol)
    if trip is None:
        open_trips[symbol] = RoundTrip(
            symbol=symbol,
            entry_date=ts,
            exit_date=None,
            side="LONG",
            shares=shares,
            entry_price=price,
            exit_price=None,
            entry_commission=fee,
            exit_commission=0.0,
            pnl=-fee,
            return_pct=None,
            open=True,
            buy_notional=shares * price,
            peak_shares=shares,
        )
        return
    total_cost = trip.shares * trip.entry_price + shares * price
    trip.shares += shares
    trip.entry_price = total_cost / trip.shares if trip.shares else price
    trip.entry_commission += fee
    trip.pnl = (trip.pnl or 0.0) - fee
    trip.buy_notional += shares * price
    trip.peak_shares = max(trip.peak_shares, trip.shares)


def _reduce_or_close(
    open_trips: dict[str, RoundTrip],
    symbol: str,
    ts: pd.Timestamp,
    shares: int,
    price: float,
    fee: float,
) -> RoundTrip | None:
    trip = open_trips.get(symbol)
    if trip is None:
        return None
    realized = (price - trip.entry_price) * shares - fee
    trip.pnl = (trip.pnl or 0.0) + realized
    trip.exit_commission += fee
    trip.shares -= shares
    if trip.shares > 0:
        return None
    trip.exit_date = ts
    trip.exit_price = price
    trip.open = False
    trip.shares = 0
    trip.return_pct = (trip.pnl / trip.buy_notional) if trip.buy_notional else None
    del open_trips[symbol]
    return trip


def _align_signals(
    signals: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("generate_signals must return a DataFrame (dates × symbols, boolean)")
    cols = {str(c).upper(): c for c in signals.columns}
    data = {}
    for s in symbols:
        if s in cols:
            data[s] = signals[cols[s]]
        elif s in signals.columns:
            data[s] = signals[s]
        else:
            data[s] = False
    out = pd.DataFrame(data, index=signals.index).reindex(calendar).fillna(False).astype(bool)
    out.columns = symbols
    return out


def _align_weights(
    weights: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("generate_target_weights must return a DataFrame (dates × symbols)")
    cols = {str(c).upper(): c for c in weights.columns}
    data = {}
    for s in symbols:
        src = cols.get(s, s if s in weights.columns else None)
        data[s] = weights[src] if src is not None else 0.0
    out = pd.DataFrame(data, index=weights.index).reindex(calendar).fillna(0.0).astype(float).clip(lower=0.0)
    row_sum = out.sum(axis=1)
    over = row_sum > 1.0 + _WEIGHT_ATOL
    if bool(over.any()):
        out.loc[over] = out.loc[over].div(row_sum.loc[over], axis=0)
    out.columns = symbols
    return out
