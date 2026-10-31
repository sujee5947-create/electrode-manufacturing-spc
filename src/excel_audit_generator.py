"""Generate a row-count and SPEC-order independent Excel audit workbook.

All quality/SPC/capability calculations on the primary sheets use live formulas.
Rerun the pipeline after changing the CSV or specification: the workbook is a
snapshot of those input files, not an ingestion mechanism.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union
import math
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

from src.data_loader import load_raw_data, load_spec
from src.spec_validator import validate_spec_and_raw
from src.quality_judgment import evaluate_quality
from src.equipment_analysis import analyze_by_equipment, capability_comparison_table


def _ref(sheet: str, col: int, row: int) -> str:
    return f"'{sheet}'!{get_column_letter(col)}{row}"


def _initialize(wb: Workbook, title: str, headers: list[str]):
    sheet = wb.create_sheet(title)
    sheet.append(headers)
    sheet.freeze_panes = 'C2' if len(headers) > 2 else 'A2'
    sheet.sheet_view.showGridLines = False
    sheet.auto_filter.ref = f'A1:{get_column_letter(len(headers))}1'
    for cell in sheet[1]:
        cell.fill = PatternFill('solid', fgColor='163A5F')
        cell.font = Font(name='Aptos', bold=True, color='FFFFFF')
        cell.alignment = Alignment(vertical='center', wrap_text=True)
    sheet.row_dimensions[1].height = 30
    return sheet


def _style(wb):
    for ws in wb:
        for i in range(1, ws.max_column + 1):
            max_len = max(len(str(ws.cell(row=r, column=i).value or ''))
                          for r in range(1, min(ws.max_row, 18)+1))
            ws.column_dimensions[get_column_letter(i)].width = min(45, max(14, max_len + 3))


def _judge_formula(raw_cell: str, row: pd.Series, spec_index: int, spec_column_index: dict[str, int]) -> str:
    # Resolve by SPEC header NAME, not a fixed E/G Excel letter.
    s_lsl = f"'01_SPEC_Master'!${get_column_letter(spec_column_index['LSL'])}${spec_index}"
    s_usl = f"'01_SPEC_Master'!${get_column_letter(spec_column_index['USL'])}${spec_index}"
    guard = f'NOT(ISNUMBER({raw_cell}))'
    dtype = row['data_type']
    if dtype == 'count':
        return (f'=IF({guard},"INVALID",'
                f'IF(OR({raw_cell}<0,MOD({raw_cell},1)<>0),"INVALID",'
                f'IF({raw_cell}>{s_usl},"NG_HIGH","OK")))')
    if pd.notna(row['LSL']):
        lower = f'IF({raw_cell}<{s_lsl},"NG_LOW",'
        close = ')'
    else:
        lower, close = '', ''
    upper = f'IF({raw_cell}>{s_usl},"NG_HIGH","OK")' if pd.notna(row['USL']) else '"OK"'
    return f'=IF({guard},"INVALID",{lower}{upper}{close})'


def create_calculation_trace_workbook(
    spec_path: Union[str, Path], raw_path: Union[str, Path],
    output_excel_path: Union[str, Path], baseline_n: int = 200
) -> str:
    if baseline_n < 2:
        raise ValueError('baseline_n must be >=2')
    spec_df, raw_df = load_spec(spec_path), load_raw_data(raw_path)
    validate_spec_and_raw(spec_df, raw_df)
    if len(raw_df) < 2:
        raise ValueError('At least 2 rows are required for I-MR analysis')
    N = len(raw_df)
    last = N + 1
    nbase = min(baseline_n, N)
    cont = [(i, r) for i, r in spec_df.iterrows() if r['data_type'] == 'continuous']
    wb = Workbook()
    wb.remove(wb.active)
    wb.calculation = CalcProperties(calcMode='auto', fullCalcOnLoad=True)

    guide = _initialize(wb, '00_Audit_Guide', ['Metric', 'Definition / reference'])
    guide_rows = [
        ('Source rows', N), ('Enabled SPEC items', len(spec_df)),
        ('Baseline observations', nbase), ('Judgment', 'Raw measurement vs SPEC: bounds inclusive'),
        ('INVALID', 'Non-numeric, null, negative/fractional count; default CLI rejects these rows'),
        ('Overall NG', 'If ANY quality characteristic is NG, row is NG; else INVALID/OK'),
        ('MR calculation', 'Previous observation from SAME machine; first observation has blank MR'),
        ('SPC baseline', f'First {nbase} sorted records; mixed machine global chart is reference-only'),
        ('Sigma within', 'Mean within-machine MR / 1.128, pooled view is descriptive'),
        ('Cp/Cpk', 'Use within-machine MR sigma; requires stable process to interpret'),
        ('Pp/Ppk', 'Uses overall sample standard deviation, ddof=1'),
        ('Excel recalculation', 'Formulas may not show cached values until opened/recalculated in Excel'),
        ('Provenance', 'See run_manifest.json for input SHA256 and analysis settings'),
        ('Equipment capability', 'Snapshot values from Python; rerun pipeline when source changes'),
    ]
    for row in guide_rows:
        guide.append(list(row))

    spec_column_index = {c: i + 1 for i, c in enumerate(spec_df.columns)}
    ws_spec = _initialize(wb, '01_SPEC_Master', list(spec_df.columns))
    for _, r in spec_df.iterrows():
        vals = [None if pd.isna(r[c]) else r[c] for c in spec_df.columns]
        ws_spec.append(vals)
    raw_cols = list(raw_df.columns)
    ws_raw = _initialize(wb, '02_Raw_Measurements', raw_cols)
    raw_col_index = {c: i+1 for i, c in enumerate(raw_cols)}
    for row in raw_df.itertuples(index=False, name=None):
        vals = []
        for col, val in zip(raw_cols, row):
            if pd.isna(val):
                vals.append(None)
            elif col == 'timestamp':
                vals.append(val.to_pydatetime() if hasattr(val, 'to_pydatetime') else val)
            elif hasattr(val, 'item'):
                vals.append(val.item())
            else:
                vals.append(val)
        ws_raw.append(vals)
    if 'timestamp' in raw_col_index:
        for row in ws_raw.iter_rows(min_row=2, min_col=raw_col_index['timestamp'], max_col=raw_col_index['timestamp']):
            row[0].number_format = 'yyyy-mm-dd hh:mm:ss'

    judge_cols = [f"{r['raw_column']}__judgment" for _, r in spec_df.iterrows()]
    over_col = 3 + len(judge_cols)
    count_col = over_col + 1
    ws_j = _initialize(wb, '03_Quality_Judgment',
                       ['measurement_row', 'timestamp'] + judge_cols + ['overall_judgment', 'ng_count_per_row'])
    for i in range(N):
        erow = i+2
        ws_j.cell(erow,1,i+1)
        ws_j.cell(erow,2,f"={_ref('02_Raw_Measurements',raw_col_index['timestamp'], erow)}")
        ws_j.cell(erow,2).number_format = 'yyyy-mm-dd hh:mm:ss'
        for si, spec in spec_df.iterrows():
            source_col = raw_col_index[spec['raw_column']]
            ws_j.cell(erow,3+si,_judge_formula(_ref('02_Raw_Measurements', source_col, erow),spec,si+2,spec_column_index))
        first, last_j = get_column_letter(3),get_column_letter(over_col-1)
        span = f'{first}{erow}:{last_j}{erow}'
        ws_j.cell(erow,over_col,f'=IF(COUNTIF({span},"NG*")>0,"NG",IF(COUNTIF({span},"INVALID")>0,"INVALID","OK"))')
        ws_j.cell(erow,count_col,f'=COUNTIF({span},"NG*")')

    stats_col = count_col + 2
    scol = get_column_letter(stats_col+1)
    over_letter=get_column_letter(over_col)
    cnt_letter=get_column_letter(count_col)
    stats=[('Total rows',f'=COUNTA(A2:A{last})'),
           ('OK rows',f'=COUNTIF({over_letter}2:{over_letter}{last},"OK")'),
           ('NG rows',f'=COUNTIF({over_letter}2:{over_letter}{last},"NG")'),
           ('INVALID rows',f'=COUNTIF({over_letter}2:{over_letter}{last},"INVALID")'),
           ('NG rate',f'={scol}4/{scol}2'),
           ('Multi-defect rows',f'=COUNTIF({cnt_letter}2:{cnt_letter}{last},">=2")')]
    for r,(label,formula) in enumerate(stats,start=2):
        ws_j.cell(r, stats_col,label)
        ws_j.cell(r, stats_col+1,formula)
        if label=='NG rate':
            ws_j.cell(r,stats_col+1).number_format='0.00%'
    for i,spec in spec_df.iterrows():
        r=10+i
        j_letter=get_column_letter(3+i)
        ws_j.cell(r,stats_col,str(spec['raw_column']))
        ws_j.cell(r,stats_col+1,f'=COUNTIF({j_letter}2:{j_letter}{last},"NG*")')

    ws_mr = _initialize(wb, '04_SPC_IMR_Formulas',
                        ['Metric'] + [s['raw_column'] for _,s in cont])
    titles={4:'CL (baseline mean)',5:'MR_bar baseline',6:'MR_bar full',7:'I UCL baseline',
            8:'I LCL baseline',9:'MR CL',10:'MR UCL',11:'MR LCL'}
    for row,title in titles.items():
        ws_mr.cell(row,1,title)
    ws_mr.cell(15,1,'Moving ranges (first record for each machine is blank)')
    ws_mr.cell(16,1,'measurement_row')
    for j,(_,s) in enumerate(cont,start=2):
        ws_mr.cell(16,j,s['raw_column'])
    # Historical preceding measurement for each machine; based on current imported CSV snapshot.
    previous = {}
    for i in range(N):
        ws_mr.cell(17+i,1,i+1)
        machine = raw_df.iloc[i]['machine_id'] if 'machine_id' in raw_df.columns else '__ONE_MACHINE__'
        for col_idx,(_,spec) in enumerate(cont, start=2):
            if machine in previous:
                cur = _ref('02_Raw_Measurements',raw_col_index[spec['raw_column']],i+2)
                prior = _ref('02_Raw_Measurements',raw_col_index[spec['raw_column']],previous[machine]+2)
                ws_mr.cell(17+i,col_idx,f'=IF(AND(ISNUMBER({cur}),ISNUMBER({prior})),ABS({cur}-{prior}),"")')
        previous[machine]=i
    last_mr = 16+N
    base_mr = 16+nbase
    for j,(_,spec) in enumerate(cont,start=2):
        a=get_column_letter(j)
        rcol = get_column_letter(raw_col_index[spec['raw_column']])
        ws_mr.cell(4,j,f"=AVERAGE('02_Raw_Measurements'!{rcol}2:{rcol}{nbase+1})")
        ws_mr.cell(5,j,f'=IFERROR(AVERAGE({a}17:{a}{base_mr}),"")')
        ws_mr.cell(6,j,f'=IFERROR(AVERAGE({a}17:{a}{last_mr}),"")')
        ws_mr.cell(7,j,f'=IF(ISNUMBER({a}5),{a}4+2.66*{a}5,"")')
        ws_mr.cell(8,j,f'=IF(ISNUMBER({a}5),{a}4-2.66*{a}5,"")')
        ws_mr.cell(9,j,f'={a}5')
        ws_mr.cell(10,j,f'=IF(ISNUMBER({a}5),3.267*{a}5,"")')
        ws_mr.cell(11,j,0)

    ws_c = _initialize(wb, '05_Capability_Formulas', ['Metric'] + [s['raw_column'] for _,s in cont])
    cap_labels = {
        4:'N',5:'Mean',6:'Overall std (s)',7:'Within sigma (MR/d2)',8:'LSL',9:'USL',
        10:'Cp',11:'Cpu',12:'Cpl',13:'Cpk',14:'Pp',15:'Ppk',
        16:'Out of spec count',17:'Out of spec rate',18:'Cpk using baseline MR (reference)'
    }
    for r,label in cap_labels.items():ws_c.cell(r,1,label)
    for j,(si,spec) in enumerate(cont,start=2):
        a=get_column_letter(j)
        raw_letter=get_column_letter(raw_col_index[spec['raw_column']])
        range_ref=f"'02_Raw_Measurements'!{raw_letter}2:{raw_letter}{last}"
        sc=si+2
        def specref(name):
            return _ref("01_SPEC_Master", spec_column_index[name], sc)
        def put(r,f): ws_c.cell(r,j,f)
        put(4,f'=COUNT({range_ref})')
        put(5,f'=IFERROR(AVERAGE({range_ref}),"")')
        put(6,f'=IFERROR(STDEV.S({range_ref}),"")')
        put(7,f'=IFERROR(\'04_SPC_IMR_Formulas\'!{a}6/1.128,"")')
        put(8,f'={specref("LSL")}' if pd.notna(spec['LSL']) else None)
        put(9,f'={specref("USL")}' if pd.notna(spec['USL']) else None)
        put(10,f'=IFERROR(({a}9-{a}8)/(6*{a}7),"")' if pd.notna(spec['LSL']) and pd.notna(spec['USL']) else None)
        put(11,f'=IFERROR(({a}9-{a}5)/(3*{a}7),"")' if pd.notna(spec['USL']) else None)
        put(12,f'=IFERROR(({a}5-{a}8)/(3*{a}7),"")' if pd.notna(spec['LSL']) else None)
        terms=[f'{a}11' if pd.notna(spec['USL']) else None,f'{a}12' if pd.notna(spec['LSL']) else None]
        terms=[t for t in terms if t]
        put(13, f'=IFERROR(MIN({",".join(terms)}),"")' if terms else None)
        put(14,f'=IFERROR(({a}9-{a}8)/(6*{a}6),"")' if pd.notna(spec['LSL']) and pd.notna(spec['USL']) else None)
        pm=[]
        if pd.notna(spec['USL']):pm.append(f'({a}9-{a}5)/(3*{a}6)')
        if pd.notna(spec['LSL']):pm.append(f'({a}5-{a}8)/(3*{a}6)')
        put(15,f'=IFERROR(MIN({",".join(pm)}),"")' if pm else None)
        counts=[]
        if pd.notna(spec['LSL']): counts.append(f'COUNTIF({range_ref},"<"&{a}8)')
        if pd.notna(spec['USL']): counts.append(f'COUNTIF({range_ref},">"&{a}9)')
        put(16,'='+'+'.join(counts) if counts else '=0')
        put(17,f'=IFERROR({a}16/{a}4,"")')
        base=[]
        if pd.notna(spec['USL']):base.append(f'({a}9-{a}5)/(3*(\'04_SPC_IMR_Formulas\'!{a}5/1.128))')
        if pd.notna(spec['LSL']):base.append(f'({a}5-{a}8)/(3*(\'04_SPC_IMR_Formulas\'!{a}5/1.128))')
        put(18,f'=IFERROR(MIN({",".join(base)}),"")' if base else None)
        ws_c.cell(17,j).number_format='0.00%'

    validated, _ = evaluate_quality(raw_df,spec_df)
    equip = analyze_by_equipment(validated,spec_df,baseline_n=baseline_n)
    comparison = capability_comparison_table(equip)
    ws_e = _initialize(wb,'06_Equipment_Capability',
        list(comparison.columns) if len(comparison.columns) else ['equipment','note'])
    for tup in comparison.itertuples(index=False, name=None):
        ws_e.append([None if pd.isna(x) else (x.item() if hasattr(x,'item') else x) for x in tup])
    _style(wb)
    out=Path(output_excel_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    wb.save(out)
    return str(out)
