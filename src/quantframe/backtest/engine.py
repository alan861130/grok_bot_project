"""Long-only / long-flat daily backtester.

Fills the signal from session t at the open of session t+1. Integer shares.
Rebalances only when the target weight changes (hold through a regime).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from quantframe.backtest.commission import Commission
from quantframe.backtest.result import BacktestResult, Fill, RoundTrip
from quantframe.data.provider import DataProvider, _normalize_ohlcv
from quantframe.strategy.base import Strategy

_WEIGHT_EPS = 1e-9


class Backtester:
    """Run a strategy over daily US equity bars.

    Parameters
    ----------
    initial_cash:
        Starting cash in USD.
    commission:
        Per-fill cost model.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission: Commission | None = None,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.initial_cash = float(initial_cash)
        self.commission = commission or Commission(kind="bps", value=1.0)

    def run(
        self,
        *,
        provider: DataProvider,
        strategy: Strategy,
        symbol: str,
        start: date,
        end: date,
    ) -> BacktestResult:
        bars = _normalize_ohlcv(provider.get_daily_bars(symbol, start, end))
        return self.run_bars(bars=bars, strategy=strategy, symbol=symbol)

    def run_bars(
        self,
        *,
        bars: pd.DataFrame,
        strategy: Strategy,
        symbol: str,
    ) -> BacktestResult:
        bars = _normalize_ohlcv(bars)
        if len(bars) < 2:
            raise ValueError("need at least two daily bars to fill at next open")

        raw_signals = strategy.generate_signals(bars)
        signals = _align_signals(raw_signals, bars.index)

        cash = self.initial_cash
        shares = 0
        equity_vals: list[float] = []
        fills: list[Fill] = []
        round_trips: list[RoundTrip] = []
        open_trip: RoundTrip | None = None
        prev_target = 0.0

        for i, ts in enumerate(bars.index):
            row = bars.iloc[i]
            o = float(row["open"])
            c = float(row["close"])

            # Execute yesterday's close-time signal at today's open.
            if i > 0:
                target = float(signals.iloc[i - 1])
                if abs(target - prev_target) > _WEIGHT_EPS:
                    cash, shares, fill, open_trip, closed = self._rebalance(
                        ts=ts,
                        open_price=o,
                        cash=cash,
                        shares=shares,
                        target=target,
                        open_trip=open_trip,
                    )
                    if fill is not None:
                        fills.append(fill)
                    if closed is not None:
                        round_trips.append(closed)
                    prev_target = target

            equity_vals.append(cash + shares * c)

        equity = pd.Series(equity_vals, index=bars.index, name="equity")

        if open_trip is not None:
            last_close = float(bars["close"].iloc[-1])
            open_trip.exit_price = last_close
            open_trip.pnl = (last_close - open_trip.entry_price) * open_trip.shares - (
                open_trip.entry_commission + open_trip.exit_commission
            )
            denom = open_trip.entry_price * open_trip.shares
            open_trip.return_pct = (open_trip.pnl / denom) if denom else None
            round_trips.append(open_trip)

        notes = [
            "Phase 1: long-only / long-flat, daily bars, next-open fills.",
            "Signal at close t is filled at open t+1 (no same-bar close fill).",
            "Whole shares only; leftover cash stays in the account.",
            "Position is held while the target weight is unchanged (no daily drift rebalance).",
            "Prices from the data provider are used as-is (yfinance default is auto-adjusted).",
        ]

        return BacktestResult(
            symbol=symbol.upper(),
            start=bars.index[0].date(),
            end=bars.index[-1].date(),
            strategy_name=strategy.name,
            strategy_params=strategy.params(),
            initial_cash=self.initial_cash,
            commission=self.commission,
            bars=bars,
            signals=signals,
            equity_curve=equity,
            fills=fills,
            round_trips=round_trips,
            notes=notes,
        )

    def _rebalance(
        self,
        *,
        ts: pd.Timestamp,
        open_price: float,
        cash: float,
        shares: int,
        target: float,
        open_trip: RoundTrip | None,
    ) -> tuple[float, int, Fill | None, RoundTrip | None, RoundTrip | None]:
        target = 0.0 if target < 0.5 else 1.0  # Phase 1: binary long/flat
        desired = 0 if target == 0.0 else _max_shares(cash, shares, open_price, self.commission)
        delta = desired - shares
        if delta == 0:
            return cash, shares, None, open_trip, None

        notional = abs(delta) * open_price
        fee = self.commission.on_fill(notional)

        if delta > 0:
            cost = delta * open_price + fee
            if cost > cash + 1e-9:
                # Should not happen if _max_shares is correct; fail safe to no-op.
                return cash, shares, None, open_trip, None
            cash -= cost
            shares += delta
            fill = Fill(
                date=ts,
                side="BUY",
                shares=delta,
                price=open_price,
                commission=fee,
                cash_after=cash,
                shares_after=shares,
            )
            open_trip = RoundTrip(
                entry_date=ts,
                exit_date=None,
                side="LONG",
                shares=delta,
                entry_price=open_price,
                exit_price=None,
                entry_commission=fee,
                exit_commission=0.0,
                pnl=None,
                return_pct=None,
                open=True,
            )
            return cash, shares, fill, open_trip, None

        # Sell (flatten).
        proceeds = abs(delta) * open_price - fee
        cash += proceeds
        sold = abs(delta)
        shares += delta  # delta negative
        fill = Fill(
            date=ts,
            side="SELL",
            shares=sold,
            price=open_price,
            commission=fee,
            cash_after=cash,
            shares_after=shares,
        )
        closed: RoundTrip | None = None
        if open_trip is not None:
            open_trip.exit_date = ts
            open_trip.exit_price = open_price
            open_trip.exit_commission = fee
            open_trip.open = False
            open_trip.pnl = (open_price - open_trip.entry_price) * open_trip.shares - (
                open_trip.entry_commission + open_trip.exit_commission
            )
            denom = open_trip.entry_price * open_trip.shares
            open_trip.return_pct = (open_trip.pnl / denom) if denom else None
            closed = open_trip
        return cash, shares, fill, None, closed


def _max_shares(cash: float, shares: int, price: float, commission: Commission) -> int:
    """Largest whole-share long size affordable from cash+position at ``price``."""
    equity = cash + shares * price
    if equity <= 0 or price <= 0:
        return 0
    # Iterate a couple of times so fixed commissions still fit.
    guess = int(equity // price)
    for _ in range(4):
        notional = guess * price
        fee = commission.on_fill(notional) if guess > 0 else 0.0
        affordable = int((equity - fee) // price)
        if affordable <= 0:
            return 0
        if affordable == guess:
            return guess
        guess = affordable
    return max(0, guess)


def _align_signals(signals: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    if not isinstance(signals, pd.Series):
        raise TypeError("generate_signals must return a pandas Series")
    aligned = signals.reindex(index)
    if aligned.isna().all():
        raise ValueError("strategy signals could not be aligned to bar index")
    aligned = aligned.fillna(0.0).astype(float).clip(lower=0.0, upper=1.0)
    aligned.name = "target_weight"
    return aligned
