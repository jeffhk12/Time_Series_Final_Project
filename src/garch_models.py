"""GARCH forecasting utilities for Layer 2 timing experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from arch import arch_model


TRADING_DAYS_PER_YEAR = 252.0


@dataclass(frozen=True)
class GarchConfig:
    p: int = 1
    q: int = 1
    mean: str = "Zero"
    vol: str = "GARCH"
    dist: str = "normal"
    fit_window: int = 252
    refit_every: int = 21
    return_scale: float = 100.0


def compute_garch_vol(
    log_returns: pd.Series,
    config: GarchConfig = GarchConfig(),
) -> pd.DataFrame:
    """Build a rolling one-step-ahead GARCH volatility forecast series.

    The forecast at index ``t`` is fit only on information available through
    ``t-1`` to avoid look-ahead bias.
    """
    returns = log_returns.fillna(0.0).astype(float).reset_index(drop=True)
    n = len(returns)
    forecast_var = np.full(n, np.nan, dtype=float)

    for t in range(config.fit_window, n):
        should_refit = (t == config.fit_window) or ((t - config.fit_window) % config.refit_every == 0)
        if not should_refit and t > config.fit_window and np.isfinite(forecast_var[t - 1]):
            # Reuse the previous one-step forecast until the next scheduled refit.
            forecast_var[t] = forecast_var[t - 1]
            continue

        window = returns.iloc[t - config.fit_window:t] * config.return_scale
        model = arch_model(
            window,
            mean=config.mean,
            vol=config.vol,
            p=config.p,
            q=config.q,
            dist=config.dist,
            rescale=False,
        )
        fit = model.fit(disp="off", show_warning=False)
        variance_next = float(fit.forecast(horizon=1, reindex=False).variance.iloc[-1, 0])
        forecast_var[t] = variance_next / (config.return_scale ** 2)

    daily = np.sqrt(forecast_var)
    annual = daily * np.sqrt(TRADING_DAYS_PER_YEAR)
    return pd.DataFrame(
        {
            "garch_vol_daily": daily,
            "garch_vol_annual": annual,
        },
        index=log_returns.index,
    )
