"""Charts for Layer 1 backtest results."""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import pandas as pd

CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "charts")
os.makedirs(CHART_DIR, exist_ok=True)


def plot_underlying(price: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(price["date"], price["uso_close"], color="black", lw=1.0)
    ax.set_title("USO Daily Close (split-adjusted, 2020-05 onward)")
    ax.set_ylabel("Price ($)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "01_underlying_price.png"), dpi=130)
    plt.close(fig)


def plot_ewma_vol(price: pd.DataFrame, ewma_annual: pd.Series):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(price["date"], ewma_annual * 100, color="navy", lw=1.0)
    ax.set_title("EWMA Realized Volatility (annualized, λ=0.94)")
    ax.set_ylabel("Volatility (%)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "02_ewma_realized_vol.png"), dpi=130)
    plt.close(fig)


def plot_iv_vs_ewma(iv_series: pd.Series, ewma_annual: pd.Series, dates: pd.Series):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(dates, ewma_annual * 100, label="EWMA realized vol", color="navy", lw=1.1)
    ax.plot(dates, iv_series * 100, label="ATM-30d implied vol (mid)", color="crimson", lw=1.1, alpha=0.8)
    ax.set_title("Implied vs. EWMA Realized Volatility")
    ax.set_ylabel("Volatility (%)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "03_iv_vs_ewma.png"), dpi=130)
    plt.close(fig)


def plot_cumulative_pnl(daily_by_strategy: dict):
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, daily in daily_by_strategy.items():
        ax.plot(daily["date"], daily["total_pnl"].cumsum(), label=name, lw=1.2)
    ax.set_title("Cumulative P&L — Layer 1 Strategy Comparison")
    ax.set_ylabel("Cumulative P&L ($)")
    ax.axhline(0, color="grey", lw=0.6)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "04_cumulative_pnl.png"), dpi=130)
    plt.close(fig)


def plot_drawdown(daily_by_strategy: dict):
    fig, ax = plt.subplots(figsize=(11, 4))
    for name, daily in daily_by_strategy.items():
        cum = daily["total_pnl"].cumsum()
        dd = cum - cum.cummax()
        ax.plot(daily["date"], dd, label=name, lw=1.0)
    ax.set_title("Drawdown ($) — Layer 1 Strategy Comparison")
    ax.set_ylabel("Drawdown ($)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "05_drawdown.png"), dpi=130)
    plt.close(fig)


def plot_trade_pnl_hist(trades_by_strategy: dict):
    n = len(trades_by_strategy)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, (name, tl) in zip(axes, trades_by_strategy.items()):
        if tl.empty:
            ax.set_title(f"{name}\n(no trades)")
            continue
        ax.hist(tl["trade_pnl"], bins=20, color="steelblue", edgecolor="black")
        ax.axvline(0, color="black", lw=0.7)
        ax.set_title(name)
        ax.set_xlabel("Trade P&L ($)")
    fig.suptitle("Trade-level P&L distributions")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "06_trade_pnl_hist.png"), dpi=130)
    plt.close(fig)


def plot_hedge_vs_unhedged(daily_by_strategy: dict):
    pairs = [("A_no_hedge_uncond", "B_hedge_uncond"),
             ("C_no_hedge_ewma", "D_hedge_ewma_stop")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, (no_h, h) in zip(axes, pairs):
        if no_h in daily_by_strategy and h in daily_by_strategy:
            ax.plot(daily_by_strategy[no_h]["date"], daily_by_strategy[no_h]["total_pnl"].cumsum(),
                    label="no hedge", color="darkorange", lw=1.2)
            ax.plot(daily_by_strategy[h]["date"], daily_by_strategy[h]["total_pnl"].cumsum(),
                    label="delta hedged", color="navy", lw=1.2)
            ax.set_title(f"{no_h}  vs  {h}")
            ax.axhline(0, color="grey", lw=0.6)
            ax.grid(alpha=0.3)
            ax.legend()
    fig.suptitle("Hedged vs. unhedged short volatility")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "07_hedge_vs_unhedged.png"), dpi=130)
    plt.close(fig)
