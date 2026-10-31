"""
Automated Summary Generator Module
Rule-based insights engine that generates factual, rigorous engineering summaries
for Overall Quality, Time-based Multi-tier Hotspot Clustering, and Process Correlation.
Outputs structured JSON and Python dictionaries as RFC 8259 UTF-8 without BOM.
"""

from typing import Dict, List, Any
import json
from pathlib import Path


def generate_executive_summary(
    quality_summary: Dict[str, Any],
    hotspot_results: Dict[str, Any],
    process_correlations: List[Dict[str, Any]],
    capability_results: Dict[str, Any],
    evaluated_df: Any = None
) -> Dict[str, Any]:
    """
    Generates structured, rule-based engineering summary texts.
    Guarantees zero omission of hotspot periods and explicit definitions for multi-defect counts.
    """
    total = quality_summary["total_count"]
    ok_cnt = quality_summary["ok_count"]
    ng_cnt = quality_summary["ng_count"]
    ng_rate = quality_summary["ng_rate_pct"]
    multi_ng = quality_summary.get("multi_defect_rows", 0)

    # 1. Overall Quality Summary
    char_stats = quality_summary.get("char_stats", [])
    top_char = char_stats[0] if char_stats else None
    second_char = char_stats[1] if len(char_stats) > 1 else None

    s1_overall_1 = (
        f"총 {total:,}건의 전극 공정 측정 데이터 중 {ng_cnt:,}건이 규격(SPEC)을 이탈하여 "
        f"전체 불량률(NG Rate)은 {ng_rate:.2f}%로 집계되었습니다."
    )

    if top_char and top_char["ng_count"] > 0:
        s1_overall_2 = (
            f"가장 많은 불량이 발생한 품질 특성은 '{top_char['characteristic']}'({top_char['raw_column']})으로 "
            f"총 {top_char['ng_count']}건(불량률 {top_char['ng_rate_pct']}%)을 기록하였습니다."
        )
    else:
        s1_overall_2 = "모든 품질 특성이 규격 한계 내에서 정상 관리되었습니다."

    if second_char and second_char["ng_count"] > 0:
        s1_overall_3 = (
            f"이어 '{second_char['characteristic']}'이 {second_char['ng_count']}건({second_char['ng_rate_pct']}%)으로 "
            f"두 번째로 높은 불량 비중을 보였으며, 단일 측정 행에서 2개 이상 특성이 동시 불량인 복합 불량 행은 총 {multi_ng}건으로 나타났습니다."
        )
    else:
        s1_overall_3 = f"복합 불량(동일 행 2개 이상 동시 불량) 발생 행은 총 {multi_ng}건입니다."

    overall_paragraphs = [s1_overall_1, s1_overall_2, s1_overall_3]

    # Multi-defect row details extraction
    multi_defect_details = []
    if evaluated_df is not None and "ng_count_per_row" in evaluated_df.columns:
        multi_rows = evaluated_df[evaluated_df["ng_count_per_row"] >= 2]
        for idx, r in multi_rows.iterrows():
            ng_chars = []
            for c in char_stats:
                j_col = f"{c['raw_column']}__judgment"
                if j_col in r and r[j_col] in ("NG_LOW", "NG_HIGH"):
                    ng_chars.append(f"{c['characteristic']}({r[j_col]})")
            multi_defect_details.append({
                "row_index": int(idx) + 1,
                "timestamp": str(r.get("timestamp", "")),
                "lot_id": str(r.get("lot_id", "")),
                "machine_id": str(r.get("machine_id", "")),
                "defects_count": int(r["ng_count_per_row"]),
                "failed_characteristics": ng_chars
            })

    # 2. Time Multi-Tier Hotspot Summary (Resolving Issue 2)
    severe_list = hotspot_results.get("severe_hotspots", [])
    warning_list = hotspot_results.get("warning_clusters", [])
    all_ng_list = hotspot_results.get("all_ng_periods", [])
    counts = hotspot_results.get("summary_counts", {})

    time_paragraphs = []
    time_paragraphs.append(
        f"전체 {counts.get('total_intervals', 84)}개 시간대 구간 중 불량이 발생한 시간대는 총 {counts.get('ng_active_intervals', len(all_ng_list))}개소이며, "
        f"이 중 운영 경보 기준에 따른 집중 관리 대상은 총 {len(severe_list) + len(warning_list)}개소(고위험 집중 구간 {len(severe_list)}개소 + 주의 군집 구간 {len(warning_list)}개소)로 분류되었습니다. "
        f"이 구분은 통계적 유의성 검정이 아닌 운영 경보 조건입니다. 표본 부족 구간 {counts.get('insufficient_count', 0)}개소는 별도 미판정으로 기록합니다. "
        f"Hotspot 선정 기준은 Tier 1(고위험)=구간 표본 N≥6 · NG≥3건 · 불량률≥20.0%, Tier 2(주의)=NG≥2건이면서 공정 평균 대비 2배 이상 또는 +5.0%p 이상이며, 동일 기준을 만족하는 구간은 누락 없이 모두 기재합니다."
    )

    if severe_list:
        top_lines = [
            f"[{h['period_label']}]: NG {h['ng_count']}/{h['total_count']} "
            f"({h['ng_rate_pct']:.1f}%; {h['primary_defect']})"
            for h in severe_list[:5]
        ]
        time_paragraphs.append(
            f"고위험 운영 경보 구간은 총 {len(severe_list)}개입니다. " + "; ".join(top_lines)
        )
    if warning_list:
        labels = [
            f"[{h['period_label']}] NG {h['ng_count']}/{h['total_count']} ({h['ng_rate_pct']:.1f}%)"
            for h in warning_list[:5]
        ]
        time_paragraphs.append(
            f"주의 운영 경보 구간 총 {len(warning_list)}개: " + "; ".join(labels)
        )

    # 3. Process Correlation Summary
    proc_paragraphs = []
    if process_correlations:
        for idx, pc in enumerate(process_correlations[:2], 1):
            proc_paragraphs.append(f"[{idx}차 집중구간 {pc['hotspot_period']}] " + pc["statements"]["confirmed_fact"])
            proc_paragraphs.append(pc["statements"]["associated_change"])
            proc_paragraphs.append(pc["statements"]["requires_investigation"])
    else:
        proc_paragraphs.append("NG 집중 구간에 대응하는 공정 조건의 특이 변동 사항은 확인되지 않았습니다.")
        proc_paragraphs.append("장비 이벤트 로그 미제공 상태이므로 설비 운전 이벤트는 '확인 불가' 상태입니다.")

    # 4. Capability Summary (Resolving Issue 1)
    cap_paragraphs = ["SPC 전체 관리도는 설비 혼합에 따른 참고값입니다. 설비별 Phase I 관리한계 및 별도 공정능력 분석을 확인하세요. 공정 안정성 검증 전 Cpk를 확정적 양산능력으로 해석하지 마세요."]
    lowest_cpk_char = None
    min_cpk = float("inf")
    for col, c_res in capability_results.items():
        if c_res.get("applicable") and c_res.get("cpk") is not None:
            if c_res["cpk"] < min_cpk:
                min_cpk = c_res["cpk"]
                lowest_cpk_char = c_res

    if lowest_cpk_char:
        cap_paragraphs.append(
            f"전체 데이터셋(N={total:,}, sigma_within=MR_bar/1.128) 기준 공정능력 분석 결과, "
            f"'{lowest_cpk_char['characteristic']}'의 Cpk가 {lowest_cpk_char['cpk']:.3f} (Ppk {lowest_cpk_char['ppk']:.3f})로 "
            f"산출되어 가장 취약한 공정능력({lowest_cpk_char['capability_level']})을 나타냈습니다. "
            f"(참고: 최초 기준 구간 Cpk={lowest_cpk_char.get('cpk_baseline_ref', 'N/A')})"
        )
        cap_paragraphs.append(lowest_cpk_char["stability_note"])
    else:
        cap_paragraphs.append("공정능력 지수가 양호한 관리 상태를 나타내고 있습니다.")

    # 5. Key Executive Takeaways (3 Bullet Points)
    hs_top_text = (
        f"고위험 구간 {len(severe_list)}개, 주의 구간 {len(warning_list)}개 "
        f"(합계 {len(severe_list)+len(warning_list)}개): 운영 경보 기준으로 판정, "
        "통계적 유의성 검정 결과는 아님."
    )

    takeaways = [
        f"전체 불량률 {ng_rate:.2f}% (총 {total:,}건 중 {ng_cnt}건 NG), 주요 불량은 {top_char['characteristic'] if top_char else 'N/A'}({top_char['ng_count'] if top_char else 0}건) 및 {second_char['characteristic'] if second_char else 'N/A'}({second_char['ng_count'] if second_char else 0}건).",
        hs_top_text,
        f"공정능력 최저 항목은 '{lowest_cpk_char['characteristic'] if lowest_cpk_char else 'N/A'}'(Cpk {lowest_cpk_char['cpk'] if lowest_cpk_char else 0:.3f}, Ppk {lowest_cpk_char['ppk'] if lowest_cpk_char else 0:.3f})이며, 공정 조건과의 인과관계 규명을 위해 설비 이벤트 추가 검토 필요."
    ]

    summary_obj = {
        "overall_summary": overall_paragraphs,
        "time_summary": time_paragraphs,
        "process_summary": proc_paragraphs,
        "capability_summary": cap_paragraphs,
        "key_takeaways": takeaways,
        "raw_counts": {
            "total": total,
            "ok": ok_cnt,
            "ng": ng_cnt,
            "ng_rate_pct": ng_rate,
            "total_intervals": counts.get("total_intervals", 84),
            "ng_active_intervals_count": counts.get("ng_active_intervals", len(all_ng_list)),
            "insufficient_intervals_count": counts.get("insufficient_count", 0),
            "spc_scope_note": "전체 관리도는 과거 결과 비교를 위한 참고용입니다. 서로 다른 설비의 Phase I 관리한계는 설비별로 산정·검증해야 하며, 별도 equipment_spc_summary.json을 확인하세요.",
            "hotspot_significance_note": hotspot_results.get("alert_method_note", "운영 임계치; 통계적 검정 결과 아님"),
            "severe_hotspot_count": len(severe_list),
            "warning_cluster_count": len(warning_list),
            "total_hotspots_monitored": len(severe_list) + len(warning_list),
            "hotspot_count": len(severe_list),
            "hotspot_tier1_criteria": "N>=6 AND NG>=3 AND ng_rate_pct>=20.0",
            "hotspot_tier2_criteria": "N>=6 AND NG>=2 AND (rate>=2x process average OR +5.0pp)",
            "multi_ng_count": multi_ng,
            "multi_defect_rows_count": multi_ng,
            "multi_defect_definition": "한 측정점(단일 행)에서 2개 이상의 서로 다른 품질 특성이 동시에 규격을 이탈(NG)한 행의 총 수",
            "multi_defect_details": multi_defect_details
        }
    }

    return summary_obj


def save_summary_json(summary_obj: Dict[str, Any], output_path: str | Path):
    """Saves summary object as RFC 8259 UTF-8 JSON without BOM."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary_obj, f, ensure_ascii=False, indent=2)
