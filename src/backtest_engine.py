"""Layer 1 short-volatility backtest engine.

Strategies:
  A: Short ATM straddle, no hedge, unconditional entry
  B: Short ATM straddle, daily delta hedge, unconditional entry
  C: Short ATM straddle, no hedge, EWMA entry signal
  D: Short ATM straddle, daily delta hedge, EWMA entry signal, stop loss

Conventions:
  - 1 contract = 100 shares of underlying.
  - Entry: sell call at bid, sell put at bid (premium received).
  - Exit / mark-to-market: buy back at ask. Daily MTM uses mid.
  - Hedge: delta-equivalent shares of USO. Hedge cost rate = 5 bps of notional.
  - Stop loss: exit if straddle ask >= 2 * initial premium received.
  - Holding: enter once per month (no overlapping trades), close 5 trading days
    before expiry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from option_selector import select_atm_straddle, lookup_option


CONTRACT_MULTIPLIER = 100.0
HEDGE_COST_RATE = 0.0005  # 5 bps on underlying notional traded
EXIT_BUFFER_DAYS = 5      # close N trading days before expiry
ENTRY_GAP_DAYS = 21       # at least N trading days between entries
EWMA_THRESHOLD = 1.10     # IV/EWMA-vol must exceed this for "C"/"D" entry
STOP_LOSS_MULT = 2.0      # exit if straddle value >= mult * initial premium


@dataclass
class StrategyConfig:
    name: str
    use_hedge: bool
    use_ewma_signal: bool
    use_stop_loss: bool
    entry_threshold: float = EWMA_THRESHOLD
    stop_loss_mult: float = STOP_LOSS_MULT
    signal_name: str = ""


STRATEGIES = [
    StrategyConfig("A_no_hedge_uncond", use_hedge=False, use_ewma_signal=False, use_stop_loss=False),
    StrategyConfig("B_hedge_uncond",    use_hedge=True,  use_ewma_signal=False, use_stop_loss=False),
    StrategyConfig("C_no_hedge_ewma",   use_hedge=False, use_ewma_signal=True,  use_stop_loss=False),
    StrategyConfig("D_hedge_ewma_stop", use_hedge=True,  use_ewma_signal=True,  use_stop_loss=True),
]


@dataclass
class OpenTrade:
    entry_date: pd.Timestamp
    expiry: pd.Timestamp
    strike: float
    premium_received: float           # per straddle (1 lot, multiplied by contract size)
    call_entry_bid: float
    put_entry_bid: float
    hedge_shares: float = 0.0         # current hedge position (shares of USO)
    last_call_mid: float = 0.0
    last_put_mid: float = 0.0
    last_spot: float = 0.0
    cum_option_pnl: float = 0.0
    cum_hedge_pnl: float = 0.0
    cum_tcost: float = 0.0
    days_held: int = 0


def _signal_ok(cfg: StrategyConfig, iv: float, signal_vol: float) -> bool:
    if not cfg.use_ewma_signal:
        return True
    if not (np.isfinite(iv) and np.isfinite(signal_vol) and signal_vol > 0):
        return False
    return (iv / signal_vol) > cfg.entry_threshold


def run_backtest(
    cfg: StrategyConfig,
    price: pd.DataFrame,
    chain_by_date: dict,
    signal_vol: pd.Series,
    entry_veto: Optional[pd.Series] = None,
):
    """Run a single-strategy daily loop. Returns (daily_df, trade_log_df).

    `signal_vol` is the annualized volatility forecast used for the entry filter
    (e.g. EWMA, GARCH). Only consulted when `cfg.use_ewma_signal` is True.

    `entry_veto`, if provided, is a boolean Series indexed like `price` where
    True blocks new entries on that day (used by the Layer 3 COT filter). Open
    trades are still managed normally — the veto only gates new entries.
    """
    trade: Optional[OpenTrade] = None
    last_entry_date: Optional[pd.Timestamp] = None
    daily_rows = []
    trade_rows = []

    for i, row in price.iterrows():
        date = row["date"]
        spot = row["uso_close"]
        chain_today = chain_by_date.get(pd.Timestamp(date))
        opt_pnl = 0.0
        hedge_pnl = 0.0
        tcost = 0.0
        opened = False
        closed = False

        # ----- Mark-to-market existing trade -----
        if trade is not None and chain_today is not None:
            call_row = lookup_option(chain_today, trade.expiry, trade.strike, "c")
            put_row = lookup_option(chain_today, trade.expiry, trade.strike, "p")
            # Hedge P&L from previous day's hedge size and today's spot move
            hedge_pnl = trade.hedge_shares * (spot - trade.last_spot)

            if call_row is not None and put_row is not None and np.isfinite(call_row["mid"]) and np.isfinite(put_row["mid"]):
                straddle_mid = call_row["mid"] + put_row["mid"]
                prev_straddle_mid = trade.last_call_mid + trade.last_put_mid
                # Short straddle P&L = -(value_t - value_{t-1}) per option, scaled by contract size
                opt_pnl = -(straddle_mid - prev_straddle_mid) * CONTRACT_MULTIPLIER

                # Update tracking
                trade.last_call_mid = call_row["mid"]
                trade.last_put_mid = put_row["mid"]
                trade.cum_option_pnl += opt_pnl
                trade.cum_hedge_pnl += hedge_pnl
                trade.last_spot = spot
                trade.days_held += 1

                # Decide whether to exit
                exit_now = False
                exit_reason = ""
                trading_days_to_expiry = np.busday_count(date.date(), trade.expiry.date())
                if trading_days_to_expiry <= EXIT_BUFFER_DAYS:
                    exit_now = True
                    exit_reason = "near_expiry"
                if cfg.use_stop_loss and not exit_now:
                    straddle_ask = call_row["ask"] + put_row["ask"]
                    if straddle_ask * CONTRACT_MULTIPLIER >= cfg.stop_loss_mult * trade.premium_received:
                        exit_now = True
                        exit_reason = "stop_loss"

                # Rebalance hedge (or unwind) BEFORE exit
                if cfg.use_hedge and not exit_now:
                    target_delta = -(call_row["delta"] + put_row["delta"]) * CONTRACT_MULTIPLIER
                    target_shares = target_delta  # hedge = -option position delta
                    delta_change = target_shares - trade.hedge_shares
                    tc = abs(delta_change) * spot * HEDGE_COST_RATE
                    tcost += tc
                    trade.cum_tcost += tc
                    trade.hedge_shares = target_shares

                if exit_now:
                    # Close: buy back at ask, unwind hedge to zero
                    close_value = (call_row["ask"] + put_row["ask"]) * CONTRACT_MULTIPLIER
                    # Already MTM'd to mid; adjust for ask vs mid slippage on close
                    slippage = (call_row["ask"] - call_row["mid"]) + (put_row["ask"] - put_row["mid"])
                    slippage_cost = slippage * CONTRACT_MULTIPLIER
                    opt_pnl -= slippage_cost
                    trade.cum_option_pnl -= slippage_cost

                    if cfg.use_hedge and trade.hedge_shares != 0:
                        unwind_tc = abs(trade.hedge_shares) * spot * HEDGE_COST_RATE
                        tcost += unwind_tc
                        trade.cum_tcost += unwind_tc
                        trade.hedge_shares = 0.0

                    trade_pnl = trade.cum_option_pnl + trade.cum_hedge_pnl - trade.cum_tcost
                    # Note: premium_received and close_value are reflected in cum_option_pnl
                    # via the entry-day MTM and daily MTM updates.
                    trade_rows.append({
                        "entry_date": trade.entry_date,
                        "exit_date": date,
                        "expiry": trade.expiry,
                        "strike": trade.strike,
                        "premium_received": trade.premium_received,
                        "exit_reason": exit_reason,
                        "trade_pnl": trade_pnl,
                        "option_pnl": trade.cum_option_pnl,
                        "hedge_pnl": trade.cum_hedge_pnl,
                        "transaction_costs": trade.cum_tcost,
                        "holding_days": trade.days_held,
                    })
                    trade = None
                    closed = True
            else:
                # Couldn't find this day's option row; carry hedge but no MTM
                trade.last_spot = spot
                trade.cum_hedge_pnl += hedge_pnl

        # ----- Entry logic -----
        if trade is None and chain_today is not None:
            gap_ok = (last_entry_date is None) or (np.busday_count(last_entry_date.date(), date.date()) >= ENTRY_GAP_DAYS)
            veto_today = bool(entry_veto.iloc[i]) if entry_veto is not None and i < len(entry_veto) else False
            if gap_ok and not veto_today:
                # IV check: use selected ATM IV if available
                pick = select_atm_straddle(chain_today, spot)
                if pick is not None:
                    call_row, put_row, strike, expiry = pick
                    iv = (call_row["iv_mid"] + put_row["iv_mid"]) / 2.0
                    signal_today = signal_vol.iloc[i] if i < len(signal_vol) else np.nan
                    if _signal_ok(cfg, iv, signal_today):
                        # Entry: sell at bid
                        premium = (call_row["bid"] + put_row["bid"]) * CONTRACT_MULTIPLIER
                        # Establish initial hedge if applicable
                        hedge_shares = 0.0
                        if cfg.use_hedge:
                            target_delta = -(call_row["delta"] + put_row["delta"]) * CONTRACT_MULTIPLIER
                            hedge_shares = target_delta
                            tc = abs(hedge_shares) * spot * HEDGE_COST_RATE
                            tcost += tc
                        # Entry-day option P&L = premium received minus mark-to-mid liability.
                        # This equals the bid->mid slippage cost (negative, small).
                        entry_mid_value = (call_row["mid"] + put_row["mid"]) * CONTRACT_MULTIPLIER
                        entry_day_option_pnl = premium - entry_mid_value
                        trade = OpenTrade(
                            entry_date=date,
                            expiry=pd.Timestamp(expiry),
                            strike=float(strike),
                            premium_received=premium,
                            call_entry_bid=call_row["bid"],
                            put_entry_bid=put_row["bid"],
                            hedge_shares=hedge_shares,
                            last_call_mid=call_row["mid"],
                            last_put_mid=put_row["mid"],
                            last_spot=spot,
                            cum_option_pnl=entry_day_option_pnl,
                            cum_tcost=tcost,
                        )
                        last_entry_date = date
                        opened = True
                        opt_pnl = entry_day_option_pnl

        total = opt_pnl + hedge_pnl - tcost
        daily_rows.append({
            "date": date,
            "spot": spot,
            "option_pnl": opt_pnl,
            "hedge_pnl": hedge_pnl,
            "tcost": tcost,
            "total_pnl": total,
            "in_trade": trade is not None,
            "opened": opened,
            "closed": closed,
        })

    daily = pd.DataFrame(daily_rows)
    trade_log = pd.DataFrame(trade_rows)
    return daily, trade_log


def build_chain_by_date(option_chain: pd.DataFrame) -> dict:
    """Group option-chain rows by trade_date for fast daily lookup."""
    return {pd.Timestamp(d): grp for d, grp in option_chain.groupby("trade_date")}
