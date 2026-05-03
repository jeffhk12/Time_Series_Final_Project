"""ATM short straddle — sell ~50-delta call + ~50-delta put on USO."""

from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import load_data, run_strangle_backtest, summarize

CALL_DELTA = 0.50
PUT_DELTA  = -0.50
NAME       = "ATM_straddle"


def main():
    price, chain_by_date = load_data()
    daily, trades = run_strangle_backtest(price, chain_by_date, CALL_DELTA, PUT_DELTA, NAME)
    summarize(daily, trades, NAME)


if __name__ == "__main__":
    main()
