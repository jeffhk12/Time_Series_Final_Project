"""Layer 1 short-volatility backtest — main entry point.

Run with:
    /path/to/python src/run_layer1.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from data_loader import load_price_data, load_option_chain  # noqa: E402
from volatility_models import compute_ewma_vol  # noqa: E402
from option_selector import select_atm_straddle  # noqa: E402
from backtest_engine import STRATEGIES, run_backtest, build_chain_by_date  # noqa: E402
from metrics import calculate_performance_metrics  # noqa: E402
import plots  # noqa: E402


WORKSPACE = os.path.dirname(HERE)
TABLE_DIR = os.path.join(WORKSPACE, "outputs", "tables")
os.makedirs(TABLE_DIR, exist_ok=True)


def build_daily_iv_series(price: pd.DataFrame, chain_by_date: dict) -> pd.Series:
    """For each trading day, return IV of the ATM-30d straddle (mid) — used for charts."""
    out = []
    for _, row in price.iterrows():
        d = pd.Timestamp(row["date"])
        ch = chain_by_date.get(d)
        if ch is None:
            out.append(np.nan)
            continue
        pick = select_atm_straddle(ch, row["uso_close"])
        if pick is None:
            out.append(np.nan)
        else:
            c, p, _, _ = pick
            iv = (c["iv_mid"] + p["iv_mid"]) / 2.0
            out.append(iv if iv > 0 else np.nan)
    return pd.Series(out, index=price.index)


def main():
    print("Loading price data...")
    price = load_price_data()
    print(f"  {len(price)} rows  {price['date'].min().date()} -> {price['date'].max().date()}")

    print("Loading option chain (this is ~200MB across 28 CSVs)...")
    chain = load_option_chain()
    print(f"  {len(chain):,} option rows")

    print("Indexing chain by trade date...")
    chain_by_date = build_chain_by_date(chain)

    print("Computing EWMA realized volatility (lambda=0.94)...")
    ewma = compute_ewma_vol(price["log_return"], lam=0.94)
    price["ewma_vol_daily"] = ewma["ewma_vol_daily"].values
    price["ewma_vol_annual"] = ewma["ewma_vol_annual"].values

    print("Building daily ATM-30d IV series for plots...")
    iv_series = build_daily_iv_series(price, chain_by_date)
    price["atm_iv"] = iv_series.values

    # Static charts
    plots.plot_underlying(price)
    plots.plot_ewma_vol(price, price["ewma_vol_annual"])
    plots.plot_iv_vs_ewma(price["atm_iv"], price["ewma_vol_annual"], price["date"])

    print("\nRunning strategies...")
    daily_by_strategy = {}
    trades_by_strategy = {}
    metrics_rows = []
    for cfg in STRATEGIES:
        print(f"  -> {cfg.name}")
        daily, trades = run_backtest(cfg, price, chain_by_date, price["ewma_vol_annual"])
        daily_by_strategy[cfg.name] = daily
        trades_by_strategy[cfg.name] = trades
        m = calculate_performance_metrics(daily["total_pnl"], trades)
        m["strategy"] = cfg.name
        metrics_rows.append(m)
        # Save per-strategy artifacts
        daily.to_csv(os.path.join(TABLE_DIR, f"daily_{cfg.name}.csv"), index=False)
        trades.to_csv(os.path.join(TABLE_DIR, f"trades_{cfg.name}.csv"), index=False)

    # Combined comparison charts + table
    plots.plot_cumulative_pnl(daily_by_strategy)
    plots.plot_drawdown(daily_by_strategy)
    plots.plot_trade_pnl_hist(trades_by_strategy)
    plots.plot_hedge_vs_unhedged(daily_by_strategy)

    metrics_df = pd.DataFrame(metrics_rows)
    cols = ["strategy", "num_trades", "total_pnl", "ann_return_$", "ann_vol_$", "sharpe",
            "max_drawdown_$", "win_rate_%", "avg_trade_pnl", "worst_trade", "best_trade",
            "avg_holding_days", "avg_tcost_per_trade"]
    metrics_df = metrics_df[cols]
    metrics_path = os.path.join(TABLE_DIR, "performance_summary.csv")
    metrics_df.to_csv(metrics_path, index=False)

    print("\n========== LAYER 1 PERFORMANCE SUMMARY ==========")
    with pd.option_context("display.float_format", "{:,.2f}".format, "display.width", 160, "display.max_columns", 20):
        print(metrics_df.to_string(index=False))
    print(f"\nCharts written to: {os.path.join(WORKSPACE, 'outputs', 'charts')}")
    print(f"Tables written to: {TABLE_DIR}")


if __name__ == "__main__":
    main()
