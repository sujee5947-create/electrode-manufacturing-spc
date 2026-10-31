"""
Vision Defect Analysis Module
Implements C-chart (constant inspection area) and U-chart (variable inspection area)
for vision inspection defect counts.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


def analyze_vision_defects(
    df: pd.DataFrame,
    col: str,
    spec_row: Optional[pd.Series] = None,
    area_col: str = "inspection_area_m2"
) -> Dict[str, Any]:
    """
    Performs attribute control chart analysis (C-chart or U-chart).
    """
    series = df[col].astype(float)
    total_points = len(series)

    has_area = area_col in df.columns and not df[area_col].isna().all()
    is_constant_area = True

    if has_area:
        areas = df[area_col].astype(float)
        # Check if area variation exists
        if areas.nunique() > 1:
            is_constant_area = False
    else:
        areas = pd.Series([1.0] * total_points)

    c_vals = series.to_numpy()
    a_vals = areas.to_numpy()

    requested_chart = str(spec_row.get('chart_type', 'C')) if spec_row is not None else ('C' if is_constant_area else 'U')
    if requested_chart == 'U' and not has_area:
        raise ValueError(f'U-chart for {col} requires positive inspection_area_m2 in the Raw Data.')
    if requested_chart == 'C' and not is_constant_area:
        raise ValueError(f'C-chart for {col} cannot be used with variable inspection area. Set SPEC chart_type to U.')
    if requested_chart == 'C':
        # C-Chart
        cl = float(np.mean(c_vals))
        sigma = np.sqrt(cl)
        ucl = cl + 3.0 * sigma
        lcl = max(0.0, cl - 3.0 * sigma)

        ucl_arr = np.full(total_points, ucl)
        lcl_arr = np.full(total_points, lcl)
        cl_arr = np.full(total_points, cl)
        rate_arr = c_vals
        chart_type = "C-Chart"
    else:
        # U-Chart: always normalize counts by inspection exposure, including constant areas.
        if (areas.isna() | ~np.isfinite(areas) | (areas <= 0)).any():
            raise ValueError(f'U-chart for {col} requires finite positive inspection_area_m2.')
        total_c = np.sum(c_vals)
        total_a = np.sum(a_vals)
        u_bar = float(total_c / total_a) if total_a > 0 else 0.0

        cl = u_bar
        rate_arr = c_vals / a_vals
        ucl_arr = u_bar + 3.0 * np.sqrt(u_bar / a_vals)
        lcl_arr = np.maximum(0.0, u_bar - 3.0 * np.sqrt(u_bar / a_vals))
        cl_arr = np.full(total_points, cl)
        chart_type = "U-Chart"

    # Diagnostic: for a simple Poisson count model, sample variance should be close to mean.
    sample_variance = float(series.var(ddof=1)) if total_points > 1 else 0.0
    mean_count = float(series.mean()) if total_points else 0.0
    dispersion_ratio = sample_variance / mean_count if mean_count > 0 else None
    dispersion_note = (
        "과산포 가능성: 표본분산/평균 > 1.2, C/U-chart 포아송 가정 확인 필요. "
        "설비/시간대/검사 면적 차이 및 안정 구간을 검토하세요."
        if dispersion_ratio is not None and dispersion_ratio > 1.2 else
        "과산포 비율만으로 분포 적합성을 확정할 수 없음; 관리도 해석 시 안정성과 독립성 검토 필요."
    )

    # Out of control detection (Rule 1: exceed UCL/LCL)
    ooc_indices = []
    for i in range(total_points):
        if rate_arr[i] > ucl_arr[i] or rate_arr[i] < lcl_arr[i]:
            ooc_indices.append(i)

    # Consecutive high runs (7 consecutive above CL)
    run_indices = []
    for i in range(6, total_points):
        window = rate_arr[i-6:i+1]
        if all(w > cl for w in window):
            run_indices.append(i)

    usl = spec_row["USL"] if spec_row is not None else None

    # Compare SPC OOC vs SPEC NG
    spec_ng_indices = [i for i, v in enumerate(c_vals) if usl is not None and v > usl]

    return {
        "column": col,
        "characteristic": spec_row["characteristic"] if spec_row is not None else col,
        "unit": spec_row["unit"] if spec_row is not None else "count",
        "chart_type": chart_type,
        "data_type": "count",
        "cl": round(cl, 4),
        "ucl": round(float(np.mean(ucl_arr)), 4),
        "lcl": round(float(np.mean(lcl_arr)), 4),
        "ucl_array": ucl_arr.tolist(),
        "lcl_array": lcl_arr.tolist(),
        "rate_array": rate_arr.tolist(),
        "spec_limit_usl": usl,
        "ooc_indices": ooc_indices,
        "run_indices": run_indices,
        "spec_ng_indices": spec_ng_indices,
        "count_variance": round(sample_variance, 4),
        "variance_to_mean_ratio": round(dispersion_ratio, 4) if dispersion_ratio is not None else None,
        "poisson_assumption_note": dispersion_note,
        "total_points": total_points,
        "total_defects": int(np.sum(c_vals)),
        "avg_defect_rate": round(float(np.mean(rate_arr)), 4)
    }
