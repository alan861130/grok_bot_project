"""Convert a boolean long set into equal-weight target holdings."""

from __future__ import annotations

import pandas as pd

_EPS = 1e-12


def equal_weight_long_set(signals: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight names that are True/positive; all-zero row → 100% cash."""
    if signals.empty:
        return signals.astype(float)
    long = signals.fillna(False).astype(bool)
    n_long = long.sum(axis=1)
    weights = long.astype(float)
    scale = n_long.where(n_long > 0)
    weights = weights.div(scale, axis=0).fillna(0.0)
    weights = weights.clip(lower=0.0)
    # Guard against float residue if a row somehow exceeded 1.
    row_sum = weights.sum(axis=1)
    over = row_sum > 1.0 + _EPS
    if bool(over.any()):
        weights.loc[over] = weights.loc[over].div(row_sum.loc[over], axis=0)
    return weights
