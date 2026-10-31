"""Safety regressions: malformed production specs must never produce false OK."""
import pandas as pd
import pytest
from pathlib import Path
from src.spec_validator import validate_spec_and_raw, SpecValidationError
from src.data_loader import load_spec, load_raw_data, load_equipment_event_log
from src.vision_analysis import analyze_vision_defects


def test_spec_rejects_missing_usl():
    spec = pd.DataFrame([dict(raw_column='value', characteristic='value', unit='mm', data_type='continuous',
                              LSL=0., TARGET=2., USL=float('nan'), chart_type='I-MR', enabled='Y')])
    raw = pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=2), 'value': [1., 2.]})
    with pytest.raises(SpecValidationError, match='USL cannot be empty'):
        validate_spec_and_raw(spec, raw)


def test_spec_rejects_non_numeric_usl_file(tmp_path):
    df = pd.DataFrame([dict(raw_column='value', characteristic='value', unit='mm', data_type='continuous',
                            LSL=0., TARGET=2., USL='not_a_number', chart_type='I-MR', enabled='Y')])
    f = tmp_path / 'wrong.xlsx'
    with pd.ExcelWriter(f) as writer:
        df.to_excel(writer, sheet_name='SPEC', index=False)
    with pytest.raises(ValueError, match='Non-numeric USL'):
        load_spec(f)


def test_machine_id_missing_is_rejected(tmp_path):
    df = pd.DataFrame({'timestamp': ['2026-01-01', '2026-01-02'], 'machine_id': ['M1', None]})
    f = tmp_path / 'bad.csv'; df.to_csv(f, index=False)
    with pytest.raises(ValueError, match='machine_id'):
        load_raw_data(f)


def test_explicit_missing_event_log_is_not_ignored(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_equipment_event_log(tmp_path / 'missing.csv')


def test_chart_type_follows_spec_not_area_heuristic():
    df = pd.DataFrame({'defects': [1, 0, 1, 4], 'inspection_area_m2': [2.] * 4})
    spec = pd.Series({'chart_type': 'U', 'USL': 4, 'characteristic': 'defects', 'unit': 'count'})
    a = analyze_vision_defects(df, 'defects', spec)
    assert a['chart_type'] == 'U-Chart'
    assert a['rate_array'] == [0.5, 0, 0.5, 2.0]


def test_c_chart_variable_area_is_rejected():
    df = pd.DataFrame({'defects': [1, 0, 1], 'inspection_area_m2': [1., 2., 3.]})
    spec = pd.Series({'chart_type': 'C', 'USL': 4, 'characteristic': 'defects', 'unit': 'count'})
    with pytest.raises(ValueError, match='variable inspection area'):
        analyze_vision_defects(df, 'defects', spec)
