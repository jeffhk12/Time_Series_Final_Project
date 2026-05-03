"""Load USO price and option-chain data."""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd


WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_XLSX = os.path.join(WORKSPACE, "WTI_COT_TimeSeries.xlsx")
OPTION_DIR = os.path.join(WORKSPACE, "option_chains")

# USO had a 1-for-8 reverse split on 2020-04-29. Bloomberg PX_LAST is split-adjusted
# so pre-split prices are 8x what option strikes show. Restrict the backtest to the
# post-split window where strikes and prices align (within ~2% from cost-of-carry).
BACKTEST_START = pd.Timestamp("2020-05-04")


def load_price_data(path: str = PRICE_XLSX) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Price_TimeSeries_HardCoded", header=3)
    df.columns = [
        "date",
        "cl1",
        "cl2",
        "co1",
        "ovx",
        "uso_close",
        "uso_bid",
        "uso_ask",
        "uso_volume",
    ]
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["uso_close"]).sort_values("date").reset_index(drop=True)
    df = df[df["date"] >= BACKTEST_START].reset_index(drop=True)
    df["log_return"] = np.log(df["uso_close"] / df["uso_close"].shift(1))
    return df


def load_option_chain(option_dir: str = OPTION_DIR) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(option_dir, "USO_*_option_chain.csv")))
    parts = []
    for f in files:
        df = pd.read_csv(f, parse_dates=["Trade Date", "Expiry Date"])
        parts.append(df)
    oc = pd.concat(parts, ignore_index=True)
    oc.columns = [c.strip() for c in oc.columns]
    rename = {
        "Trade Date": "trade_date",
        "Strike": "strike",
        "Expiry Date": "expiry",
        "Call/Put": "cp",
        "Last Trade Price": "last",
        "Bid Price": "bid",
        "Ask Price": "ask",
        "Bid Implied Volatility": "iv_bid",
        "Ask Implied Volatility": "iv_ask",
        "Open Interest": "oi",
        "Volume": "volume",
        "Delta": "delta",
        "Gamma": "gamma",
        "Vega": "vega",
        "Theta": "theta",
        "Rho": "rho",
    }
    oc = oc.rename(columns=rename)
    oc["cp"] = oc["cp"].str.lower()
    oc["mid"] = (oc["bid"] + oc["ask"]) / 2.0
    oc["iv_mid"] = (oc["iv_bid"] + oc["iv_ask"]) / 2.0
    oc["dte"] = (oc["expiry"] - oc["trade_date"]).dt.days
    oc = oc[oc["trade_date"] >= BACKTEST_START].reset_index(drop=True)
    # Drop rows with no real quote
    oc = oc[(oc["bid"] >= 0) & (oc["ask"] > 0)].reset_index(drop=True)
    return oc


if __name__ == "__main__":
    px = load_price_data()
    oc = load_option_chain()
    print("price rows:", len(px), "range", px["date"].min().date(), "->", px["date"].max().date())
    print("option rows:", len(oc), "range", oc["trade_date"].min().date(), "->", oc["trade_date"].max().date())
