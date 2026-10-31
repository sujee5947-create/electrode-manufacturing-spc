# Electrode Manufacturing SPC — Dynamic Local Analysis System

Python workflow for **data-driven electrode manufacturing quality monitoring**.
Reads the **specified** raw CSV and SPEC workbook, checks data integrity, classifies each measurement, performs I-MR and C/U analysis, calculates process capability, and exports CSV / Excel audit / PPT / offline HTML reports.

## Important

- **No outcome is hard-coded.** The demonstration input in `raw data/` has 1,000 samples, 48 NG (4.8%), 2 severe and 7 warning intervals at 60-minute aggregation. These are **example input results**, not universal thresholds and not real manufacturing improvement claims.
- The previously published GitHub demo dataset is **different synthetic input**, producing 39 NG (3.9%). It does **not** represent a correction to the 48-NG dataset.
- SPC control limits must be validated from a stable *Phase I* process; especially review baseline stability for **each machine**. Global mixed-machine charts are reference only.
- Hotspot Tiers are **operational rules, not statistical significance tests**.
- Excel formulas may initially display blank until Excel recalculates. The workbook is a generated snapshot. **Rerun `main.py` after changing data.**
- **Never upload production/customer/company files or specifications to public GitHub without authorization.** This full-project package is intended for local/internal use.

## Local quick start (Python 3.10+)

```bash
python -m pip install -r requirements.txt
python main.py
python main.py --raw "C:/path/to/measurements.csv" --spec "C:/path/to/specification.xlsx" --output "C:/path/to/report_out" --interval 60 --baseline-n 200
python -m pytest -q
streamlit run app.py
```

- Default data files: `raw data/Electrode_Quality_Raw_Data.csv` and `raw data/Electrode_Quality_SPEC.xlsx`
- **When changing input, use exact input paths** (`--raw` and `--spec`), and do not overwrite the default example unless intentional. An incorrect path results in an error rather than silently loading a fallback dataset.
- CSV must have `timestamp` and columns listed in enabled SPEC rows. For full reporting, provide `machine_id`, `lot_id` and the optional process columns (`line_speed_m_min`, `drying_temperature_c`, `roll_pressure`).
- SPEC sheet columns: `raw_column`, `characteristic`, `unit`, `data_type` (`continuous` / `count`), `LSL`, `TARGET`, `USL`, `chart_type` (`I-MR` / `C` / `U`), `enabled` (`Y` / `N`).
- Negative, fractional, null or nonnumeric defect counts, null or invalid continuous values produce `INVALID`. CLI halts by default to avoid plausible but misleading reports; `--allow-invalid` is exploratory only.
- `--baseline-n` adjusts per-machine baseline sample count; `--interval` controls time grouping in minutes.

## Results

`result/` is generated on execution:

- `evaluated_quality_data.csv`: row-by-row judgments, incl. `INVALID` and multi-defect rows
- `interval_aggregation.csv`: time-bucket counts and tier inputs
- `analysis_summary.json`: dynamic key findings
- `run_manifest.json`: SHA256 hashes of the exact input files and runtime options
- `equipment_spc_summary.json` / `equipment_capability.csv`: per-machine SPC and capability diagnostics
- `Electrode_Quality_Calculation_Trace.xlsx`: dynamic Excel formula audit (variable N and SPEC order)
- `Electrode_Quality_SPC_Report.pptx` / `.html`: visual reports
- `charts/`: time trend, Pareto, heatmap, per-feature I-MR and per-machine charts

## Quality checks and interpretation

1. Judge all enabled SPEC characteristics independently and aggregate NG at row level. Multi-defect rows are counted only once in overall NG, but contribute to each affected characteristic's NG count.
2. Detect severe/warning periods only when enough observations exist (`N >= 6` by default). Low-sample intervals are kept as **insufficient** even when NG count is zero.
3. Baseline I-MR limits: `UCL/LCL = mean ± 2.66 × mean moving range`; moving ranges must not cross between machines. Report baseline stability warnings, not validated specification tolerances.
4. Within-machine MR standard deviation (`MR_bar / 1.128`) is used for Cp/Cpk estimation; overall `STDEV.S` is used for Pp/Ppk. Interpret with caution on unstable processes or mixed populations.
5. Excel workbook is generated with **dynamic data row count and dynamic SPEC column mapping**. Validate source inputs and use the JSON/CSV values as authoritative if spreadsheet formulas are not recalculated locally.

## Reproducibility

`run_manifest.json` records raw/SPEC SHA256 and analysis parameters. Tests cover both the provided reference snapshot and varied data sizes, reordered specifications, and invalid data handling. Results and tests are not tied to the demo’s 48-NG number for future inputs.

## Important U-chart limitation

For variable inspection area, U-chart visualization divides the observed count by exposure. The current row-level quality pass/fail check still compares **raw counts** to the SPEC USL. If your production specification is rate-based (defects per m²), adapt the quality rule and Excel trace before operational use.
