"""
Main Entry Point
Orchestrates the entire Electrode Quality SPC Monitoring & Automated Reporting Pipeline.

Usage:
    python main.py
    python main.py --interval 60
    python main.py --spec raw data/Electrode_Quality_SPEC.xlsx --raw raw data/Electrode_Quality_Raw_Data.csv
"""

import argparse
import sys
import os
import logging
from pathlib import Path

# Setup logging
import io
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Electrode_SPC")

from src.data_loader import load_spec, load_raw_data, load_equipment_event_log
from src.spec_validator import validate_spec_and_raw
from src.quality_judgment import evaluate_quality
from src.spc_analysis import analyze_imr
from src.vision_analysis import analyze_vision_defects
from src.capability_analysis import analyze_all_capabilities
from src.equipment_analysis import analyze_by_equipment, capability_comparison_table
import json
from src.time_analysis import aggregate_by_time_interval, generate_date_hour_heatmap_matrix
from src.hotspot_detection import detect_ng_hotspots, HotspotConfig
from src.process_analysis import analyze_hotspot_process_correlation
from src.summary_generator import generate_executive_summary, save_summary_json
from src.visualization import (
    plot_pareto_chart,
    plot_time_ng_trend,
    plot_spc_imr_single,
    plot_vision_cchart,
    plot_process_conditions_timeline,
    plot_date_hour_heatmap,
    plot_lot_machine_comparison
)
from src.ppt_report_generator import generate_ppt_report
from src.html_report_generator import generate_html_report
from src.excel_audit_generator import create_calculation_trace_workbook


def run_pipeline(
    spec_path: str = "raw data/Electrode_Quality_SPEC.xlsx",
    raw_path: str = "raw data/Electrode_Quality_Raw_Data.csv",
    output_dir: str = "result",
    interval_minutes: int = 60,
    event_log_path: str = None,
    baseline_n: int = 200,
    allow_invalid: bool = False
) -> dict:
    """
    Executes the full automated analysis and reporting workflow.
    Stores all final deliverables directly into the specified output folder (default: 'result').
    """
    if baseline_n < 2:
        raise ValueError("baseline_n must be >= 2")
    if interval_minutes < 1:
        raise ValueError("interval_minutes must be >= 1")
    out_path = Path(output_dir)
    charts_dir = out_path / "charts"
    reports_dir = out_path  # Save reports directly into result/ for easy access
    analysis_dir = out_path  # Save analysis data directly into result/

    logger.info("================================================================================")
    logger.info("Starting Electrode Quality SPC Monitoring & Automated Reporting Pipeline")
    logger.info(f"SPEC File: {spec_path} | Raw Data: {raw_path}")
    logger.info(f"Output Directory: {output_dir} | Time Interval: {interval_minutes} min")
    logger.info("================================================================================")

    # Step 1: Load inputs
    try:
        logger.info("[Step 1/14] Loading SPEC and Raw Data...")
        spec_df = load_spec(spec_path)
        raw_df = load_raw_data(raw_path)
        event_df = load_equipment_event_log(event_log_path)
        logger.info(f"Loaded {len(spec_df)} enabled specifications and {len(raw_df)} raw measurement rows.")
    except Exception as e:
        logger.error(f"Failed at Step 1 (Data Loading): {e}")
        raise

    # Step 2: Validate integrity
    try:
        logger.info("[Step 2/14] Validating SPEC and Raw Data compatibility...")
        is_valid, msgs = validate_spec_and_raw(spec_df, raw_df)
        for msg in msgs:
            logger.warning(f"Spec Notice: {msg}")
    except Exception as e:
        logger.error(f"Failed at Step 2 (Validation): {e}")
        raise

    # Step 3: Quality Judgment
    try:
        logger.info("[Step 3/14] Evaluating quality against SPEC limits...")
        evaluated_df, quality_summary = evaluate_quality(raw_df, spec_df)
        logger.info(
            f"Quality Judgment Complete: Total={quality_summary['total_count']}, "
            f"OK={quality_summary['ok_count']} ({quality_summary['ok_rate_pct']}%), "
            f"NG={quality_summary['ng_count']} ({quality_summary['ng_rate_pct']}%), "
            f"Multi-defect rows={quality_summary['multi_defect_rows']}"
        )
    except Exception as e:
        logger.error(f"Failed at Step 3 (Quality Judgment): {e}")
        raise

    # A row can be NG for one feature and INVALID for another; overall NG
    # must not hide invalid measurements in other enabled characteristics.
    invalid_columns = [f"{col}__judgment" for col in spec_df["raw_column"]]
    any_invalid = evaluated_df[invalid_columns].eq("INVALID").any(axis=1)
    if any_invalid.any() and not allow_invalid:
        bad = evaluated_df[any_invalid]
        raise ValueError(
            f"Raw Data contains {len(bad)} INVALID rows. Correct input values before analysis "
            f"(example original sorted index: {bad.index[:10].tolist()}). "
            "Use --allow-invalid only for exploratory analysis; results may be incomplete."
        )

    # Avoid creating a plausible-looking output directory before validation passes.
    for d in [out_path, charts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Step 4: SPC Control Charts Analysis
    try:
        logger.info("[Step 4/14] Performing SPC Control Chart Analysis (I-MR & C-Chart)...")
        spc_results = {}
        vision_results = {}

        for _, spec_row in spec_df.iterrows():
            col = spec_row["raw_column"]
            ctype = spec_row.get("chart_type", "I-MR")
            if ctype == "I-MR":
                spc_results[col] = analyze_imr(evaluated_df, col, spec_row, baseline_n=baseline_n)
            elif ctype in ("C", "U"):
                vision_results[col] = analyze_vision_defects(evaluated_df, col, spec_row)

        logger.info(f"Calculated I-MR charts for {len(spc_results)} continuous variables, C/U-charts for {len(vision_results)} vision characteristics.")
    except Exception as e:
        logger.error(f"Failed at Step 4 (SPC Analysis): {e}")
        raise

    # Step 5: Process Capability Analysis
    try:
        logger.info("[Step 5/14] Calculating Process Capability Indices (Cp, Cpk, Pp, Ppk)...")
        cap_results = analyze_all_capabilities(evaluated_df, spec_df, spc_results, baseline_n=baseline_n)
        equipment_results = analyze_by_equipment(evaluated_df, spec_df, baseline_n=baseline_n)
        equipment_json_path = analysis_dir / "equipment_spc_summary.json"
        with equipment_json_path.open("w", encoding="utf-8") as fp:
            json.dump(equipment_results, fp, ensure_ascii=False, indent=2, default=str)
        equipment_table = capability_comparison_table(equipment_results)
        equipment_table.to_csv(analysis_dir / "equipment_capability.csv", index=False, encoding="utf-8-sig")
        logger.info(f"Equipment-specific SPC: {len(equipment_results['equipment'])} machine(s); output {equipment_json_path}")
        for col, c_res in cap_results.items():
            if c_res.get("applicable"):
                logger.info(f"Capability [{c_res['characteristic']}]: Cp={c_res['cp']}, Cpk={c_res['cpk']}, Pp={c_res['pp']}, Ppk={c_res['ppk']} ({c_res['capability_level']})")
    except Exception as e:
        logger.error(f"Failed at Step 5 (Capability Analysis): {e}")
        raise

    # Step 6: Time-based Aggregation & Heatmap Matrix
    try:
        logger.info(f"[Step 6/14] Aggregating data across {interval_minutes}-minute intervals...")
        interval_df = aggregate_by_time_interval(evaluated_df, spec_df, interval_minutes=interval_minutes)
        heatmap_matrix = generate_date_hour_heatmap_matrix(evaluated_df)
        logger.info(f"Generated {len(interval_df)} time intervals and {heatmap_matrix.shape[0]}x{heatmap_matrix.shape[1]} heatmap matrix.")
    except Exception as e:
        logger.error(f"Failed at Step 6 (Time Analysis): {e}")
        raise

    # Step 7: Hotspot Detection
    try:
        logger.info("[Step 7/14] Detecting anomalous defect clustering intervals (Multi-tier Hotspots)...")
        hotspot_res = detect_ng_hotspots(
            interval_df,
            overall_ng_rate_pct=quality_summary["ng_rate_pct"],
            config=HotspotConfig(min_samples=6, severe_min_ng=3, severe_min_rate_pct=20.0, warning_min_ng=2)
        )
        severe_hotspots = hotspot_res["severe_hotspots"]
        warning_clusters = hotspot_res["warning_clusters"]
        logger.info(
            f"Detected {len(severe_hotspots)} Severe Hotspots (Tier 1) and "
            f"{len(warning_clusters)} Warning Clusters (Tier 2). Total NG intervals: {len(hotspot_res['all_ng_periods'])}."
        )
        for idx, h in enumerate(severe_hotspots):
            logger.info(f"  [Tier 1 Severe #{idx+1}] [{h['period_label']}] NG={h['ng_count']}/{h['total_count']} ({h['ng_rate_pct']}%) Top={h['primary_defect']}")
        for idx, h in enumerate(warning_clusters):
            logger.info(f"  [Tier 2 Warning #{idx+1}] [{h['period_label']}] NG={h['ng_count']}/{h['total_count']} ({h['ng_rate_pct']}%) Top={h['primary_defect']}")
    except Exception as e:
        logger.error(f"Failed at Step 7 (Hotspot Detection): {e}")
        raise

    # Step 8: Process Condition Correlation
    try:
        logger.info("[Step 8/14] Analyzing process condition correlation with detected hotspots...")
        process_correlations = []
        for hs in severe_hotspots:
            corr = analyze_hotspot_process_correlation(evaluated_df, hs, buffer_minutes=30, event_log_df=event_df)
            process_correlations.append(corr)
        logger.info(f"Analyzed process condition changes across {len(process_correlations)} hotspot periods.")
    except Exception as e:
        logger.error(f"Failed at Step 8 (Process Correlation): {e}")
        raise

    # Step 9: Automated Summary Generation
    try:
        logger.info("[Step 9/14] Generating rule-based executive insights and summaries...")
        summary_obj = generate_executive_summary(
            quality_summary, hotspot_res, process_correlations, cap_results, evaluated_df=evaluated_df
        )
        summary_json_path = analysis_dir / "analysis_summary.json"
        summary_obj["audit_version"] = "2026-10-30-fix1"
        summary_obj["equipment_spc_artifact"] = "equipment_spc_summary.json"
        summary_obj["vision_dispersion_diagnostics"] = {
            col: {"ratio": res.get("variance_to_mean_ratio"), "note": res["poisson_assumption_note"]}
            for col, res in vision_results.items()
        }
        summary_obj["insufficient_intervals"] = [
            {**v, "start_time": str(v["start_time"]), "end_time": str(v["end_time"])}
            for v in hotspot_res.get("insufficient_periods", [])
        ]
        save_summary_json(summary_obj, summary_json_path)
        logger.info(f"Saved structured analysis summary to {summary_json_path}")
    except Exception as e:
        logger.error(f"Failed at Step 9 (Summary Generation): {e}")
        raise

    # Step 10: High-Resolution Static Visualizations
    # Remove stale generated charts when a later run has fewer/other enabled specs.
    # This output location is exclusively for generated chart_*.png files.
    try:
        for old_chart in charts_dir.glob("chart_*.png"):
            old_chart.unlink()
        logger.info("[Step 10/14] Generating high-resolution static charts for PPT...")
        chart_paths = {}
        chart_paths["pareto"] = plot_pareto_chart(quality_summary["char_stats"], charts_dir / "chart_pareto.png")
        chart_paths["time_trend"] = plot_time_ng_trend(interval_df, charts_dir / "chart_time_trend.png")
        chart_paths["heatmap"] = plot_date_hour_heatmap(heatmap_matrix, charts_dir / "chart_heatmap.png")
        chart_paths["process_timeline"] = plot_process_conditions_timeline(evaluated_df, severe_hotspots, charts_dir / "chart_process_timeline.png")
        chart_paths["lot_machine"] = plot_lot_machine_comparison(quality_summary, charts_dir / "chart_lot_machine.png")

        # SPC charts
        for col, spc_info in spc_results.items():
            p = charts_dir / f"chart_spc_{col}.png"
            plot_spc_imr_single(evaluated_df, col, spc_info, p)
            chart_paths[f"spc_{col}"] = str(p)

        # Machine-specific charts: avoid applying COATER-01's reference baseline to COATER-02.
        if "machine_id" in evaluated_df.columns:
            for machine, machine_result in equipment_results["equipment"].items():
                machine_df = evaluated_df[evaluated_df["machine_id"].astype(str) == machine].sort_values("timestamp").reset_index(drop=True)
                safe_machine = "".join(c if c.isalnum() or c in "-_" else "_" for c in machine)
                for col, spc_info in machine_result["spc"].items():
                    chart = charts_dir / f"chart_spc_{col}_{safe_machine}.png"
                    plot_spc_imr_single(machine_df, col, spc_info, chart)

        # Vision charts
        for col, v_info in vision_results.items():
            p = charts_dir / f"chart_vision_{col}.png"
            plot_vision_cchart(v_info, p)
            chart_paths[f"vision_{col}"] = str(p)

        logger.info(f"Successfully rendered {len(list(charts_dir.glob("*.png")))} charts to {charts_dir}")
    except Exception as e:
        logger.error(f"Failed at Step 10 (Static Visualizations): {e}")
        raise

    # Step 11: PowerPoint Report Generation
    try:
        logger.info("[Step 11/14] Generating PowerPoint (16:9, 12 slides) Report...")
        pptx_path = reports_dir / "Electrode_Quality_SPC_Report.pptx"
        generate_ppt_report(
            summary_obj=summary_obj,
            quality_summary=quality_summary,
            hotspots=severe_hotspots,
            process_correlations=process_correlations,
            capability_results=cap_results,
            chart_paths=chart_paths,
            output_path=pptx_path
        )
        logger.info(f"Successfully generated PowerPoint Report: {pptx_path}")
    except Exception as e:
        logger.error(f"Failed at Step 11 (PPT Generation): {e}")
        raise

    # Step 12: HTML Responsive Report Generation
    try:
        logger.info("[Step 12/14] Generating Standalone Mobile-Responsive HTML Report...")
        html_path = reports_dir / "Electrode_Quality_SPC_Report.html"
        generate_html_report(
            summary_obj=summary_obj,
            quality_summary=quality_summary,
            hotspots=hotspot_res,
            process_correlations=process_correlations,
            capability_results=cap_results,
            interval_df=interval_df,
            raw_df=evaluated_df,
            spc_results=spc_results,
            vision_results=vision_results,
            heatmap_matrix=heatmap_matrix,
            output_path=html_path,
            interval_minutes=interval_minutes
        )
        logger.info(f"Successfully generated HTML Report: {html_path}")
    except Exception as e:
        logger.error(f"Failed at Step 12 (HTML Generation): {e}")
        raise

    # Step 13: Save Evaluated Data and Artifacts
    try:
        logger.info("[Step 13/14] Saving evaluated data CSV and final verification...")
        evaluated_df.to_csv(analysis_dir / "evaluated_quality_data.csv", index=False, encoding="utf-8-sig")
        interval_df.to_csv(analysis_dir / "interval_aggregation.csv", index=False, encoding="utf-8-sig")
    except Exception as e:
        logger.error(f"Failed at Step 13 (Data Export): {e}")
        raise

    # Input provenance supports auditing reproducibility across runs.
    import hashlib
    def _sha256(file_path):
        p = Path(file_path)
        if not p.is_file():
            from src.data_loader import resolve_path
            p = resolve_path(file_path, p.name)
        return hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "raw_input": str(raw_path), "raw_sha256": _sha256(raw_path),
        "spec_input": str(spec_path), "spec_sha256": _sha256(spec_path),
        "rows": len(raw_df), "enabled_specs": list(spec_df["raw_column"]),
        "interval_minutes": interval_minutes, "baseline_n": baseline_n,
        "allow_invalid": allow_invalid,
        "overall_ng_count": quality_summary["ng_count"],
        "overall_invalid_count": quality_summary["invalid_count"],
    }
    # Step 14: Generate Excel Calculation Trace Workbook with Live Formulas
    try:
        logger.info("[Step 14/14] Generating Calculation & Formula Trace Audit Workbook...")
        excel_audit_path = out_path / "Electrode_Quality_Calculation_Trace.xlsx"
        create_calculation_trace_workbook(spec_path, raw_path, excel_audit_path, baseline_n=baseline_n)
        logger.info(f"Successfully generated Live Formula Audit Workbook: {excel_audit_path}")
        (out_path / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Pipeline execution successfully completed!")
    except Exception as e:
        logger.error(f"Failed at Step 14 (Excel Audit Generation): {e}")
        raise

    return {
        "status": "SUCCESS",
        "pptx_report": str(pptx_path),
        "html_report": str(html_path),
        "excel_audit": str(excel_audit_path),
        "analysis_summary": str(summary_json_path),
        "equipment_spc_summary": str(equipment_json_path),
        "quality_summary": quality_summary,
        "hotspots_count": len(severe_hotspots),
        "severe_hotspots_count": len(severe_hotspots),
        "warning_clusters_count": len(warning_clusters),
        "all_ng_intervals_count": len(hotspot_res["all_ng_periods"])
    }


def main():
    parser = argparse.ArgumentParser(description="Electrode Quality SPC Monitoring & Automated Reporting System")
    parser.add_argument("--spec", default="raw data/Electrode_Quality_SPEC.xlsx", help="Path to Electrode_Quality_SPEC.xlsx")
    parser.add_argument("--raw", default="raw data/Electrode_Quality_Raw_Data.csv", help="Path to Electrode_Quality_Raw_Data.csv")
    parser.add_argument("--output", default="result", help="Output directory (default: result)")
    parser.add_argument("--interval", type=int, default=60, help="Time analysis interval in minutes (default: 60)")
    parser.add_argument("--event-log", default=None, help="Optional equipment event log CSV")
    parser.add_argument("--baseline-n", type=int, default=200, help="Initial Phase I baseline samples per equipment (default: 200)")
    parser.add_argument("--allow-invalid", action="store_true", help="Continue even if source values are INVALID; use for exploratory analysis only")

    args = parser.parse_args()

    try:
        res = run_pipeline(
            spec_path=args.spec,
            raw_path=args.raw,
            output_dir=args.output,
            interval_minutes=args.interval,
            event_log_path=args.event_log,
            baseline_n=args.baseline_n,
            allow_invalid=args.allow_invalid
        )
        print("\n" + "="*80)
        print("  PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
        print("="*80)
        print(f"[*] PowerPoint Report : {res['pptx_report']}")
        print(f"[*] HTML Web Report   : {res['html_report']}")
        print(f"[*] Excel Audit Trace : {res['excel_audit']}")
        print(f"[*] Analysis Summary  : {res['analysis_summary']}")
        print(f"[*] Total Evaluated   : {res['quality_summary']['total_count']:,} rows")
        print(f"[*] Defect Rate (NG)  : {res['quality_summary']['ng_rate_pct']:.2f}% ({res['quality_summary']['ng_count']} rows)")
        print(f"[*] Hotspots Detected : {res['hotspots_count']} periods")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed with error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
