"""
Unit Tests for Report Generation (PPT & HTML)
"""

from pathlib import Path
import pytest
from pptx import Presentation


def find_file(filename: str) -> Path:
    candidates = [
        Path("result") / filename,
        Path("outputs/reports") / filename,
        Path("outputs/results") / filename,
        Path("outputs/analysis") / filename
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def test_pptx_report_structure():
    pptx_path = find_file("Electrode_Quality_SPC_Report.pptx")
    assert pptx_path.exists(), "PPTX report does not exist."

    prs = Presentation(pptx_path)
    # Check slide count
    assert len(prs.slides) == 12, f"Expected 12 slides, found {len(prs.slides)}"

    # Check slide dimensions (16:9 widescreen: 13.333 x 7.5 inches)
    assert pytest.approx(prs.slide_width.inches, 0.01) == 13.333
    assert pytest.approx(prs.slide_height.inches, 0.01) == 7.5


def test_html_report_content():
    html_path = find_file("Electrode_Quality_SPC_Report.html")
    assert html_path.exists(), "HTML report does not exist."

    content = html_path.read_text(encoding="utf-8")

    # Check essential section headings and elements
    required_strings = [
        "ELECTRODE QUALITY SPC MONITORING SYSTEM",
        "1. Executive Summary",
        "2. Quality KPI Dashboard",
        "3. SPEC Compliance",
        "4. SPC Monitoring",
        "5. Time-Series Defect Trend",
        "6. NG Hotspot Detection",
        "7. Process Conditions",
        "8. Vision Defect Analysis",
        "9. LOT & Equipment Comparison",
        "10. Process Capability",
        "11. Automated Analysis Summary",
        "12. Conclusions"
    ]
    for req in required_strings:
        assert req in content, f"Missing required string in HTML report: {req}"

    # Verify offline plotly bundle is included
    assert "Plotly.newPlot" in content
    assert len(content) > 1_000_000, "HTML file should be standalone and contain bundled Plotly.js"
    assert "initNavHighlight" in content
    assert "setActiveNavLink" in content


def test_summary_json():
    import json
    from src.data_loader import load_raw_data, load_spec
    from src.quality_judgment import evaluate_quality
    json_path = find_file("analysis_summary.json")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    _, expected = evaluate_quality(
        load_raw_data('raw data/Electrode_Quality_Raw_Data.csv'),
        load_spec('raw data/Electrode_Quality_SPEC.xlsx')
    )
    assert data["raw_counts"]["total"] == expected["total_count"]
    assert data["raw_counts"]["ng"] == expected["ng_count"]
    assert len(data["key_takeaways"]) == 3
    assert "N=" in " ".join(data["capability_summary"])
    assert not json_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_excel_audit_trace_workbook():
    import openpyxl
    excel_path = find_file("Electrode_Quality_Calculation_Trace.xlsx")
    assert excel_path.exists(), "Calculation Trace Excel does not exist."

    wb = openpyxl.load_workbook(excel_path, data_only=False)
    expected_sheets = [
        "00_Audit_Guide", "01_SPEC_Master", "02_Raw_Measurements",
        "03_Quality_Judgment", "04_SPC_IMR_Formulas", "05_Capability_Formulas"
    ]
    for s in expected_sheets:
        assert s in wb.sheetnames, f"Missing sheet: {s}"

    # Verify live formulas exist
    ws_judge = wb["03_Quality_Judgment"]
    assert str(ws_judge["B2"].value).startswith("=")
    assert str(ws_judge["C7"].value).startswith("=IF")

    ws_cap = wb["05_Capability_Formulas"]
    assert "AVERAGE" in str(ws_cap["B5"].value)
    assert "MIN" in str(ws_cap["B13"].value)

