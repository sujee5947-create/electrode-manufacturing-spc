"""
SPC Analysis Module
Implements Individuals and Moving Range (I-MR) control charts with baseline period
and Western Electric / Nelson out-of-control detection rules.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


class SPCAnalysisError(Exception):
    pass


def calculate_imr_limits(series: pd.Series, baseline_n: int = 200) -> Dict[str, float]:
    """
    Calculates I-MR limits based on the baseline period (first baseline_n data points).
    """
    clean_series = series.dropna().reset_index(drop=True)
    n_total = len(clean_series)
    if n_total < 2:
        raise SPCAnalysisError("At least 2 points are required for I-MR calculations.")

    n_base = min(n_total, baseline_n)
    baseline_vals = clean_series.iloc[:n_base]

    # I Chart Center Line
    cl_i = float(baseline_vals.mean())

    # Moving Range
    mr_vals = baseline_vals.diff().abs().dropna()
    if len(mr_vals) == 0:
        mr_bar = 0.0
    else:
        mr_bar = float(mr_vals.mean())

    # Limits
    ucl_i = cl_i + 2.66 * mr_bar
    lcl_i = cl_i - 2.66 * mr_bar

    cl_mr = mr_bar
    ucl_mr = 3.267 * mr_bar
    lcl_mr = 0.0

    return {
        "baseline_n": n_base,
        "cl_i": cl_i,
        "ucl_i": ucl_i,
        "lcl_i": lcl_i,
        "cl_mr": cl_mr,
        "ucl_mr": ucl_mr,
        "lcl_mr": lcl_mr,
        "mr_bar": mr_bar
    }


def detect_imr_violations(
    values: pd.Series,
    mr_values: pd.Series,
    limits: Dict[str, float]
) -> Dict[str, List[int]]:
    """
    Detects Western Electric / Nelson out-of-control rules:
    - Rule 1: Point beyond UCL or LCL
    - Rule 2: 7 consecutive points on one side of center line (Run)
    - Rule 3: 6 consecutive points steadily increasing or decreasing (Trend)
    """
    cl_i = limits["cl_i"]
    ucl_i = limits["ucl_i"]
    lcl_i = limits["lcl_i"]

    ucl_mr = limits["ucl_mr"]
    lcl_mr = limits["lcl_mr"]

    v_arr = values.to_numpy()
    n = len(v_arr)

    # I chart violations
    i_rule1 = []
    i_rule2 = []
    i_rule3 = []

    # Rule 1
    for idx, val in enumerate(v_arr):
        if pd.notna(val):
            if val > ucl_i or val < lcl_i:
                i_rule1.append(idx)

    # Rule 2: 7 on one side of CL
    for i in range(6, n):
        window = v_arr[i-6:i+1]
        if all(pd.notna(w) and w > cl_i for w in window) or all(pd.notna(w) and w < cl_i for w in window):
            i_rule2.append(i)

    # Rule 3: 6 consecutive increasing or decreasing
    for i in range(5, n):
        window = v_arr[i-5:i+1]
        if all(pd.notna(w) for w in window):
            diffs = np.diff(window)
            if all(d > 0 for d in diffs) or all(d < 0 for d in diffs):
                i_rule3.append(i)

    # MR chart violations (Rule 1)
    mr_arr = mr_values.to_numpy()
    mr_rule1 = []
    for idx, mr in enumerate(mr_arr):
        if pd.notna(mr):
            if mr > ucl_mr or mr < lcl_mr:
                mr_rule1.append(idx)

    return {
        "i_rule1": sorted(list(set(i_rule1))),
        "i_rule2": sorted(list(set(i_rule2))),
        "i_rule3": sorted(list(set(i_rule3))),
        "mr_rule1": sorted(list(set(mr_rule1))),
        "all_i_violations": sorted(list(set(i_rule1 + i_rule2 + i_rule3)))
    }


def analyze_imr(
    df: pd.DataFrame,
    col: str,
    spec_row: Optional[pd.Series] = None,
    baseline_n: int = 200
) -> Dict[str, Any]:
    """
    Full I-MR analysis for a continuous variable.
    """
    series = df[col].astype(float)
    mr_series = series.diff().abs()

    limits = calculate_imr_limits(series, baseline_n=baseline_n)
    violations = detect_imr_violations(series, mr_series, limits)

    # Check baseline stability
    n_base = limits["baseline_n"]
    base_violations = [idx for idx in violations["all_i_violations"] if idx < n_base]
    base_stability = "STABLE" if len(base_violations) == 0 else "UNSTABLE"
    base_stability_note = (
        f"Baseline ({n_base} pts) is stable with 0 out-of-control signals."
        if base_stability == "STABLE"
        else f"Baseline ({n_base} pts) contains {len(base_violations)} out-of-control points. Interpret limits with caution."
    )

    # Flag cases where the reference baseline covers only a subset of machines.
    # Preserve legacy pooled limits for historical comparison, but do not endorse
    # them for interpreting other machines; see equipment_analysis.py.
    # Equipment mix check
    machine_mix_warning = ""
    if "machine_id" in df.columns:
        m_counts = df.iloc[:n_base]["machine_id"].nunique()
        full_machines = df["machine_id"].dropna().nunique()
        if full_machines > 1 and m_counts == 1:
            machine_mix_warning = (
                f"WARNING: This pooled chart has {full_machines} machines but its "
                f"baseline uses only {df.iloc[0]['machine_id']}. "
                "These limits are NOT suitable for other machines; consult "
                "equipment_spc_summary.json for machine-specific provisional limits."
            )
        if m_counts > 1:
            machine_mix_warning = (
                f"Notice: Baseline combines {m_counts} machines. Separate baseline per machine is recommended if line characteristics differ."
            )

    result = {
        "column": col,
        "characteristic": spec_row["characteristic"] if spec_row is not None else col,
        "unit": spec_row["unit"] if spec_row is not None else "",
        "data_type": "continuous",
        "chart_type": "I-MR",
        "limits": limits,
        "spec_limits": {
            "LSL": spec_row["LSL"] if spec_row is not None else None,
            "TARGET": spec_row["TARGET"] if spec_row is not None else None,
            "USL": spec_row["USL"] if spec_row is not None else None,
        },
        "violations": violations,
        "violation_counts": {
            "i_rule1_count": len(violations["i_rule1"]),
            "i_rule2_count": len(violations["i_rule2"]),
            "i_rule3_count": len(violations["i_rule3"]),
            "all_i_count": len(violations["all_i_violations"]),
            "mr_rule1_count": len(violations["mr_rule1"])
        },
        "baseline_stability": base_stability,
        "baseline_stability_note": base_stability_note,
        "machine_mix_warning": machine_mix_warning,
        "total_points": len(series)
    }
    return result
