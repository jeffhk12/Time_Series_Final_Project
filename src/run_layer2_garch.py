"""Layer 2 GARCH timing backtest.

Run with:
    ./bin/python src/run_layer2_garch.py
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from backtest_engine import StrategyConfig, build_chain_by_date, run_backtest  # noqa: E402
from data_loader import load_option_chain, load_price_data  # noqa: E402
from garch_models import GarchConfig, compute_garch_vol  # noqa: E402
from metrics import calculate_performance_metrics  # noqa: E402
from option_selector import select_atm_straddle  # noqa: E402
from volatility_models import compute_ewma_vol  # noqa: E402


WORKSPACE = os.path.dirname(HERE)
TABLE_DIR = os.path.join(WORKSPACE, "outputs", "tables")
os.makedirs(TABLE_DIR, exist_ok=True)

LAYER2_STRATEGIES = [
    StrategyConfig("D_hedge_ewma_stop", use_hedge=True, use_ewma_signal=True, use_stop_loss=True),
    StrategyConfig("E_no_hedge_garch", use_hedge=False, use_ewma_signal=True, use_stop_loss=False),
    StrategyConfig("F_hedge_garch_stop", use_hedge=True, use_ewma_signal=True, use_stop_loss=True),
]


def build_daily_iv_series(price: pd.DataFrame, chain_by_date: dict) -> pd.Series:
    out = []
    for _, row in price.iterrows():
        ch = chain_by_date.get(pd.Timestamp(row["date"]))
        if ch is None:
            out.append(float("nan"))
            continue
        pick = select_atm_straddle(ch, row["uso_close"])
        if pick is None:
            out.append(float("nan"))
            continue
        call_row, put_row, _, _ = pick
        iv = (call_row["iv_mid"] + put_row["iv_mid"]) / 2.0
        out.append(iv if iv > 0 else float("nan"))
    return pd.Series(out, index=price.index)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-window", type=int, default=252, help="Rolling estimation window in trading days")
    parser.add_argument("--refit-every", type=int, default=21, help="Refit GARCH every N trading days")
    parser.add_argument("--p", type=int, default=1, help="GARCH p parameter")
    parser.add_argument("--q", type=int, default=1, help="GARCH q parameter")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Loading price data...")
    price = load_price_data()
    print(f"  {len(price)} rows  {price['date'].min().date()} -> {price['date'].max().date()}")

    print("Loading option chain...")
    chain = load_option_chain()
    print(f"  {len(chain):,} option rows")

    print("Indexing option chain by date...")
    chain_by_date = build_chain_by_date(chain)

    print("Computing EWMA benchmark volatility...")
    ewma = compute_ewma_vol(price["log_return"], lam=0.94)
    price["ewma_vol_annual"] = ewma["ewma_vol_annual"].values

    print(
        "Computing rolling GARCH forecast "
        f"(window={args.fit_window}, refit_every={args.refit_every}, p={args.p}, q={args.q})..."
    )
    garch_cfg = GarchConfig(
        p=args.p,
        q=args.q,
        fit_window=args.fit_window,
        refit_every=args.refit_every,
    )
    garch = compute_garch_vol(price["log_return"], garch_cfg)
    price["garch_vol_daily"] = garch["garch_vol_daily"].values
    price["garch_vol_annual"] = garch["garch_vol_annual"].values

    print("Building ATM IV series...")
    price["atm_iv"] = build_daily_iv_series(price, chain_by_date).values

    print("\nRunning Layer 2 strategies...")
    results = []
    strategy_signal_map = {
        "D_hedge_ewma_stop": price["ewma_vol_annual"],
        "E_no_hedge_garch": price["garch_vol_annual"],
        "F_hedge_garch_stop": price["garch_vol_annual"],
    }
    for cfg in LAYER2_STRATEGIES:
        print(f"  -> {cfg.name}")
        signal_vol = strategy_signal_map[cfg.name]
        daily, trades = run_backtest(cfg, price, chain_by_date, signal_vol)
        daily.to_csv(os.path.join(TABLE_DIR, f"daily_{cfg.name}.csv"), index=False)
        trades.to_csv(os.path.join(TABLE_DIR, f"trades_{cfg.name}.csv"), index=False)
        metrics = calculate_performance_metrics(daily["total_pnl"], trades)
        metrics["strategy"] = cfg.name
        results.append(metrics)

    metrics_df = pd.DataFrame(results)
    cols = [
        "strategy",
        "num_trades",
        "total_pnl",
        "ann_return_$",
        "ann_vol_$",
        "sharpe",
        "max_drawdown_$",
        "win_rate_%",
        "avg_trade_pnl",
        "worst_trade",
        "best_trade",
        "avg_holding_days",
        "avg_tcost_per_trade",
    ]
    metrics_df = metrics_df[cols]
    out_path = os.path.join(TABLE_DIR, "performance_summary_layer2_garch.csv")
    metrics_df.to_csv(out_path, index=False)

    forecast_df = price[["date", "atm_iv", "ewma_vol_annual", "garch_vol_annual"]].copy()
    forecast_df.to_csv(os.path.join(TABLE_DIR, "forecast_comparison_layer2_garch.csv"), index=False)

    print("\n========== LAYER 2 GARCH SUMMARY ==========")
    with pd.option_context("display.float_format", "{:,.2f}".format, "display.width", 160, "display.max_columns", 20):
        print(metrics_df.to_string(index=False))
    print(f"\nLayer 2 tables written to: {TABLE_DIR}")
    print(f"Forecast comparison written to: {os.path.join(TABLE_DIR, 'forecast_comparison_layer2_garch.csv')}")


if __name__ == "__main__":
    main()
