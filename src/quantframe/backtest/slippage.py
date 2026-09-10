"""Optional fill-price adjustment. Phase 1 default is zero (no slippage model)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Slippage(ABC):
    """Hook for later slippage models. Applied to the execution price of a fill."""

    @abstractmethod
    def on_fill(self, price: float, side: str) -> float:
        """Return the execution price given the bar price and ``BUY`` / ``SELL``."""


class ZeroSlippage(Slippage):
    """No slippage — fill at the bar price (Phase 1 default)."""

    def on_fill(self, price: float, side: str) -> float:
        return float(price)
