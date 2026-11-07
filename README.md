# Battery Electrode Manufacturing SPC & Quality Monitoring System

### Python-Based Quality Analysis & Automated Reporting

A Python-based automated quality monitoring system for battery electrode manufacturing.

This project demonstrates how manufacturing data can be analyzed using **Statistical Process Control (SPC)** to detect quality abnormalities, evaluate process capability, and generate automated engineering reports.

> **Portfolio Project | Synthetic Data | Python Automation**
>
> All example data and specifications are synthetic and intended for demonstration purposes.

---

## 1. Project Objectives

- Automate quality inspection and OK/NG classification.
- Monitor manufacturing process stability using SPC.
- Evaluate process capability using Cp/Cpk and Pp/Ppk.
- Identify defect patterns and abnormal production intervals.
- Generate automated Excel, PowerPoint, and HTML reports.

## 2. Key Features

| Feature | Description |
|---|---|
| Quality Inspection | Automatic OK/NG classification based on specifications |
| SPC Monitoring | I-MR, C-chart, and U-chart analysis |
| Process Capability | Cp, Cpk, Pp, and Ppk calculations |
| Defect Analysis | Defect trends and time-based hotspot detection |
| Equipment Comparison | Equipment-level quality monitoring |
| Automated Reporting | Excel, PowerPoint, and interactive HTML reports |

## 3. Example Results

The included synthetic dataset demonstrates the system's analysis capabilities.

| Indicator | Result |
|---|---:|
| Total Inspections | 1,000 |
| OK | 952 |
| NG | **48** |
| NG Rate | **4.80%** |
| High-Risk Intervals | 2 |
| Warning Intervals | 7 |
| Automated Tests | **35 Passed** |

*These results are based on demonstration data. The program automatically recalculates all results when new data is provided.*

## 4. Technologies

**Python · pandas · NumPy · Matplotlib · Plotly · SPC · Excel Automation · PowerPoint Automation**

## 5. How to Run

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

Run the analysis:

```bash
python main.py
```

Run automated tests (run the analysis first — the report tests check the files generated in `result/`):

```bash
python main.py
python -m pytest -q
```

To analyze a different dataset:

```bash
python main.py --raw "new_raw.csv" --spec "new_spec.xlsx" --output "results"
```

## 6. Related Project

**[Battery Quality Data Analysis & Report Automation](https://github.com/sujee5947-create/battery-quality-analysis)**

A complementary Python project focused on battery cell quality analysis and automated reporting.

---

**Focus:** Battery Manufacturing · Quality Engineering · Statistical Process Control · Python Automation
