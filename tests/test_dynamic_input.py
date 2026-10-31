"""Critical checks for practical reuse with different RAW inputs and SPEC row order."""
import json
import pandas as pd
import pytest
from pathlib import Path
from openpyxl import load_workbook
from src.data_loader import load_spec, load_raw_data
from src.excel_audit_generator import create_calculation_trace_workbook
from src.quality_judgment import evaluate_quality
from src.spec_validator import SpecValidationError, validate_spec_and_raw
from src.hotspot_detection import detect_ng_hotspots
from src.time_analysis import aggregate_by_time_interval
from main import run_pipeline

SPEC = Path('raw data/Electrode_Quality_SPEC.xlsx')
RAW = Path('raw data/Electrode_Quality_Raw_Data.csv')


def test_reordered_specs_and_shorter_data_produce_dynamic_excel(tmp_path):
    spec = load_spec(SPEC)
    raw = load_raw_data(RAW).iloc[:51].copy()
    spec = spec.iloc[::-1].reset_index(drop=True)
    spec = spec[list(reversed(spec.columns))]  # reorder headers as well
    # write reordered enabled SPEC while retaining additional columns
    spec_path = tmp_path / 'reversed_spec.xlsx'
    with pd.ExcelWriter(spec_path, engine='openpyxl') as writer:
        spec.to_excel(writer, sheet_name='SPEC', index=False)
    raw_path = tmp_path / 'short.csv'
    raw.to_csv(raw_path, index=False)
    dest = tmp_path / 'audit.xlsx'
    create_calculation_trace_workbook(spec_path, raw_path, dest, baseline_n=20)
    w = load_workbook(dest)
    judge = w['03_Quality_Judgment']
    assert judge.max_row == 52
    assert judge['C1'].value == spec.iloc[0]['raw_column'] + '__judgment'
    usl_letter = __import__('openpyxl').utils.get_column_letter(list(spec.columns).index('USL') + 1)
    assert f"'01_SPEC_Master'!${usl_letter}$2" in judge['C2'].value
    assert "M2" in judge['C2'].value or "N2" in judge['C2'].value
    assert w['04_SPC_IMR_Formulas']['B6'].value.endswith('B67),"")')


def test_longer_and_alternating_machines_have_dynamic_ranges(tmp_path):
    raw = load_raw_data(RAW)
    expanded = pd.concat([raw, raw.iloc[:27]], ignore_index=True)
    expanded.loc[1000:, 'timestamp'] = pd.to_datetime(raw['timestamp'].max()) + pd.to_timedelta(range(1,28), unit='min')
    expanded['machine_id'] = ['A' if i%2 else 'B' for i in range(len(expanded))]
    raw_path = tmp_path / 'long.csv'
    expanded.to_csv(raw_path, index=False)
    dest = tmp_path / 'audit.xlsx'
    create_calculation_trace_workbook(SPEC, raw_path, dest)
    w=load_workbook(dest)
    assert w['03_Quality_Judgment'].max_row == 1028
    mr=w['04_SPC_IMR_Formulas']
    assert mr['B17'].value is None and mr['B18'].value is None
    assert "'02_Raw_Measurements'!H2" in mr['B19'].value
    assert 'B1043' in mr['B6'].value


def test_wrong_path_fails_instead_of_loading_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_raw_data(tmp_path / 'missing.csv')


def test_invalid_count_is_rejected_before_reports(tmp_path):
    raw=load_raw_data(RAW).iloc[:20].copy()
    raw['crater_count'] = raw['crater_count'].astype(float)
    raw.loc[0,'crater_count']=1.5
    src=tmp_path/'raw.csv'
    raw.to_csv(src,index=False)
    with pytest.raises(ValueError, match='INVALID'):
        run_pipeline(spec_path=str(SPEC), raw_path=str(src), output_dir=str(tmp_path/'out'))


def test_hotspot_counts_change_with_input_not_hardcoded():
    spec=load_spec(SPEC)
    raw=load_raw_data(RAW)
    for n in [60, 190, 1000]:
        evaluated, quality=evaluate_quality(raw.iloc[:n], spec)
        grouped=aggregate_by_time_interval(evaluated, spec)
        alerts=detect_ng_hotspots(grouped, quality['ng_rate_pct'])
        assert sum(grouped['ng_count']) == quality['ng_count']
        assert alerts['summary_counts']['total_intervals'] == len(grouped)
        assert all(x['total_count'] >= 6 for x in alerts['severe_hotspots'])


def test_dynamic_report_sources_do_not_contain_demo_metrics():
    template = Path('templates/report.html').read_text(encoding='utf-8')
    ppt = Path('src/ppt_report_generator.py').read_text(encoding='utf-8')
    for snapshot in ['전체 84개 시간대', '열주름(Heat Wrinkle) 12건', '규격(9~11.4mm) 대비 총 6건']:
        assert snapshot not in template + ppt
    assert 'spc_select_options' in template
    assert 'vision_select_options' in template
