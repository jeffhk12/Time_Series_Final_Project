# Reproducibility Notes

This package contains the code, notebooks, generated tables, charts, report, and
presentation for the Time Series final project. It intentionally excludes the raw
Bloomberg and option-chain data files because those inputs are large and may be
vendor-licensed.

## What Is Included

- `src/`: backtest engine, volatility models, COT feature code, robustness runs,
  report generation, and PowerPoint generation.
- `notebooks/`: notebook-building utilities.
- `short-strangle/`: earlier short-strangle exploration scripts and outputs.
- `outputs/tables/`: generated CSV result tables.
- `outputs/charts/`: generated figures used in the report and presentation.
- `outputs/Time_Series_Final_Presentation.pptx`: final presentation deck.
- `README.md`, `final_results_report.md`, and
  `layer_1_short_vol_project_plan.md`.

## Raw Data Omitted

The following raw data files are not included in the reproducibility zip:

- `WTI_COT_TimeSeries.xlsx`
- `WTI_COT_TimeSeries.cleaned.xlsx`
- `option_chains/`

To rerun the project from raw data, restore the raw files to these paths:

```text
WTI_COT_TimeSeries.xlsx
option_chains/USO_YYYY_qN_option_chain.csv
```

The option-chain files should follow the naming pattern already used by the
loader, for example:

```text
option_chains/USO_2024_q1_option_chain.csv
option_chains/USO_2024_q2_option_chain.csv
```

## Python Dependencies

Install the required packages in your Python environment:

```bash
python -m pip install pandas numpy matplotlib openpyxl arch python-pptx
```

## Suggested Run Order

From the project root, after restoring the raw data files:

```bash
python src/run_layer1.py
python src/run_layer2_garch.py
python src/run_robustness.py
python src/run_layer3_cot.py
python src/build_final_report.py
python src/build_presentation.py
```

## Expected Outputs

The scripts write generated artifacts to:

```text
outputs/tables/
outputs/charts/
outputs/Time_Series_Final_Presentation.pptx
final_results_report.md
```

The included zip already contains these generated outputs so the report and deck
can be reviewed without rerunning the raw-data backtests.
