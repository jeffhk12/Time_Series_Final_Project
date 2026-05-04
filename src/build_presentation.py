"""Build the final PowerPoint deck for the Time Series project.

Generates outputs/Time_Series_Final_Presentation.pptx using all charts and
tables already produced by run_layer1.py / run_layer2_garch.py /
run_robustness.py / run_layer3_cot.py.
"""

from __future__ import annotations

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_DIR = os.path.join(WORKSPACE, "outputs", "charts")
OUT_PATH = os.path.join(WORKSPACE, "outputs", "Time_Series_Final_Presentation.pptx")

# 16:9 widescreen
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)

NAVY = RGBColor(0x0B, 0x2A, 0x5B)
TEAL = RGBColor(0x12, 0x6E, 0x82)
LIGHT_GREY = RGBColor(0xEF, 0xEF, 0xEF)
DARK_TEXT = RGBColor(0x22, 0x22, 0x22)
ACCENT = RGBColor(0xC0, 0x39, 0x2B)


def _set_text(frame, paragraphs, default_size=18, default_color=DARK_TEXT):
    """Replace a text frame with a list of (text, level) tuples."""
    frame.clear()
    for i, item in enumerate(paragraphs):
        if isinstance(item, tuple):
            text, level = item
        else:
            text, level = item, 0
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.level = level
        run = p.add_run()
        run.text = text
        run.font.size = Pt(default_size if level == 0 else max(default_size - 2, 12))
        run.font.color.rgb = default_color
        run.font.name = "Calibri"


def _add_title_bar(slide, title: str, subtitle: str | None = None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.9))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    tf = bar.text_frame
    tf.margin_left = Inches(0.5)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.05)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = title
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    run.font.name = "Calibri"
    if subtitle:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.LEFT
        r2 = p2.add_run()
        r2.text = subtitle
        r2.font.size = Pt(14)
        r2.font.color.rgb = RGBColor(0xCD, 0xD9, 0xE8)
        r2.font.name = "Calibri"


def _add_footer(slide, text: str):
    box = slide.shapes.add_textbox(Inches(0.4), SLIDE_H - Inches(0.4), SLIDE_W - Inches(0.8), Inches(0.3))
    p = box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    r.font.name = "Calibri"


def add_blank(prs, layout_index=6):
    return prs.slides.add_slide(prs.slide_layouts[layout_index])


def add_bullets_slide(prs, title, bullets, subtitle=None, footer=None):
    slide = add_blank(prs)
    _add_title_bar(slide, title, subtitle)
    box = slide.shapes.add_textbox(Inches(0.6), Inches(1.15), SLIDE_W - Inches(1.2), SLIDE_H - Inches(1.7))
    tf = box.text_frame
    tf.word_wrap = True
    _set_text(tf, bullets, default_size=20)
    if footer:
        _add_footer(slide, footer)
    return slide


def add_split_slide(prs, title, bullets, image_path, subtitle=None, footer=None,
                    image_width=Inches(7.0), image_left=None, text_width=Inches(5.4)):
    slide = add_blank(prs)
    _add_title_bar(slide, title, subtitle)

    # Left text box
    txt = slide.shapes.add_textbox(Inches(0.5), Inches(1.15), text_width, SLIDE_H - Inches(1.7))
    tf = txt.text_frame
    tf.word_wrap = True
    _set_text(tf, bullets, default_size=18)

    # Right image
    if image_left is None:
        image_left = SLIDE_W - image_width - Inches(0.4)
    if image_path and os.path.exists(image_path):
        slide.shapes.add_picture(image_path, image_left, Inches(1.2),
                                 width=image_width)
    if footer:
        _add_footer(slide, footer)
    return slide


def add_image_slide(prs, title, image_path, caption=None, subtitle=None, footer=None,
                    image_width=Inches(11.5)):
    slide = add_blank(prs)
    _add_title_bar(slide, title, subtitle)
    if image_path and os.path.exists(image_path):
        left = (SLIDE_W - image_width) / 2
        slide.shapes.add_picture(image_path, left, Inches(1.15), width=image_width)
    if caption:
        cap = slide.shapes.add_textbox(Inches(0.6), SLIDE_H - Inches(0.7), SLIDE_W - Inches(1.2), Inches(0.4))
        tf = cap.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = caption
        r.font.size = Pt(13)
        r.font.italic = True
        r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        r.font.name = "Calibri"
    if footer:
        _add_footer(slide, footer)
    return slide


def add_table_slide(prs, title, header, rows, subtitle=None,
                    col_widths_in=None, footer=None, highlight_row=None,
                    note=None):
    slide = add_blank(prs)
    _add_title_bar(slide, title, subtitle)

    n_cols = len(header)
    n_rows = len(rows) + 1
    table_w = SLIDE_W - Inches(1.2)
    table_h = Inches(min(0.55 * n_rows, 5.0))
    left = Inches(0.6)
    top = Inches(1.4)
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, left, top, table_w, table_h)
    tbl = tbl_shape.table

    if col_widths_in:
        total = sum(col_widths_in)
        for i, w in enumerate(col_widths_in):
            tbl.columns[i].width = Inches((w / total) * (table_w / Inches(1)))

    # Header row
    for j, h in enumerate(header):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        tf = cell.text_frame
        tf.margin_left = Inches(0.08)
        tf.margin_right = Inches(0.08)
        tf.margin_top = Inches(0.04)
        tf.margin_bottom = Inches(0.04)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = h
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.name = "Calibri"

    # Body rows
    for i, row in enumerate(rows, start=1):
        is_hl = (highlight_row is not None and i - 1 == highlight_row)
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = (RGBColor(0xE8, 0xF0, 0xE8) if is_hl
                                        else (LIGHT_GREY if i % 2 == 0 else RGBColor(0xFF, 0xFF, 0xFF)))
            tf = cell.text_frame
            tf.margin_left = Inches(0.08)
            tf.margin_right = Inches(0.08)
            tf.margin_top = Inches(0.04)
            tf.margin_bottom = Inches(0.04)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(val)
            r.font.size = Pt(12)
            r.font.bold = is_hl
            r.font.color.rgb = DARK_TEXT
            r.font.name = "Calibri"

    if note:
        nb = slide.shapes.add_textbox(Inches(0.6), top + table_h + Inches(0.15),
                                      SLIDE_W - Inches(1.2), Inches(1.5))
        tf = nb.text_frame
        tf.word_wrap = True
        _set_text(tf, note, default_size=15)

    if footer:
        _add_footer(slide, footer)
    return slide


# --------------------------------------------------------------------------
# Build the deck
# --------------------------------------------------------------------------

def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    footer = "MSQF · Time Series Econometrics Final Project"

    # ---- 1. Title ----
    slide = add_blank(prs)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.3), SLIDE_W - Inches(1.6), Inches(2.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = "Forecasting Volatility for a Short-Vol Strategy on USO"
    r.font.size = Pt(44); r.font.bold = True
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); r.font.name = "Calibri"

    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.LEFT
    r2 = p2.add_run()
    r2.text = "EWMA, Rolling GARCH(1,1), and a COT Positioning Filter"
    r2.font.size = Pt(22); r2.font.color.rgb = RGBColor(0xCD, 0xD9, 0xE8); r2.font.name = "Calibri"

    p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.LEFT
    p3.space_before = Pt(36)
    r3 = p3.add_run()
    r3.text = "Time Series Econometrics  ·  MSQF  ·  Spring 2026"
    r3.font.size = Pt(16); r3.font.color.rgb = RGBColor(0xAE, 0xC0, 0xD8); r3.font.name = "Calibri"

    # ---- 2. Agenda ----
    add_bullets_slide(
        prs, "Agenda",
        [
            "1.  Project overview and motivation",
            "2.  Data sources (Bloomberg + CFTC + options vendor)",
            "3.  Strategy design — short ATM straddle, hedge, stop",
            "4.  Time series methods — EWMA and rolling GARCH(1,1)",
            "5.  Layer 1 (EWMA) and Layer 2 (GARCH) results",
            "6.  Robustness tests — windows, refit, thresholds, subperiods",
            "7.  COT positioning as an exploratory risk filter",
            "8.  Limitations and next steps",
        ],
        footer=footer,
    )

    # ---- 3. Project Overview ----
    add_bullets_slide(
        prs, "Project Overview",
        [
            "Goal: build a disciplined short-volatility strategy on the USO oil ETF, "
            "with timing driven by time-series volatility forecasts.",
            ("Core question: does forecasting realized volatility (EWMA / GARCH) and "
             "comparing it to implied volatility produce a persistent edge?", 0),
            "Three-layer build:",
            ("Layer 1 — short ATM straddle baseline with an EWMA-based timing filter.", 1),
            ("Layer 2 — replace EWMA with a rolling GARCH(1,1) forecast.", 1),
            ("Layer 3 — add a COT positioning veto as an exploratory risk filter.", 1),
            ("Time series methods are the heart of the project — option strategy is the "
             "vehicle through which the forecast quality is measured.", 0),
        ],
        subtitle="Connecting volatility forecasting to a tradable P&L outcome",
        footer=footer,
    )

    # ---- 4. Why short-vol on USO ----
    add_bullets_slide(
        prs, "Why Short Volatility on USO?",
        [
            "Crude oil volatility carries a persistent risk premium: implied vol "
            "tends to exceed realized vol on average, especially in calm regimes.",
            "USO is a liquid, listed-options vehicle on WTI exposure — accessible "
            "without a futures account, and with publicly available chains.",
            "Oil is heavily news-driven (OPEC, geopolitics, refinery cycles). Vol "
            "forecasting is hard precisely because of regime shifts — which makes "
            "it a real test of EWMA vs GARCH.",
            ("Key challenge: short straddles are short gamma and short vega. "
             "Without timing, premium collected in calm years is given back in "
             "spike years (Russia/Ukraine 2022, Iran/Israel 2024).", 0),
            "Practical use: a vol-selling sleeve in a multi-strategy book, sized "
            "small, with disciplined entry filters and stop-losses to cap tail trades.",
        ],
        subtitle="Persistent vol risk premium meets a regime-shifting underlying",
        footer=footer,
    )

    # ---- 5. Data sources ----
    add_bullets_slide(
        prs, "Data Sources",
        [
            "WTI / USO price data — Bloomberg BDH:",
            ("CL1, CL2, CO1, OVX, USO close/bid/ask/volume; 2010-01-05 → 2026-04-10.", 1),
            ("Backtest restricted to 2020-05-04 → 2026-04-10 (post 1-for-8 USO reverse split).", 1),
            "COT positioning — CFTC weekly disaggregated report via Bloomberg:",
            ("Managed Money (MM) and Non-Commercial (NC) net positioning, Total OI.", 1),
            ("Tuesday positioning, released Friday — we apply a 7-day lag to avoid look-ahead.", 1),
            "USO option chains — external vendor:",
            ("28 quarterly CSVs; ~2,015,055 rows of bid/ask/IV/Greeks across all strikes/expiries.", 1),
            ("Filtered to bid ≥ 0, ask > 0, post-split window.", 1),
            ("Mid prices = (bid + ask) / 2; mid IV = (iv_bid + iv_ask) / 2.", 1),
            "Cleaning choices: post-split alignment, drop quote-stale rows, "
            "EWMA seed = sample variance of first 20 returns to limit warm-up bias.",
        ],
        subtitle="Three independent sources stitched on a daily index",
        footer=footer,
    )

    # ---- 6. Strategy design — straddle ----
    add_split_slide(
        prs, "Strategy Design — Short ATM Straddle",
        [
            "On entry day, sell 1 ATM call + 1 ATM put with ~30 DTE (21–45 day window).",
            "Premium received at the bid; daily MTM at the mid; exit at the ask.",
            "1 contract = 100 shares of underlying.",
            ("Entry pacing: re-enter every ~21 trading days (no overlapping trades).", 0),
            ("Exit: 5 trading days before expiry, or on stop-loss.", 0),
            "Stop-loss rule: exit if straddle ask ≥ 2× initial premium received.",
            "Hedge: daily rebalance of USO shares to delta-neutral (when enabled).",
            ("Transaction costs: 5 bps on USO notional traded for hedge rebalances; "
             "bid/ask slippage already captured in entry/exit prices.", 0),
        ],
        image_path=os.path.join(CHART_DIR, "01_underlying_price.png"),
        subtitle="Monthly cadence, defined exit rules, explicit cost model",
        footer=footer,
    )

    # ---- 7. Strategy design — entry filter ----
    add_split_slide(
        prs, "Strategy Design — Entry Filter",
        [
            "Conditional entry: only sell vol when implied is rich vs forecasted realized.",
            ("Filter rule:    IV(ATM) / σ̂_forecast > threshold (default 1.10).", 0),
            "EWMA branch (Layer 1): σ̂ from λ = 0.94 EWMA of daily log returns.",
            "GARCH branch (Layer 2): σ̂ from rolling GARCH(1,1) one-step forecast.",
            ("Same backtest engine for both — only the forecast series changes.", 0),
            "Threshold > 1 keeps trades only when IV looks ≥ 10% above forecasted realized "
            "vol (i.e. options are rich), which is the structural source of edge.",
            "Strategies tested across the project:",
            ("A — naked straddle, no filter      (B + delta hedge)", 1),
            ("C — EWMA filter, no hedge          (D + hedge + stop)", 1),
            ("E — GARCH filter, no hedge          (F + hedge + stop)", 1),
            ("G — F + COT positioning veto  (Layer 3 exploratory)", 1),
        ],
        image_path=os.path.join(CHART_DIR, "03_iv_vs_ewma.png"),
        subtitle="Trade only when implied vol is rich relative to the forecast",
        footer=footer,
    )

    # ---- 8. Time series methods — EWMA ----
    add_split_slide(
        prs, "Time Series Method 1 — EWMA Volatility",
        [
            "RiskMetrics-style EWMA on daily log returns:",
            ("σ²_t  =  λ · σ²_{t−1}  +  (1 − λ) · r²_t", 0),
            "λ = 0.94 (RiskMetrics default; ~75-day half-life).",
            ("Seeded with the sample variance of the first 20 returns to avoid warm-up bias.", 0),
            "Strengths:",
            ("Single parameter, fully recursive, no estimation step → robust and stable.", 1),
            ("No forecast distribution assumption — purely a smoothing filter.", 1),
            "Weaknesses:",
            ("Cannot mean-revert: forecast slowly trails realized after a spike.", 1),
            ("No conditional fat-tail or persistence parameter — one number for everything.", 1),
            ("Use here: the published Layer 1 baseline filter.", 0),
        ],
        image_path=os.path.join(CHART_DIR, "02_ewma_realized_vol.png"),
        subtitle="Recursive smoother — simple, stable, but not mean-reverting",
        footer=footer,
    )

    # ---- 9. Time series methods — GARCH ----
    add_split_slide(
        prs, "Time Series Method 2 — Rolling GARCH(1,1)",
        [
            "Standard GARCH(1,1) on daily log returns (zero-mean, normal innovations):",
            ("σ²_t = ω + α · r²_{t−1} + β · σ²_{t−1}", 0),
            "Rolling estimation:",
            ("Fit window = 252 trading days (~1 year).", 1),
            ("Refit every 21 trading days (~monthly).", 1),
            ("Forecast horizon = 1 day, used at trade-decision time.", 1),
            ("Estimation as of t uses returns through t−1 only — no look-ahead.", 1),
            "Why GARCH for short-vol timing:",
            ("Captures volatility clustering and mean reversion explicitly.", 1),
            ("Reacts to a vol spike without permanently re-leveling like EWMA.", 1),
            ("Provides a richer conditional model — α + β captures persistence.", 1),
            "Implemented with the `arch` package; returns rescaled by 100 for fit stability.",
        ],
        image_path=os.path.join(CHART_DIR, "08_forecast_comparison_ewma_vs_garch.png"),
        subtitle="Rolling refit captures regime shifts with a 1-step forecast",
        footer=footer,
    )

    # ---- 10. EWMA vs GARCH signal ----
    add_image_slide(
        prs, "EWMA vs GARCH — Forecast Signal Comparison",
        os.path.join(CHART_DIR, "08_forecast_comparison_ewma_vs_garch.png"),
        caption="Both forecasts track realized vol; GARCH mean-reverts faster after spikes, "
                "producing fewer but more selective entries.",
        footer=footer,
    )

    # ---- 11. Layer 1 results table ----
    add_table_slide(
        prs, "Layer 1 Results — EWMA Baseline",
        header=["Strategy", "Trades", "Total P&L", "Sharpe", "Max DD", "Worst Trade", "Win %"],
        rows=[
            ["A — naked straddle",         "74", "−$2,378", "−0.28", "−$5,069", "−$3,375", "67.6%"],
            ["B — + delta hedge",          "74", "−$4,961", "−0.33", "−$8,643", "−$6,144", "64.9%"],
            ["C — + EWMA filter",          "58", "−$104",   "−0.01", "−$4,700", "−$2,865", "65.5%"],
            ["D — + hedge + filter + stop","58", "+$557",   "+0.05", "−$4,859", "−$1,668", "58.6%"],
        ],
        highlight_row=3,
        subtitle="Sample: 2020-05-04 → 2026-04-10 · 1 contract per trade",
        note=[
            "Naked + unconditional selling loses money (A, B).",
            "Delta hedging alone makes things worse — it converts gamma into realised P&L "
            "without a timing edge to offset it.",
            "EWMA filter is the main improvement: skipping the worst 16 trades flips the "
            "Sharpe from −0.28 to ≈ 0; adding a stop-loss tightens the worst trade by 50%.",
        ],
        footer=footer,
    )

    # ---- 12. Layer 2 results table ----
    add_table_slide(
        prs, "Layer 2 Results — GARCH Extension",
        header=["Strategy", "Trades", "Total P&L", "Sharpe", "Max DD", "Worst Trade", "Win %"],
        rows=[
            ["D — EWMA + hedge + stop",     "58", "+$557",   "+0.05", "−$4,859", "−$1,668", "58.6%"],
            ["E — GARCH filter, no hedge",  "47", "+$1,587", "+0.22", "−$3,621", "−$3,359", "76.6%"],
            ["F — GARCH + hedge + stop",    "47", "+$4,987", "+0.53", "−$2,360", "−$1,676", "70.2%"],
        ],
        highlight_row=2,
        subtitle="Same engine, mechanics, hedge, and stop — only the forecast changes",
        note=[
            "GARCH cuts trade count by ~20% by being more selective in calm regimes.",
            "Sharpe rises 10× over EWMA-D; max drawdown halves; worst trade is comparable.",
            "F is the headline result of the project: hedge + stop + GARCH timing.",
        ],
        footer=footer,
    )

    # ---- 13. Cumulative P&L all methods chart ----
    add_image_slide(
        prs, "Cumulative P&L — All Methods",
        os.path.join(CHART_DIR, "09_cumulative_pnl_all_methods.png"),
        caption="GARCH-timed strategies (E, F) extend the equity curve through 2024–25 where "
                "EWMA-timed strategies stall.",
        footer=footer,
    )

    # ---- 14. Drawdown comparison ----
    add_image_slide(
        prs, "Drawdown Comparison",
        os.path.join(CHART_DIR, "10_drawdown_all_methods.png"),
        caption="Hedged + GARCH (F) keeps the deepest drawdown at ~$2,400 vs ~$8,600 for the "
                "naked hedged baseline (B).",
        footer=footer,
    )

    # ---- 15. Robustness — GARCH window x refit ----
    add_image_slide(
        prs, "Robustness — GARCH Fit Window × Refit Frequency",
        os.path.join(CHART_DIR, "14_robustness_garch_fit_refit.png"),
        caption="Sharpe stable across most W × R cells. Failure mode: short window (W=126) + "
                "frequent refits (R=5) overfits the recent regime.",
        footer=footer,
    )

    # ---- 16. Robustness — threshold x stop ----
    add_image_slide(
        prs, "Robustness — Entry Threshold × Stop-Loss Multiple",
        os.path.join(CHART_DIR, "13_robustness_garch_threshold_stop.png"),
        caption="At W=252 / R=21, Sharpe is positive across nearly all (threshold × stop) "
                "cells — the baseline is not a single lucky setting.",
        footer=footer,
    )

    # ---- 17. Robustness — subperiods ----
    add_image_slide(
        prs, "Robustness — Subperiod Performance",
        os.path.join(CHART_DIR, "16_robustness_subperiods.png"),
        caption="GARCH-default is positive in every subperiod; EWMA-default is propped up by "
                "2022–23 alone and negative in 2024–26.",
        footer=footer,
    )

    # ---- 18. Robustness summary ----
    add_bullets_slide(
        prs, "Robustness — What the Tests Tell Us",
        [
            "108-cell GARCH grid: fit window {126, 252, 504} × refit {5, 21, 63} × "
            "threshold {1.05, 1.10, 1.15, 1.20} × stop {1.5, 2.0, 2.5}.",
            ("Sharpe distribution: mean +0.17, median +0.23, range −0.71 to +0.77.", 1),
            ("68% of cells are profitable; 19/108 beat the published 0.53.", 1),
            ("Default cell sits inside the bulk, not at an extreme.", 1),
            "EWMA grid (36 cells) is bimodal-flat: median Sharpe ≈ 0.04, max 0.45.",
            ("Confirms GARCH dominates EWMA across the parameter space, not at one point.", 1),
            "Subperiod splits show GARCH is positive in 2020–21, 2022–23, and 2024–26;",
            ("EWMA is negative in 2020–21 and 2024–26 — its full-sample 0.05 leans on 2022–23 alone.", 1),
            "Bottom line: the GARCH result is structurally stable, not a parameter artefact.",
        ],
        subtitle="The headline GARCH result survives sensible perturbations",
        footer=footer,
    )

    # ---- 19. COT exploration ----
    add_split_slide(
        prs, "COT Positioning — Exploratory Risk Filter",
        [
            "CFTC weekly disaggregated report:",
            ("Managed Money (MM) Net / OI — speculator positioning.", 1),
            ("Non-Commercial (NC) Net / OI — broader speculator class.", 1),
            "Hypothesis: do not sell vol when speculators are extremely short.",
            ("Crowded short positioning has historically preceded sharp vol expansions.", 1),
            "Construction:",
            ("Rolling 104-week z-score of MM and NC Net / OI.", 1),
            ("Risk-off veto if MM-z OR NC-z < threshold.", 1),
            ("7-day release lag applied — uses only reports public by trade date.", 1),
            "Layer 3 strategy G = Layer 2 strategy F + COT veto.",
        ],
        image_path=os.path.join(CHART_DIR, "17_cot_features_timeline.png"),
        subtitle="Net positioning, rolling z-score, and the resulting veto window",
        footer=footer,
    )

    # ---- 20. COT result ----
    add_table_slide(
        prs, "Layer 3 Result — COT Filter (Exploratory)",
        header=["z-window (w)", "risk-off z", "veto %", "Trades", "Total P&L", "Sharpe", "Max DD"],
        rows=[
            ["52",  "−1.0", "45%", "31", "+$2,982", "+0.32", "−$3,235"],
            ["52",  "−1.5", "25%", "39", "+$1,727", "+0.20", "−$2,772"],
            ["104", "−1.0", "47%", "26", "+$564",   "+0.06", "−$3,069"],
            ["104", "−1.5", "28%", "37", "+$3,769", "+0.39", "−$3,414"],
            ["156", "−1.0", "48%", "26", "+$1,244", "+0.13", "−$4,997"],
            ["156", "−1.5", "29%", "35", "+$1,912", "+0.23", "−$2,604"],
            ["F (no COT) — baseline", "—", "0%", "47", "+$4,987", "+0.53", "−$2,360"],
        ],
        highlight_row=6,
        subtitle="No COT cell beats the unfiltered GARCH baseline (Sharpe 0.53)",
        note=[
            "Filter throws away enough good trades that gross premium collected falls more "
            "than it cuts losers — net Sharpe drops in every cell.",
            "Honest negative result: with this construction, COT positioning is orthogonal to "
            "the GARCH IV-vs-realized signal but not additive on top of it.",
            "Reported as exploratory rather than production — sensitivity grid is the main message.",
        ],
        footer=footer,
    )

    # ---- 21. Limitations ----
    add_bullets_slide(
        prs, "Limitations",
        [
            "Capital and margin: short straddles are short gamma and short vega; broker margin "
            "easily dwarfs notional premium received.",
            ("The dollar P&L numbers are per-1-contract — capital intensity is the unmodelled cost.", 1),
            "Tail risk: a single fat-tail event can erase years of premium. Stop-loss caps the "
            "trade-level loss but not the gap risk overnight or on weekend headlines.",
            "Transaction-cost model is simple: 5 bps on hedge notional, mid-quote MTM, "
            "bid/ask on entry/exit. Real execution would face slippage and venue spreads.",
            "Model risk:",
            ("EWMA — single λ, no fat-tail or asymmetry.", 1),
            ("GARCH — symmetric, normal innovations; misses leverage effect and jumps.", 1),
            "Sample size: ~6 years and ~50 trades per timed strategy — wide confidence intervals "
            "around the headline Sharpe of 0.53.",
            "Parameter risk: 144-cell sweep helps but is not a true cross-validation.",
            "Data scope: USO ≠ WTI futures; tracking error from roll, expense ratio, and "
            "creation/redemption mechanics is not modelled.",
        ],
        subtitle="Where the result is fragile",
        footer=footer,
    )

    # ---- 22. Next steps ----
    add_bullets_slide(
        prs, "Potential Next Steps",
        [
            "Expand robustness:",
            ("Walk-forward / out-of-sample splits beyond simple subperiod cuts.", 1),
            ("Bootstrap confidence intervals on Sharpe by resampling trades.", 1),
            "Improve the volatility model:",
            ("EGARCH and GJR-GARCH for the leverage effect (likely larger in equities/oil).", 1),
            ("HAR-RV using realized variance from intraday data, if obtainable.", 1),
            ("Heavier-tailed innovations (Student-t) inside the same arch framework.", 1),
            "Richer signals:",
            ("Option skew and term-structure features (vol-of-vol, contango of variance).", 1),
            ("COT change-in-position rather than levels (momentum of speculator flows).", 1),
            ("Use COT as a sizing input rather than a binary veto.", 1),
            "Execution and capital realism:",
            ("Margin-aware sizing; explicit capital base; risk budgeting per trade.", 1),
            ("Slippage scaling with size and realised vol; weekend gap modelling.", 1),
            "Extend universe: SPY, GLD, TLT vol-selling sleeves; broader commodity vol.",
        ],
        subtitle="From a single-asset prototype to a robust, capacity-aware sleeve",
        footer=footer,
    )

    # ---- 23. Key takeaways ----
    add_bullets_slide(
        prs, "Key Takeaways",
        [
            "Unconditional short-vol on USO loses money over 2020–26.",
            "Delta hedging without a timing edge converts gamma into negative P&L.",
            "EWMA timing flips the strategy from clearly losing to roughly break-even — "
            "timing is the main source of edge, not hedging.",
            "Rolling GARCH(1,1) substantially improves on EWMA: Sharpe rises from 0.05 → 0.53, "
            "max drawdown halves, and the curve is positive in every subperiod.",
            "Robustness sweep (108 GARCH cells) shows the result is structurally stable, not "
            "a single-point fluke; failure modes are interpretable (short window + frequent refits).",
            "COT positioning is interesting but doesn't add value as a binary veto on top of "
            "GARCH — useful exploratory signal, not a production filter in this version.",
            "Honest scope: the project is a forecasting study with a tradable yardstick. "
            "The volatility model quality is what drives the differences between layers.",
        ],
        subtitle="Timing matters most — and GARCH does timing better than EWMA in this sample",
        footer=footer,
    )

    # ---- 24. Closing ----
    slide = add_blank(prs)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.8), SLIDE_W - Inches(1.6), Inches(2.0))
    tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = "Thank you"
    r.font.size = Pt(60); r.font.bold = True
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); r.font.name = "Calibri"
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.LEFT
    r2 = p2.add_run()
    r2.text = "Questions and discussion"
    r2.font.size = Pt(22); r2.font.color.rgb = RGBColor(0xCD, 0xD9, 0xE8); r2.font.name = "Calibri"

    prs.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    size_kb = os.path.getsize(path) / 1024.0
    print(f"Wrote {path}  ({size_kb:,.1f} KB)")
