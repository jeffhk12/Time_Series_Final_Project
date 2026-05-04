"""Robustness runner for the Layer 1 / Layer 2 short-vol strategy.

Sweeps:
  * GARCH fit_window x refit_every x entry_threshold x stop_loss_mult
  * EWMA lambda x entry_threshold x stop_loss_mult
  * Subperiod splits of the default GARCH and EWMA hedged-stop variants

Outputs:
  outputs/tables/robustness_garch_grid.csv
  outputs/tables/robustness_ewma_grid.csv
  outputs/tables/robustness_subperiods.csv
  outputs/charts/13_robustness_garch_threshold_stop.png
  outputs/charts/14_robustness_garch_fit_refit.png
  outputs/charts/15_robustness_ewma.png
  outputs/charts/16_robustness_subperiods.png

Run:
    /path/to/python src/run_robustness.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from backtest_engine import StrategyConfig, build_chain_by_date, run_backtest  # noqa: E402
from data_loader import load_option_chain, load_price_data  # noqa: E402
from garch_models import GarchConfig, compute_garch_vol  # noqa: E402
from metrics import calculate_performance_metrics  # noqa: E402
from volatility_models import compute_ewma_vol  # noqa: E402


WORKSPACE = os.path.dirname(HERE)
TABLE_DIR = os.path.join(WORKSPACE, "outputs", "tables")
CHART_DIR = os.path.join(WORKSPACE, "outputs", "charts")
os.makedirs(TABLE_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)


# Defaults pin the centre of every grid so each parameter axis can be shown
# with the others held at the published baseline.
DEFAULT_FIT_WINDOW = 252
DEFAULT_REFIT_EVERY = 21
DEFAULT_LAMBDA = 0.94
DEFAULT_THRESHOLD = 1.10
DEFAULT_STOP_MULT = 2.0

FIT_WINDOWS = [126, 252, 504]
REFIT_EVERS = [5, 21, 63]
THRESHOLDS = [1.05, 1.10, 1.15, 1.20]
STOP_MULTS = [1.5, 2.0, 2.5]
LAMBDAS = [0.90, 0.94, 0.97]

SUBPERIODS = [
    ("2020-05-04_to_2021-12-31", pd.Timestamp("2020-05-04"), pd.Timestamp("2021-12-31")),
    ("2022-01-01_to_2023-12-31", pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")),
    ("2024-01-01_to_2026-04-10", pd.Timestamp("2024-01-01"), pd.Timestamp("2026-04-10")),
    ("full_sample",              pd.Timestamp("2020-05-04"), pd.Timestamp("2026-04-10")),
]


METRIC_COLS = [
    "num_trades",
    "total_pnl",
    "sharpe",
    "max_drawdown_$",
    "worst_trade",
    "best_trade",
    "win_rate_%",
    "avg_trade_pnl",
    "ann_return_$",
    "ann_vol_$",
]


@dataclass
class DefaultRun:
    daily: pd.DataFrame
    trades: pd.DataFrame


def _build_strategy(name: str, threshold: float, stop_mult: float, signal_name: str) -> StrategyConfig:
    return StrategyConfig(
        name=name,
        use_hedge=True,
        use_ewma_signal=True,
        use_stop_loss=True,
        entry_threshold=threshold,
        stop_loss_mult=stop_mult,
        signal_name=signal_name,
    )


def run_garch_grid(price: pd.DataFrame, chain_by_date: dict):
    rows = []
    default_run: Optional[DefaultRun] = None

    for W in FIT_WINDOWS:
        for R in REFIT_EVERS:
            print(f"  GARCH fit_window={W}, refit_every={R} ...", flush=True)
            gcfg = GarchConfig(p=1, q=1, fit_window=W, refit_every=R)
            garch = compute_garch_vol(price["log_return"], gcfg)
            signal_vol = garch["garch_vol_annual"]

            for th in THRESHOLDS:
                for sm in STOP_MULTS:
                    cfg = _build_strategy(
                        name=f"garch_W{W}_R{R}_t{th:.2f}_s{sm:.1f}",
                        threshold=th,
                        stop_mult=sm,
                        signal_name="GARCH",
                    )
                    daily, trades = run_backtest(cfg, price, chain_by_date, signal_vol)
                    m = calculate_performance_metrics(daily["total_pnl"], trades)
                    rows.append({
                        "signal": "GARCH",
                        "fit_window": W,
                        "refit_every": R,
                        "entry_threshold": th,
                        "stop_loss_mult": sm,
                        **{k: m.get(k, np.nan) for k in METRIC_COLS},
                    })
                    if (W == DEFAULT_FIT_WINDOW and R == DEFAULT_REFIT_EVERY
                            and th == DEFAULT_THRESHOLD and sm == DEFAULT_STOP_MULT):
                        default_run = DefaultRun(daily=daily.copy(), trades=trades.copy())

    return pd.DataFrame(rows), default_run


def run_ewma_grid(price: pd.DataFrame, chain_by_date: dict):
    rows = []
    default_run: Optional[DefaultRun] = None

    for lam in LAMBDAS:
        print(f"  EWMA lambda={lam} ...", flush=True)
        ewma = compute_ewma_vol(price["log_return"], lam=lam)
        signal_vol = ewma["ewma_vol_annual"]

        for th in THRESHOLDS:
            for sm in STOP_MULTS:
                cfg = _build_strategy(
                    name=f"ewma_lam{lam:.2f}_t{th:.2f}_s{sm:.1f}",
                    threshold=th,
                    stop_mult=sm,
                    signal_name="EWMA",
                )
                daily, trades = run_backtest(cfg, price, chain_by_date, signal_vol)
                m = calculate_performance_metrics(daily["total_pnl"], trades)
                rows.append({
                    "signal": "EWMA",
                    "lambda": lam,
                    "entry_threshold": th,
                    "stop_loss_mult": sm,
                    **{k: m.get(k, np.nan) for k in METRIC_COLS},
                })
                if (lam == DEFAULT_LAMBDA and th == DEFAULT_THRESHOLD and sm == DEFAULT_STOP_MULT):
                    default_run = DefaultRun(daily=daily.copy(), trades=trades.copy())

    return pd.DataFrame(rows), default_run


def subperiod_metrics(label: str, run: DefaultRun) -> list[dict]:
    out = []
    daily = run.daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    trades = run.trades.copy() if len(run.trades) else run.trades
    if len(trades):
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])

    for name, start, end in SUBPERIODS:
        d = daily[(daily["date"] >= start) & (daily["date"] <= end)]
        if len(trades):
            t = trades[(trades["entry_date"] >= start) & (trades["entry_date"] <= end)]
        else:
            t = trades
        m = calculate_performance_metrics(d["total_pnl"], t)
        out.append({
            "signal": label,
            "subperiod": name,
            "start": start.date(),
            "end": end.date(),
            "n_days": len(d),
            **{k: m.get(k, np.nan) for k in METRIC_COLS},
        })
    return out


def _heatmap(ax, data: pd.DataFrame, value_col: str, x_col: str, y_col: str, title: str):
    pivot = data.pivot(index=y_col, columns=x_col, values=value_col)
    pivot = pivot.sort_index().sort_index(axis=1)
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn", origin="lower")
    ax.set_xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(c) for c in pivot.index])
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color="black")
    return im


def plot_garch_threshold_stop(garch_df: pd.DataFrame, path: str):
    sub = garch_df[(garch_df["fit_window"] == DEFAULT_FIT_WINDOW)
                   & (garch_df["refit_every"] == DEFAULT_REFIT_EVERY)].copy()
    fig, axes = plt.subplots(1, 5, figsize=(22, 4.5))
    metrics = [("sharpe", "Sharpe"),
               ("total_pnl", "Total P&L ($)"),
               ("max_drawdown_$", "Max DD ($)"),
               ("num_trades", "Trade count"),
               ("worst_trade", "Worst trade ($)")]
    for ax, (col, label) in zip(axes, metrics):
        _heatmap(ax, sub, col, x_col="stop_loss_mult", y_col="entry_threshold",
                 title=f"{label}\n(GARCH W={DEFAULT_FIT_WINDOW}, R={DEFAULT_REFIT_EVERY})")
    fig.suptitle("Layer 2 GARCH robustness: entry threshold x stop multiple")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_garch_fit_refit(garch_df: pd.DataFrame, path: str):
    sub = garch_df[(garch_df["entry_threshold"] == DEFAULT_THRESHOLD)
                   & (garch_df["stop_loss_mult"] == DEFAULT_STOP_MULT)].copy()
    fig, axes = plt.subplots(1, 5, figsize=(22, 4.5))
    metrics = [("sharpe", "Sharpe"),
               ("total_pnl", "Total P&L ($)"),
               ("max_drawdown_$", "Max DD ($)"),
               ("num_trades", "Trade count"),
               ("worst_trade", "Worst trade ($)")]
    for ax, (col, label) in zip(axes, metrics):
        _heatmap(ax, sub, col, x_col="refit_every", y_col="fit_window",
                 title=f"{label}\n(threshold={DEFAULT_THRESHOLD}, stop={DEFAULT_STOP_MULT})")
    fig.suptitle("Layer 2 GARCH robustness: fit_window x refit_every")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_ewma_grid(ewma_df: pd.DataFrame, path: str):
    fig, axes = plt.subplots(len(LAMBDAS), 5, figsize=(22, 4.0 * len(LAMBDAS)))
    metrics = [("sharpe", "Sharpe"),
               ("total_pnl", "Total P&L ($)"),
               ("max_drawdown_$", "Max DD ($)"),
               ("num_trades", "Trade count"),
               ("worst_trade", "Worst trade ($)")]
    for r, lam in enumerate(LAMBDAS):
        sub = ewma_df[ewma_df["lambda"] == lam]
        for c, (col, label) in enumerate(metrics):
            ax = axes[r, c]
            _heatmap(ax, sub, col, x_col="stop_loss_mult", y_col="entry_threshold",
                     title=f"{label} (lambda={lam})")
    fig.suptitle("Layer 1 EWMA robustness: lambda x threshold x stop")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_subperiods(sub_df: pd.DataFrame, path: str):
    fig, axes = plt.subplots(1, 5, figsize=(22, 4.5))
    metrics = [("sharpe", "Sharpe"),
               ("total_pnl", "Total P&L ($)"),
               ("max_drawdown_$", "Max DD ($)"),
               ("num_trades", "Trade count"),
               ("worst_trade", "Worst trade ($)")]
    signals = list(sub_df["signal"].unique())
    width = 0.8 / max(len(signals), 1)
    period_order = [name for name, _, _ in SUBPERIODS]
    for ax, (col, label) in zip(axes, metrics):
        for i, sig in enumerate(signals):
            s = sub_df[sub_df["signal"] == sig].set_index("subperiod").reindex(period_order)
            x = np.arange(len(period_order)) + (i - (len(signals) - 1) / 2) * width
            ax.bar(x, s[col].values, width=width, label=sig)
        ax.set_xticks(range(len(period_order)), period_order, rotation=20, ha="right", fontsize=8)
        ax.set_title(label)
        ax.legend(fontsize=8)
        ax.axhline(0, color="black", linewidth=0.6)
    fig.suptitle("Subperiod performance: default GARCH vs default EWMA (hedged + stop)")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    print("Loading price data...")
    price = load_price_data()
    print(f"  {len(price)} rows  {price['date'].min().date()} -> {price['date'].max().date()}")

    print("Loading option chain...")
    chain = load_option_chain()
    print(f"  {len(chain):,} option rows")

    print("Indexing chain by date...")
    chain_by_date = build_chain_by_date(chain)

    print("\n=== GARCH grid ===")
    garch_df, garch_default = run_garch_grid(price, chain_by_date)
    garch_path = os.path.join(TABLE_DIR, "robustness_garch_grid.csv")
    garch_df.to_csv(garch_path, index=False)
    print(f"  -> {garch_path}  ({len(garch_df)} rows)")

    print("\n=== EWMA grid ===")
    ewma_df, ewma_default = run_ewma_grid(price, chain_by_date)
    ewma_path = os.path.join(TABLE_DIR, "robustness_ewma_grid.csv")
    ewma_df.to_csv(ewma_path, index=False)
    print(f"  -> {ewma_path}  ({len(ewma_df)} rows)")

    print("\n=== Subperiods ===")
    sub_rows: list[dict] = []
    if garch_default is not None:
        sub_rows.extend(subperiod_metrics("GARCH_default", garch_default))
    if ewma_default is not None:
        sub_rows.extend(subperiod_metrics("EWMA_default", ewma_default))
    sub_df = pd.DataFrame(sub_rows)
    sub_path = os.path.join(TABLE_DIR, "robustness_subperiods.csv")
    sub_df.to_csv(sub_path, index=False)
    print(f"  -> {sub_path}  ({len(sub_df)} rows)")

    print("\n=== Charts ===")
    plot_garch_threshold_stop(garch_df, os.path.join(CHART_DIR, "13_robustness_garch_threshold_stop.png"))
    plot_garch_fit_refit(garch_df,      os.path.join(CHART_DIR, "14_robustness_garch_fit_refit.png"))
    plot_ewma_grid(ewma_df,             os.path.join(CHART_DIR, "15_robustness_ewma.png"))
    plot_subperiods(sub_df,             os.path.join(CHART_DIR, "16_robustness_subperiods.png"))
    print(f"  charts -> {CHART_DIR}")

    # Sanity readout: confirm published GARCH default reproduces inside the grid.
    default_row = garch_df[
        (garch_df["fit_window"] == DEFAULT_FIT_WINDOW)
        & (garch_df["refit_every"] == DEFAULT_REFIT_EVERY)
        & (garch_df["entry_threshold"] == DEFAULT_THRESHOLD)
        & (garch_df["stop_loss_mult"] == DEFAULT_STOP_MULT)
    ]
    print("\nDefault GARCH row inside the grid:")
    print(default_row.to_string(index=False))


if __name__ == "__main__":
    main()
