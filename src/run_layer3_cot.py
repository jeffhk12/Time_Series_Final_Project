"""Layer 3: COT positioning filter on top of the F_hedge_garch_stop strategy.

Adds a `cot_risk_off` veto: when managed-money or non-commercial net positioning
on WTI futures is extremely short (rolling z-score below a threshold), block new
short-vol entries that day. The hypothesis is that systematic shorts already
crowded into the trade act as a leading indicator of vol spikes — selling
volatility into that setup is what hurts the unconditional/EWMA strategies.

Outputs:
  outputs/tables/cot_features_daily.csv
  outputs/tables/daily_G_hedge_garch_stop_cot.csv
  outputs/tables/trades_G_hedge_garch_stop_cot.csv
  outputs/tables/performance_summary_layer3_cot.csv
  outputs/tables/layer3_cot_sensitivity.csv
  outputs/charts/17_cot_features_timeline.png
  outputs/charts/18_layer3_cot_comparison.png
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from backtest_engine import StrategyConfig, build_chain_by_date, run_backtest  # noqa: E402
from cot_features import CotConfig, load_daily_cot_features  # noqa: E402
from data_loader import load_option_chain, load_price_data  # noqa: E402
from garch_models import GarchConfig, compute_garch_vol  # noqa: E402
from metrics import calculate_performance_metrics  # noqa: E402


WORKSPACE = os.path.dirname(HERE)
TABLE_DIR = os.path.join(WORKSPACE, "outputs", "tables")
CHART_DIR = os.path.join(WORKSPACE, "outputs", "charts")
os.makedirs(TABLE_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)


METRIC_COLS = [
    "num_trades", "total_pnl", "sharpe", "max_drawdown_$",
    "worst_trade", "best_trade", "win_rate_%", "avg_trade_pnl",
    "ann_return_$", "ann_vol_$",
]


# Default config — picked to be conservative ("extremely short" should be rare).
DEFAULT_COT = CotConfig(z_window_weeks=104, release_lag_days=7, risk_off_z=-1.5)
DEFAULT_GARCH = GarchConfig(p=1, q=1, fit_window=252, refit_every=21)
DEFAULT_THRESHOLD = 1.10
DEFAULT_STOP_MULT = 2.0


def _strategy_F() -> StrategyConfig:
    """The published baseline GARCH strategy (no COT filter)."""
    return StrategyConfig(
        name="F_hedge_garch_stop",
        use_hedge=True, use_ewma_signal=True, use_stop_loss=True,
        entry_threshold=DEFAULT_THRESHOLD, stop_loss_mult=DEFAULT_STOP_MULT,
        signal_name="GARCH",
    )


def _strategy_G(label: str = "G_hedge_garch_stop_cot") -> StrategyConfig:
    """COT-filtered GARCH strategy (same parameters as F)."""
    return StrategyConfig(
        name=label,
        use_hedge=True, use_ewma_signal=True, use_stop_loss=True,
        entry_threshold=DEFAULT_THRESHOLD, stop_loss_mult=DEFAULT_STOP_MULT,
        signal_name="GARCH+COT",
    )


def plot_cot_features(daily_cot: pd.DataFrame, path: str):
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    d = daily_cot["date"]
    axes[0].plot(d, daily_cot["mm_net_oi"], color="tab:blue", label="MM Net / OI")
    axes[0].plot(d, daily_cot["nc_net_oi"], color="tab:orange", label="NC Net / OI")
    axes[0].axhline(0, color="black", linewidth=0.5)
    axes[0].set_ylabel("Net / OI")
    axes[0].legend(loc="best", fontsize=9)
    axes[0].set_title("WTI futures positioning (Net / OI)")

    axes[1].plot(d, daily_cot["mm_net_oi_z"], color="tab:blue", label="MM z")
    axes[1].plot(d, daily_cot["nc_net_oi_z"], color="tab:orange", label="NC z")
    axes[1].axhline(DEFAULT_COT.risk_off_z, color="red", linestyle="--", linewidth=0.8,
                    label=f"risk-off z = {DEFAULT_COT.risk_off_z}")
    axes[1].axhline(0, color="black", linewidth=0.5)
    axes[1].set_ylabel("rolling z-score")
    axes[1].legend(loc="best", fontsize=9)
    axes[1].set_title(f"Rolling z-score (window = {DEFAULT_COT.z_window_weeks} weeks)")

    axes[2].fill_between(d, 0, daily_cot["cot_risk_off"].astype(int), color="tab:red", alpha=0.5,
                         step="pre")
    axes[2].set_ylim(-0.05, 1.1)
    axes[2].set_yticks([0, 1], ["trade", "veto"])
    axes[2].set_title(f"COT entry veto  ({daily_cot['cot_risk_off'].mean()*100:.1f}% of days)")

    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_layer3_comparison(daily_F: pd.DataFrame, daily_G: pd.DataFrame, path: str):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    d_F = pd.to_datetime(daily_F["date"])
    d_G = pd.to_datetime(daily_G["date"])
    axes[0].plot(d_F, daily_F["total_pnl"].cumsum(), color="tab:blue",
                 label="F  GARCH (no COT filter)")
    axes[0].plot(d_G, daily_G["total_pnl"].cumsum(), color="tab:green",
                 label="G  GARCH + COT veto")
    axes[0].axhline(0, color="black", linewidth=0.5)
    axes[0].set_ylabel("Cumulative P&L ($)")
    axes[0].set_title("Layer 3: GARCH timing with vs without COT positioning veto")
    axes[0].legend(loc="best")

    cum_F = daily_F["total_pnl"].cumsum()
    cum_G = daily_G["total_pnl"].cumsum()
    dd_F = cum_F - cum_F.cummax()
    dd_G = cum_G - cum_G.cummax()
    axes[1].fill_between(d_F, dd_F, 0, color="tab:blue", alpha=0.4, label="F drawdown")
    axes[1].fill_between(d_G, dd_G, 0, color="tab:green", alpha=0.4, label="G drawdown")
    axes[1].axhline(0, color="black", linewidth=0.5)
    axes[1].set_ylabel("Drawdown ($)")
    axes[1].legend(loc="best")

    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def run_sensitivity(
    price: pd.DataFrame,
    chain_by_date: dict,
    signal_vol: pd.Series,
) -> pd.DataFrame:
    rows = []
    for z_window in [52, 104, 156]:
        for risk_off_z in [-0.5, -1.0, -1.5]:
            cot_cfg = CotConfig(z_window_weeks=z_window, release_lag_days=7, risk_off_z=risk_off_z)
            daily_cot = load_daily_cot_features(price["date"], cot_cfg)
            veto = daily_cot["cot_risk_off"].reindex(price.index, fill_value=False)
            cfg = _strategy_G(label=f"G_z{z_window}_t{risk_off_z:.1f}")
            daily, trades = run_backtest(cfg, price, chain_by_date, signal_vol, entry_veto=veto)
            m = calculate_performance_metrics(daily["total_pnl"], trades)
            rows.append({
                "z_window_weeks": z_window,
                "risk_off_z": risk_off_z,
                "veto_pct_days": float(veto.mean() * 100.0),
                **{k: m.get(k, np.nan) for k in METRIC_COLS},
            })
    return pd.DataFrame(rows)


def main():
    print("Loading price data...")
    price = load_price_data()

    print("Loading option chain...")
    chain = load_option_chain()
    chain_by_date = build_chain_by_date(chain)

    print(f"Computing GARCH({DEFAULT_GARCH.p},{DEFAULT_GARCH.q}) "
          f"window={DEFAULT_GARCH.fit_window}, refit_every={DEFAULT_GARCH.refit_every}...")
    garch = compute_garch_vol(price["log_return"], DEFAULT_GARCH)
    signal_vol = garch["garch_vol_annual"]

    print(f"Loading COT features (z_window={DEFAULT_COT.z_window_weeks}w, "
          f"lag={DEFAULT_COT.release_lag_days}d, risk_off_z={DEFAULT_COT.risk_off_z})...")
    daily_cot = load_daily_cot_features(price["date"], DEFAULT_COT)
    daily_cot_path = os.path.join(TABLE_DIR, "cot_features_daily.csv")
    daily_cot.to_csv(daily_cot_path, index=False)
    veto = daily_cot["cot_risk_off"].reindex(price.index, fill_value=False)
    print(f"  veto-active days: {veto.sum()} / {len(veto)} ({veto.mean()*100:.1f}%)")

    print("\nRunning baseline F (no COT) and Layer 3 G (with COT veto)...")
    cfg_F = _strategy_F()
    daily_F, trades_F = run_backtest(cfg_F, price, chain_by_date, signal_vol)
    metrics_F = calculate_performance_metrics(daily_F["total_pnl"], trades_F)
    metrics_F["strategy"] = cfg_F.name

    cfg_G = _strategy_G()
    daily_G, trades_G = run_backtest(cfg_G, price, chain_by_date, signal_vol, entry_veto=veto)
    metrics_G = calculate_performance_metrics(daily_G["total_pnl"], trades_G)
    metrics_G["strategy"] = cfg_G.name

    daily_F.to_csv(os.path.join(TABLE_DIR, f"daily_{cfg_F.name}.csv"), index=False)
    daily_G.to_csv(os.path.join(TABLE_DIR, f"daily_{cfg_G.name}.csv"), index=False)
    trades_F.to_csv(os.path.join(TABLE_DIR, f"trades_{cfg_F.name}.csv"), index=False)
    trades_G.to_csv(os.path.join(TABLE_DIR, f"trades_{cfg_G.name}.csv"), index=False)

    summary_cols = ["strategy", "num_trades", "total_pnl", "sharpe", "max_drawdown_$",
                    "worst_trade", "best_trade", "win_rate_%", "avg_trade_pnl"]
    summary = pd.DataFrame([metrics_F, metrics_G])[summary_cols]
    summary_path = os.path.join(TABLE_DIR, "performance_summary_layer3_cot.csv")
    summary.to_csv(summary_path, index=False)

    print("\n========== LAYER 3 SUMMARY ==========")
    with pd.option_context("display.float_format", "{:,.2f}".format,
                           "display.width", 160, "display.max_columns", 20):
        print(summary.to_string(index=False))

    print("\nRunning COT sensitivity grid (3 windows x 3 thresholds)...")
    sens = run_sensitivity(price, chain_by_date, signal_vol)
    sens_path = os.path.join(TABLE_DIR, "layer3_cot_sensitivity.csv")
    sens.to_csv(sens_path, index=False)
    with pd.option_context("display.float_format", "{:,.2f}".format,
                           "display.width", 160, "display.max_columns", 20):
        print(sens.to_string(index=False))

    print("\nWriting charts...")
    plot_cot_features(daily_cot, os.path.join(CHART_DIR, "17_cot_features_timeline.png"))
    plot_layer3_comparison(daily_F, daily_G, os.path.join(CHART_DIR, "18_layer3_cot_comparison.png"))

    print(f"\nDaily COT features -> {daily_cot_path}")
    print(f"Layer 3 summary    -> {summary_path}")
    print(f"Sensitivity grid   -> {sens_path}")


if __name__ == "__main__":
    main()
