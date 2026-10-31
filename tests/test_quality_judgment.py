"""
Unit Tests for Quality Judgment Module
"""

import pytest
import pandas as pd
import numpy as np

from src.quality_judgment import judge_value, evaluate_quality
from src.data_loader import load_spec, load_raw_data


def test_judge_value_continuous():
    # Boundary tests
    assert judge_value(10.0, "continuous", 9.0, 11.4) == "OK"
    assert judge_value(9.0, "continuous", 9.0, 11.4) == "OK"
    assert judge_value(11.4, "continuous", 9.0, 11.4) == "OK"

    # Out of spec
    assert judge_value(8.99, "continuous", 9.0, 11.4) == "NG_LOW"
    assert judge_value(11.41, "continuous", 9.0, 11.4) == "NG_HIGH"

    # Invalid / Missing
    assert judge_value(None, "continuous", 9.0, 11.4) == "INVALID"
    assert judge_value(np.nan, "continuous", 9.0, 11.4) == "INVALID"
    assert judge_value("bad_str", "continuous", 9.0, 11.4) == "INVALID"


def test_judge_value_count():
    # Upper spec = 4.0
    assert judge_value(0, "count", None, 4.0) == "OK"
    assert judge_value(4, "count", None, 4.0) == "OK"
    assert judge_value(5, "count", None, 4.0) == "NG_HIGH"
    assert judge_value(-1, "count", None, 4.0) == "INVALID"


def test_actual_dataset_judgment():
    spec_df = load_spec("raw data/Electrode_Quality_SPEC.xlsx")
    raw_df = load_raw_data("raw data/Electrode_Quality_Raw_Data.csv")

    eval_df, summary = evaluate_quality(raw_df, spec_df)

    # Reference Snapshot Assertions
    assert summary["total_count"] == 1000
    assert summary["ok_count"] == 952
    assert summary["ng_count"] == 48
    assert summary["invalid_count"] == 0
    assert summary["multi_defect_rows"] == 2

    # Characteristic defect breakdown check
    char_ng_dict = {c["raw_column"]: c["ng_count"] for c in summary["char_stats"]}
    assert char_ng_dict["uncoated_width_mm"] == 6
    assert char_ng_dict["coated_width_mm"] == 2
    assert char_ng_dict["uncoated_gap_mm"] == 2
    assert char_ng_dict["coating_thickness_um"] == 10
    assert char_ng_dict["coating_weight_mg_cm2"] == 7
    assert char_ng_dict["crater_count"] == 11
    assert char_ng_dict["heat_wrinkle_count"] == 12

    # Sum of char defects is 50, but total NG rows is 48 due to 2 multi-defect rows
    total_char_defects = sum(char_ng_dict.values())
    assert total_char_defects == 50
    assert summary["ng_count"] == 48
