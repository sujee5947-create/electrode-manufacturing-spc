"""Equipment-specific Phase I I-MR and process capability diagnostics.

A moving range must never bridge equipment changes.  This module calculates each
machine on its own chronological sequence, so one machine's baseline is never
silently applied to a different machine.  The initial baseline is provisional:
a true Phase I baseline needs engineering stability validation.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
from src.spc_analysis import analyze_imr
from src.capability_analysis import calculate_capability


def analyze_by_equipment(df: pd.DataFrame, spec_df: pd.DataFrame, baseline_n: int = 200) -> dict[str, Any]:
    if "machine_id" not in df.columns:
        return {"method_note": "설비 식별자 부재: 설비별 SPC를 수행하지 않았습니다.", "equipment": {}}
    if baseline_n < 2:
        raise ValueError("baseline_n must be at least 2")

    results = {}
    for machine, group in df.groupby("machine_id", sort=True, dropna=False):
        group = group.sort_values("timestamp").reset_index(drop=True)
        unit = {"sample_count": int(len(group)), "spc": {}, "capability": {}}
        for _, spec_row in spec_df.iterrows():
            if spec_row.get("chart_type") != "I-MR" or spec_row.get("data_type") != "continuous":
                continue
            col = spec_row["raw_column"]
            if len(group[col].dropna()) < 2:
                continue
            spc = analyze_imr(group, col, spec_row, baseline_n=baseline_n)
            capability = calculate_capability(
                group, col, spec_row, baseline_n=baseline_n,
                has_spc_violations=spc["violation_counts"]["all_i_count"] > 0
            )
            unit["spc"][col] = spc
            unit["capability"][col] = capability
        results[str(machine)] = unit

    return {
        "method_note": (
            "설비별 시간순 최초 baseline_n개 데이터로 I-MR 한계를 잠정 산출했습니다. "
            "이동범위는 설비 경계를 연결하지 않습니다. 관리 이탈이 있는 Phase I 기준은 "
            "공식 관리한계가 아니라 검토용이며, 원인 분석 및 안정 구간 재선정이 필요합니다. "
            "Cp/Cpk 역시 안정성 검증 전에는 참고값입니다."
        ),
        "baseline_n": baseline_n,
        "equipment": results
    }


def capability_comparison_table(equipment_result: dict) -> pd.DataFrame:
    records = []
    for machine, unit in equipment_result.get("equipment", {}).items():
        for col, cap in unit.get("capability", {}).items():
            spc = unit["spc"][col]
            records.append({
                "machine_id": machine,
                "raw_column": col,
                "characteristic": cap["characteristic"],
                "sample_count": cap["sample_size"],
                "Cp": cap["cp"], "Cpk": cap["cpk"],
                "Pp": cap["pp"], "Ppk": cap["ppk"],
                "Cpk_baseline_reference": cap["cpk_baseline_ref"],
                "baseline_stability": spc["baseline_stability"],
                "i_violations": spc["violation_counts"]["all_i_count"],
                "mr_violations": spc["violation_counts"]["mr_rule1_count"],
                "interpretation": "PROVISIONAL - verify Phase I stability"
            })
    return pd.DataFrame.from_records(records)
