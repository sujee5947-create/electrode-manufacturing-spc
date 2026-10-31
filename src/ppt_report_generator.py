"""
PowerPoint Report Generator Module
Creates professional, executive-ready 16:9 engineering quality presentation
using python-pptx with zero text/chart overlaps.
"""

from pathlib import Path
from typing import Dict, List, Any
import numpy as np
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE


# Design Constants
FONT_HEADING = "Malgun Gothic"
FONT_BODY = "Malgun Gothic"

COLOR_PRIMARY = RGBColor(16, 44, 87)       # Navy
COLOR_SECONDARY = RGBColor(53, 162, 235)   # Light Blue
COLOR_ACCENT_NG = RGBColor(220, 53, 69)    # Red
COLOR_ACCENT_OK = RGBColor(40, 167, 69)    # Green
COLOR_TEXT_DARK = RGBColor(33, 37, 41)     # Dark Gray
COLOR_TEXT_MUTED = RGBColor(108, 117, 125) # Muted Gray
COLOR_BG_CARD = RGBColor(248, 249, 250)    # Soft Gray Card
COLOR_BORDER = RGBColor(222, 226, 230)


def create_slide_header(slide, title_text: str, subtitle_text: str = ""):
    """Adds a standard clean header banner across slides."""
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.9))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_title = tf.paragraphs[0]
    p_title.text = title_text
    p_title.font.name = FONT_HEADING
    p_title.font.size = Pt(22)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_PRIMARY

    if subtitle_text:
        p_sub = tf.add_paragraph()
        p_sub.text = subtitle_text
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(11)
        p_sub.font.color.rgb = COLOR_TEXT_MUTED
        p_sub.space_before = Pt(3)


def add_kpi_card(slide, left: float, top: float, width: float, height: float, title: str, value: str, sub: str = "", is_ng: bool = False):
    """Draws a modern KPI metric card."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    card.fill.solid()
    card.fill.fore_color.rgb = COLOR_BG_CARD
    card.line.color.rgb = COLOR_BORDER
    card.line.width = Pt(1)

    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.15)
    tf.margin_right = Inches(0.15)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.1)

    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.name = FONT_HEADING
    p0.font.size = Pt(10)
    p0.font.color.rgb = COLOR_TEXT_MUTED

    p1 = tf.add_paragraph()
    p1.text = value
    p1.font.name = FONT_HEADING
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_ACCENT_NG if is_ng else COLOR_PRIMARY
    p1.space_before = Pt(2)

    if sub:
        p2 = tf.add_paragraph()
        p2.text = sub
        p2.font.name = FONT_BODY
        p2.font.size = Pt(9)
        p2.font.color.rgb = COLOR_TEXT_MUTED
        p2.space_before = Pt(2)


def generate_ppt_report(
    summary_obj: Dict[str, Any],
    quality_summary: Dict[str, Any],
    hotspots: Any,
    process_correlations: List[Dict[str, Any]],
    capability_results: Dict[str, Any],
    chart_paths: Dict[str, str],
    output_path: str | Path
) -> str:
    """
    Generates 12-slide comprehensive presentation.
    """
    if isinstance(hotspots, dict):
        hotspots = hotspots.get("severe_hotspots", [])

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # ==========================================
    # Slide 1: Cover Slide
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = COLOR_PRIMARY
    bg1.line.fill.background()

    tb1 = s1.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(10.9), Inches(3.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "ELECTRODE QUALITY SPC MONITORING SYSTEM"
    p.font.name = FONT_HEADING
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)

    p2 = tf1.add_paragraph()
    p2.text = "배터리 전극 제조 공정 자동 품질 판정 및 통계적 공정 관리(SPC) 보고서"
    p2.font.name = FONT_BODY
    p2.font.size = Pt(18)
    p2.font.color.rgb = COLOR_SECONDARY
    p2.space_before = Pt(12)

    p3 = tf1.add_paragraph()
    p3.text = "Automated Quality Judgment | I-MR & C-Chart SPC | Hotspot Clustering | Process Correlation"
    p3.font.name = FONT_BODY
    p3.font.size = Pt(12)
    p3.font.color.rgb = RGBColor(200, 220, 240)
    p3.space_before = Pt(16)

    p4 = tf1.add_paragraph()
    p4.text = "분석 대상: 전극 코팅 치수, 코팅 두께/중량, 비전 결함(크레이터, 열주름) 및 공정 운전 조건"
    p4.font.name = FONT_BODY
    p4.font.size = Pt(11)
    p4.font.color.rgb = RGBColor(180, 195, 210)
    p4.space_before = Pt(28)

    # ==========================================
    # Slide 2: Executive Summary
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    create_slide_header(s2, "Executive Summary", "핵심 품질 KPI 현황 및 주요 엔지니어링 관찰 결과")

    # 4 KPI cards
    add_kpi_card(s2, 0.8, 1.4, 2.7, 1.25, "총 검사 건수", f"{summary_obj['raw_counts']['total']:,}건", "전체 검사 행")
    add_kpi_card(s2, 3.8, 1.4, 2.7, 1.25, "정상 합격 (OK)", f"{summary_obj['raw_counts']['ok']:,}건", f"합격률 {100 - summary_obj['raw_counts']['ng_rate_pct']:.1f}%")
    add_kpi_card(s2, 6.8, 1.4, 2.7, 1.25, "규격 이탈 (NG)", f"{summary_obj['raw_counts']['ng']:,}건", f"불량률 {summary_obj['raw_counts']['ng_rate_pct']:.2f}%", is_ng=True)
    add_kpi_card(s2, 9.8, 1.4, 2.7, 1.25, "이상 집중 구간", f"{summary_obj['raw_counts']['hotspot_count']}개소", "NG Hotspot 탐지")

    # Takeaways box
    t_box = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.9), Inches(11.7), Inches(4.0))
    t_box.fill.solid()
    t_box.fill.fore_color.rgb = RGBColor(245, 248, 252)
    t_box.line.color.rgb = COLOR_SECONDARY
    tf_t = t_box.text_frame
    tf_t.word_wrap = True
    tf_t.margin_left = Inches(0.4)
    tf_t.margin_top = Inches(0.3)

    p = tf_t.paragraphs[0]
    p.text = "■ 핵심 관찰 및 엔지니어링 분석 요약 (Key Engineering Takeaways)"
    p.font.name = FONT_HEADING
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    for idx, tk in enumerate(summary_obj.get("key_takeaways", [])):
        p_tk = tf_t.add_paragraph()
        p_tk.text = f"{idx+1}. {tk}"
        p_tk.font.name = FONT_BODY
        p_tk.font.size = Pt(11.5)
        p_tk.font.color.rgb = COLOR_TEXT_DARK
        p_tk.space_before = Pt(12)

    for para in summary_obj.get("overall_summary", []):
        p_extra = tf_t.add_paragraph()
        p_extra.text = f"• {para}"
        p_extra.font.name = FONT_BODY
        p_extra.font.size = Pt(10.5)
        p_extra.font.color.rgb = COLOR_TEXT_MUTED
        p_extra.space_before = Pt(8)

    # ==========================================
    # Slide 3: Quality Specification Overview
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    create_slide_header(s3, "Quality Specification (SPEC) Overview", "공정 품질 관리 기준 규격 및 데이터 매핑 체계")

    # Table of specifications
    char_list = quality_summary.get("char_stats", [])
    rows = len(char_list) + 1
    cols = 6
    tbl_shape = s3.shapes.add_table(rows, cols, Inches(0.8), Inches(1.5), Inches(11.7), Inches(5.2))
    table = tbl_shape.table

    col_widths = [Inches(1.8), Inches(2.4), Inches(1.2), Inches(1.5), Inches(1.5), Inches(3.3)]
    for i, w in enumerate(col_widths):
        table.columns[i].width = w

    headers = ["품질 특성", "Raw 데이터 컬럼", "단위", "LSL (하한)", "USL (상한)", "판정 로직 및 관리도"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_PRIMARY
        p = cell.text_frame.paragraphs[0]
        p.font.name = FONT_HEADING
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

    for r_idx, c_item in enumerate(char_list):
        cell_vals = [
            c_item["characteristic"],
            c_item["raw_column"],
            c_item["unit"],
            f"{c_item['LSL']}" if c_item["LSL"] is not None and not (isinstance(c_item['LSL'], float) and np.isnan(c_item['LSL'])) else "-",
            f"{c_item['USL']}",
            f"{c_item['data_type'].upper()} ({'I-MR 관리도' if c_item['data_type'] == 'continuous' else 'C 관리도'})"
        ]
        for c_idx, val in enumerate(cell_vals):
            cell = table.cell(r_idx + 1, c_idx)
            cell.text = str(val)
            p = cell.text_frame.paragraphs[0]
            p.font.name = FONT_BODY
            p.font.size = Pt(9.5)
            p.font.color.rgb = COLOR_TEXT_DARK
            p.alignment = PP_ALIGN.CENTER if c_idx in [2, 3, 4] else PP_ALIGN.LEFT

    # ==========================================
    # Slide 4: Overall Quality Performance (Pareto)
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    create_slide_header(s4, "Overall Quality Performance & Pareto Analysis", "전체 불량 분포 및 주요 품질 특성별 NG 기여도")

    if "pareto" in chart_paths and Path(chart_paths["pareto"]).exists():
        s4.shapes.add_picture(chart_paths["pareto"], Inches(0.8), Inches(1.5), Inches(8.0), Inches(5.3))

    # Summary side panel
    side_box = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.1), Inches(1.5), Inches(3.4), Inches(5.3))
    side_box.fill.solid()
    side_box.fill.fore_color.rgb = COLOR_BG_CARD
    side_box.line.color.rgb = COLOR_BORDER
    tf_side = side_box.text_frame
    tf_side.word_wrap = True
    tf_side.margin_left = Inches(0.2)
    tf_side.margin_top = Inches(0.2)

    p = tf_side.paragraphs[0]
    p.text = "■ 파레토 분석 주요 시사점"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    char_stats = sorted(quality_summary.get('char_stats', []),
                        key=lambda item: item.get('ng_count', 0), reverse=True)
    total_feature_ng = sum(int(c.get('ng_count', 0)) for c in char_stats)
    top = char_stats[:2]
    top_share = (sum(int(c.get('ng_count', 0)) for c in top) / total_feature_ng * 100) if total_feature_ng else 0
    feature_lines = [f"{c.get('characteristic', c.get('raw_column', '?'))}: {c.get('ng_count', 0)}건"
                     for c in top]
    lines = [
        f"• 주요 불량: {', '.join(feature_lines) if feature_lines else '검출된 불량 없음'}",
        f"• 상위 2개 항목의 특성별 NG 점유율: {top_share:.1f}% (중복 불량은 항목별로 집계)",
        f"• 전체 NG {quality_summary.get('ng_count', 0)}건 / 총 {quality_summary.get('total_count', 0)}건",
        f"• 복합 불량 행: {quality_summary.get('multi_defect_rows', 0)}건, 원인 검증은 별도 필요"
    ]
    for line in lines:
        p_l = tf_side.add_paragraph()
        p_l.text = line
        p_l.font.name = FONT_BODY
        p_l.font.size = Pt(9.5)
        p_l.font.color.rgb = COLOR_TEXT_DARK
        p_l.space_before = Pt(8)

    # ==========================================
    # Slide 5: Time-based NG Analysis
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    create_slide_header(s5, "Time-Series Defect Rate & Cluster Trend", "시간대별 생산량 및 NG 불량률 변동 추이")

    if "time_trend" in chart_paths and Path(chart_paths["time_trend"]).exists():
        s5.shapes.add_picture(chart_paths["time_trend"], Inches(0.8), Inches(1.4), Inches(11.7), Inches(4.3))

    # Time summary text below
    tb_time = s5.shapes.add_textbox(Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.3))
    tf_time = tb_time.text_frame
    tf_time.word_wrap = True
    for idx, txt in enumerate(summary_obj.get("time_summary", [])):
        p = tf_time.paragraphs[0] if idx == 0 else tf_time.add_paragraph()
        p.text = f"• {txt}"
        p.font.name = FONT_BODY
        p.font.size = Pt(10)
        p.font.color.rgb = COLOR_TEXT_DARK
        if idx > 0:
            p.space_before = Pt(4)

    # ==========================================
    # Slide 6: NG Hotspot Detail
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    create_slide_header(s6, "NG Hotspot Deep Dive", "불량 집중 구간(Hotspot) 통계 및 공정 조건 전/후 변동 분석")

    if hotspots:
        hs = hotspots[0]
        # Hotspot profile card
        add_kpi_card(s6, 0.8, 1.4, 3.6, 1.3, "최대 불량 집중 구간", hs["period_label"], f"불량률 {hs['ng_rate_pct']:.1f}% (+{hs['diff_pp']:.1f}%p)", is_ng=True)
        add_kpi_card(s6, 4.8, 1.4, 3.6, 1.3, "주요 발생 결함", hs["primary_defect"], f"NG 건수: {hs['ng_count']}건 / {hs['total_count']}건")
        add_kpi_card(s6, 8.8, 1.4, 3.7, 1.3, "생산 설비 및 LOT", f"{hs['machines']}", f"LOT: {hs['lots']}")

    # Process correlation box
    if process_correlations:
        pc = process_correlations[0]
        p_card = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.9), Inches(11.7), Inches(4.1))
        p_card.fill.solid()
        p_card.fill.fore_color.rgb = RGBColor(253, 247, 247)
        p_card.line.color.rgb = COLOR_ACCENT_NG
        tf_pc = p_card.text_frame
        tf_pc.word_wrap = True
        tf_pc.margin_left = Inches(0.3)
        tf_pc.margin_top = Inches(0.25)

        p = tf_pc.paragraphs[0]
        p.text = "■ 엔지니어링 분석 진술문 (Three-Tier Engineering Attribution)"
        p.font.name = FONT_HEADING
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY

        st = pc["statements"]
        items = [
            ("[확인된 사실 (Confirmed Fact)]", st["confirmed_fact"], COLOR_PRIMARY),
            ("[연관된 변화 (Associated Change)]", st["associated_change"], RGBColor(190, 80, 0)),
            ("[추가 검토 필요 (Requires Investigation)]", st["requires_investigation"], COLOR_TEXT_MUTED)
        ]
        for tag, body, color in items:
            p_tag = tf_pc.add_paragraph()
            p_tag.text = tag
            p_tag.font.name = FONT_HEADING
            p_tag.font.size = Pt(10.5)
            p_tag.font.bold = True
            p_tag.font.color.rgb = color
            p_tag.space_before = Pt(8)

            p_body = tf_pc.add_paragraph()
            p_body.text = body
            p_body.font.name = FONT_BODY
            p_body.font.size = Pt(10)
            p_body.font.color.rgb = COLOR_TEXT_DARK
            p_body.space_before = Pt(2)

    # ==========================================
    # Slide 7: SPC Dimensional Monitoring
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    create_slide_header(s7, "SPC Dimensional Monitoring (I-MR Charts)", "전극 폭 치수(유지부/무지부/간격) 통계적 공정 관리")

    first_spc = next((key for key in chart_paths if key.startswith('spc_') and Path(chart_paths[key]).exists()), None)
    if first_spc:
        s7.shapes.add_picture(chart_paths[first_spc], Inches(0.8), Inches(1.4), Inches(8.0), Inches(5.4))

    # Notes panel
    s7_notes = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.0), Inches(1.4), Inches(3.5), Inches(5.4))
    s7_notes.fill.solid()
    s7_notes.fill.fore_color.rgb = COLOR_BG_CARD
    s7_notes.line.color.rgb = COLOR_BORDER
    tf7 = s7_notes.text_frame
    tf7.word_wrap = True
    tf7.margin_left = Inches(0.2)
    tf7.margin_top = Inches(0.2)

    p = tf7.paragraphs[0]
    p.text = "■ 치수 관리도 관리 현황"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    desc_lines = [
        "• 활성화된 연속형 품질 항목의 I-MR 관리도이며, SPEC의 규격 한계와 통계적 관리한계는 서로 다릅니다.",
        "• 관리한계는 기준 데이터의 공정 안정성을 확인한 뒤 현장에서 승인해야 합니다.",
        "• 여러 설비가 섞인 통합 관리도 대신 설비별 관리도를 함께 검토하세요."
    ]
    for d in desc_lines:
        p_d = tf7.add_paragraph()
        p_d.text = d
        p_d.font.name = FONT_BODY
        p_d.font.size = Pt(9.5)
        p_d.font.color.rgb = COLOR_TEXT_DARK
        p_d.space_before = Pt(8)

    # ==========================================
    # Slide 8: Coating Quality Monitoring & Capability
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    create_slide_header(s8, "Coating Quality & Capability Analysis", "코팅 두께 및 중량 관리도와 공정능력 지수 (Cp/Cpk)")

    preferred_spc = 'spc_coating_thickness_um' if 'spc_coating_thickness_um' in chart_paths else first_spc
    if preferred_spc and Path(chart_paths[preferred_spc]).exists():
        s8.shapes.add_picture(chart_paths[preferred_spc], Inches(0.8), Inches(1.4), Inches(7.5), Inches(5.4))

    # Capability stats box
    cap_box = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.5), Inches(1.4), Inches(4.0), Inches(5.4))
    cap_box.fill.solid()
    cap_box.fill.fore_color.rgb = COLOR_BG_CARD
    cap_box.line.color.rgb = COLOR_BORDER
    tf_c = cap_box.text_frame
    tf_c.word_wrap = True
    tf_c.margin_left = Inches(0.2)
    tf_c.margin_top = Inches(0.2)

    p = tf_c.paragraphs[0]
    p.text = "■ 코팅 품질 공정능력 결과"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    for col in list(capability_results)[:2]:
        if col in capability_results:
            cr = capability_results[col]
            p_sub = tf_c.add_paragraph()
            p_sub.text = f"▶ {cr['characteristic']}"
            p_sub.font.name = FONT_HEADING
            p_sub.font.size = Pt(10)
            p_sub.font.bold = True
            p_sub.font.color.rgb = COLOR_SECONDARY
            p_sub.space_before = Pt(8)

            metrics = [
                f"평균: {cr['mean']}{cr['unit']} (표준편차: {cr['std_overall']})",
                f"Cp: {cr['cp']} | Cpk: {cr['cpk']}",
                f"Pp: {cr['pp']} | Ppk: {cr['ppk']}",
                f"규격 이탈: {cr['out_of_spec_count']}건 ({cr['out_of_spec_rate_pct']}%)",
                f"판정: {cr['capability_level']}"
            ]
            for m in metrics:
                p_m = tf_c.add_paragraph()
                p_m.text = f"  • {m}"
                p_m.font.name = FONT_BODY
                p_m.font.size = Pt(9)
                p_m.font.color.rgb = COLOR_TEXT_DARK
                p_m.space_before = Pt(2)

    # ==========================================
    # Slide 9: Vision Defect Monitoring
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    create_slide_header(s9, "Vision Defect Monitoring (C-Chart)", "표면 비전 검사 결함(크레이터, 열주름) 관리도 분석")

    first_vision = next((key for key in chart_paths if key.startswith('vision_') and Path(chart_paths[key]).exists()), None)
    if first_vision:
        s9.shapes.add_picture(chart_paths[first_vision], Inches(0.8), Inches(1.4), Inches(11.7), Inches(4.3))

    tb_v = s9.shapes.add_textbox(Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.3))
    tf_v = tb_v.text_frame
    tf_v.word_wrap = True
    p = tf_v.paragraphs[0]
    p.text = "• 계수형 결함은 검사 단위/면적과 C/U 차트 설정에 따라 집계되며, C 차트는 검사 기회 일정성이 전제됩니다."
    p.font.name = FONT_BODY
    p.font.size = Pt(10)
    p.font.color.rgb = COLOR_TEXT_DARK

    p2 = tf_v.add_paragraph()
    count_stats = [c for c in quality_summary.get('char_stats', []) if c.get('data_type') == 'count']
    p2.text = ("• 결함 수 기준 규격 이탈: " + ", ".join(
        f"{c.get('characteristic', c.get('raw_column', '?'))} {c.get('ng_count', 0)}건" for c in count_stats)
        if count_stats else "• 활성화된 계수형 품질 항목 없음")
    p2.font.name = FONT_BODY
    p2.font.size = Pt(10)
    p2.font.color.rgb = COLOR_TEXT_DARK
    p2.space_before = Pt(4)

    # ==========================================
    # Slide 10: Process Conditions & Quality Correlation
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    create_slide_header(s10, "Process Conditions & Quality Correlation", "생산 속도, 건조 온도, 롤 압력 변화와 품질 이상 구간 연계 분석")

    if "process_timeline" in chart_paths and Path(chart_paths["process_timeline"]).exists():
        s10.shapes.add_picture(chart_paths["process_timeline"], Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))

    # ==========================================
    # Slide 11: LOT & Equipment Analysis
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    create_slide_header(s11, "LOT & Equipment Quality Comparison", "생산 로트 및 코터 설비별 불량률 편차 분석")

    if "lot_machine" in chart_paths and Path(chart_paths["lot_machine"]).exists():
        s11.shapes.add_picture(chart_paths["lot_machine"], Inches(0.8), Inches(1.4), Inches(8.5), Inches(5.4))

    s11_box = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.5), Inches(1.4), Inches(3.0), Inches(5.4))
    s11_box.fill.solid()
    s11_box.fill.fore_color.rgb = COLOR_BG_CARD
    s11_box.line.color.rgb = COLOR_BORDER
    tf11 = s11_box.text_frame
    tf11.word_wrap = True
    tf11.margin_left = Inches(0.15)
    tf11.margin_top = Inches(0.2)

    p = tf11.paragraphs[0]
    p.text = "■ 설비/로트 분석 시사점"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    lines11 = [
        "• 설비 간 불량률 편차를 모니터링하여 특정 설비의 챔버 노후화 및 롤 편차를 감지합니다.",
        "• LOT 전환 시점(Changeover) 부근의 초기 안정화 구간에서 불량 집중 여부를 점검합니다.",
        "• 추후 설비 이벤트 로그가 연계되면 설비 알람 및 유지보수 이력과의 결합 분석이 가능합니다."
    ]
    for l in lines11:
        p_l = tf11.add_paragraph()
        p_l.text = l
        p_l.font.name = FONT_BODY
        p_l.font.size = Pt(9.5)
        p_l.font.color.rgb = COLOR_TEXT_DARK
        p_l.space_before = Pt(8)

    # ==========================================
    # Slide 12: Conclusions & Next Steps
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    create_slide_header(s12, "Conclusions & Engineering Next Steps", "종합 결론 및 향후 공정 개선/시스템 확장 방향")

    box_concl = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))
    box_concl.fill.solid()
    box_concl.fill.fore_color.rgb = COLOR_BG_CARD
    box_concl.line.color.rgb = COLOR_BORDER
    tfc = box_concl.text_frame
    tfc.word_wrap = True
    tfc.margin_left = Inches(0.4)
    tfc.margin_top = Inches(0.3)

    p = tfc.paragraphs[0]
    p.text = "■ 핵심 결론 및 엔지니어링 실행 방안 (Actionable Next Steps)"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY

    actions = [
        ("1. 데이터 기반 품질 모니터링 자동화 달성",
         "SPEC과 계측 데이터를 매핑하여 OK/NG 판정, I-MR/C/U 관리도, Cp/Cpk/Pp/Ppk와 보고서 생성을 자동 수행합니다. 현장 승인 기준이 아닌 분석 지원 도구입니다."),
        ("2. 시간대별 이상 집중 구간(Hotspot) 조기 감지 체계",
         "사용자가 지정한 시간 간격을 기준으로 NG 비율을 집계하고, 표본 수 및 운영 경보 조건에 따라 고위험·주의·표본 부족을 구분합니다."),
        ("3. 공정 조건 연계 및 엄격한 엔지니어링 해석 준수",
         "불량 집중 구간 전/후 공정 조건 변동(온도, 속도, 압력)을 기술통계로 비교하되, 확인된 사실/연관된 변화/추가 검토 필요의 3단계 엄격한 엔지니어링 진술 체계를 준수합니다."),
        ("4. 확장성 및 현장 적용성 (Equipment Event Log Ready)",
         "선택적 설비 이벤트 로그 연계 인터페이스를 제공하지만, 실무 배포 전 공정별 SPEC·MSA·Phase I 기준·로그 품질을 검증해야 합니다.")
    ]

    for title, desc in actions:
        p_t = tfc.add_paragraph()
        p_t.text = title
        p_t.font.name = FONT_HEADING
        p_t.font.size = Pt(11)
        p_t.font.bold = True
        p_t.font.color.rgb = COLOR_SECONDARY
        p_t.space_before = Pt(10)

        p_d = tfc.add_paragraph()
        p_d.text = desc
        p_d.font.name = FONT_BODY
        p_d.font.size = Pt(10)
        p_d.font.color.rgb = COLOR_TEXT_DARK
        p_d.space_before = Pt(2)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    return str(output_path)
