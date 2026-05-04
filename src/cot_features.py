"""COT positioning features for the Layer 3 risk filter.

Pulls the `COT_TimeSeries Hard Coded` sheet from the WTI workbook, builds
rolling z-scores of managed-money and non-commercial net positioning, then
forward-fills onto the daily price grid with a one-report lag so no row at
day t uses a report whose release post-dates t.

Columns produced for the daily-aligned frame:
    mm_net, mm_net_oi, mm_net_oi_z
    nc_net, nc_net_oi, nc_net_oi_z
    total_oi
    cot_risk_off  (bool: positioning extremely short on either leg)

CFTC weekly reports reference Tuesday positioning and are released the
following Friday, ~3 calendar days later. We use a 7-day lag, which is
deliberately conservative: it guarantees the report is public by the time
we act on it without depending on intraday release timing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WORKBOOK = os.path.join(WORKSPACE, "WTI_COT_TimeSeries.xlsx")
DEFAULT_SHEET = "COT_TimeSeries Hard Coded"

# Header is on row index 3 (the row containing "Report Date", "NC Net", ...).
HEADER_ROW = 3

# Source-column → tidy-column mapping (only what Layer 3 uses).
COT_COLS = {
    "Report Date": "report_date",
    "NC Net": "nc_net",
    "MM Net": "mm_net",
    "Total OI (Fut)": "total_oi",
    "NC Net / OI": "nc_net_oi",
    "MM Net / OI": "mm_net_oi",
}


@dataclass(frozen=True)
class CotConfig:
    z_window_weeks: int = 104        # rolling window for the z-score (~2y)
    release_lag_days: int = 7        # min calendar days from report_date to first usable date
    risk_off_z: float = -1.0         # extremely-short threshold on either leg
    require_full_window: bool = True # NaN out the warm-up; never trade off partial stats


def _rolling_z(s: pd.Series, window: int, require_full: bool) -> pd.Series:
    minp = window if require_full else max(window // 4, 5)
    mu = s.rolling(window=window, min_periods=minp).mean()
    sd = s.rolling(window=window, min_periods=minp).std(ddof=0)
    z = (s - mu) / sd.replace(0.0, np.nan)
    return z


def load_cot_raw(
    path: str = DEFAULT_WORKBOOK,
    sheet: str = DEFAULT_SHEET,
) -> pd.DataFrame:
    """Read the COT sheet and return only the columns Layer 3 consumes."""
    df = pd.read_excel(path, sheet_name=sheet, header=HEADER_ROW)
    missing = [c for c in COT_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing expected COT columns: {missing}")
    df = df[list(COT_COLS.keys())].rename(columns=COT_COLS)
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df = df.dropna(subset=["report_date"]).sort_values("report_date").reset_index(drop=True)
    return df


def build_cot_features(
    cot_raw: pd.DataFrame,
    cfg: CotConfig = CotConfig(),
) -> pd.DataFrame:
    """Add z-scores and the available_date column."""
    df = cot_raw.copy()
    df["mm_net_oi_z"] = _rolling_z(df["mm_net_oi"], cfg.z_window_weeks, cfg.require_full_window)
    df["nc_net_oi_z"] = _rolling_z(df["nc_net_oi"], cfg.z_window_weeks, cfg.require_full_window)
    df["available_date"] = df["report_date"] + pd.Timedelta(days=cfg.release_lag_days)
    return df


def align_cot_to_daily(
    price_dates: pd.Series,
    cot_features: pd.DataFrame,
    cfg: CotConfig = CotConfig(),
) -> pd.DataFrame:
    """For each daily price date, attach the most recent COT row whose
    available_date ≤ the price date. Daily dates with no eligible report yet
    receive NaNs (warm-up handled downstream).
    """
    p = pd.DataFrame({"date": pd.to_datetime(price_dates).reset_index(drop=True)})
    cot = cot_features.sort_values("available_date").reset_index(drop=True)
    merged = pd.merge_asof(
        p.sort_values("date"),
        cot[["available_date", "report_date", "mm_net", "mm_net_oi", "mm_net_oi_z",
             "nc_net", "nc_net_oi", "nc_net_oi_z", "total_oi"]],
        left_on="date",
        right_on="available_date",
        direction="backward",
        allow_exact_matches=True,
    )

    risk_off = (
        (merged["mm_net_oi_z"] < cfg.risk_off_z)
        | (merged["nc_net_oi_z"] < cfg.risk_off_z)
    )
    merged["cot_risk_off"] = risk_off.fillna(False).astype(bool)
    return merged.reset_index(drop=True)


def load_daily_cot_features(
    price_dates: pd.Series,
    cfg: CotConfig = CotConfig(),
    workbook: Optional[str] = None,
) -> pd.DataFrame:
    """Convenience: raw → features → daily aligned in one call."""
    raw = load_cot_raw(workbook or DEFAULT_WORKBOOK)
    feats = build_cot_features(raw, cfg)
    return align_cot_to_daily(price_dates, feats, cfg)


if __name__ == "__main__":
    import sys

    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, HERE)
    from data_loader import load_price_data  # noqa: E402

    px = load_price_data()
    daily = load_daily_cot_features(px["date"])
    print(f"Daily COT rows: {len(daily)}  ({daily['date'].min().date()} -> {daily['date'].max().date()})")
    print(daily[["date", "report_date", "mm_net_oi", "mm_net_oi_z",
                 "nc_net_oi", "nc_net_oi_z", "cot_risk_off"]].head(10).to_string(index=False))
    print("...")
    print(daily[["date", "report_date", "mm_net_oi", "mm_net_oi_z",
                 "nc_net_oi", "nc_net_oi_z", "cot_risk_off"]].tail(10).to_string(index=False))
    print(f"\nrisk_off days: {daily['cot_risk_off'].sum()} / {len(daily)} "
          f"({daily['cot_risk_off'].mean()*100:.1f}%)")
