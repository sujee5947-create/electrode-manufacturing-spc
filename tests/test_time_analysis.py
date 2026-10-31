"""
Unit Tests for Time Analysis, Hotspot Detection, and Process Correlation
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta

from src.time_analysis import aggregate_by_time_interval, generate_date_hour_heatmap_matrix
from src.hotspot_detection import detect_ng_hotspots, HotspotConfig
from src.process_analysis import analyze_hotspot_process_correlation


def test_time_aggregation():
    # Build synthetic time dataset
    timestamps = [datetime(2026, 1, 1, 8, 0) + timedelta(minutes=5*i) for i in range(24)] # 2 hours
    df = pd.DataFrame({
        "timestamp": timestamps,
        "overall_judgment": ["OK"]*20 + ["NG"]*4,
        "machine_id": ["M1"]*24,
        "lot_id": ["LOT1"]*24,
        "line_speed_m_min": [30.0]*24,
        "drying_temperature_c": [120.0]*24,
        "roll_pressure": [15.0]*24,
        "uncoated_width_mm__judgment": ["OK"]*24
    })
    spec_df = pd.DataFrame([{
        "raw_column": "uncoated_width_mm",
        "characteristic": "무지부 폭",
        "unit": "mm",
        "data_type": "continuous",
        "LSL": 9.0,
        "TARGET": 10.0,
        "USL": 11.4,
        "enabled": "Y"
    }])

    int_df = aggregate_by_time_interval(df, spec_df, interval_minutes=60)
    assert len(int_df) == 2
    assert int_df.iloc[0]["total_count"] == 12
    assert int_df.iloc[1]["total_count"] == 12


def test_primary_defect_follows_actual_ng_column_not_korean_label():
    timestamps = [datetime(2026, 1, 6, 1, 0) + timedelta(minutes=5 * i) for i in range(12)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "overall_judgment": ["NG"] + ["OK"] * 11,
        "machine_id": ["M1"] * 12,
        "lot_id": ["LOT1"] * 12,
        "uncoated_width_mm__judgment": ["OK"] * 12,
        "coated_width_mm__judgment": ["NG_HIGH"] + ["OK"] * 11,
        "crater_count__judgment": ["OK"] * 12,
        "heat_wrinkle_count__judgment": ["OK"] * 12,
    })
    spec_df = pd.DataFrame([
        {"raw_column": "uncoated_width_mm", "characteristic": "코(팅) 폭"},
        {"raw_column": "coated_width_mm", "characteristic": "코(팅) 폭"},
        {"raw_column": "crater_count", "characteristic": "크레이터 수"},
        {"raw_column": "heat_wrinkle_count", "characteristic": "열주름 수"},
    ])

    int_df = aggregate_by_time_interval(df, spec_df, interval_minutes=60)
    assert int_df.iloc[0]["primary_defect_column"] == "coated_width_mm"
    assert int_df.iloc[0]["coated_width_mm__ng"] == 1
    assert int_df.iloc[0]["uncoated_width_mm__ng"] == 0


def test_primary_defect_prefers_heat_wrinkle_over_crater_when_counts_differ():
    timestamps = [datetime(2026, 1, 6, 13, 0) + timedelta(minutes=5 * i) for i in range(12)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "overall_judgment": ["NG", "NG"] + ["OK"] * 10,
        "machine_id": ["M1"] * 12,
        "lot_id": ["LOT1"] * 12,
        "uncoated_width_mm__judgment": ["OK"] * 12,
        "coated_width_mm__judgment": ["OK"] * 12,
        "crater_count__judgment": ["OK"] * 12,
        "heat_wrinkle_count__judgment": ["NG_HIGH", "NG_HIGH"] + ["OK"] * 10,
    })
    spec_df = pd.DataFrame([
        {"raw_column": "uncoated_width_mm", "characteristic": "무지부 폭"},
        {"raw_column": "coated_width_mm", "characteristic": "유지부(코팅) 폭"},
        {"raw_column": "crater_count", "characteristic": "크레이터 수"},
        {"raw_column": "heat_wrinkle_count", "characteristic": "열주름 수"},
    ])

    int_df = aggregate_by_time_interval(df, spec_df, interval_minutes=60)
    assert int_df.iloc[0]["primary_defect_column"] == "heat_wrinkle_count"
    assert int_df.iloc[0]["primary_defect"] == "열주름 수"
    assert int_df.iloc[0]["heat_wrinkle_count__ng"] == 2
    assert int_df.iloc[0]["crater_count__ng"] == 0


def test_hotspot_detection():
    # Construct interval DF with one high-NG window
    int_df = pd.DataFrame([
        {
            "period_label": "Window 1",
            "start_time": datetime(2026, 1, 1, 8, 0),
            "end_time": datetime(2026, 1, 1, 9, 0),
            "total_count": 12,
            "ng_count": 4, # 33.3%
            "ng_rate_pct": 33.33,
            "primary_defect": "크레이터",
            "machines": "M1",
            "lots": "LOT1"
        },
        {
            "period_label": "Window 2",
            "start_time": datetime(2026, 1, 1, 9, 0),
            "end_time": datetime(2026, 1, 1, 10, 0),
            "total_count": 12,
            "ng_count": 0,
            "ng_rate_pct": 0.0,
            "primary_defect": "None",
            "machines": "M1",
            "lots": "LOT1"
        },
        {
            "period_label": "Window 3",
            "start_time": datetime(2026, 1, 1, 10, 0),
            "end_time": datetime(2026, 1, 1, 10, 30),
            "total_count": 4, # Low sample size (<6)
            "ng_count": 3,
            "ng_rate_pct": 75.0,
            "primary_defect": "열주름",
            "machines": "M1",
            "lots": "LOT1"
        }
    ])

    res = detect_ng_hotspots(
        int_df,
        overall_ng_rate_pct=4.8,
        config=HotspotConfig(min_samples=6, severe_min_ng=3, severe_min_rate_pct=20.0, warning_min_ng=2)
    )

    # Window 1 is severe hotspot
    assert len(res["severe_hotspots"]) == 1
    assert res["severe_hotspots"][0]["period_label"] == "Window 1"
    # Window 3 is marked as insufficient data in all_ng_periods
    insufficient = [p for p in res["all_ng_periods"] if p["tier"] == "INSUFFICIENT_DATA"]
    assert len(insufficient) == 1


def test_process_correlation_statements():
    timestamps = [datetime(2026, 1, 1, 8, 0) + timedelta(minutes=5*i) for i in range(36)] # 3 hours
    df = pd.DataFrame({
        "timestamp": timestamps,
        "overall_judgment": ["OK"]*12 + ["NG"]*4 + ["OK"]*20,
        "line_speed_m_min": [30.0]*12 + [35.0]*12 + [30.0]*12,
        "drying_temperature_c": [120.0]*36,
        "roll_pressure": [15.0]*36
    })

    hotspot = {
        "period_label": "2026-01-01 09:00 ~ 10:00",
        "start_time": datetime(2026, 1, 1, 9, 0),
        "end_time": datetime(2026, 1, 1, 10, 0),
        "ng_count": 4,
        "ng_rate_pct": 33.3,
        "primary_defect": "코팅 두께"
    }

    res = analyze_hotspot_process_correlation(df, hotspot, buffer_minutes=30)
    statements = res["statements"]

    assert len(statements["confirmed_fact"]) > 10
    assert len(statements["associated_change"]) > 10
    assert "추가 검토" in statements["requires_investigation"]
