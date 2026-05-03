"""Normalize the Bloomberg workbook into the schema expected by data_loader.py.

This keeps the existing backtest code unchanged by producing a cleaned workbook
with the exact column layout the loader expects.

Usage:
    ./bin/python src/prepare_price_workbook.py
    ./bin/python src/prepare_price_workbook.py --input WTI_COT_TimeSeries.xlsx --output WTI_COT_TimeSeries.cleaned.xlsx
"""

from __future__ import annotations

import argparse
import os

import pandas as pd


WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INPUT = os.path.join(WORKSPACE, "WTI_COT_TimeSeries.xlsx")
DEFAULT_OUTPUT = os.path.join(WORKSPACE, "WTI_COT_TimeSeries.cleaned.xlsx")
SHEET_NAME = "Price_TimeSeries_HardCoded"
EXPECTED_COLUMNS = [
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


def build_clean_price_sheet(input_path: str) -> pd.DataFrame:
    df = pd.read_excel(input_path, sheet_name=SHEET_NAME, header=3)
    if df.shape[1] < len(EXPECTED_COLUMNS):
        raise ValueError(
            f"{SHEET_NAME} only has {df.shape[1]} columns; expected at least {len(EXPECTED_COLUMNS)}."
        )

    clean = df.iloc[:, : len(EXPECTED_COLUMNS)].copy()
    clean.columns = EXPECTED_COLUMNS
    clean["date"] = pd.to_datetime(clean["date"])
    clean = clean.dropna(subset=["date"]).reset_index(drop=True)
    return clean


def write_clean_workbook(df: pd.DataFrame, output_path: str) -> None:
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False, startrow=3)
        ws = writer.book[SHEET_NAME]
        ws["A2"] = "META"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Source workbook path")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Cleaned workbook path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean = build_clean_price_sheet(args.input)
    write_clean_workbook(clean, args.output)
    print(f"Wrote cleaned workbook to: {args.output}")


if __name__ == "__main__":
    main()
