"""
Time Analysis Module
Aggregates quality metrics across configurable time intervals (30m, 1h, 2h),
LOTs, machines, and generates cross-tabulations (Date x Hour) for heatmaps.
Ensures 100% standardized English column identifiers and UTF-8-sig encoding.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd
import numpy as np


def aggregate_by_time_interval(
    df: pd.DataFrame,
    spec_df: pd.DataFrame,
    interval_minutes: int = 60,
    process_cols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Aggregates evaluated quality data by fixed time interval (in minutes).
    Uses consistent snake_case English column identifiers to prevent encoding corruption.
    """
    if process_cols is None:
        process_cols = ["line_speed_m_min", "drying_temperature_c", "roll_pressure"]

    work_df = df.copy()
    work_df["timestamp"] = pd.to_datetime(work_df["timestamp"])

    # Floor timestamp to interval
    freq = f"{interval_minutes}min" if interval_minutes < 60 else f"{interval_minutes // 60}h" if interval_minutes % 60 == 0 else f"{interval_minutes}T"
    work_df["time_bucket"] = work_df["timestamp"].dt.floor(freq)

    # Standardized English defect columns: {raw_col}__ng
    char_map = {r["raw_column"]: r["characteristic"] for _, r in spec_df.iterrows()}

    records = []
    prev_proc_means = {p: None for p in process_cols}

    for bucket, group in work_df.groupby("time_bucket", sort=True):
        total = len(group)
        ok_count = int((group["overall_judgment"] == "OK").sum())
        ng_count = int((group["overall_judgment"] == "NG").sum())
        ng_rate = (ng_count / total * 100) if total > 0 else 0.0

        # Characteristic defect breakdown keyed by English raw_column (never by Korean label).
        # Korean names can collide (e.g. "코(팅) 폭"), so primary defect must follow NG counts per column.
        char_ng_counts = {}
        raw_ng_counts = {}
        spec_order = {}
        for spec_idx, (raw_col, char_kor_name) in enumerate(char_map.items()):
            judge_col = f"{raw_col}__judgment"
            cnt = int((group[judge_col].isin(["NG_LOW", "NG_HIGH"])).sum()) if judge_col in group.columns else 0
            char_ng_counts[f"{raw_col}__ng"] = cnt
            raw_ng_counts[raw_col] = cnt
            spec_order[raw_col] = spec_idx

        ng_columns = [col for col, cnt in raw_ng_counts.items() if cnt > 0]
        if ng_columns:
            primary_col = sorted(
                ng_columns,
                key=lambda col: (-raw_ng_counts[col], spec_order[col])
            )[0]
            primary_defect = char_map.get(primary_col, primary_col)
            primary_defect_column = primary_col
        else:
            primary_defect = "None"
            primary_defect_column = ""

        # Unique machines and lots
        machines = sorted(group["machine_id"].dropna().unique().tolist()) if "machine_id" in group.columns else []
        lots = sorted(group["lot_id"].dropna().unique().tolist()) if "lot_id" in group.columns else []

        # Process condition averages and deltas
        proc_means = {}
        proc_deltas = {}
        for p in process_cols:
            if p in group.columns:
                m_val = float(group[p].mean())
                proc_means[p] = round(m_val, 2)
                if prev_proc_means[p] is not None:
                    delta = round(m_val - prev_proc_means[p], 2)
                    proc_deltas[f"{p}__delta"] = delta
                else:
                    proc_deltas[f"{p}__delta"] = 0.0
                prev_proc_means[p] = m_val

        start_time_str = bucket.strftime("%Y-%m-%d %H:%M")
        end_time = bucket + pd.Timedelta(minutes=interval_minutes)
        end_time_str = end_time.strftime("%H:%M")

        row_dict = {
            "time_bucket": bucket,
            "period_label": f"{start_time_str} ~ {end_time_str}",
            "start_time": bucket,
            "end_time": end_time,
            "total_count": total,
            "ok_count": ok_count,
            "ng_count": ng_count,
            "ng_rate_pct": round(ng_rate, 2),
            "primary_defect": primary_defect,
            "primary_defect_column": primary_defect_column,
            "machines": ", ".join(machines),
            "lots": ", ".join(lots),
            **char_ng_counts,
            **proc_means,
            **proc_deltas
        }
        records.append(row_dict)

    res_df = pd.DataFrame(records)
    return res_df


def generate_date_hour_heatmap_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates a Date x Hour matrix of NG counts for heatmap visualization.
    """
    work_df = df.copy()
    work_df["timestamp"] = pd.to_datetime(work_df["timestamp"])
    work_df["date"] = work_df["timestamp"].dt.strftime("%Y-%m-%d")
    work_df["hour"] = work_df["timestamp"].dt.hour

    # Group by date and hour safely
    records = []
    for (d, h), g in work_df.groupby(["date", "hour"], sort=True):
        total = len(g)
        ng_cnt = int((g["overall_judgment"] == "NG").sum())
        ng_rate = (ng_cnt / total * 100) if total > 0 else 0.0
        records.append({"date": d, "hour": h, "total": total, "ng_count": ng_cnt, "ng_rate_pct": ng_rate})
    grouped = pd.DataFrame(records)

    # Pivot table for NG count
    pivot_ng = grouped.pivot(index="date", columns="hour", values="ng_count").fillna(0).astype(int)
    
    # Ensure all observed hours are represented
    all_hours = list(range(int(grouped["hour"].min()), int(grouped["hour"].max()) + 1))
    pivot_ng = pivot_ng.reindex(columns=all_hours, fill_value=0)

    return pivot_ng
