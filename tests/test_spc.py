"""
Unit Tests for SPC Analysis & Capability Modules
"""

import pytest
import pandas as pd
import numpy as np

from src.spc_analysis import calculate_imr_limits, detect_imr_violations, analyze_imr
from src.vision_analysis import analyze_vision_defects
from src.capability_analysis import calculate_capability


def test_calculate_imr_limits():
    # Synthetic series
    data = pd.Series([10.0, 12.0, 11.0, 13.0, 10.0] * 40) # 200 points
    limits = calculate_imr_limits(data, baseline_n=200)

    assert "cl_i" in limits
    assert "ucl_i" in limits
    assert "lcl_i" in limits
    assert "cl_mr" in limits
    assert "ucl_mr" in limits
    assert "lcl_mr" in limits

    # Formulas check
    cl = limits["cl_i"]
    mr_bar = limits["mr_bar"]
    assert pytest.approx(limits["ucl_i"], 0.01) == cl + 2.66 * mr_bar
    assert pytest.approx(limits["lcl_i"], 0.01) == cl - 2.66 * mr_bar
    assert pytest.approx(limits["ucl_mr"], 0.01) == 3.267 * mr_bar
    assert limits["lcl_mr"] == 0.0


def test_detect_imr_violations():
    # 10 normal points + 1 high outlier
    series = pd.Series([10.0]*10 + [50.0])
    mr_series = series.diff().abs()
    limits = {
        "cl_i": 10.0,
        "ucl_i": 15.0,
        "lcl_i": 5.0,
        "cl_mr": 1.0,
        "ucl_mr": 3.0,
        "lcl_mr": 0.0
    }
    violations = detect_imr_violations(series, mr_series, limits)
    assert 10 in violations["i_rule1"]


def test_vision_cchart():
    df = pd.DataFrame({"crater_count": [0, 1, 0, 2, 0, 10, 0, 1]}) # 10 is outlier
    res = analyze_vision_defects(df, "crater_count")

    assert res["chart_type"] == "C-Chart"
    assert res["cl"] > 0
    assert res["ucl"] > res["cl"]
    assert res["lcl"] >= 0
    assert len(res["ooc_indices"]) > 0


def test_capability_calculation():
    spec_row = pd.Series({
        "raw_column": "coating_thickness_um",
        "characteristic": "코팅 두께",
        "unit": "um",
        "data_type": "continuous",
        "LSL": 98.0,
        "TARGET": 100.0,
        "USL": 102.5
    })
    # Controlled data with mean=100.0, std ~ 0.5
    np.random.seed(42)
    vals = np.random.normal(loc=100.0, scale=0.5, size=200)
    df = pd.DataFrame({"coating_thickness_um": vals})

    cap = calculate_capability(df, "coating_thickness_um", spec_row, baseline_n=200)
    assert cap["applicable"] is True
    assert cap["cp"] is not None
    assert cap["cpk"] is not None
    assert cap["cp"] > 1.0
