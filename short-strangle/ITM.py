"""ITM short strangle — sell ~75-delta call + ~75-delta put on USO."""

from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import load_data, run_strangle_backtest, summarize

CALL_DELTA = 0.75
PUT_DELTA  = -0.75
NAME       = "ITM_strangle"


def main():
    price, chain_by_date = load_data()
    daily, trades = run_strangle_backtest(price, chain_by_date, CALL_DELTA, PUT_DELTA, NAME)
    summarize(daily, trades, NAME)


if __name__ == "__main__":
    main()
