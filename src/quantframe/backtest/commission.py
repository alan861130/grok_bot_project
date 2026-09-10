"""Simple commission models: fixed dollars per fill, or basis points of notional."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CommissionKind = Literal["fixed", "bps"]


@dataclass(frozen=True)
class Commission:
    """Transaction cost applied on each fill (entry or exit).

    ``kind="fixed"``: ``value`` is dollars per fill (e.g. 1.0 → $1).
    ``kind="bps"``: ``value`` is basis points of fill notional (e.g. 1.0 → 0.01%).
    """

    kind: CommissionKind = "bps"
    value: float = 5.0

    def __post_init__(self) -> None:
        if self.kind not in ("fixed", "bps"):
            raise ValueError("commission kind must be 'fixed' or 'bps'")
        if self.value < 0:
            raise ValueError("commission value must be >= 0")

    def on_fill(self, notional: float) -> float:
        """Dollar cost for a fill with the given absolute notional."""
        notional = abs(float(notional))
        if self.kind == "fixed":
            return float(self.value) if notional > 0 else 0.0
        return notional * (self.value / 10_000.0)

    def label(self) -> str:
        if self.kind == "fixed":
            return f"${self.value:.4g} per fill"
        return f"{self.value:.4g} bps of notional"
