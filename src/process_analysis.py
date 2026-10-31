"""
Process Condition Correlation Analysis Module
Compares process conditions (line speed, drying temperature, roll pressure)
across Before (30m), During, and After (30m) windows for detected NG hotspots.
Enforces strict engineering attribution language.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


PROCESS_LABELS = {
    "line_speed_m_min": {"name": "생산 속도 (Line Speed)", "unit": "m/min"},
    "drying_temperature_c": {"name": "건조 온도 (Drying Temp)", "unit": "°C"},
    "roll_pressure": {"name": "롤 압력 (Roll Pressure)", "unit": "bar"}
}


def analyze_hotspot_process_correlation(
    df: pd.DataFrame,
    hotspot: Dict[str, Any],
    buffer_minutes: int = 30,
    process_cols: Optional[List[str]] = None,
    event_log_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Compares process conditions across Before, During, and After periods of an NG hotspot.
    """
    if process_cols is None:
        process_cols = ["line_speed_m_min", "drying_temperature_c", "roll_pressure"]

    work_df = df.copy()
    work_df["timestamp"] = pd.to_datetime(work_df["timestamp"])

    t_start = pd.to_datetime(hotspot["start_time"])
    t_end = pd.to_datetime(hotspot["end_time"])

    # Define windows
    before_start = t_start - pd.Timedelta(minutes=buffer_minutes)
    before_end = t_start

    during_start = t_start
    during_end = t_end

    after_start = t_end
    after_end = t_end + pd.Timedelta(minutes=buffer_minutes)

    df_before = work_df[(work_df["timestamp"] >= before_start) & (work_df["timestamp"] < before_end)]
    df_during = work_df[(work_df["timestamp"] >= during_start) & (work_df["timestamp"] < during_end)]
    df_after = work_df[(work_df["timestamp"] >= after_start) & (work_df["timestamp"] < after_end)]

    windows = {
        "before": {"df": df_before, "label": f"전 {buffer_minutes}분 ({before_start.strftime('%H:%M')}~{before_end.strftime('%H:%M')})"},
        "during": {"df": df_during, "label": f"집중 구간 ({during_start.strftime('%H:%M')}~{during_end.strftime('%H:%M')})"},
        "after": {"df": df_after, "label": f"후 {buffer_minutes}분 ({after_start.strftime('%H:%M')}~{after_end.strftime('%H:%M')})"}
    }

    process_metrics = {}
    for p in process_cols:
        meta = PROCESS_LABELS.get(p, {"name": p, "unit": ""})
        p_res = {"name": meta["name"], "unit": meta["unit"], "windows": {}}

        prev_mean = None
        for w_key in ["before", "during", "after"]:
            w_df = windows[w_key]["df"]
            n_pts = len(w_df)
            if n_pts > 0 and p in w_df.columns:
                s = w_df[p].dropna().astype(float)
                m = float(s.mean()) if len(s) > 0 else None
                s_min = float(s.min()) if len(s) > 0 else None
                s_max = float(s.max()) if len(s) > 0 else None
                s_std = float(s.std(ddof=1)) if len(s) > 1 else 0.0
            else:
                m, s_min, s_max, s_std = None, None, None, None

            delta = None
            pct_change = None
            if m is not None and prev_mean is not None:
                delta = round(m - prev_mean, 2)
                if abs(prev_mean) > 1e-6:
                    pct_change = round((m - prev_mean) / prev_mean * 100, 2)

            p_res["windows"][w_key] = {
                "count": n_pts,
                "mean": round(m, 2) if m is not None else None,
                "min": round(s_min, 2) if s_min is not None else None,
                "max": round(s_max, 2) if s_max is not None else None,
                "std": round(s_std, 2) if s_std is not None else None,
                "delta_from_prev": delta,
                "pct_change_from_prev": pct_change
            }
            if m is not None:
                prev_mean = m

        process_metrics[p] = p_res

    # Check equipment events
    event_status = "확인 불가 (설비 이벤트 로그 미제공)"
    event_details = []
    if event_log_df is not None and not event_log_df.empty and "timestamp" in event_log_df.columns:
        ev_sub = event_log_df[
            (event_log_df["timestamp"] >= before_start) & (event_log_df["timestamp"] <= after_end)
        ]
        if not ev_sub.empty:
            event_status = f"{len(ev_sub)}건의 설비 이벤트 기록됨"
            event_details = ev_sub.to_dict(orient="records")
        else:
            event_status = "해당 구간 설비 이벤트 없음"

    # Construct strict engineering 3-tier statement
    during_total = len(df_during)
    during_ng = int((df_during["overall_judgment"] == "NG").sum()) if "overall_judgment" in df_during.columns else hotspot["ng_count"]
    during_ng_rate = (during_ng / during_total * 100) if during_total > 0 else hotspot["ng_rate_pct"]
    primary_def = hotspot.get("primary_defect", "불량")

    # Confirmed fact
    confirmed_fact = (
        f"{hotspot['period_label']} 구간에서 전체 {during_total}건 중 {during_ng}건의 NG가 발생하여 "
        f"불량률 {during_ng_rate:.1f}%를 기록하였으며, 주요 불량 유형은 '{primary_def}'로 확인되었습니다."
    )

    # Associated changes
    changes_desc = []
    for p, meta in process_metrics.items():
        dur_w = meta["windows"]["during"]
        bef_w = meta["windows"]["before"]
        if dur_w["delta_from_prev"] not in (None, 0) and bef_w["mean"] is not None:
            unit = meta["unit"]
            changes_desc.append(
                f"{meta['name']} 평균은 직전 {buffer_minutes}분({bef_w['mean']}{unit}) 대비 "
                f"{abs(dur_w['delta_from_prev'])}{unit} {'상승' if dur_w['delta_from_prev'] > 0 else '하강'}"
                f"({dur_w['mean']}{unit})"
            )

    associated_change = (
        f"동일 시간대에 " + ", ".join(changes_desc) + "하는 공정 조건 변화가 관측되었습니다. 이는 시간상 동시 관찰일 뿐 통계적 연관성 검정 결과가 아닙니다."
        if changes_desc else "동일 시간대에 현저한 공정 조건 변화는 관측되지 않았습니다."
    )

    # Requires investigation
    requires_investigation = (
        f"공정 조건과 {primary_def} 불량이 같은 시간대에 관측되었습니다. 그러나 "
        f"상관계수, 유의성 검정 및 LOT/설비 교란인자 통제는 수행되지 않아 통계적 연관성이나 인과관계를 주장할 수 없고, "
        f"설비 운전 상태({event_status}) 및 원자재 물성 등에 대한 추가 검토가 필요합니다."
    )

    return {
        "hotspot_period": hotspot["period_label"],
        "primary_defect": primary_def,
        "windows": {k: {"label": v["label"], "count": len(v["df"])} for k, v in windows.items()},
        "process_metrics": process_metrics,
        "equipment_event_status": event_status,
        "equipment_events": event_details,
        "statements": {
            "confirmed_fact": confirmed_fact,
            "associated_change": associated_change,
            "requires_investigation": requires_investigation
        }
    }
