"""Performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_performance_metrics(daily_pnl: pd.Series, trade_log: pd.DataFrame, capital: float = 10_000.0) -> dict:
    pnl = daily_pnl.fillna(0.0)
    cum = pnl.cumsum()
    n_days = len(pnl)
    total = cum.iloc[-1] if n_days else 0.0
    ann_return = total / max(n_days, 1) * 252.0
    ann_vol = pnl.std() * np.sqrt(252.0)
    sharpe = ann_return / ann_vol if ann_vol > 0 else np.nan

    # Drawdown on cumulative P&L (in dollars; capital used only for percentage scale)
    peak = cum.cummax()
    dd = cum - peak
    max_dd = dd.min()

    metrics = {
        "total_pnl": total,
        "ann_return_$": ann_return,
        "ann_return_pct_capital": ann_return / capital * 100.0,
        "ann_vol_$": ann_vol,
        "sharpe": sharpe,
        "max_drawdown_$": max_dd,
        "n_days": n_days,
    }

    if trade_log is not None and len(trade_log):
        tl = trade_log
        metrics.update({
            "num_trades": len(tl),
            "win_rate_%": (tl["trade_pnl"] > 0).mean() * 100.0,
            "avg_trade_pnl": tl["trade_pnl"].mean(),
            "worst_trade": tl["trade_pnl"].min(),
            "best_trade": tl["trade_pnl"].max(),
            "avg_holding_days": tl["holding_days"].mean(),
            "avg_tcost_per_trade": tl.get("transaction_costs", pd.Series([np.nan])).mean(),
        })
    else:
        metrics.update({
            "num_trades": 0,
            "win_rate_%": np.nan,
            "avg_trade_pnl": np.nan,
            "worst_trade": np.nan,
            "best_trade": np.nan,
            "avg_holding_days": np.nan,
            "avg_tcost_per_trade": np.nan,
        })
    return metrics
