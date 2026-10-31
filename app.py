"""
Streamlit Web Dashboard
Interactive Electrode Quality SPC Monitoring & Hotspot Analytics System.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

from src.data_loader import load_spec, load_raw_data, load_equipment_event_log
from src.spec_validator import validate_spec_and_raw
from src.quality_judgment import evaluate_quality
from src.spc_analysis import analyze_imr
from src.vision_analysis import analyze_vision_defects
from src.capability_analysis import analyze_all_capabilities
from src.equipment_analysis import analyze_by_equipment, capability_comparison_table
from src.time_analysis import aggregate_by_time_interval, generate_date_hour_heatmap_matrix
from src.hotspot_detection import detect_ng_hotspots, HotspotConfig
from src.process_analysis import analyze_hotspot_process_correlation
from src.summary_generator import generate_executive_summary
from src.html_report_generator import (
    create_plotly_pareto,
    create_plotly_time_trend,
    create_plotly_heatmap,
    create_plotly_imr,
    create_plotly_vision,
    create_plotly_process_timeline,
    create_plotly_bar_compare
)
from main import run_pipeline

st.set_page_config(
    page_title="Electrode Quality SPC Monitoring",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #102c57;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def get_cached_analysis(spec_file: str, raw_file: str, interval: int, baseline_n: int,
                        spec_fingerprint: tuple, raw_fingerprint: tuple):
    spec_df = load_spec(spec_file)
    raw_df = load_raw_data(raw_file)
    validate_spec_and_raw(spec_df, raw_df)
    eval_df, quality_summary = evaluate_quality(raw_df, spec_df)
    invalid_columns = [f"{col}__judgment" for col in spec_df["raw_column"]]
    invalid_rows = eval_df[invalid_columns].eq("INVALID").any(axis=1).sum()
    if invalid_rows:
        raise ValueError(f"INVALID 측정값이 {invalid_rows}행 발견되었습니다. CSV 확인 후 재실행하세요.")

    spc_results = {}
    vision_results = {}
    for _, spec_row in spec_df.iterrows():
        col = spec_row["raw_column"]
        ctype = spec_row.get("chart_type", "I-MR")
        if ctype == "I-MR":
            spc_results[col] = analyze_imr(eval_df, col, spec_row, baseline_n=baseline_n)
        elif ctype in ("C", "U"):
            vision_results[col] = analyze_vision_defects(eval_df, col, spec_row)

    cap_results = analyze_all_capabilities(eval_df, spec_df, spc_results, baseline_n=baseline_n)
    equipment_results = analyze_by_equipment(eval_df, spec_df, baseline_n=baseline_n)
    interval_df = aggregate_by_time_interval(eval_df, spec_df, interval_minutes=interval)
    heatmap_matrix = generate_date_hour_heatmap_matrix(eval_df)
    hotspots = detect_ng_hotspots(interval_df, overall_ng_rate_pct=quality_summary["ng_rate_pct"])
    correlations = [analyze_hotspot_process_correlation(eval_df, h) for h in hotspots["severe_hotspots"]]
    summary_obj = generate_executive_summary(quality_summary, hotspots, correlations, cap_results, evaluated_df=eval_df)

    return {
        "spec_df": spec_df,
        "raw_df": eval_df,
        "quality_summary": quality_summary,
        "spc_results": spc_results,
        "vision_results": vision_results,
        "cap_results": cap_results,
        "equipment_results": equipment_results,
        "interval_df": interval_df,
        "heatmap_matrix": heatmap_matrix,
        "hotspots": hotspots,
        "correlations": correlations,
        "summary_obj": summary_obj
    }


# Sidebar Controls
st.sidebar.title("⚙️ 시스템 설정 (Settings)")

spec_path = st.sidebar.text_input("SPEC 경로", value="raw data/Electrode_Quality_SPEC.xlsx")
raw_path = st.sidebar.text_input("Raw Data 경로", value="raw data/Electrode_Quality_Raw_Data.csv")
interval_min = st.sidebar.selectbox("분석 시간 간격", options=[30, 60, 120], index=1, format_func=lambda x: f"{x}분 단위")
baseline_n = st.sidebar.number_input("설비별 Baseline 샘플 수", min_value=2, max_value=1000000, value=200, step=10)

if st.sidebar.button("🔄 자동 보고서 (PPT & HTML) 생성", type="primary"):
    with st.spinner("PPTX 및 HTML 보고서 자동 생성 중..."):
        res = run_pipeline(spec_path=spec_path, raw_path=raw_path, interval_minutes=interval_min, baseline_n=int(baseline_n))
        st.sidebar.success("✅ 보고서 생성 완료!")

try:
    # Streamlit cache must invalidate when a file is replaced at the same path.
    def fingerprint(path):
        meta = Path(path).stat()
        return (meta.st_size, meta.st_mtime_ns)
    data = get_cached_analysis(spec_path, raw_path, interval_min, int(baseline_n),
                               fingerprint(spec_path), fingerprint(raw_path))
except Exception as e:
    st.error(f"데이터 로드 및 분석 실패: {e}")
    st.stop()

# Header
st.markdown("<div class='main-header'>🔋 Electrode Quality SPC Monitoring System</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>배터리 전극 제조 공정 자동 품질 판정 및 통계적 공정 관리 대시보드</div>", unsafe_allow_html=True)

# Top KPIs
q_sum = data["quality_summary"]
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("총 검사 건수", f"{q_sum['total_count']:,}건")
with col2:
    st.metric("정상 합격 (OK)", f"{q_sum['ok_count']:,}건", f"{q_sum['ok_rate_pct']:.2f}%")
with col3:
    st.metric("규격 이탈 (NG)", f"{q_sum['ng_count']:,}건", f"{q_sum['ng_rate_pct']:.2f}%", delta_color="inverse")
with col4:
    st.metric("복합 불량 행", f"{q_sum['multi_defect_rows']}건")
with col5:
    st.metric("이상 집중 구간 (Hotspots)", f"{len(data['hotspots']['severe_hotspots']) + len(data['hotspots']['warning_clusters'])}개소")

# Tabs
tabs = st.tabs([
    "📊 종합 품질 & 파레토",
    "📈 SPC 관리도 (I-MR & C)",
    "🎯 공정능력 분석 (Cpk)",
    "⏰ 시간대별 이상 집중 (Hotspots)",
    "⚙️ 공정 조건 연관 분석",
    "📄 보고서 다운로드"
])

# Tab 1: Overall Quality & Pareto
with tabs[0]:
    st.subheader("품질 규격 준수 및 파레토 분석")
    p_fig = go.Figure(create_plotly_pareto(q_sum["char_stats"]))
    st.plotly_chart(p_fig, use_container_width=True)

    st.subheader("품질 특성별 상세 판정 현황")
    st.dataframe(pd.DataFrame(q_sum["char_stats"]), use_container_width=True)

# Tab 2: SPC Control Charts
with tabs[1]:
    st.subheader("통계적 공정 관리 (SPC Control Charts)")
    spc_type = st.radio("관리도 유형 선택", ["연속형 치수 (I-MR 관리도)", "외관 비전 결함 (C 관리도)"], horizontal=True)

    if "I-MR" in spc_type:
        selected_col = st.selectbox("품질 특성 선택", list(data["spc_results"].keys()))
        spc_info = data["spc_results"][selected_col]
        fig_dict = create_plotly_imr(data["raw_df"], selected_col, spc_info)
        st.plotly_chart(go.Figure(fig_dict), use_container_width=True)
        st.info(f"기준 기간 안정성: {spc_info['baseline_stability_note']}")
    else:
        v_col = st.selectbox("비전 결함 항목 선택", list(data["vision_results"].keys()))
        v_info = data["vision_results"][v_col]
        fig_dict = create_plotly_vision(v_info)
        st.plotly_chart(go.Figure(fig_dict), use_container_width=True)

# Tab 3: Process Capability
with tabs[2]:
    st.subheader("연속형 특성 공정능력 지수 (Process Capability)")
    cap_rows = [v for k, v in data["cap_results"].items() if v.get("applicable")]
    st.dataframe(pd.DataFrame(cap_rows), use_container_width=True)
    st.warning("전체 데이터 통합 Cp/Cpk는 참고용입니다. 양산 판단은 설비별 관리안정성 검토 후 진행하세요.")
    st.subheader("설비별 공정능력 및 기준 구간 안정성")
    st.dataframe(capability_comparison_table(data["equipment_results"]), use_container_width=True)

# Tab 4: Time Analysis & Hotspots
with tabs[3]:
    st.subheader(f"시간대별 불량률 추이 ({interval_min}분 인터벌)")
    t_fig = go.Figure(create_plotly_time_trend(data["interval_df"]))
    st.plotly_chart(t_fig, use_container_width=True)

    st.subheader("일자별 × 시간대별 불량 발생 히트맵")
    hm_fig = go.Figure(create_plotly_heatmap(data["heatmap_matrix"]))
    st.plotly_chart(hm_fig, use_container_width=True)

    st.subheader("자동 탐지된 불량 집중 구간 (Hotspot List)")
    if data["hotspots"]["all_ng_periods"]:
        st.dataframe(pd.DataFrame(data["hotspots"]["all_ng_periods"]), use_container_width=True)
    else:
        st.success("임계치를 초과한 불량 집중 구간이 없습니다.")

# Tab 5: Process Correlation
with tabs[4]:
    st.subheader("공정 운전 조건 시계열 및 Hotspot 구간 연계")
    proc_fig = go.Figure(create_plotly_process_timeline(data["raw_df"], data["hotspots"]["severe_hotspots"]))
    st.plotly_chart(proc_fig, use_container_width=True)

    for corr in data["correlations"]:
        with st.expander(f"📍 집중 구간: {corr['hotspot_period']} (주요 결함: {corr['primary_defect']})", expanded=True):
            st.markdown(f"**[확인된 사실]** {corr['statements']['confirmed_fact']}")
            st.markdown(f"**[연관된 변화]** {corr['statements']['associated_change']}")
            st.markdown(f"**[추가 검토 필요]** {corr['statements']['requires_investigation']}")

# Tab 6: Reports
with tabs[5]:
    st.subheader("자동 생성된 엔지니어링 품질 보고서 및 수식 추적 엑셀")
    # Report files must originate from the current pipeline output folder only.
    # Do not silently return an old file from outputs/reports or outputs/results.
    def get_existing_path(filename):
        return Path('result') / filename

    pptx_file = get_existing_path("Electrode_Quality_SPC_Report.pptx")
    html_file = get_existing_path("Electrode_Quality_SPC_Report.html")
    excel_file = get_existing_path("Electrode_Quality_Calculation_Trace.xlsx")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if pptx_file.exists():
            with open(pptx_file, "rb") as f:
                st.download_button(
                    label="📥 PowerPoint (.pptx) 다운로드",
                    data=f.read(),
                    file_name="Electrode_Quality_SPC_Report.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    type="primary"
                )
        else:
            st.warning("PPTX 보고서 미생성")

    with col_b:
        if html_file.exists():
            with open(html_file, "rb") as f:
                st.download_button(
                    label="🌐 반응형 HTML (.html) 다운로드",
                    data=f.read(),
                    file_name="Electrode_Quality_SPC_Report.html",
                    mime="text/html",
                    type="primary"
                )
        else:
            st.warning("HTML 보고서 미생성")

    with col_c:
        if excel_file.exists():
            with open(excel_file, "rb") as f:
                st.download_button(
                    label="📊 수식 추적 엑셀 (.xlsx) 다운로드",
                    data=f.read(),
                    file_name="Electrode_Quality_Calculation_Trace.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        else:
            st.warning("수식 추적 엑셀 미생성")
