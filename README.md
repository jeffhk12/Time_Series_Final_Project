# Layer 1: Short-Volatility Backtest

Baseline backtesting engine for a short-volatility strategy on USO options.

## Quick Start

```bash
cd /path/to/Workspace
/path/to/python src/run_layer1.py
```

Outputs go to `outputs/charts/` (7 PNGs) and `outputs/tables/` (4 CSVs + summary).

## Results (2020-05-04 → 2026-04-10)

| Strategy | Trades | Total P&L | Sharpe | Max DD | Win % |
|---|---:|---:|---:|---:|---:|
| A — raw short straddle | 74 | -$2,378 | -0.28 | -$5,069 | 67.6% |
| B — + delta hedge | 74 | -$4,961 | -0.33 | -$8,643 | 64.9% |
| C — + EWMA filter | 58 | -$104 | -0.01 | -$4,700 | 65.5% |
| **D — + hedge + filter + stop** | **58** | **+$557** | **+0.05** | **-$4,859** | **58.6%** |

## Files

- **`src/`** — backtesting engine and utilities
  - `data_loader.py` — USO price + option-chain loader
  - `volatility_models.py` — EWMA realized volatility
  - `option_selector.py` — ATM straddle selection (21–45 DTE)
  - `backtest_engine.py` — daily loop, P&L accounting, four strategies
  - `metrics.py`, `plots.py` — performance & visualization
  - `run_layer1.py` — main entry point

- **`notebooks/`** — Jupyter notebooks
  - `layer1_results.ipynb` — interactive walkthrough of all four strategies
  - `build_notebook.py` — notebook generator

- **`layer_1_short_vol_project_plan.md`** — detailed specification

## Design Notes

**Backtest window.** 2020-05-04 → 2026-04-10 (post-USO 1:8 reverse split, where
Bloomberg PX_LAST and option-chain strikes align).

**Entry.** Every ~21 trading days, sell 1 ATM call + 1 ATM put (~30 DTE) if:
- Unconditional (A, B): always
- EWMA-timed (C, D): `IV/EWMA-vol > 1.10`

**Hedge.** Daily rebalancing to delta-neutral; 5 bps cost on notional traded.

**Exit.** 5 trading days before expiry or on stop-loss (if straddle value ≥ 2× premium received).

**P&L.** Entry at bid, daily mark-to-mid, exit at ask.

## Key Findings

1. **Unconditional selling loses.** Naked short-vol collected premium in calm years but
   gave it back in spike years (Russia-Ukraine 2022, Iran-Israel 2024).

2. **Hedging alone doesn't help.** Delta hedging converts gamma into realized P&L.
   In trending oil markets it's a cost without the timing filter.

3. **EWMA timing is the main edge.** Skipping the worst 16 trades (where IV ≈ RV)
   turns the baseline from -0.28 Sharpe to –0.01. The filter cuts both tails
   (fewer small losses but also fewer small wins).

4. **Stop loss caps tail risk.** The worst single trade shrinks from -$3,375 (A) to
   -$1,668 (D). The full package yields the only positive-Sharpe baseline.

## Layer 2 Extensions

- COT positioning signals (avoid selling when CTAs are net short)
- Option skew & term-structure features
- GARCH or HAR-RV forecasts vs. EWMA
- Richer execution model (slippage scaling with size/vol)

## Dependencies

- pandas, numpy, matplotlib
- openpyxl (for Bloomberg Excel loader)
