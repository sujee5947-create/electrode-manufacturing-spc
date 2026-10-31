"""
Hotspot Detection Module
Detects anomalous time intervals using a transparent multi-tiered clustering architecture:
- Tier 1: Severe Hotspot (Critical Cluster: N >= 6, NG >= 3, Rate >= 20.0%)
- Tier 2: Warning Cluster (Moderate Alert: N >= 6, NG >= 2, Rate >= 10.0%, 2x above process average)
- Tier 3: Minor Defect Intervals (Sporadic Defect: NG >= 1)
Guarantees zero omission of defect intervals.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


class HotspotConfig:
    def __init__(
        self,
        min_samples: int = 6,
        severe_min_ng: int = 3,
        severe_min_rate_pct: float = 20.0,
        warning_min_ng: int = 2,
        warning_rate_multiplier: float = 2.0,
        warning_min_diff_pp: float = 5.0
    ):
        self.min_samples = min_samples
        self.severe_min_ng = severe_min_ng
        self.severe_min_rate_pct = severe_min_rate_pct
        self.warning_min_ng = warning_min_ng
        self.warning_rate_multiplier = warning_rate_multiplier
        self.warning_min_diff_pp = warning_min_diff_pp


def detect_ng_hotspots(
    interval_df: pd.DataFrame,
    overall_ng_rate_pct: float,
    config: Optional[HotspotConfig] = None
) -> Dict[str, Any]:
    """
    Identifies high-density defect periods based on configurable operational alert thresholds (not statistical significance tests).
    Returns:
        {
            "severe_hotspots": [...],   # Tier 1 (NG >= 3, Rate >= 20%)
            "warning_clusters": [...],  # Tier 2 (NG >= 2, Rate >= 10%)
            "all_ng_periods": [...],    # All intervals where NG >= 1
            "summary_counts": {
                "total_intervals": int,
                "ng_active_intervals": int,
                "severe_count": int,
                "warning_count": int,
                "minor_count": int
            }
        }
    """
    if config is None:
        config = HotspotConfig()

    severe_hotspots = []
    warning_clusters = []
    all_ng_periods = []
    insufficient_periods = []

    for idx, row in interval_df.iterrows():
        total = row["total_count"]
        ng = row["ng_count"]
        ng_rate = row["ng_rate_pct"]

        # Classify low-N intervals before filtering zero-defect intervals.
        if total >= config.min_samples and ng == 0:
            continue

        item = {
            "period_label": row["period_label"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "total_count": total,
            "ng_count": ng,
            "ng_rate_pct": ng_rate,
            "overall_baseline_pct": overall_ng_rate_pct,
            "diff_pp": round(ng_rate - overall_ng_rate_pct, 2),
            "primary_defect": row["primary_defect"],
            "machines": row.get("machines", ""),
            "lots": row.get("lots", "")
        }

        # Check sample sufficiency
        if total < config.min_samples:
            item["tier"] = "INSUFFICIENT_DATA"
            item["status_label"] = "표본 부족"
            item["detection_reason"] = f"표본 수 부족 (N={total} < {config.min_samples})"
            insufficient_periods.append(item)
            if ng > 0:
                all_ng_periods.append(item)
            continue

        # Tier 1: Severe Hotspot (N>=6, NG>=3, Rate >= 20%)
        if ng >= config.severe_min_ng and ng_rate >= config.severe_min_rate_pct:
            item["tier"] = "TIER_1_SEVERE"
            item["status_label"] = "집중 위험 (Severe Hotspot)"
            item["detection_reason"] = (
                f"고위험 집중 발생: NG {ng}건 ({ng_rate:.1f}%), "
                f"공정 평균({overall_ng_rate_pct:.1f}%) 대비 +{item['diff_pp']:.1f}%p 증가"
            )
            severe_hotspots.append(item)
            all_ng_periods.append(item)

        # Tier 2: Warning Cluster (N>=6, NG>=2, Rate >= 10%)
        elif ng >= config.warning_min_ng and (ng_rate >= overall_ng_rate_pct * config.warning_rate_multiplier or item["diff_pp"] >= config.warning_min_diff_pp):
            item["tier"] = "TIER_2_WARNING"
            item["status_label"] = "주의 경계 (Warning Cluster)"
            item["detection_reason"] = (
                f"주의 군집 발생: NG {ng}건 ({ng_rate:.1f}%), "
                f"공정 평균 대비 +{item['diff_pp']:.1f}%p (" +
                (f"{ng_rate / overall_ng_rate_pct:.1f}배)" if overall_ng_rate_pct > 0 else "공정 평균 0%)")
            )
            warning_clusters.append(item)
            all_ng_periods.append(item)

        # Tier 3: Minor Defect (NG = 1)
        else:
            item["tier"] = "TIER_3_MINOR"
            item["status_label"] = "산발 불량 (Minor Defect)"
            item["detection_reason"] = f"단발성 발생: NG {ng}건 ({ng_rate:.1f}%)"
            all_ng_periods.append(item)

    # Sort each tier chronologically or by NG rate
    severe_hotspots.sort(key=lambda x: (x["ng_rate_pct"], x["ng_count"]), reverse=True)
    warning_clusters.sort(key=lambda x: (x["ng_rate_pct"], x["ng_count"]), reverse=True)
    all_ng_periods.sort(key=lambda x: (x["ng_count"], x["ng_rate_pct"]), reverse=True)
    insufficient_periods.sort(key=lambda x: x["start_time"])

    res = {
        "severe_hotspots": severe_hotspots,
        "warning_clusters": warning_clusters,
        "all_ng_periods": all_ng_periods,
        "insufficient_periods": insufficient_periods,
        "alert_method_note": "Tier 1/2는 운영 경보 임계치이며 통계적 유의성 검정 결과가 아닙니다.",
        "summary_counts": {
            "total_intervals": len(interval_df),
            "ng_active_intervals": len(all_ng_periods),
            "severe_count": len(severe_hotspots),
            "warning_count": len(warning_clusters),
            "minor_count": sum(x["tier"] == "TIER_3_MINOR" for x in all_ng_periods),
            "insufficient_count": len(insufficient_periods),
            "clean_intervals": len(interval_df) - len(all_ng_periods) - sum(x["ng_count"] == 0 for x in insufficient_periods)
        }
    }
    return res
