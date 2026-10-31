"""Regressions for independent Oct 2026 raw-vs-result audit findings."""
import pandas as pd
from src.hotspot_detection import detect_ng_hotspots
from src.quality_judgment import judge_value
from src.equipment_analysis import analyze_by_equipment
from src.process_analysis import analyze_hotspot_process_correlation
from src.vision_analysis import analyze_vision_defects


def test_zero_ng_interval_with_insufficient_samples_is_not_clean():
    rows = pd.DataFrame([
        {"period_label": "short", "start_time": pd.Timestamp("2026-01-01 00:00"),
         "end_time": pd.Timestamp("2026-01-01 01:00"), "total_count": 4,
         "ng_count": 0, "ng_rate_pct": 0., "primary_defect": "", "machines": "M1", "lots": "L1"},
        {"period_label": "clean", "start_time": pd.Timestamp("2026-01-01 01:00"),
         "end_time": pd.Timestamp("2026-01-01 02:00"), "total_count": 12,
         "ng_count": 0, "ng_rate_pct": 0., "primary_defect": "", "machines": "M1", "lots": "L1"},
    ])
    result = detect_ng_hotspots(rows, 4.8)
    assert result["summary_counts"]["insufficient_count"] == 1
    assert result["summary_counts"]["clean_intervals"] == 1
    assert result["summary_counts"]["ng_active_intervals"] == 0
    assert result["insufficient_periods"][0]["period_label"] == "short"


def test_count_rejects_negative_noninteger_and_nonnumeric():
    for v in [-1, -0.2, 1.5, "bad", float("nan")]:
        assert judge_value(v, "count", None, 3) == "INVALID"
    assert judge_value(0, "count", None, 3) == "OK"
    assert judge_value(4, "count", None, 3) == "NG_HIGH"


def test_grouped_mr_does_not_bridge_machine_switch():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=10, freq="5min"),
        "machine_id": ["A", "B"] * 5,
        "width": [10, 100, 10.2, 100.2, 10.4, 100.4, 10.6, 100.6, 10.8, 100.8],
    })
    spec = pd.DataFrame([{
        "raw_column": "width", "characteristic": "width", "unit": "mm",
        "chart_type": "I-MR", "data_type": "continuous", "LSL": 0,
        "TARGET": 50, "USL": 110,
    }])
    result = analyze_by_equipment(df, spec, baseline_n=3)
    assert list(result["equipment"]) == ["A", "B"]
    for machine in ("A", "B"):
        cap = result["equipment"][machine]["capability"]["width"]
        assert abs(cap["mr_bar_full"] - 0.2) < 1e-6
        assert cap["sample_size"] == 5


def test_process_statement_does_not_claim_significance():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 08:00", periods=36, freq="5min"),
        "overall_judgment": ["OK"] * 12 + ["NG"] * 3 + ["OK"] * 21,
        "line_speed_m_min": [30.] * 12 + [35.] * 12 + [30.] * 12,
        "drying_temperature_c": [120.] * 36, "roll_pressure": [15.] * 36,
    })
    hotspot = {"period_label": "09:00-10:00", "start_time": pd.Timestamp("2026-01-01 09:00"),
               "end_time": pd.Timestamp("2026-01-01 10:00"), "ng_count": 3,
               "ng_rate_pct": 25., "primary_defect": "width"}
    statement = analyze_hotspot_process_correlation(df, hotspot)["statements"]["requires_investigation"]
    assert "상관성이 관측" not in statement
    assert "통계적 연관성이나 인과관계를 주장할 수 없" in statement


def test_count_chart_dispersion_is_diagnostic():
    df = pd.DataFrame({"crater_count": [0, 0, 0, 1, 1, 2, 3, 7]})
    data = analyze_vision_defects(df, "crater_count")
    assert data["variance_to_mean_ratio"] > 1.2
    assert "과산포" in data["poisson_assumption_note"]


def test_excel_audit_generated_formulas_are_consistent():
    from openpyxl import load_workbook
    from pathlib import Path
    from src.data_loader import load_raw_data, load_spec
    manifest = __import__('json').loads(Path('result/run_manifest.json').read_text(encoding='utf-8'))
    w = load_workbook(Path('result/Electrode_Quality_Calculation_Trace.xlsx'))
    rows = len(load_raw_data(manifest['raw_input']))
    spec = load_spec(manifest['spec_input'])
    judge = w['03_Quality_Judgment']
    assert judge.max_row == rows + 1
    assert judge['C2'].value.startswith('=IF(')
    assert judge.cell(1, 3).value == spec.iloc[0]['raw_column'] + '__judgment'
    imr = w['04_SPC_IMR_Formulas']
    assert imr['B17'].value is None  # not a zero MR
    assert str(imr['B6'].value).endswith(f'B{16 + rows}),"")')
    assert 'AVERAGE' in imr['B5'].value


def test_generated_summary_preserves_raw_judgments():
    import json
    from pathlib import Path
    from src.data_loader import load_raw_data, load_spec
    from src.quality_judgment import evaluate_quality
    result = Path('result')
    summary = json.loads((result / 'analysis_summary.json').read_text(encoding='utf-8'))
    audit = json.loads((result / 'equipment_spc_summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((result / 'run_manifest.json').read_text(encoding='utf-8'))
    source = load_raw_data(manifest['raw_input'])
    _, counts = evaluate_quality(source, load_spec(manifest['spec_input']))
    assert summary['raw_counts']['total'] == counts['total_count']
    assert summary['raw_counts']['ng'] == counts['ng_count']
    assert summary['raw_counts']['multi_ng_count'] == counts['multi_defect_rows']
    assert sum(v['sample_count'] for v in audit['equipment'].values()) == len(source)
    assert (result / 'run_manifest.json').is_file()
