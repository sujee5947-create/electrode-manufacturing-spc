"""
Process Capability Analysis Module
Calculates Cp, Cpk, Pp, Ppk, overall/within variation, and out-of-spec rates
for continuous quality characteristics.
Provides both Full-dataset within-variation (MR_bar / d2) and Baseline-within-variation
with 100% transparent formula documentation.
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


def calculate_capability(
    df: pd.DataFrame,
    col: str,
    spec_row: pd.Series,
    baseline_n: int = 200,
    has_spc_violations: bool = False
) -> Dict[str, Any]:
    """
    Calculates process capability indices for a continuous variable.
    Uses full-dataset MR_bar / d2 as standard within-process variation estimator
    (aligned with global Six Sigma / SPC audit standards), while recording baseline metrics.
    """
    data_type = spec_row.get("data_type", "continuous")
    if data_type == "count":
        return {
            "column": col,
            "characteristic": spec_row.get("characteristic", col),
            "applicable": False,
            "reason": "Cp/Cpk is not applicable to attribute/count defect data."
        }

    series = pd.to_numeric(df[col], errors="coerce").dropna().astype(float)
    n = len(series)
    if n < 2:
        return {
            "column": col,
            "characteristic": spec_row.get("characteristic", col),
            "applicable": False,
            "reason": "Insufficient sample size (N < 2)."
        }

    lsl = spec_row.get("LSL")
    usl = spec_row.get("USL")
    target = spec_row.get("TARGET")

    mean_val = float(series.mean())
    std_overall = float(series.std(ddof=1))

    # 1. Full dataset within-process variation (variable N, MR_bar / 1.128)
    if "machine_id" in df.columns:
        # Global capability is descriptive. Avoid across-machine moving ranges.
        mr_full = df.assign(_measurement=pd.to_numeric(df[col], errors="coerce"))\
            .groupby("machine_id", sort=False, dropna=False)["_measurement"]\
            .diff().abs().dropna()
    else:
        mr_full = series.diff().abs().dropna()
    mr_bar_full = float(mr_full.mean()) if len(mr_full) > 0 else 0.0
    sigma_within_full = mr_bar_full / 1.128 if mr_bar_full > 0 else std_overall

    # 2. Baseline within-subgroup variation (N=200, Baseline MR_bar / 1.128)
    n_base = min(n, baseline_n)
    if "machine_id" in df.columns:
        mr_base = df.iloc[:n_base].assign(_measurement=pd.to_numeric(df.iloc[:n_base][col], errors="coerce"))\
            .groupby("machine_id", sort=False, dropna=False)["_measurement"]\
            .diff().abs().dropna()
    else:
        mr_base = series.iloc[:n_base].diff().abs().dropna()
    mr_bar_base = float(mr_base.mean()) if len(mr_base) > 0 else 0.0
    sigma_within_base = mr_bar_base / 1.128 if mr_bar_base > 0 else std_overall

    # We adopt the full dataset MR_bar / d2 as the primary within-subgroup estimator
    sigma_within = sigma_within_full

    # Potential capability (Cp, Pp)
    cp = None
    pp = None
    if not pd.isna(lsl) and not pd.isna(usl) and (usl > lsl):
        if sigma_within > 0:
            cp = (usl - lsl) / (6.0 * sigma_within)
        if std_overall > 0:
            pp = (usl - lsl) / (6.0 * std_overall)

    # Actual capability (Cpk, Ppk)
    cpu, cpl, cpk = None, None, None
    ppu, ppl, ppk = None, None, None

    if sigma_within > 0:
        if not pd.isna(usl):
            cpu = (usl - mean_val) / (3.0 * sigma_within)
        if not pd.isna(lsl):
            cpl = (mean_val - lsl) / (3.0 * sigma_within)

        if cpu is not None and cpl is not None:
            cpk = min(cpu, cpl)
        elif cpu is not None:
            cpk = cpu
        elif cpl is not None:
            cpk = cpl

    if std_overall > 0:
        if not pd.isna(usl):
            ppu = (usl - mean_val) / (3.0 * std_overall)
        if not pd.isna(lsl):
            ppl = (mean_val - lsl) / (3.0 * std_overall)

        if ppu is not None and ppl is not None:
            ppk = min(ppu, ppl)
        elif ppu is not None:
            ppk = ppu
        elif ppl is not None:
            ppk = ppl

    # Baseline-based Cpk for reference
    cpk_baseline = None
    if sigma_within_base > 0:
        cpu_b = (usl - mean_val) / (3.0 * sigma_within_base) if not pd.isna(usl) else None
        cpl_b = (mean_val - lsl) / (3.0 * sigma_within_base) if not pd.isna(lsl) else None
        if cpu_b is not None and cpl_b is not None:
            cpk_baseline = min(cpu_b, cpl_b)

    # Out of spec count and rate
    out_of_spec_low = int((series < lsl).sum()) if not pd.isna(lsl) else 0
    out_of_spec_high = int((series > usl).sum()) if not pd.isna(usl) else 0
    out_of_spec_total = out_of_spec_low + out_of_spec_high
    out_of_spec_rate_pct = (out_of_spec_total / n * 100) if n > 0 else 0.0

    # Process stability note
    stability_note = ""
    if has_spc_violations:
        stability_note = (
            "주의: SPC 모니터링에서 관리 이탈(Out-of-Control) 신호가 감지되었습니다. "
            "공정이 완전한 통계적 관리 상태가 아니므로 Cpk 해석 시 주의가 필요합니다."
        )
    else:
        stability_note = "공정이 통계적으로 안정적인 관리 상태를 나타내고 있습니다."

    # Benchmark interpretation
    capability_level = "Excellent"
    if cpk is not None:
        if cpk < 1.0:
            capability_level = "Inadequate (Cpk < 1.00)"
        elif cpk < 1.33:
            capability_level = "Marginal (1.00 <= Cpk < 1.33)"
        elif cpk < 1.67:
            capability_level = "Capable (1.33 <= Cpk < 1.67)"
        else:
            capability_level = "Excellent (Cpk >= 1.67)"

    return {
        "column": col,
        "characteristic": spec_row.get("characteristic", col),
        "unit": spec_row.get("unit", ""),
        "applicable": True,
        "sample_size": n,
        "sample_range": f"전체 데이터셋 기준 (N={n}, MR_bar/d2 기준)",
        "mean": round(mean_val, 4),
        "std_overall": round(std_overall, 4),
        "sigma_within": round(sigma_within, 4),
        "mr_bar_full": round(mr_bar_full, 4),
        "mr_bar_baseline": round(mr_bar_base, 4),
        "sigma_within_baseline": round(sigma_within_base, 4),
        "lsl": lsl,
        "target": target,
        "usl": usl,
        "cp": round(cp, 3) if cp is not None else None,
        "cpk": round(cpk, 3) if cpk is not None else None,
        "pp": round(pp, 3) if pp is not None else None,
        "ppk": round(ppk, 3) if ppk is not None else None,
        "cpu": round(cpu, 3) if cpu is not None else None,
        "cpl": round(cpl, 3) if cpl is not None else None,
        "cpk_baseline_ref": round(cpk_baseline, 3) if cpk_baseline is not None else None,
        "out_of_spec_count": out_of_spec_total,
        "out_of_spec_rate_pct": round(out_of_spec_rate_pct, 3),
        "out_of_spec_low": out_of_spec_low,
        "out_of_spec_high": out_of_spec_high,
        "stability_note": stability_note,
        "capability_level": capability_level,
        "calculation_formula": "Cpk = min((USL-Mean)/(3*sigma_w), (Mean-LSL)/(3*sigma_w)), sigma_w = MR_bar / 1.128"
    }


def analyze_all_capabilities(
    df: pd.DataFrame,
    spec_df: pd.DataFrame,
    spc_results: Dict[str, Any],
    baseline_n: int = 200
) -> Dict[str, Dict[str, Any]]:
    """
    Computes capability for all continuous characteristics in SPEC.
    """
    cap_results = {}
    for _, spec_row in spec_df.iterrows():
        col = spec_row["raw_column"]
        if spec_row.get("data_type") == "continuous":
            spc_info = spc_results.get(col, {})
            has_viol = spc_info.get("violation_counts", {}).get("all_i_count", 0) > 0
            cap_results[col] = calculate_capability(
                df, col, spec_row,
                baseline_n=baseline_n,
                has_spc_violations=has_viol
            )
    return cap_results
