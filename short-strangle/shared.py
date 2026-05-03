"""Shared backtest runner for ITM / ATM / OTM short-strangle strategies."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.dirname(HERE)
SRC = os.path.join(PROJ_ROOT, "Time_Series_Final_Project", "Time_Series_Final_Project", "src")
sys.path.insert(0, SRC)

from data_loader import load_price_data, load_option_chain
from backtest_engine import build_chain_by_date
from option_selector import select_strangle_by_delta, lookup_option

CONTRACT = 100.0
EXIT_BUFFER_DAYS = 5
ENTRY_GAP_DAYS = 21

OUTPUT_DIR = os.path.join(HERE, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class OpenStrangle:
    entry_date: pd.Timestamp
    expiry: pd.Timestamp
    call_strike: float
    put_strike: float
    premium_received: float
    last_call_mid: float
    last_put_mid: float
    last_spot: float
    cum_pnl: float = 0.0
    days_held: int = 0
    entry_gamma: float = np.nan
    entry_vega: float = np.nan
    entry_delta: float = np.nan


def load_data():
    """Load price data and build chain_by_date index. Shared across all three strats."""
    print("Loading price data...")
    price = load_price_data()
    print(f"  {len(price)} rows  {price['date'].min().date()} -> {price['date'].max().date()}")

    print("Loading option chain...")
    chain = load_option_chain()
    print(f"  {len(chain):,} option rows")

    print("Indexing chain by date...")
    chain_by_date = build_chain_by_date(chain)
    return price, chain_by_date


def run_strangle_backtest(
    price: pd.DataFrame,
    chain_by_date: dict,
    call_delta: float,
    put_delta: float,
    name: str,
    stop_loss_mult: float = 2.0,
):
    """Short strangle / straddle backtest — no hedge, no filters.

    Exits at EXIT_BUFFER_DAYS before expiry or when the strangle ask value reaches
    stop_loss_mult * initial premium received.
    Returns (daily_df, trade_log_df).
    """
    trade: Optional[OpenStrangle] = None
    last_entry_date: Optional[pd.Timestamp] = None
    daily_rows = []
    trade_rows = []

    for i, row in price.iterrows():
        date = pd.Timestamp(row["date"])
        spot = row["uso_close"]
        chain_today = chain_by_date.get(date)
        opt_pnl = 0.0
        opened = closed = False

        # ---- Mark-to-market ----
        if trade is not None and chain_today is not None:
            c = lookup_option(chain_today, trade.expiry, trade.call_strike, "c")
            p = lookup_option(chain_today, trade.expiry, trade.put_strike, "p")

            if c is not None and p is not None and np.isfinite(c["mid"]) and np.isfinite(p["mid"]):
                opt_pnl = -(c["mid"] + p["mid"] - trade.last_call_mid - trade.last_put_mid) * CONTRACT
                trade.last_call_mid = c["mid"]
                trade.last_put_mid = p["mid"]
                trade.cum_pnl += opt_pnl
                trade.last_spot = spot
                trade.days_held += 1

                dte_left = np.busday_count(date.date(), trade.expiry.date())
                strangle_ask = (c["ask"] + p["ask"]) * CONTRACT
                stop_hit = strangle_ask >= stop_loss_mult * trade.premium_received

                if dte_left <= EXIT_BUFFER_DAYS or stop_hit:
                    exit_reason = "stop_loss" if stop_hit else "near_expiry"
                    slip = ((c["ask"] - c["mid"]) + (p["ask"] - p["mid"])) * CONTRACT
                    opt_pnl -= slip
                    trade.cum_pnl -= slip
                    trade_rows.append({
                        "entry_date":       trade.entry_date,
                        "exit_date":        date,
                        "expiry":           trade.expiry,
                        "call_strike":      trade.call_strike,
                        "put_strike":       trade.put_strike,
                        "premium_received": trade.premium_received,
                        "trade_pnl":        trade.cum_pnl,
                        "holding_days":     trade.days_held,
                        "exit_reason":      exit_reason,
                        "entry_gamma":      trade.entry_gamma,
                        "entry_vega":       trade.entry_vega,
                        "entry_delta":      trade.entry_delta,
                    })
                    trade = None
                    closed = True
            else:
                trade.last_spot = spot

        # ---- Entry ----
        if trade is None and chain_today is not None:
            gap_ok = (last_entry_date is None) or (
                np.busday_count(last_entry_date.date(), date.date()) >= ENTRY_GAP_DAYS
            )
            if gap_ok:
                pick = select_strangle_by_delta(chain_today, spot, call_delta, put_delta)
                if pick is not None:
                    c, p, c_strike, p_strike, expiry = pick
                    premium = (c["bid"] + p["bid"]) * CONTRACT
                    entry_pnl = premium - (c["mid"] + p["mid"]) * CONTRACT  # bid-to-mid cost

                    def _greek(c_val, p_val):
                        return (c_val + p_val) * CONTRACT if (np.isfinite(c_val) and np.isfinite(p_val)) else np.nan

                    trade = OpenStrangle(
                        entry_date=date,
                        expiry=pd.Timestamp(expiry),
                        call_strike=float(c_strike),
                        put_strike=float(p_strike),
                        premium_received=premium,
                        last_call_mid=c["mid"],
                        last_put_mid=p["mid"],
                        last_spot=spot,
                        cum_pnl=entry_pnl,
                        entry_gamma=_greek(c["gamma"], p["gamma"]),
                        entry_vega=_greek(c["vega"],  p["vega"]),
                        entry_delta=_greek(c["delta"], p["delta"]),
                    )
                    last_entry_date = date
                    opened = True
                    opt_pnl = entry_pnl

        daily_rows.append({
            "date":       date,
            "spot":       spot,
            "option_pnl": opt_pnl,
            "total_pnl":  opt_pnl,
            "in_trade":   trade is not None,
            "opened":     opened,
            "closed":     closed,
        })

    return pd.DataFrame(daily_rows), pd.DataFrame(trade_rows)


def summarize(daily: pd.DataFrame, trades: pd.DataFrame, name: str):
    """Print performance + gamma/vega summary, save CSVs."""
    pnl = daily["total_pnl"].fillna(0.0)
    cum = pnl.cumsum()
    n = len(pnl)
    total = cum.iloc[-1] if n else 0.0
    ann_ret = total / max(n, 1) * 252.0
    ann_vol = pnl.std() * np.sqrt(252.0)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    dd = (cum - cum.cummax()).min()

    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    print(f"  Total P&L          : ${total:>10,.2f}")
    print(f"  Ann. Return ($)    : ${ann_ret:>10,.2f}")
    print(f"  Ann. Vol ($)       : ${ann_vol:>10,.2f}")
    print(f"  Sharpe             : {sharpe:>11.3f}")
    print(f"  Max Drawdown ($)   : ${dd:>10,.2f}")

    if len(trades):
        tl = trades
        win_rate = (tl["trade_pnl"] > 0).mean() * 100
        n_stopped = (tl["exit_reason"] == "stop_loss").sum() if "exit_reason" in tl.columns else 0
        print(f"  Trades             : {len(tl):>11}")
        print(f"  Stop-outs          : {n_stopped:>11}")
        print(f"  Win Rate           : {win_rate:>10.1f}%")
        print(f"  Avg Trade P&L      : ${tl['trade_pnl'].mean():>10,.2f}")
        print(f"  Best / Worst       : ${tl['trade_pnl'].max():>,.2f} / ${tl['trade_pnl'].min():>,.2f}")
        print(f"  Avg Holding Days   : {tl['holding_days'].mean():>11.1f}")
        print(f"  Avg Premium Recv'd : ${tl['premium_received'].mean():>10,.2f}")
        print(f"  --- Greeks at entry (per 1-lot short) ---")
        print(f"  Avg Entry Gamma    : {tl['entry_gamma'].mean():>11.4f}")
        print(f"  Avg Entry Vega     : {tl['entry_vega'].mean():>11.4f}")
        print(f"  Avg Entry Delta    : {tl['entry_delta'].mean():>11.4f}")
        # Normalised: greek exposure per $1 of premium received
        gpp = (tl["entry_gamma"] / tl["premium_received"]).mean()
        vpp = (tl["entry_vega"]  / tl["premium_received"]).mean()
        print(f"  Gamma / Premium    : {gpp:>11.6f}  (gamma risk per $1 collected)")
        print(f"  Vega  / Premium    : {vpp:>11.6f}  (vega  risk per $1 collected)")

    # Save
    daily.to_csv(os.path.join(OUTPUT_DIR, f"daily_{name}.csv"), index=False)
    if len(trades):
        trades.to_csv(os.path.join(OUTPUT_DIR, f"trades_{name}.csv"), index=False)
    print(f"\n  Saved to strat/outputs/")
