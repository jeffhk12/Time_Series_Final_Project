"""ATM straddle selection logic."""

from __future__ import annotations

import numpy as np
import pandas as pd


DTE_MIN = 21
DTE_MAX = 45
DTE_TARGET = 30


def select_atm_straddle(chain_today: pd.DataFrame, spot: float):
    """Return (call_row, put_row, strike, expiry) for the ATM straddle, or None.

    Selection:
      1. Filter to expirations in [DTE_MIN, DTE_MAX].
      2. Pick the expiration whose DTE is closest to DTE_TARGET.
      3. Among that expiry, pick strike closest to `spot` that has both call and put quoted
         with positive bid on each leg.
    """
    df = chain_today[(chain_today["dte"] >= DTE_MIN) & (chain_today["dte"] <= DTE_MAX)]
    if df.empty:
        return None

    # Pick best expiry
    expiries = df["expiry"].drop_duplicates()
    expiry = min(expiries, key=lambda e: abs((e - chain_today["trade_date"].iloc[0]).days - DTE_TARGET))
    df = df[df["expiry"] == expiry]

    calls = df[df["cp"] == "c"].copy()
    puts = df[df["cp"] == "p"].copy()
    if calls.empty or puts.empty:
        return None

    common = sorted(set(calls["strike"]).intersection(puts["strike"]))
    if not common:
        return None

    # Need positive bids on both legs to be tradable as a short
    candidates = []
    for k in common:
        c = calls[calls["strike"] == k].iloc[0]
        p = puts[puts["strike"] == k].iloc[0]
        if c["bid"] > 0 and p["bid"] > 0 and not np.isnan(c["delta"]) and not np.isnan(p["delta"]):
            candidates.append((abs(k - spot), k, c, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, strike, call_row, put_row = candidates[0]
    return call_row, put_row, strike, expiry


def lookup_option(chain_today: pd.DataFrame, expiry, strike: float, cp: str):
    """Find a specific option row on a given trade date."""
    df = chain_today[
        (chain_today["expiry"] == expiry)
        & (chain_today["strike"] == strike)
        & (chain_today["cp"] == cp)
    ]
    if df.empty:
        return None
    return df.iloc[0]
