"""Generate a final markdown report with charts and analysis for all methods."""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_DIR = os.path.join(WORKSPACE, "outputs", "charts")
TABLE_DIR = os.path.join(WORKSPACE, "outputs", "tables")
REPORT_PATH = os.path.join(WORKSPACE, "final_results_report.md")


def _load_daily(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(TABLE_DIR, f"daily_{name}.csv"), parse_dates=["date"])


def _load_trades(name: str) -> pd.DataFrame:
    return pd.read_csv(
        os.path.join(TABLE_DIR, f"trades_{name}.csv"),
        parse_dates=["entry_date", "exit_date", "expiry"],
    )


def plot_forecast_comparison() -> str:
    df = pd.read_csv(os.path.join(TABLE_DIR, "forecast_comparison_layer2_garch.csv"), parse_dates=["date"])
    path = os.path.join(CHART_DIR, "08_forecast_comparison_ewma_vs_garch.png")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(df["date"], df["atm_iv"] * 100, label="ATM IV", color="crimson", lw=1.0, alpha=0.8)
    ax.plot(df["date"], df["ewma_vol_annual"] * 100, label="EWMA", color="navy", lw=1.0)
    ax.plot(df["date"], df["garch_vol_annual"] * 100, label="GARCH(1,1)", color="darkgreen", lw=1.0)
    ax.set_title("Forecast Comparison: Implied Vol vs EWMA vs GARCH")
    ax.set_ylabel("Volatility (%)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_cumulative_all() -> str:
    strategy_names = [
        "A_no_hedge_uncond",
        "B_hedge_uncond",
        "C_no_hedge_ewma",
        "D_hedge_ewma_stop",
        "E_no_hedge_garch",
        "F_hedge_garch_stop",
    ]
    path = os.path.join(CHART_DIR, "09_cumulative_pnl_all_methods.png")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name in strategy_names:
        daily = _load_daily(name)
        ax.plot(daily["date"], daily["total_pnl"].cumsum(), label=name, lw=1.2)
    ax.set_title("Cumulative P&L Comparison: Layer 1 and Layer 2")
    ax.set_ylabel("Cumulative P&L ($)")
    ax.axhline(0, color="grey", lw=0.6)
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_drawdown_all() -> str:
    strategy_names = [
        "A_no_hedge_uncond",
        "B_hedge_uncond",
        "C_no_hedge_ewma",
        "D_hedge_ewma_stop",
        "E_no_hedge_garch",
        "F_hedge_garch_stop",
    ]
    path = os.path.join(CHART_DIR, "10_drawdown_all_methods.png")
    fig, ax = plt.subplots(figsize=(11, 5))
    for name in strategy_names:
        daily = _load_daily(name)
        cum = daily["total_pnl"].cumsum()
        dd = cum - cum.cummax()
        ax.plot(daily["date"], dd, label=name, lw=1.1)
    ax.set_title("Drawdown Comparison: Layer 1 and Layer 2")
    ax.set_ylabel("Drawdown ($)")
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_trade_hist_all() -> str:
    strategy_names = [
        "A_no_hedge_uncond",
        "B_hedge_uncond",
        "C_no_hedge_ewma",
        "D_hedge_ewma_stop",
        "E_no_hedge_garch",
        "F_hedge_garch_stop",
    ]
    path = os.path.join(CHART_DIR, "11_trade_pnl_hist_all_methods.png")
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharey=True)
    for ax, name in zip(axes.flatten(), strategy_names):
        trades = _load_trades(name)
        ax.hist(trades["trade_pnl"], bins=18, color="steelblue", edgecolor="black")
        ax.axvline(0, color="black", lw=0.7)
        ax.set_title(name, fontsize=9)
        ax.set_xlabel("Trade P&L ($)")
    fig.suptitle("Trade-Level P&L Distributions Across All Methods")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_layer2_only() -> str:
    strategy_names = [
        "D_hedge_ewma_stop",
        "E_no_hedge_garch",
        "F_hedge_garch_stop",
    ]
    colors = {
        "D_hedge_ewma_stop": "navy",
        "E_no_hedge_garch": "darkorange",
        "F_hedge_garch_stop": "darkgreen",
    }
    path = os.path.join(CHART_DIR, "12_layer2_strategy_comparison.png")
    fig, ax = plt.subplots(figsize=(11, 5))
    for name in strategy_names:
        daily = _load_daily(name)
        ax.plot(daily["date"], daily["total_pnl"].cumsum(), label=name, lw=1.3, color=colors[name])
    ax.set_title("Layer 2 Comparison: EWMA Benchmark vs GARCH Timing")
    ax.set_ylabel("Cumulative P&L ($)")
    ax.axhline(0, color="grey", lw=0.6)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def _to_markdown_table(df: pd.DataFrame) -> str:
    fmt_df = df.copy()
    for col in fmt_df.columns:
        if pd.api.types.is_float_dtype(fmt_df[col]):
            fmt_df[col] = fmt_df[col].map(lambda x: f"{x:.2f}")
    header = "| " + " | ".join(fmt_df.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(fmt_df.columns)) + " |"
    rows = [
        "| " + " | ".join(str(row[col]) for col in fmt_df.columns) + " |"
        for _, row in fmt_df.iterrows()
    ]
    return "\n".join([header, divider, *rows])


def build_report() -> str:
    plot_forecast_comparison()
    plot_cumulative_all()
    plot_drawdown_all()
    plot_trade_hist_all()
    plot_layer2_only()

    layer1 = pd.read_csv(os.path.join(TABLE_DIR, "performance_summary.csv"))
    layer2 = pd.read_csv(os.path.join(TABLE_DIR, "performance_summary_layer2_garch.csv"))

    report = f"""# Final Project Results: Layer 1 EWMA Baseline and Layer 2 GARCH Extension

## Executive Summary

This report combines the full Layer 1 baseline backtest with the Layer 2 GARCH timing extension for the USO short-volatility strategy. The main result is that timing quality matters more than raw short-vol exposure, and the initial GARCH timing implementation materially outperformed the EWMA benchmark in this sample.

The baseline Layer 1 result established that unconditional short-volatility selling performed poorly, daily hedging alone did not improve outcomes, and the EWMA timing filter was the primary source of improvement. Layer 2 then replaced the EWMA timing forecast with a rolling GARCH(1,1) forecast while keeping the rest of the backtest framework intact. In the first pass, the hedged GARCH strategy with stop loss produced the strongest performance across all tested methods.

## Layer 1 Summary Table

{_to_markdown_table(layer1[[
    "strategy", "num_trades", "total_pnl", "sharpe", "max_drawdown_$", "win_rate_%"
]])}

## Layer 2 Summary Table

{_to_markdown_table(layer2[[
    "strategy", "num_trades", "total_pnl", "sharpe", "max_drawdown_$", "win_rate_%"
]])}

## Layer 1 Charts

### Underlying Price

![Underlying Price](outputs/charts/01_underlying_price.png)

### EWMA Realized Volatility

![EWMA Realized Volatility](outputs/charts/02_ewma_realized_vol.png)

### Implied Volatility vs EWMA

![Implied Volatility vs EWMA](outputs/charts/03_iv_vs_ewma.png)

### Layer 1 Cumulative P&L

![Layer 1 Cumulative P&L](outputs/charts/04_cumulative_pnl.png)

### Layer 1 Drawdown

![Layer 1 Drawdown](outputs/charts/05_drawdown.png)

### Layer 1 Trade P&L Distributions

![Layer 1 Trade P&L Histograms](outputs/charts/06_trade_pnl_hist.png)

### Hedged vs Unhedged Comparisons

![Layer 1 Hedge Comparison](outputs/charts/07_hedge_vs_unhedged.png)

## Layer 2 Charts

### Forecast Comparison: IV vs EWMA vs GARCH

![Forecast Comparison](outputs/charts/08_forecast_comparison_ewma_vs_garch.png)

### All Methods: Cumulative P&L

![All Methods Cumulative P&L](outputs/charts/09_cumulative_pnl_all_methods.png)

### All Methods: Drawdown

![All Methods Drawdown](outputs/charts/10_drawdown_all_methods.png)

### All Methods: Trade-Level P&L

![All Methods Trade Histograms](outputs/charts/11_trade_pnl_hist_all_methods.png)

### Layer 2 Strategy Comparison

![Layer 2 Strategy Comparison](outputs/charts/12_layer2_strategy_comparison.png)

## Analysis

### 1. What Layer 1 proved

Layer 1 showed that unconditional short-volatility selling was not attractive in this sample. Strategy A lost money, and Strategy B performed even worse, which suggests that hedging alone did not create edge. The main improvement came from timing: Strategy C dramatically reduced losses relative to A, and Strategy D added a modestly positive total P&L and the only positive Sharpe among the Layer 1 set.

The implication is that the project should not be framed as “hedging fixes the strategy.” A more accurate interpretation is that timing is the main source of edge, while hedging and stop-loss logic help make the timed strategy more robust.

### 2. What changed in Layer 2

The Layer 2 extension kept the same backtest engine, option selection, holding period, hedge mechanics, and stop-loss logic. The key change was the volatility forecast used for trade entry. EWMA is a fixed-rule exponential smoother of recent realized volatility, while GARCH is a fitted rolling forecast designed to capture volatility clustering and persistence more explicitly.

In practical terms, both methods still use the same decision rule structure:

- enter only when implied volatility is sufficiently above forecasted realized volatility

But the forecast itself changes from EWMA to GARCH. That means Layer 2 is a cleaner model-comparison experiment rather than a wholesale redesign of the strategy.

### 3. What the first GARCH results suggest

The first GARCH pass was materially stronger than the EWMA benchmark. Strategy E, which used GARCH timing without hedge, outperformed the Layer 1 no-hedge timed strategy C by a wide margin. Strategy F, which combined GARCH timing with hedge and stop-loss controls, produced the strongest total P&L, strongest Sharpe, and shallowest drawdown of the compared timed strategies.

This suggests that the GARCH forecast filtered entries more effectively than EWMA in this sample. It also reduced the number of trades from 58 to 47, which is consistent with a more selective timing model.

### 4. Cautions and next steps

These Layer 2 results are promising, but they should still be treated as a first research result rather than a final production conclusion. The GARCH specification here is a simple rolling GARCH(1,1) with periodic refits. A fuller analysis should test sensitivity to:

- GARCH window length
- refit frequency
- alternative volatility models such as EGARCH or GJR-GARCH
- different IV-to-forecast thresholds
- stability across subperiods

The next strongest extension would be a robustness section showing whether the GARCH advantage persists under reasonable parameter changes rather than only in the default configuration.

## Conclusion

The combined evidence from Layer 1 and Layer 2 supports a clear storyline. Short-volatility selling without timing performs poorly. EWMA timing improves the baseline, but the initial GARCH timing implementation appears to improve it further, especially when combined with hedge and stop-loss controls. In the current sample, GARCH-based timing is the strongest candidate for the project’s Layer 2 improvement.
"""

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    return REPORT_PATH


def main() -> None:
    path = build_report()
    print(f"Wrote final report to: {path}")


if __name__ == "__main__":
    main()
