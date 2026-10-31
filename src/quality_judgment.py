"""
Quality Judgment Module
Evaluates continuous and count quality characteristics against SPEC limits.
Produces row-level evaluations and comprehensive aggregations.
"""

from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np


def judge_value(val: Any, data_type: str, lsl: float, usl: float) -> str:
    """
    Evaluates a single value against specification limits.
    Returns: 'OK', 'NG_LOW', 'NG_HIGH', or 'INVALID'
    """
    if pd.isna(val):
        return "INVALID"

    try:
        num_val = float(val)
    except (ValueError, TypeError):
        return "INVALID"

    if np.isnan(num_val) or np.isinf(num_val):
        return "INVALID"

    if data_type == "count":
        # Counts must be finite, non-negative integers regardless of USL.
        if num_val < 0 or not num_val.is_integer():
            return "INVALID"
        if not pd.isna(usl) and num_val > usl:
            return "NG_HIGH"
        return "OK"
    else:
        # Continuous characteristic
        if not pd.isna(lsl) and num_val < lsl:
            return "NG_LOW"
        if not pd.isna(usl) and num_val > usl:
            return "NG_HIGH"
        return "OK"


def evaluate_quality(raw_df: pd.DataFrame, spec_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Performs quality judgment for each characteristic and overall row judgment.
    Returns:
        evaluated_df: DataFrame with judgment columns added
        summary_stats: Comprehensive dictionary with overall, characteristic-level,
                       lot-level, and machine-level statistics.
    """
    df = raw_df.copy()
    char_cols = []
    
    # Evaluate each characteristic
    for _, spec_row in spec_df.iterrows():
        col = spec_row["raw_column"]
        data_type = spec_row.get("data_type", "continuous")
        lsl = spec_row.get("LSL")
        usl = spec_row.get("USL")
        
        judge_col = f"{col}__judgment"
        char_cols.append(judge_col)
        
        df[judge_col] = df[col].apply(lambda v: judge_value(v, data_type, lsl, usl))

    # Overall row judgment
    def get_overall_judgment(row) -> str:
        judgments = [row[c] for c in char_cols]
        if any(j in ("NG_LOW", "NG_HIGH") for j in judgments):
            return "NG"
        if any(j == "INVALID" for j in judgments):
            return "INVALID"
        return "OK"

    df["overall_judgment"] = df.apply(get_overall_judgment, axis=1)

    # Count defects per row
    def count_row_ng(row) -> int:
        return sum(1 for c in char_cols if row[c] in ("NG_LOW", "NG_HIGH"))

    df["ng_count_per_row"] = df.apply(count_row_ng, axis=1)

    # Aggregations
    total_count = len(df)
    ok_count = int((df["overall_judgment"] == "OK").sum())
    ng_count = int((df["overall_judgment"] == "NG").sum())
    invalid_count = int((df["overall_judgment"] == "INVALID").sum())
    ng_rate = (ng_count / total_count * 100) if total_count > 0 else 0.0
    ok_rate = (ok_count / total_count * 100) if total_count > 0 else 0.0

    multi_defect_count = int((df["ng_count_per_row"] >= 2).sum())

    # Characteristic-level statistics
    char_stats = []
    for _, spec_row in spec_df.iterrows():
        col = spec_row["raw_column"]
        name = spec_row.get("characteristic", col)
        unit = spec_row.get("unit", "")
        data_type = spec_row.get("data_type", "continuous")
        lsl = spec_row.get("LSL")
        target = spec_row.get("TARGET")
        usl = spec_row.get("USL")
        
        judge_col = f"{col}__judgment"
        series_j = df[judge_col]
        
        c_ng_low = int((series_j == "NG_LOW").sum())
        c_ng_high = int((series_j == "NG_HIGH").sum())
        c_ng = c_ng_low + c_ng_high
        c_ok = int((series_j == "OK").sum())
        c_invalid = int((series_j == "INVALID").sum())
        c_ng_rate = (c_ng / total_count * 100) if total_count > 0 else 0.0

        char_stats.append({
            "raw_column": col,
            "characteristic": name,
            "unit": unit,
            "data_type": data_type,
            "LSL": lsl,
            "TARGET": target,
            "USL": usl,
            "total": total_count,
            "ok_count": c_ok,
            "ng_count": c_ng,
            "ng_rate_pct": round(c_ng_rate, 3),
            "ng_low_count": c_ng_low,
            "ng_high_count": c_ng_high,
            "invalid_count": c_invalid
        })

    char_stats_df = pd.DataFrame(char_stats).sort_values("ng_count", ascending=False)

    # LOT-level statistics
    lot_stats = []
    if "lot_id" in df.columns:
        for lot, group in df.groupby("lot_id"):
            l_total = len(group)
            l_ng = int((group["overall_judgment"] == "NG").sum())
            l_ok = int((group["overall_judgment"] == "OK").sum())
            lot_stats.append({
                "lot_id": lot,
                "total": l_total,
                "ok_count": l_ok,
                "ng_count": l_ng,
                "ng_rate_pct": round(l_ng / l_total * 100, 2) if l_total > 0 else 0.0
            })
    lot_stats_df = pd.DataFrame(lot_stats)

    # Machine-level statistics
    machine_stats = []
    if "machine_id" in df.columns:
        for m_id, group in df.groupby("machine_id"):
            m_total = len(group)
            m_ng = int((group["overall_judgment"] == "NG").sum())
            m_ok = int((group["overall_judgment"] == "OK").sum())
            machine_stats.append({
                "machine_id": m_id,
                "total": m_total,
                "ok_count": m_ok,
                "ng_count": m_ng,
                "ng_rate_pct": round(m_ng / m_total * 100, 2) if m_total > 0 else 0.0
            })
    machine_stats_df = pd.DataFrame(machine_stats)

    summary_stats = {
        "total_count": total_count,
        "ok_count": ok_count,
        "ng_count": ng_count,
        "invalid_count": invalid_count,
        "ng_rate_pct": round(ng_rate, 3),
        "ok_rate_pct": round(ok_rate, 3),
        "multi_defect_rows": multi_defect_count,
        "char_stats": char_stats_df.to_dict(orient="records"),
        "lot_stats": lot_stats_df.to_dict(orient="records"),
        "machine_stats": machine_stats_df.to_dict(orient="records")
    }

    return df, summary_stats
