# Layer 1 Project Plan: Baseline Short-Volatility Backtest

## 1. Project Objective

The objective of Layer 1 is to build a clean baseline backtesting engine for a short-volatility strategy using available option-chain data and Bloomberg price data.

The core research question is:

> Can a simple volatility forecast improve the timing and risk control of a short-volatility options strategy?

The Layer 1 deliverable should focus on a working P&L backtest rather than only statistical model fits.

The minimum viable deliverable is:

1. A working options backtest engine
2. A baseline short-volatility strategy
3. Daily delta-hedging logic
4. Transaction-cost-aware P&L
5. Basic performance and risk metrics
6. Clear charts and tables for presentation

COT data and more advanced option-chain signals should be reserved for Layer 2 unless Layer 1 is completed early.

---

## 2. Strategy Overview

The baseline strategy is a short-volatility strategy on USO or another oil-linked optionable instrument.

The preferred structure is:

> Sell an at-the-money straddle and delta-hedge daily.

A short straddle is preferred because it is a cleaner volatility trade than selling only calls or puts. The goal is to isolate volatility exposure while reducing directional exposure through delta hedging.

If the short straddle is too complex to implement in time, the fallback strategy is:

> Sell an at-the-money call or put and delta-hedge daily.

---

## 3. Data Inputs

### 3.1 Required Data

| Data Source | Required Fields | Purpose |
|---|---|---|
| Bloomberg price data | Date, close price, adjusted close if available | Underlying return, realized volatility, hedge P&L |
| Option-chain data | Date, expiration, strike, call/put flag, bid, ask, mid, implied volatility, delta | Option selection, trade pricing, mark-to-market, hedge ratio |
| Daily closing prices | Date, close price | Hedge rebalancing and realized volatility calculation |

### 3.2 Optional Data for Later Layers

| Data Source | Purpose |
|---|---|
| COT data | Phase-two positioning signal |
| Option skew | Phase-two risk-premium signal |
| Option term structure | Phase-two entry and exit signal |
| GARCH forecasts | Model comparison or alternative volatility forecast |

For Layer 1, COT should be cleaned but not required for the baseline strategy.

---

## 4. Universe and Instrument Choice

### Primary Underlying

Use **USO** as the primary underlying because option-chain data is available and it provides oil-linked exposure.

### Option Maturity

Start with options closest to **30 calendar days to expiration**, using a maturity window such as:

```text
21 <= days_to_expiration <= 45
```

If multiple expirations qualify, select the expiration closest to 30 days.

### Strike Selection

Select the strike closest to the current underlying price.

For a straddle:

1. Select the ATM call
2. Select the ATM put
3. Use the same expiration and strike when possible

---

## 5. Volatility Forecast Signal

Layer 1 should use EWMA realized volatility as the first volatility forecast.

The EWMA variance update is:

```text
sigma_t^2 = lambda * sigma_{t-1}^2 + (1 - lambda) * r_t^2
```

Recommended daily parameter:

```text
lambda = 0.94
```

Where:

| Symbol | Meaning |
|---|---|
| sigma_t | EWMA daily volatility estimate |
| r_t | Daily log return |
| lambda | Decay factor |

Annualized EWMA volatility:

```text
annualized_vol = daily_vol * sqrt(252)
```

---

## 6. Entry Rules

### Version A: Unconditional Baseline

Enter a short ATM straddle on every eligible rebalance date.

Purpose:

> Establish the raw short-volatility baseline.

### Version B: EWMA-Timed Strategy

Enter the trade only when implied volatility is sufficiently above EWMA realized volatility.

Suggested rule:

```text
implied_vol / ewma_realized_vol > 1.10
```

Alternative rule:

```text
implied_vol - ewma_realized_vol > 0.02
```

The first version is easier to explain because it uses a ratio threshold.

### Version C: No-Hedge Comparison

Run the same entry rule but without daily delta hedging.

Purpose:

> Compare raw short-option exposure against delta-hedged volatility exposure.

---

## 7. Position Construction

### 7.1 Short ATM Straddle

At entry:

```text
Sell 1 ATM call at bid
Sell 1 ATM put at bid
```

Initial premium received:

```text
premium_received = call_bid + put_bid
```

Daily mark-to-market value:

```text
straddle_mid_t = call_mid_t + put_mid_t
```

To close the trade:

```text
Buy back call at ask
Buy back put at ask
```

### 7.2 Delta Hedge

The option position delta is:

```text
option_position_delta = -call_delta - put_delta
```

The hedge position should offset option delta:

```text
hedge_units = -option_position_delta
```

For example:

If the short straddle has total delta of -0.20, buy 0.20 units of the underlying.

If the short straddle has total delta of +0.30, short 0.30 units of the underlying.

---

## 8. Daily Backtest Loop

Each trading day, the backtest should perform the following steps:

1. Load current underlying price
2. Load current option-chain data
3. Update EWMA realized volatility
4. Check if a new trade should be opened
5. If opening a trade, select ATM option or straddle
6. Sell options at bid price
7. Compute initial delta hedge
8. For each open trade:
   1. Update option mark-to-market value
   2. Compute option P&L
   3. Compute hedge P&L
   4. Rebalance hedge to new delta
   5. Apply transaction costs
   6. Check stop loss
   7. Close trade at expiry or target exit date
9. Record daily portfolio P&L
10. Record cumulative P&L

---

## 9. P&L Accounting

### 9.1 Option P&L

For a short option position:

```text
option_pnl_t = -(option_value_t - option_value_{t-1})
```

For a short straddle:

```text
option_pnl_t = -(straddle_value_t - straddle_value_{t-1})
```

### 9.2 Hedge P&L

Using the hedge position from the previous day:

```text
hedge_pnl_t = hedge_units_{t-1} * (S_t - S_{t-1})
```

### 9.3 Rebalancing Cost

When hedge size changes:

```text
hedge_trade_size = abs(hedge_units_t - hedge_units_{t-1})
hedge_cost_t = hedge_trade_size * S_t * cost_rate
```

Suggested underlying transaction cost:

```text
cost_rate = 0.0005
```

This is equivalent to 5 basis points.

### 9.4 Total Daily P&L

```text
total_pnl_t = option_pnl_t + hedge_pnl_t - hedge_cost_t - option_transaction_cost_t
```

Option transaction costs should use bid/ask execution:

```text
Entry: sell at bid
Daily mark: mark at mid
Exit: buy back at ask
```

---

## 10. Stop-Loss Rule

Use a simple stop-loss rule for the first version.

Recommended rule:

```text
Exit trade if mark-to-market loss exceeds 2x initial premium received.
```

Equivalent implementation:

```text
if current_straddle_ask >= 2 * premium_received:
    close_trade = True
```

Interpretation:

> If the option package doubles in value after we sold it, we exit to control tail risk.

---

## 11. Exit Rules

Use one of the following simple exit rules.

### Preferred Exit Rule

Hold until the earlier of:

1. Stop-loss trigger
2. Expiration
3. Fixed holding period, such as 20 trading days

### Simpler Exit Rule

Hold until 5 trading days before expiration, then close the position.

This avoids noisy final-expiry behavior and assignment complications.

---

## 12. Strategy Versions to Compare

Layer 1 should compare four versions.

| Strategy | Description | Purpose |
|---|---|---|
| A | Short ATM straddle, no hedge | Raw short-volatility baseline |
| B | Short ATM straddle, daily delta hedge | Direction-neutral short-volatility baseline |
| C | Short ATM straddle, EWMA entry signal, no hedge | Test timing signal without hedge |
| D | Short ATM straddle, EWMA entry signal, daily delta hedge, stop loss | Final Layer 1 baseline |

The final presentation can focus on Strategy D while showing A, B, and C as comparisons.

---

## 13. Performance Metrics

Report the following metrics:

| Metric | Purpose |
|---|---|
| Total P&L | Overall profitability |
| Annualized return | Scaled performance |
| Annualized volatility | Strategy risk |
| Sharpe ratio | Risk-adjusted return |
| Maximum drawdown | Downside risk |
| Win rate | Trade hit rate |
| Average trade P&L | Average trade quality |
| Worst trade | Tail loss |
| Number of trades | Strategy activity |
| Average holding period | Turnover and exposure |
| Average transaction cost | Cost drag |

---

## 14. Charts to Produce

The Layer 1 notebook should generate the following charts:

1. Underlying price chart
2. EWMA realized volatility chart
3. Implied volatility vs EWMA realized volatility chart
4. Cumulative P&L chart
5. Drawdown chart
6. Trade-level P&L histogram
7. Hedged vs unhedged strategy comparison
8. Strategy performance table

---

## 15. Implementation Modules

Recommended code structure:

```text
project/
│
├── data/
│   ├── raw/
│   ├── processed/
│
├── notebooks/
│   ├── 01_data_cleaning.ipynb
│   ├── 02_ewma_volatility.ipynb
│   ├── 03_layer1_backtest.ipynb
│   ├── 04_results_summary.ipynb
│
├── src/
│   ├── data_loader.py
│   ├── option_selector.py
│   ├── volatility_models.py
│   ├── backtest_engine.py
│   ├── pnl.py
│   ├── metrics.py
│   ├── plots.py
│
├── outputs/
│   ├── charts/
│   ├── tables/
│
└── README.md
```

---

## 16. Function-Level Implementation Plan

### 16.1 Data Loader

Function:

```text
load_price_data(path)
```

Purpose:

Load Bloomberg price data and return a clean dataframe with date, close price, and returns.

Function:

```text
load_option_chain(path)
```

Purpose:

Load option-chain data and standardize column names.

### 16.2 Volatility Model

Function:

```text
compute_ewma_vol(returns, lambda_=0.94)
```

Purpose:

Compute daily and annualized EWMA realized volatility.

### 16.3 Option Selector

Function:

```text
select_atm_options(option_chain, date, spot_price, target_dte=30)
```

Purpose:

Select the ATM call and put closest to 30 days to expiration.

### 16.4 Signal Generator

Function:

```text
generate_entry_signal(implied_vol, ewma_vol, threshold=1.10)
```

Purpose:

Return True when implied volatility is sufficiently above EWMA realized volatility.

### 16.5 Backtest Engine

Function:

```text
run_layer1_backtest(price_data, option_data, strategy_config)
```

Purpose:

Run the full daily backtest and return daily P&L, trade log, and performance metrics.

### 16.6 Metrics

Function:

```text
calculate_performance_metrics(daily_pnl, trade_log)
```

Purpose:

Compute P&L, Sharpe ratio, drawdown, win rate, and trade-level statistics.

---

## 17. Team Responsibilities

### Jeff Lu and James Sprizzo

Primary responsibility:

> Build the Layer 1 backtesting engine and baseline trading strategy.

Tasks:

1. Clean and structure price data
2. Build option selection logic
3. Implement short ATM straddle strategy
4. Implement daily delta hedging
5. Implement P&L calculation
6. Add transaction costs
7. Add stop loss
8. Generate performance charts and tables

### Aryan Chatterjee

Primary responsibility:

> Support EWMA and option-chain integration.

Tasks:

1. Share EWMA Python script
2. Share cleaned option-chain data
3. Write simple function comparing daily hedging vs no-hedge regimes
4. Help validate option-chain fields and delta logic

### Rishi Chauhan

Primary responsibility:

> Prepare supporting model forecasts and clean COT data for Layer 2.

Tasks:

1. Run USO analysis using existing ARMA/GARCH notebook
2. Share forecast plots
3. Continue cleaning COT data
4. Prepare COT data for possible phase-two signal integration

---

## 18. Timeline

### Day 1: Data and Skeleton Backtest

Deliverables:

1. Clean USO price dataframe
2. Clean option-chain dataframe
3. ATM option selector
4. EWMA realized volatility series
5. Initial trade log format

### Day 2: P&L Engine

Deliverables:

1. Short straddle entry logic
2. Daily mark-to-market logic
3. Delta hedge logic
4. Transaction cost logic
5. Stop-loss logic

### Day 3: Results and Presentation Output

Deliverables:

1. Strategy comparison table
2. Cumulative P&L chart
3. Drawdown chart
4. Volatility forecast chart
5. Final Layer 1 summary slides

---

## 19. Presentation Structure for Layer 1

### Slide 1: Research Question

Can a simple volatility forecast improve the timing and risk control of a short-volatility strategy on USO options?

### Slide 2: Data

Describe:

1. USO daily prices
2. Option-chain bid/ask data
3. Implied volatility and delta fields, if available
4. COT data reserved for Layer 2

### Slide 3: Baseline Model

Explain EWMA realized volatility and the IV versus realized volatility entry rule.

### Slide 4: Strategy Design

Explain:

1. Sell ATM straddle
2. Delta hedge daily
3. Rebalance daily
4. Include bid/ask costs
5. Use stop loss

### Slide 5: Backtest Setup

Explain:

1. End-of-day simulation
2. 30-day maturity target
3. Bid/ask execution
4. Hedged vs unhedged comparison

### Slide 6: Results

Show:

1. P&L chart
2. Drawdown chart
3. Performance table
4. Trade summary

### Slide 7: Interpretation

Discuss:

1. Whether delta hedging reduced directional risk
2. Whether EWMA timing improved performance
3. Whether stop loss reduced tail losses
4. Where the strategy failed

### Slide 8: Layer 2 Extensions

Discuss:

1. Add COT positioning signals
2. Add option skew and term-structure signals
3. Improve volatility spike detection
4. Compare EWMA against GARCH forecasts

---

## 20. Layer 1 Success Criteria

Layer 1 is successful if the team can show:

1. A functioning daily P&L backtest
2. A clear comparison between hedged and unhedged short-volatility positions
3. A clear EWMA-based entry rule
4. Transaction-cost-aware results
5. A reasonable explanation of why short-volatility strategies are vulnerable to volatility spikes
6. A clean path for adding COT and option-chain signals in Layer 2

---

## 21. Final Layer 1 Summary

The Layer 1 strategy is a baseline short-volatility options backtest. The strategy sells at-the-money volatility, delta-hedges daily, uses EWMA realized volatility to time entries, includes bid/ask execution costs, and applies a simple stop-loss rule.

This gives the team a working P&L framework. Once this is complete, Layer 2 can incorporate COT positioning data and richer option-chain signals to improve timing and risk control.
