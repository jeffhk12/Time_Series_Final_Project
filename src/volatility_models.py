"""EWMA realized volatility."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_ewma_vol(log_returns: pd.Series, lam: float = 0.94) -> pd.DataFrame:
    """Return daily and annualized EWMA volatility for a series of log returns.

    sigma_t^2 = lam * sigma_{t-1}^2 + (1 - lam) * r_t^2
    """
    r = log_returns.fillna(0.0).to_numpy()
    var = np.zeros_like(r)
    # Seed with the simple variance of the first 20 returns to avoid warm-up bias.
    seed = np.nanvar(r[1:21]) if len(r) > 21 else np.nanvar(r[1:])
    var[0] = seed
    for t in range(1, len(r)):
        var[t] = lam * var[t - 1] + (1.0 - lam) * r[t] ** 2
    daily = np.sqrt(var)
    annual = daily * np.sqrt(252.0)
    return pd.DataFrame(
        {"ewma_vol_daily": daily, "ewma_vol_annual": annual},
        index=log_returns.index,
    )
