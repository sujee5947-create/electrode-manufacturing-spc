"""
HTML Report Generator Module
Renders an executive, mobile-responsive standalone HTML quality report
with embedded offline Plotly.js and interactive controls.
"""

from pathlib import Path
from typing import Dict, List, Any
import json
import jinja2
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo


def create_plotly_pareto(char_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates Plotly Pareto JSON dict."""
    df = pd.DataFrame(char_stats)
    df = df[df["ng_count"] > 0].sort_values("ng_count", ascending=False).reset_index(drop=True)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="불량(NG) 데이터 없음", showarrow=False, font=dict(size=16))
        return json.loads(fig.to_json())

    df["cum_pct"] = df["ng_count"].cumsum() / df["ng_count"].sum() * 100

    labels = [f"{r['characteristic']}<br>({r['raw_column']})" for _, r in df.iterrows()]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Bar trace
    fig.add_trace(
        go.Bar(
            x=labels,
            y=df["ng_count"],
            name="NG 건수",
            marker_color="#102c57",
            text=df["ng_count"],
            textposition="outside"
        ),
        secondary_y=False
    )

    # Line trace
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=df["cum_pct"],
            name="누적 비율 (%)",
            mode="lines+markers+text",
            line=dict(color="#dc3545", width=2.5),
            text=[f"{p:.1f}%" for p in df["cum_pct"]],
            textposition="top center"
        ),
        secondary_y=True
    )

    # 80% line
    fig.add_hline(y=80, line_dash="dash", line_color="#6c757d", secondary_y=True, annotation_text="80% 기준선")

    fig.update_layout(
        title=dict(text="품질 특성별 불량 발생 파레토 분석 (Pareto Chart)", font=dict(size=16, color="#102c57")),
        margin=dict(l=50, r=50, t=70, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        template="plotly_white",
        height=450
    )
    fig.update_yaxes(title_text="NG 건수 (Count)", secondary_y=False)
    fig.update_yaxes(title_text="누적 비율 (%)", range=[0, 110], secondary_y=True)

    return json.loads(fig.to_json())


def create_plotly_time_trend(interval_df: pd.DataFrame) -> Dict[str, Any]:
    """Generates Plotly Time-series Trend JSON dict."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    x_labels = interval_df["period_label"].tolist()

    # OK / NG stacked bars
    fig.add_trace(
        go.Bar(x=x_labels, y=interval_df["ok_count"], name="OK 건수", marker_color="#28a745", opacity=0.8),
        secondary_y=False
    )
    fig.add_trace(
        go.Bar(x=x_labels, y=interval_df["ng_count"], name="NG 건수", marker_color="#dc3545", opacity=0.9),
        secondary_y=False
    )

    # NG rate line
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=interval_df["ng_rate_pct"],
            name="NG 비율 (%)",
            mode="lines+markers",
            line=dict(color="#fd7e14", width=3),
            marker=dict(size=7)
        ),
        secondary_y=True
    )

    fig.update_layout(
        barmode="stack",
        title=dict(text="시간대별 생산량 및 NG 비율 변동 추이", font=dict(size=16, color="#102c57")),
        margin=dict(l=50, r=50, t=70, b=90),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        template="plotly_white",
        height=450
    )
    fig.update_xaxes(tickangle=-25)
    fig.update_yaxes(title_text="검사 건수 (Count)", secondary_y=False)
    fig.update_yaxes(title_text="NG 비율 (%)", secondary_y=True)

    return json.loads(fig.to_json())


def create_plotly_heatmap(heatmap_matrix: pd.DataFrame) -> Dict[str, Any]:
    """Generates Plotly Date x Hour Heatmap JSON dict."""
    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_matrix.values,
            x=[f"{h:02d}:00" for h in heatmap_matrix.columns],
            y=heatmap_matrix.index.tolist(),
            colorscale="YlOrRd",
            text=heatmap_matrix.values,
            texttemplate="%{text}",
            colorbar=dict(title="NG 건수")
        )
    )
    fig.update_layout(
        title=dict(text="생산 일자 × 시간대별 불량 발생 히트맵", font=dict(size=16, color="#102c57")),
        margin=dict(l=60, r=50, t=60, b=60),
        xaxis=dict(title="시간대 (Hour)"),
        yaxis=dict(title="생산 일자 (Date)"),
        template="plotly_white",
        height=380
    )
    return json.loads(fig.to_json())


def create_plotly_imr(df: pd.DataFrame, col: str, spc_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Plotly I-MR Chart JSON dict."""
    vals = df[col].astype(float).values
    x = list(range(len(vals)))
    mr_vals = np.abs(np.diff(vals, prepend=vals[0])).astype(float)
    mr_vals[0] = np.nan  # MR_1 is undefined; do not draw it as a zero.

    limits = spc_info["limits"]
    spec_lim = spc_info["spec_limits"]
    viol = spc_info["violations"]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=[f"I 관리도 (Individual Chart) - {spc_info['characteristic']}", "MR 관리도 (Moving Range Chart)"],
        row_heights=[0.65, 0.35]
    )

    # I chart
    fig.add_trace(
        go.Scatter(x=x, y=vals, mode="lines+markers", marker=dict(size=4), line=dict(color="#102c57", width=1.2), name="측정값"),
        row=1, col=1
    )

    # Out of control
    ooc = viol["all_i_violations"]
    if ooc:
        fig.add_trace(
            go.Scatter(x=ooc, y=vals[ooc], mode="markers", marker=dict(size=8, color="#dc3545"), name="SPC 이상 신호"),
            row=1, col=1
        )

    # Limits lines for I
    fig.add_hline(y=limits["cl_i"], line_color="#0d6efd", line_width=1.5, annotation_text=f"SPC CL ({limits['cl_i']:.2f})", row=1, col=1)
    fig.add_hline(y=limits["ucl_i"], line_dash="dash", line_color="#fd7e14", annotation_text=f"SPC UCL ({limits['ucl_i']:.2f})", row=1, col=1)
    fig.add_hline(y=limits["lcl_i"], line_dash="dash", line_color="#fd7e14", annotation_text=f"SPC LCL ({limits['lcl_i']:.2f})", row=1, col=1)

    if spec_lim["USL"] is not None:
        fig.add_hline(y=spec_lim["USL"], line_dash="dot", line_color="#dc3545", annotation_text=f"SPEC USL ({spec_lim['USL']})", row=1, col=1)
    if spec_lim["LSL"] is not None:
        fig.add_hline(y=spec_lim["LSL"], line_dash="dot", line_color="#dc3545", annotation_text=f"SPEC LSL ({spec_lim['LSL']})", row=1, col=1)

    # MR chart
    fig.add_trace(
        go.Scatter(x=x, y=mr_vals, mode="lines+markers", marker=dict(size=3), line=dict(color="#495057", width=1), name="이동범위 (MR)"),
        row=2, col=1
    )
    fig.add_hline(y=limits["cl_mr"], line_color="#0d6efd", line_width=1.2, annotation_text=f"MR CL ({limits['cl_mr']:.2f})", row=2, col=1)
    fig.add_hline(y=limits["ucl_mr"], line_dash="dash", line_color="#fd7e14", annotation_text=f"MR UCL ({limits['ucl_mr']:.2f})", row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=520
    )
    fig.update_yaxes(title_text=f"[{spc_info['unit']}]", row=1, col=1)
    fig.update_yaxes(title_text=f"MR [{spc_info['unit']}]", row=2, col=1)
    fig.update_xaxes(title_text="측정 순서 (Sample Sequence)", row=2, col=1)

    return json.loads(fig.to_json())


def create_plotly_vision(vision_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Plotly C-chart JSON dict."""
    rates = vision_info["rate_array"]
    x = list(range(len(rates)))
    cl = vision_info["cl"]
    ucl = vision_info["ucl"]
    lcl = vision_info["lcl"]
    usl = vision_info["spec_limit_usl"]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(x=x, y=rates, mode="lines+markers", marker=dict(size=4), line=dict(color="#102c57", width=1.2), name="결함수")
    )

    ooc = vision_info["ooc_indices"]
    if ooc:
        ooc_y = [rates[i] for i in ooc]
        fig.add_trace(
            go.Scatter(x=ooc, y=ooc_y, mode="markers", marker=dict(size=8, color="#dc3545"), name="SPC 이상 신호")
        )

    fig.add_hline(y=cl, line_color="#0d6efd", line_width=1.5, annotation_text=f"SPC CL ({cl:.2f})")
    fig.add_hline(y=ucl, line_dash="dash", line_color="#fd7e14", annotation_text=f"SPC UCL ({ucl:.2f})")
    fig.add_hline(y=lcl, line_dash="dash", line_color="#fd7e14", annotation_text=f"SPC LCL ({lcl:.2f})")

    if usl is not None:
        fig.add_hline(y=usl, line_dash="dot", line_color="#dc3545", annotation_text=f"SPEC 허용 상한 ({usl}개)")

    fig.update_layout(
        title=dict(text=f"{vision_info['chart_type']} - {vision_info['characteristic']}", font=dict(size=16, color="#102c57")),
        template="plotly_white",
        margin=dict(l=50, r=50, t=60, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=450
    )
    fig.update_xaxes(title_text="측정 순서 (Sample Sequence)")
    fig.update_yaxes(title_text=f"결함 수 [{vision_info['unit']}]")

    return json.loads(fig.to_json())


def create_plotly_process_timeline(raw_df: pd.DataFrame, hotspots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates Process Conditions Timeline with Hotspot bands."""
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=["생산 속도 (Line Speed)", "건조 온도 (Drying Temp)", "롤 압력 (Roll Pressure)"])

    t = raw_df["timestamp"].astype(str).tolist()

    configs = [
        ("line_speed_m_min", "#0d6efd", 1),
        ("drying_temperature_c", "#fd7e14", 2),
        ("roll_pressure", "#198754", 3)
    ]

    for col, color, row_idx in configs:
        if col in raw_df.columns:
            fig.add_trace(
                go.Scatter(x=t, y=raw_df[col], mode="lines", line=dict(color=color, width=1.3), name=col),
                row=row_idx, col=1
            )
            # Add hotspot shaded shapes
            for hs in hotspots:
                s_t = str(hs["start_time"])
                e_t = str(hs["end_time"])
                fig.add_vrect(x0=s_t, x1=e_t, fillcolor="#dc3545", opacity=0.18, line_width=0, row=row_idx, col=1)

    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        margin=dict(l=50, r=50, t=50, b=60),
        height=540
    )
    fig.update_yaxes(title_text="m/min", row=1, col=1)
    fig.update_yaxes(title_text="°C", row=2, col=1)
    fig.update_yaxes(title_text="bar", row=3, col=1)
    fig.update_xaxes(title_text="시간 (Timestamp)", row=3, col=1)

    return json.loads(fig.to_json())


def create_plotly_bar_compare(stats: List[Dict[str, Any]], key_col: str, title: str) -> Dict[str, Any]:
    """Generates LOT or Machine comparison bar chart."""
    df = pd.DataFrame(stats)
    if df.empty:
        fig = go.Figure()
        return json.loads(fig.to_json())

    fig = go.Figure(
        data=go.Bar(
            x=df[key_col],
            y=df["ng_rate_pct"],
            marker_color="#102c57",
            text=[f"{v:.1f}%" for v in df["ng_rate_pct"]],
            textposition="outside"
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#102c57")),
        template="plotly_white",
        margin=dict(l=40, r=40, t=50, b=60),
        showlegend=False,
        height=380
    )
    fig.update_xaxes(tickangle=-25)
    fig.update_yaxes(title_text="NG 비율 (%)")
    return json.loads(fig.to_json())


def generate_html_report(
    summary_obj: Dict[str, Any],
    quality_summary: Dict[str, Any],
    hotspots: Any,
    process_correlations: List[Dict[str, Any]],
    capability_results: Dict[str, Any],
    interval_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    spc_results: Dict[str, Any],
    vision_results: Dict[str, Any],
    heatmap_matrix: pd.DataFrame,
    output_path: str | Path,
    interval_minutes: int = 60
) -> str:
    """
    Renders the Jinja2 HTML template into a self-contained responsive HTML report.
    """
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html")

    # Read CSS
    css_path = template_dir / "report.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    # Embedded Plotly.js for 100% offline standalone functionality
    plotly_js = pyo.get_plotlyjs()

    # Extract severe and warning lists
    if isinstance(hotspots, dict):
        hotspot_data = hotspots
        severe_hotspots = hotspots.get("severe_hotspots", [])
    else:
        hotspot_data = {
            "severe_hotspots": hotspots,
            "warning_clusters": [],
            "all_ng_periods": hotspots,
            "summary_counts": {"total_intervals": len(interval_df), "minor_count": 0, "clean_intervals": 0}
        }
        severe_hotspots = hotspots

    # Build plotly payloads
    plotly_payload = {
        "pareto": create_plotly_pareto(quality_summary.get("char_stats", [])),
        "time_trend": create_plotly_time_trend(interval_df),
        "heatmap": create_plotly_heatmap(heatmap_matrix),
        "process_timeline": create_plotly_process_timeline(raw_df, severe_hotspots),
        "lot_compare": create_plotly_bar_compare(quality_summary.get("lot_stats", []), "lot_id", "LOT별 불량률 (%)"),
        "machine_compare": create_plotly_bar_compare(quality_summary.get("machine_stats", []), "machine_id", "설비별 불량률 (%)")
    }

    # Add SPC payloads
    for col, spc_info in spc_results.items():
        plotly_payload[f"spc_{col}"] = create_plotly_imr(raw_df, col, spc_info)

    # Add Vision payloads
    for col, v_info in vision_results.items():
        plotly_payload[f"vision_{col}"] = create_plotly_vision(v_info)

    rendered_html = template.render(
        css_content=css_content,
        plotly_js=plotly_js,
        plotly_payload_json=json.dumps(plotly_payload),
        summary=quality_summary,
        automated_summary=summary_obj,
        hotspot_data=hotspot_data,
        hotspots=severe_hotspots,
        process_correlations=process_correlations,
        capability=capability_results,
        interval_minutes=interval_minutes,
        baseline_n=min(raw_df.shape[0], int(summary_obj.get("baseline_n", 200))),
        spc_select_options=[(k, v.get("characteristic", k)) for k, v in spc_results.items()],
        vision_select_options=[(k, v.get("characteristic", k)) for k, v in vision_results.items()]
    )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(rendered_html, encoding="utf-8")

    return str(out_file)
