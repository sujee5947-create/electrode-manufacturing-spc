"""
Visualization Module
Generates high-resolution static charts for PPT reports and Plotly figures for HTML/Streamlit.
Strictly adheres to Global User Rules:
- No text/element overlap
- Wide width for time series
- No legends on single-series charts
- Top/bottom legends for multi-series charts
- Clear distinction between SPEC limits and SPC control limits
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import numpy as np


# Choose a Korean-capable installed font (Windows / Linux compatible).
from matplotlib import font_manager
_available_fonts = {font.name for font in font_manager.fontManager.ttflist}
_plot_font = next((font for font in ('Malgun Gothic', 'NanumGothic', 'NanumSquare',
                                   'Noto Sans CJK KR', 'UnGraphic', 'DejaVu Sans')
                   if font in _available_fonts), 'DejaVu Sans')
sns.set_theme(style="whitegrid", font=_plot_font)
plt.rcParams['font.sans-serif'] = [_plot_font, 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def plot_pareto_chart(char_stats: List[Dict[str, Any]], output_path: str | Path) -> str:
    """
    Pareto chart of defects by quality characteristic.
    """
    df = pd.DataFrame(char_stats)
    df = df[df["ng_count"] > 0].sort_values("ng_count", ascending=False).reset_index(drop=True)
    if df.empty:
        # Dummy empty chart
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "규격 이탈(NG) 항목 없음", ha="center", va="center", fontsize=14)
        fig.tight_layout()
        fig.savefig(output_path, dpi=200)
        plt.close(fig)
        return str(output_path)

    df["cum_pct"] = df["ng_count"].cumsum() / df["ng_count"].sum() * 100

    fig, ax1 = plt.subplots(figsize=(11, 5.5))
    x = range(len(df))
    labels = [f"{r['characteristic']}\n({r['raw_column']})" for _, r in df.iterrows()]

    # Bar chart
    bars = ax1.bar(x, df["ng_count"], color="#1f77b4", width=0.55, edgecolor="#0d47a1")
    ax1.set_ylabel("NG 건수 (Defect Count)", fontsize=11, fontweight="bold", color="#0d47a1", labelpad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10, rotation=15, ha="right")
    ax1.set_ylim(0, max(df["ng_count"]) * 1.25)

    # Data labels on bars
    for bar in bars:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., h + 0.3, f"{int(h)}건",
                 ha="center", va="bottom", fontsize=10, fontweight="bold", color="#1f77b4")

    # Cumulative line
    ax2 = ax1.twinx()
    ax2.plot(x, df["cum_pct"], color="#d62728", marker="o", linewidth=2.2, markersize=6)
    ax2.set_ylabel("누적 비율 (Cumulative %)", fontsize=11, fontweight="bold", color="#d62728", labelpad=10)
    ax2.set_ylim(0, 110)
    ax2.grid(False)

    for i, pct in enumerate(df["cum_pct"]):
        ax2.text(i, pct + 2.5, f"{pct:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#d62728")

    # 80% line
    ax2.axhline(80, color="#7f7f7f", linestyle="--", alpha=0.7, linewidth=1.2)
    ax2.text(len(df)-0.6, 81.5, "80% 기준선", color="#555555", fontsize=9, fontstyle="italic")

    plt.title("품질 특성별 불량(NG) 발생 파레토 차트 (Pareto Analysis)", fontsize=14, fontweight="bold", pad=16)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_time_ng_trend(interval_df: pd.DataFrame, output_path: str | Path) -> str:
    """
    Time-series trend: Dual-axis plot of OK/NG counts and NG Rate.
    Wide width (>20cm) to prevent date/time overlapping.
    """
    fig, ax1 = plt.subplots(figsize=(14, 5.5))

    x_labels = [row["period_label"].split(" ")[1] if " " in row["period_label"] else row["period_label"] for _, row in interval_df.iterrows()]
    x_indices = np.arange(len(interval_df))

    # Stacked Bars: OK and NG
    w = 0.55
    ax1.bar(x_indices, interval_df["ok_count"], label="OK 건수", color="#2ca02c", alpha=0.75, width=w)
    ax1.bar(x_indices, interval_df["ng_count"], bottom=interval_df["ok_count"], label="NG 건수", color="#d62728", alpha=0.85, width=w)
    ax1.set_ylabel("검사 건수 (Inspection Count)", fontsize=11, fontweight="bold", color="#2c3e50", labelpad=10)
    ax1.set_ylim(0, max(interval_df["total_count"]) * 1.3)

    # NG rate line
    ax2 = ax1.twinx()
    line = ax2.plot(x_indices, interval_df["ng_rate_pct"], color="#ff7f0e", marker="s", linewidth=2.5, markersize=6, label="NG 비율 (%)")
    ax2.set_ylabel("NG 비율 (%)", fontsize=11, fontweight="bold", color="#d35400", labelpad=10)
    ax2.set_ylim(0, max(max(interval_df["ng_rate_pct"]) * 1.3, 10))
    ax2.grid(False)

    # Annotate high NG rate points
    for idx, row in interval_df.iterrows():
        if row["ng_rate_pct"] >= 10.0 or row["ng_count"] >= 3:
            ax2.annotate(
                f"{row['ng_rate_pct']:.1f}%\n({row['ng_count']}건)",
                (idx, row["ng_rate_pct"]),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#b71c1c",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#ffebee", edgecolor="#e57373", alpha=0.85)
            )

    # X axis step control to avoid overlap
    step = max(1, len(x_indices) // 14)
    ax1.set_xticks(x_indices[::step])
    ax1.set_xticklabels(x_labels[::step], rotation=25, ha="right", fontsize=9.5)
    ax1.set_xlabel("시간 구간 (Time Interval)", fontsize=11, fontweight="bold", labelpad=8)

    # Unified Legend at top
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, frameon=True, fontsize=10)

    plt.title("시간대별 생산량 및 NG 불량률 추이 (Time-series Quality Trend)", fontsize=13, fontweight="bold", y=1.18)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_spc_imr_single(
    df: pd.DataFrame,
    col: str,
    spc_info: Dict[str, Any],
    output_path: str | Path
) -> str:
    """
    Generates I and MR chart for a single continuous characteristic.
    Distinguishes SPEC lines (dashed green/red) and SPC limits (solid/dotted orange/blue).
    """
    fig, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True, gridspec_kw={'height_ratios': [2, 1.2]})

    vals = df[col].astype(float).values
    x = np.arange(len(vals))
    mr_vals = np.abs(np.diff(vals, prepend=vals[0])).astype(float)
    mr_vals[0] = np.nan  # First moving range is undefined, not zero.

    limits = spc_info["limits"]
    spec_lim = spc_info["spec_limits"]
    violations = spc_info["violations"]

    # --- I Chart ---
    ax_i.plot(x, vals, color="#2c3e50", marker="o", markersize=3, linewidth=1.0, alpha=0.8, label="측정값 (Individual)")
    
    # Highlight violations
    ooc_pts = violations["all_i_violations"]
    if ooc_pts:
        ax_i.scatter(ooc_pts, vals[ooc_pts], color="#e74c3c", s=36, zorder=5, label="SPC 이상 신호 (OOC)")

    # SPC Limits
    ax_i.axhline(limits["cl_i"], color="#2980b9", linestyle="-", linewidth=1.5, label=f"SPC CL ({limits['cl_i']:.2f})")
    ax_i.axhline(limits["ucl_i"], color="#e67e22", linestyle="--", linewidth=1.4, label=f"SPC UCL ({limits['ucl_i']:.2f})")
    ax_i.axhline(limits["lcl_i"], color="#e67e22", linestyle="--", linewidth=1.4, label=f"SPC LCL ({limits['lcl_i']:.2f})")

    # SPEC Limits
    if spec_lim["USL"] is not None:
        ax_i.axhline(spec_lim["USL"], color="#c0392b", linestyle=":", linewidth=1.8, label=f"SPEC USL ({spec_lim['USL']})")
    if spec_lim["LSL"] is not None:
        ax_i.axhline(spec_lim["LSL"], color="#c0392b", linestyle=":", linewidth=1.8, label=f"SPEC LSL ({spec_lim['LSL']})")

    # Baseline shading
    n_base = limits["baseline_n"]
    ax_i.axvspan(0, n_base, color="#ecf0f1", alpha=0.5, label=f"기준 기간 (Baseline {n_base})")

    ax_i.set_ylabel(f"측정값 [{spc_info['unit']}]", fontsize=10, fontweight="bold", labelpad=8)
    ax_i.set_title(f"I 관리도 (Individual Chart) - {spc_info['characteristic']}", fontsize=12, fontweight="bold")
    ax_i.legend(loc="upper center", bbox_to_anchor=(0.5, 1.25), ncol=4, frameon=True, fontsize=8.5)

    # --- MR Chart ---
    ax_mr.plot(x, mr_vals, color="#34495e", marker=".", markersize=2.5, linewidth=0.9, alpha=0.7)
    mr_ooc = violations["mr_rule1"]
    if mr_ooc:
        ax_mr.scatter(mr_ooc, mr_vals[mr_ooc], color="#e74c3c", s=30, zorder=5)

    ax_mr.axhline(limits["cl_mr"], color="#2980b9", linestyle="-", linewidth=1.4, label=f"MR CL ({limits['cl_mr']:.2f})")
    ax_mr.axhline(limits["ucl_mr"], color="#e67e22", linestyle="--", linewidth=1.3, label=f"MR UCL ({limits['ucl_mr']:.2f})")
    ax_mr.axvspan(0, n_base, color="#ecf0f1", alpha=0.5)

    ax_mr.set_ylabel(f"MR [{spc_info['unit']}]", fontsize=10, fontweight="bold", labelpad=8)
    ax_mr.set_xlabel("측정 순서 (Sample Sequence)", fontsize=10, fontweight="bold", labelpad=6)
    ax_mr.legend(loc="upper right", frameon=True, fontsize=8.5)

    if spc_info.get("machine_mix_warning"):
        fig.text(0.02, 0.015, "WARNING: 혼합 설비 관리한계는 과거 결과 비교용입니다. 설비별 관리한계를 확인하세요.",
                 color="#b91c1c", fontsize=9, ha="left")
        fig.tight_layout(rect=[0, 0.045, 1, 1])
    else:
        fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_vision_cchart(vision_info: Dict[str, Any], output_path: str | Path) -> str:
    """
    Generates C-chart or U-chart for vision defects.
    """
    fig, ax = plt.subplots(figsize=(13, 5))
    rates = np.array(vision_info["rate_array"])
    ucl_arr = np.array(vision_info["ucl_array"])
    lcl_arr = np.array(vision_info["lcl_array"])
    cl = vision_info["cl"]
    x = np.arange(len(rates))

    ax.plot(x, rates, color="#2c3e50", marker="o", markersize=3, linewidth=1.0, alpha=0.75, label="결함수 (Defect Count)")
    
    # Highlight OOC
    ooc = vision_info["ooc_indices"]
    if ooc:
        ax.scatter(ooc, rates[ooc], color="#e74c3c", s=36, zorder=5, label="SPC 관리한계 이탈")

    # SPEC limit
    usl = vision_info["spec_limit_usl"]
    if usl is not None:
        ax.axhline(usl, color="#c0392b", linestyle=":", linewidth=1.8, label=f"SPEC 허용 상한 ({usl}개)")

    ax.axhline(cl, color="#2980b9", linestyle="-", linewidth=1.4, label=f"SPC CL ({cl:.2f})")
    ax.plot(x, ucl_arr, color="#e67e22", linestyle="--", linewidth=1.4, label=f"SPC UCL ({np.mean(ucl_arr):.2f})")
    ax.plot(x, lcl_arr, color="#e67e22", linestyle="--", linewidth=1.4, label=f"SPC LCL ({np.mean(lcl_arr):.2f})")

    ax.set_ylabel(f"결함 수 [{vision_info['unit']}]", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_xlabel("측정 순서 (Sample Sequence)", fontsize=10, fontweight="bold", labelpad=6)
    ax.set_title(f"{vision_info['chart_type']} - {vision_info['characteristic']}", fontsize=12, fontweight="bold", pad=12)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=4, frameon=True, fontsize=9)

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_process_conditions_timeline(
    raw_df: pd.DataFrame,
    hotspots: List[Dict[str, Any]],
    output_path: str | Path
) -> str:
    """
    Subplots for 3 process conditions (Line Speed, Temp, Pressure) with Hotspot shading.
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    t = pd.to_datetime(raw_df["timestamp"])

    p_configs = [
        ("line_speed_m_min", "생산 속도 (Line Speed)", "m/min", "#2980b9"),
        ("drying_temperature_c", "건조 온도 (Drying Temp)", "°C", "#d35400"),
        ("roll_pressure", "롤 압력 (Roll Pressure)", "bar", "#27ae60")
    ]

    for ax, (col, title, unit, color) in zip(axes, p_configs):
        if col in raw_df.columns:
            ax.plot(t, raw_df[col], color=color, linewidth=1.2, alpha=0.85)
            ax.set_ylabel(f"{unit}", fontsize=10, fontweight="bold")
            ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=4)

            # Shade hotspots
            for hs in hotspots:
                s_t = pd.to_datetime(hs["start_time"])
                e_t = pd.to_datetime(hs["end_time"])
                ax.axvspan(s_t, e_t, color="#e74c3c", alpha=0.22)

    # Format x axis dates
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    axes[-1].set_xlabel("일시 (Timestamp)", fontsize=10, fontweight="bold", labelpad=8)
    fig.autofmt_xdate(rotation=25)

    plt.suptitle("공정 조건 시계열 추이 및 NG 집중 구간 (Process Conditions with Hotspots)", fontsize=13, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_date_hour_heatmap(heatmap_matrix: pd.DataFrame, output_path: str | Path) -> str:
    """
    Date x Hour heatmap of NG counts.
    """
    fig, ax = plt.subplots(figsize=(12, 4.8))
    sns.heatmap(
        heatmap_matrix,
        cmap="YlOrRd",
        annot=True,
        fmt="d",
        linewidths=0.5,
        cbar_kws={'label': 'NG 불량 건수'},
        ax=ax
    )
    ax.set_title("일자별 × 시간대별 불량(NG) 발생 분포 히트맵", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("시간대 (Hour of Day)", fontsize=10, fontweight="bold")
    ax.set_ylabel("생산 일자 (Date)", fontsize=10, fontweight="bold")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)


def plot_lot_machine_comparison(quality_summary: Dict[str, Any], output_path: str | Path) -> str:
    """
    Side-by-side comparison of LOT-level and Machine-level NG rates.
    """
    lot_df = pd.DataFrame(quality_summary.get("lot_stats", []))
    m_df = pd.DataFrame(quality_summary.get("machine_stats", []))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # LOT comparison
    if not lot_df.empty:
        x_lot = np.arange(len(lot_df))
        bars1 = ax1.bar(x_lot, lot_df["ng_rate_pct"], color="#3498db", width=0.5)
        ax1.set_title("LOT별 불량률 (%)", fontsize=12, fontweight="bold")
        ax1.set_ylabel("NG 비율 (%)", fontsize=10, fontweight="bold")
        ax1.set_xticks(x_lot)
        ax1.set_xticklabels(lot_df["lot_id"], rotation=30, ha="right", fontsize=9)
        ax1.set_ylim(0, max(lot_df["ng_rate_pct"]) * 1.25)
        for b in bars1:
            h = b.get_height()
            ax1.text(b.get_x() + b.get_width()/2., h + 0.2, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    # Machine comparison
    if not m_df.empty:
        x_m = np.arange(len(m_df))
        bars2 = ax2.bar(x_m, m_df["ng_rate_pct"], color="#9b59b6", width=0.45)
        ax2.set_title("설비(Machine)별 불량률 (%)", fontsize=12, fontweight="bold")
        ax2.set_ylabel("NG 비율 (%)", fontsize=10, fontweight="bold")
        ax2.set_xticks(x_m)
        ax2.set_xticklabels(m_df["machine_id"], fontsize=9.5)
        ax2.set_ylim(0, max(m_df["ng_rate_pct"]) * 1.25)
        for b in bars2:
            h = b.get_height()
            ax2.text(b.get_x() + b.get_width()/2., h + 0.2, f"{h:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.suptitle("생산 단위(LOT) 및 설비별 품질 불량률 비교", fontsize=13, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return str(output_path)
